"""Guardian Agent.

Validates outputs from other agents for quality, accuracy, PII exposure,
bias, and policy compliance.  Acts as a quality gate in the orchestrator
pipeline.
"""

from __future__ import annotations

from typing import Any

from src.agents.base_agent import BaseAgent
from src.agents.guardian.prompts import GUARDIAN_SYSTEM_PROMPT
from src.agents.guardian.validators import run_all_checks
from src.core.config import settings
from src.core.models import (
    GuardianReport,
    QualityVerdict,
    ValidationCheck,
)


class GuardianAgent(BaseAgent):
    """Specialist agent for output validation and quality assurance."""

    def __init__(self) -> None:
        super().__init__(
            agent_id="guardian-v1",
            name="Guardian Agent",
            description=(
                "Validates outputs for quality, accuracy, PII, "
                "bias, and policy compliance"
            ),
            capabilities=[
                "data_integrity",
                "hallucination_detection",
                "pii_scanning",
                "statistical_validation",
                "bias_detection",
            ],
            mcp_server="eval-guards-server",
            model="gpt-4o",
        )

    def get_system_prompt(self) -> str:
        return GUARDIAN_SYSTEM_PROMPT

    # ------------------------------------------------------------------
    # Main execution
    # ------------------------------------------------------------------

    async def execute(self, task: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Validate an agent's output.

        Task parameters:
            action      -- ``"validate"`` (default).
            output      -- The output dict to validate.
            source_data -- The source/context data for grounding checks.
            checks      -- Optional list of specific checks to run.
            step_id     -- ID of the step being validated.

        Returns a dict containing the :class:`GuardianReport` and raw
        check results.
        """
        action: str = task.get("action", "validate")
        output: dict[str, Any] = task.get("output", {})
        source_data: dict[str, Any] = task.get("source_data", context)
        checks: list[str] | None = task.get("checks")
        step_id: str = task.get("step_id", "unknown")

        self.logger.info(
            "guardian.execute",
            action=action,
            step_id=step_id,
            check_count=len(checks) if checks else "all",
        )

        report = await self.validate(
            output=output,
            source_data=source_data,
            checks=checks,
            step_id=step_id,
        )

        self.logger.info(
            "guardian.result",
            step_id=step_id,
            score=report.overall_score,
            verdict=report.verdict.value,
        )

        return {
            "report": report,
            "overall_score": report.overall_score,
            "verdict": report.verdict.value,
            "checks": [c.model_dump() for c in report.checks],
            "recommendations": report.recommendations,
        }

    # ------------------------------------------------------------------
    # Validation pipeline
    # ------------------------------------------------------------------

    async def validate(
        self,
        output: dict[str, Any],
        source_data: dict[str, Any],
        checks: list[str] | None = None,
        step_id: str = "unknown",
    ) -> GuardianReport:
        """Run the full validation pipeline and return a :class:`GuardianReport`.

        1. Run local heuristic checks from ``validators.py``.
        2. Optionally call MCP evaluation tools for deeper analysis.
        3. Aggregate scores and determine the verdict.
        """
        # --- Step 1: Local heuristic checks ---
        local_results = await run_all_checks(
            content=output,
            source_data=source_data,
            checks=checks,
        )

        # --- Step 2: MCP-based checks (augment local results) ---
        mcp_checks = await self._run_mcp_checks(output, source_data, checks)

        # --- Step 3: Combine check results ---
        all_check_results: list[dict[str, Any]] = local_results.get("checks", [])
        all_check_results.extend(mcp_checks)

        # Build ValidationCheck models
        validation_checks: list[ValidationCheck] = []
        for check_result in all_check_results:
            validation_checks.append(
                ValidationCheck(
                    check_name=check_result.get("check_name", "unknown"),
                    passed=check_result.get("passed", False),
                    score=check_result.get("score", 0.0),
                    details=check_result.get("details", ""),
                    warnings=check_result.get("warnings", []),
                )
            )

        # --- Step 4: Compute overall score ---
        if validation_checks:
            total_score = sum(c.score for c in validation_checks)
            overall_score = total_score / len(validation_checks)
        else:
            overall_score = 1.0  # No checks means nothing to flag

        # --- Step 5: Determine verdict ---
        verdict = self._determine_verdict(overall_score)

        # --- Step 6: Collect recommendations ---
        recommendations: list[str] = local_results.get("recommendations", [])
        for check in validation_checks:
            if not check.passed:
                for warning in check.warnings:
                    if warning not in recommendations:
                        recommendations.append(warning)

        report = GuardianReport(
            step_id=step_id,
            overall_score=round(overall_score, 4),
            verdict=verdict,
            checks=validation_checks,
            recommendations=recommendations,
        )

        return report

    # ------------------------------------------------------------------
    # MCP-based checks
    # ------------------------------------------------------------------

    async def _run_mcp_checks(
        self,
        output: dict[str, Any],
        source_data: dict[str, Any],
        checks: list[str] | None,
    ) -> list[dict[str, Any]]:
        """Run evaluation checks through the Eval Guards MCP server.

        These are deeper, model-assisted checks that complement the
        local heuristic validators.
        """
        mcp_results: list[dict[str, Any]] = []

        # Hallucination check via MCP (complements local check)
        should_run_hallucination = checks is None or "hallucination_detection" in checks
        if should_run_hallucination and self._has_text_content(output):
            try:
                result = await self.call_mcp_tool(
                    "check_hallucination",
                    {
                        "output": self._truncate_for_mcp(output),
                        "source_data": self._truncate_for_mcp(source_data),
                    },
                )
                raw = result.get("data", result)
                if isinstance(raw, dict) and "score" in raw:
                    mcp_results.append({
                        "check_name": "hallucination_detection_mcp",
                        "passed": raw.get("score", 0) >= 0.7,
                        "score": raw.get("score", 0.8),
                        "details": raw.get("details", "MCP hallucination check"),
                        "warnings": raw.get("warnings", []),
                    })
            except Exception as exc:
                self.logger.warning(
                    "guardian.mcp_check.error",
                    check="hallucination",
                    error=str(exc),
                )

        # Policy compliance check via MCP
        should_run_policy = checks is None or "policy_compliance" in checks
        if should_run_policy:
            try:
                result = await self.call_mcp_tool(
                    "check_policy_compliance",
                    {"output": self._truncate_for_mcp(output)},
                )
                raw = result.get("data", result)
                if isinstance(raw, dict) and "score" in raw:
                    mcp_results.append({
                        "check_name": "policy_compliance",
                        "passed": raw.get("compliant", True),
                        "score": raw.get("score", 0.9),
                        "details": raw.get("details", "MCP policy check"),
                        "warnings": raw.get("violations", []),
                    })
            except Exception as exc:
                self.logger.warning(
                    "guardian.mcp_check.error",
                    check="policy_compliance",
                    error=str(exc),
                )

        return mcp_results

    # ------------------------------------------------------------------
    # Verdict determination
    # ------------------------------------------------------------------

    @staticmethod
    def _determine_verdict(overall_score: float) -> QualityVerdict:
        """Map a numeric score to a quality verdict using configured thresholds."""
        if overall_score >= settings.guardian_auto_approve_threshold:
            return QualityVerdict.AUTO_APPROVE
        if overall_score >= settings.guardian_warning_threshold:
            return QualityVerdict.FLAG_WARNINGS
        if overall_score >= settings.guardian_reprocess_threshold:
            return QualityVerdict.REPROCESS
        return QualityVerdict.ESCALATE

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _has_text_content(obj: dict[str, Any]) -> bool:
        """Check if the output contains meaningful text to validate."""
        def _walk(o: Any, depth: int = 0) -> bool:
            if depth > 5:
                return False
            if isinstance(o, str) and len(o) > 20:
                return True
            if isinstance(o, dict):
                return any(_walk(v, depth + 1) for v in o.values())
            if isinstance(o, (list, tuple)):
                return any(_walk(item, depth + 1) for item in o[:20])
            return False
        return _walk(obj)

    @staticmethod
    def _truncate_for_mcp(obj: Any, max_chars: int = 10_000) -> Any:
        """Truncate large payloads before sending to MCP tools.

        Prevents oversized requests to external evaluation endpoints.
        """
        import json
        try:
            serialised = json.dumps(obj, default=str)
        except (TypeError, ValueError):
            return {}

        if len(serialised) <= max_chars:
            return obj

        # Truncate the JSON string and parse back
        truncated = serialised[:max_chars]
        # Try to find a clean break point
        for char in ("},", "],", '",'):
            idx = truncated.rfind(char)
            if idx > 0:
                truncated = truncated[: idx + 1]
                break

        try:
            return json.loads(truncated + "}")
        except json.JSONDecodeError:
            try:
                return json.loads(truncated + "]}")
            except json.JSONDecodeError:
                return {"_truncated": True, "preview": serialised[:500]}
