"""LangGraph-based Orchestrator Agent.

The orchestrator is the entry-point for every user task.  It decomposes
the request into steps, delegates each step to the appropriate specialist
agent, validates outputs through the Guardian, and assembles the final
deliverable.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from src.agents.base_agent import BaseAgent
from src.agents.orchestrator.prompts import (
    ORCHESTRATOR_SYSTEM_PROMPT,
    PLANNING_PROMPT,
    REPLANNING_PROMPT,
    SYNTHESIS_PROMPT,
)
from src.agents.orchestrator.state import OrchestratorGraphState
from src.core.config import settings
from src.core.context_store import ContextStore
from src.core.cost_tracker import CostTracker
from src.core.exceptions import (
    AgentMeshError,
    AgentTimeoutError,
    BudgetExceededError,
    GuardianRejectionError,
)
from src.core.models import (
    GuardianReport,
    OrchestratorState,
    QualityVerdict,
    StepStatus,
    TaskLedgerEntry,
    TaskStatus,
    TaskStep,
    TokenUsage,
    _utcnow,
)
from src.core.task_ledger import TaskLedger

_MAX_REPLAN_ATTEMPTS = 3


class OrchestratorAgent(BaseAgent):
    """Central orchestrator that manages the full task lifecycle.

    The orchestrator does **not** call an MCP server directly -- instead
    it coordinates other agents that each talk to their own MCP server.
    """

    def __init__(self) -> None:
        super().__init__(
            agent_id="orchestrator-v1",
            name="Orchestrator Agent",
            description=(
                "Decomposes tasks, delegates to specialist agents, "
                "orchestrates workflow, and enforces quality and budgets"
            ),
            capabilities=[
                "task_planning",
                "agent_delegation",
                "workflow_management",
                "cost_enforcement",
            ],
            mcp_server="none",
            model="gpt-4o",
        )

        # External collaborators -- wired during application startup
        self.task_ledger: TaskLedger | None = None
        self.context_store: ContextStore | None = None
        self.cost_tracker: CostTracker | None = None

        # Registered specialist agents keyed by agent_id
        self.agents: dict[str, BaseAgent] = {}

    # ------------------------------------------------------------------
    # BaseAgent interface
    # ------------------------------------------------------------------

    def get_system_prompt(self) -> str:
        return ORCHESTRATOR_SYSTEM_PROMPT

    async def execute(self, task: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Main entry-point: plan -> delegate -> monitor -> validate -> deliver.

        Parameters
        ----------
        task:
            Must contain ``"request"`` (user query string).  May contain
            ``"budget_limit_usd"`` and ``"task_id"``.
        context:
            Shared context dict; typically empty for the initial call.

        Returns
        -------
        dict
            ``{"task_id", "status", "results", "cost_breakdown", ...}``
        """
        request: str = task["request"]
        budget: float = task.get("budget_limit_usd", settings.task_budget_limit_usd)
        task_id: str = task.get("task_id", "")

        self.logger.info("orchestrator.execute.start", request=request[:120], budget=budget)

        # 1. Plan -------------------------------------------------------
        plan_steps = await self.plan_task(request)

        # Build a ledger entry to track state
        ledger_entry = TaskLedgerEntry(
            task_id=task_id or "local",
            original_request=request,
            plan=plan_steps,
            status=TaskStatus.IN_PROGRESS,
            metadata={"budget_limit_usd": budget},
        )

        # Persist to task ledger if available
        if self.task_ledger is not None:
            await self.task_ledger.update_task(
                ledger_entry.task_id,
                plan=plan_steps,
                status=TaskStatus.IN_PROGRESS,
            )

        # 2. Run pipeline -----------------------------------------------
        try:
            results = await self.run_pipeline(ledger_entry)
        except BudgetExceededError as exc:
            self.logger.warning("orchestrator.budget_exceeded", error=str(exc))
            return {
                "task_id": ledger_entry.task_id,
                "status": "budget_exceeded",
                "error": str(exc),
                "partial_results": {},
            }
        except AgentMeshError as exc:
            self.logger.error("orchestrator.pipeline_error", error=str(exc))
            return {
                "task_id": ledger_entry.task_id,
                "status": "failed",
                "error": str(exc),
                "partial_results": {},
            }

        # 3. Synthesise -------------------------------------------------
        final_output = await self._synthesise(request, results)

        # 4. Cost summary -----------------------------------------------
        cost_breakdown: dict[str, Any] = {}
        if self.cost_tracker is not None:
            cost_breakdown = self.cost_tracker.get_cost_breakdown(ledger_entry.task_id)

        self.logger.info(
            "orchestrator.execute.done",
            task_id=ledger_entry.task_id,
            steps_completed=len(results),
        )

        return {
            "task_id": ledger_entry.task_id,
            "status": "completed",
            "results": results,
            "final_output": final_output,
            "cost_breakdown": cost_breakdown,
        }

    # ------------------------------------------------------------------
    # Planning
    # ------------------------------------------------------------------

    async def plan_task(self, request: str) -> list[TaskStep]:
        """Decompose a user request into ordered :class:`TaskStep` objects.

        In production an LLM call fills in the plan using
        :data:`PLANNING_PROMPT`.  This implementation applies a sensible
        default pipeline when no LLM is available.
        """
        self.logger.info("orchestrator.plan.start", request=request[:120])

        agent_summaries = self._describe_available_agents()

        # ---- LLM-based planning (placeholder) ----
        # In production:
        #   prompt = PLANNING_PROMPT.format(request=request, agents=agent_summaries)
        #   raw = await llm.chat(system=self.get_system_prompt(), user=prompt)
        #   steps_json = json.loads(raw)

        # ---- Default deterministic pipeline ----
        steps: list[TaskStep] = []

        if self._has_agent("data-ingestion-v1"):
            ingest_step = TaskStep(
                step_id="step-ingest",
                agent="data-ingestion-v1",
                action="ingest_and_clean",
                params={"request": request},
                depends_on=[],
            )
            steps.append(ingest_step)

        if self._has_agent("analytics-v1"):
            analytics_step = TaskStep(
                step_id="step-analytics",
                agent="analytics-v1",
                action="run_analyses",
                params={
                    "analyses": ["statistics", "trend", "anomaly"],
                    "request": request,
                },
                depends_on=["step-ingest"] if self._has_agent("data-ingestion-v1") else [],
            )
            steps.append(analytics_step)

        if self._has_agent("insight-generator-v1"):
            insight_step = TaskStep(
                step_id="step-insights",
                agent="insight-generator-v1",
                action="generate_insights",
                params={"request": request},
                depends_on=["step-analytics"] if self._has_agent("analytics-v1") else [],
            )
            steps.append(insight_step)

        if self._has_agent("presentation-v1"):
            present_step = TaskStep(
                step_id="step-present",
                agent="presentation-v1",
                action="compile_report",
                params={"request": request},
                depends_on=[s.step_id for s in steps if s.step_id != "step-present"],
            )
            steps.append(present_step)

        self.logger.info("orchestrator.plan.done", step_count=len(steps))
        return steps

    # ------------------------------------------------------------------
    # Pipeline execution
    # ------------------------------------------------------------------

    async def run_pipeline(self, task_entry: TaskLedgerEntry) -> dict[str, Any]:
        """Iterate through plan steps, executing each in order.

        Handles dependency resolution, guardian validation, retries,
        replanning, and budget enforcement.

        Returns a mapping of ``step_id -> output dict``.
        """
        results: dict[str, Any] = {}
        guardian_reports: dict[str, GuardianReport] = {}
        replan_count = 0
        remaining_steps = list(task_entry.plan)

        budget: float = task_entry.metadata.get(
            "budget_limit_usd", settings.task_budget_limit_usd
        )

        while remaining_steps:
            step = remaining_steps.pop(0)

            # --- dependency check ---
            unmet = [dep for dep in step.depends_on if dep not in results]
            if unmet:
                self.logger.warning(
                    "orchestrator.step.unmet_deps",
                    step_id=step.step_id,
                    unmet=unmet,
                )
                step.status = StepStatus.FAILED
                step.error = f"Unmet dependencies: {unmet}"
                results[step.step_id] = {"error": step.error}
                continue

            # --- budget check ---
            running_cost = self._running_cost(task_entry.task_id)
            if running_cost >= budget:
                raise BudgetExceededError(
                    task_id=task_entry.task_id,
                    spent=running_cost,
                    budget=budget,
                )

            # --- execute step ---
            step.status = StepStatus.IN_PROGRESS
            step.started_at = _utcnow()

            output: dict[str, Any] | None = None
            last_error: str = ""

            for attempt in range(step.max_retries + 1):
                try:
                    output = await self.delegate_step(step, results)
                    break
                except Exception as exc:
                    last_error = str(exc)
                    step.retries = attempt + 1
                    self.logger.warning(
                        "orchestrator.step.retry",
                        step_id=step.step_id,
                        attempt=attempt + 1,
                        error=last_error,
                    )

            if output is None:
                # All retries exhausted
                step.status = StepStatus.FAILED
                step.error = last_error
                step.completed_at = _utcnow()

                self.logger.error(
                    "orchestrator.step.failed",
                    step_id=step.step_id,
                    error=last_error,
                )

                # Attempt replan
                if replan_count < _MAX_REPLAN_ATTEMPTS:
                    replan_count += 1
                    new_steps = await self._replan(task_entry, step, last_error)
                    remaining_steps = new_steps + remaining_steps
                    self.logger.info(
                        "orchestrator.replan",
                        replan_count=replan_count,
                        new_step_count=len(new_steps),
                    )
                else:
                    results[step.step_id] = {"error": last_error}

                continue

            # --- guardian validation ---
            step.status = StepStatus.COMPLETED
            step.completed_at = _utcnow()
            results[step.step_id] = output

            # Store in shared context
            if self.context_store is not None:
                await self.context_store.set(
                    task_entry.task_id,
                    f"output:{step.step_id}",
                    output,
                )

            guardian = self.agents.get("guardian-v1")
            if guardian is not None:
                report = await self._run_guardian(step, output, results)
                guardian_reports[step.step_id] = report

                if await self._should_escalate(step, report):
                    self.logger.warning(
                        "orchestrator.step.escalated",
                        step_id=step.step_id,
                        score=report.overall_score,
                    )
                    step.quality_score = report.overall_score
                elif report.verdict == QualityVerdict.REPROCESS and step.retries < step.max_retries:
                    # Put step back at the front for reprocessing
                    step.status = StepStatus.REPROCESSING
                    step.retries += 1
                    remaining_steps.insert(0, step)
                    del results[step.step_id]
                    continue
                else:
                    step.quality_score = report.overall_score

            # --- track cost ---
            if self.cost_tracker is not None:
                agent_obj = self.agents.get(step.agent)
                model = agent_obj.model if agent_obj else self.model
                self.cost_tracker.record_usage(
                    task_id=task_entry.task_id,
                    agent_id=step.agent,
                    model=model,
                    input_tokens=step.tokens.input_tokens or 50,
                    output_tokens=step.tokens.output_tokens or 30,
                )

            # Update the ledger step
            if self.task_ledger is not None:
                try:
                    await self.task_ledger.update_step(
                        task_entry.task_id,
                        step.step_id,
                        status=step.status,
                        completed_at=step.completed_at,
                        quality_score=step.quality_score,
                    )
                except (ValueError, Exception) as exc:
                    self.logger.debug("ledger.update_step.skip", reason=str(exc))

        return results

    # ------------------------------------------------------------------
    # Delegation
    # ------------------------------------------------------------------

    async def delegate_step(self, step: TaskStep, context: dict[str, Any]) -> dict[str, Any]:
        """Delegate a single step to its assigned agent.

        Raises :class:`AgentTimeoutError` if the agent is not registered.
        """
        agent = self.agents.get(step.agent)
        if agent is None:
            raise AgentTimeoutError(
                agent_id=step.agent,
                timeout_seconds=0,
            )

        self.logger.info(
            "orchestrator.delegate",
            step_id=step.step_id,
            agent=step.agent,
            action=step.action,
        )

        task_payload: dict[str, Any] = {
            "action": step.action,
            **step.params,
        }

        result = await agent.execute(task=task_payload, context=context)
        return result

    # ------------------------------------------------------------------
    # Agent registry helpers
    # ------------------------------------------------------------------

    def register_agent(self, agent: BaseAgent) -> None:
        """Register a specialist agent for delegation."""
        self.agents[agent.agent_id] = agent
        self.logger.info("orchestrator.agent_registered", agent_id=agent.agent_id)

    def _has_agent(self, agent_id: str) -> bool:
        return agent_id in self.agents

    def _describe_available_agents(self) -> str:
        """Return a newline-delimited summary of registered agents."""
        lines: list[str] = []
        for agent in self.agents.values():
            card = agent.get_agent_card()
            lines.append(
                f"- {card.agent_id}: {card.description} "
                f"(capabilities: {', '.join(card.capabilities)})"
            )
        return "\n".join(lines) if lines else "(no agents registered)"

    # ------------------------------------------------------------------
    # Guardian integration
    # ------------------------------------------------------------------

    async def _run_guardian(
        self,
        step: TaskStep,
        output: dict[str, Any],
        source_data: dict[str, Any],
    ) -> GuardianReport:
        """Invoke the Guardian agent to validate a step's output."""
        guardian = self.agents["guardian-v1"]
        validation_task: dict[str, Any] = {
            "action": "validate",
            "output": output,
            "source_data": source_data,
            "step_id": step.step_id,
        }
        result = await guardian.execute(task=validation_task, context=source_data)

        # If the guardian returned a full GuardianReport, use it
        if isinstance(result.get("report"), GuardianReport):
            return result["report"]

        # Otherwise construct one from raw dict
        return GuardianReport(
            step_id=step.step_id,
            overall_score=result.get("overall_score", 0.85),
            verdict=QualityVerdict(result.get("verdict", "auto_approve")),
            checks=result.get("checks", []),
            recommendations=result.get("recommendations", []),
        )

    async def _should_escalate(self, step: TaskStep, guardian_report: GuardianReport) -> bool:
        """Determine whether a step should be escalated based on the guardian report."""
        if guardian_report.verdict == QualityVerdict.ESCALATE:
            return True
        if guardian_report.overall_score < settings.guardian_reprocess_threshold:
            return True
        return False

    # ------------------------------------------------------------------
    # Replanning
    # ------------------------------------------------------------------

    async def _replan(
        self,
        task_entry: TaskLedgerEntry,
        failed_step: TaskStep,
        error: str,
    ) -> list[TaskStep]:
        """Produce replacement steps after a failure.

        In production an LLM call uses :data:`REPLANNING_PROMPT`.  This
        fallback simply skips the failed step.
        """
        self.logger.info(
            "orchestrator.replan.start",
            failed_step=failed_step.step_id,
            error=error[:200],
        )

        # Placeholder: skip the failed step entirely
        # In production:
        #   prompt = REPLANNING_PROMPT.format(
        #       failed_step=failed_step.model_dump_json(),
        #       error=error,
        #       plan=json.dumps([s.model_dump() for s in remaining]),
        #   )
        #   raw = await llm.chat(system=self.get_system_prompt(), user=prompt)
        #   return [TaskStep(**s) for s in json.loads(raw)]

        return []

    # ------------------------------------------------------------------
    # Synthesis
    # ------------------------------------------------------------------

    async def _synthesise(self, request: str, outputs: dict[str, Any]) -> dict[str, Any]:
        """Combine all step outputs into a final deliverable.

        In production this uses an LLM with :data:`SYNTHESIS_PROMPT`.
        The fallback simply aggregates the raw outputs.
        """
        # Placeholder: aggregate outputs
        return {
            "summary": f"Completed analysis for: {request[:200]}",
            "step_outputs": {
                step_id: (
                    out if isinstance(out, dict) else {"raw": str(out)}
                )
                for step_id, out in outputs.items()
            },
        }

    # ------------------------------------------------------------------
    # Cost helpers
    # ------------------------------------------------------------------

    def _running_cost(self, task_id: str) -> float:
        """Return the running USD cost for a task."""
        if self.cost_tracker is not None:
            return self.cost_tracker.get_task_cost(task_id)
        return 0.0
