"""Tests for src.core.models -- model creation and validation."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.core.models import (
    AgentCard,
    ApprovalGate,
    CostRecord,
    GuardianReport,
    HITLRequest,
    OrchestratorState,
    QualityVerdict,
    StepStatus,
    TaskLedgerEntry,
    TaskStatus,
    TaskStep,
    TaskSubmitRequest,
    TaskSubmitResponse,
    TokenUsage,
    ValidationCheck,
    WSEvent,
    WorkflowDef,
    WorkflowStepDef,
    _new_id,
    _utcnow,
)


class TestTokenUsage:

    def test_default_values(self) -> None:
        t = TokenUsage()
        assert t.input_tokens == 0
        assert t.output_tokens == 0
        assert t.total == 0

    def test_total_property(self) -> None:
        t = TokenUsage(input_tokens=100, output_tokens=50)
        assert t.total == 150


class TestCostRecord:

    def test_creation(self) -> None:
        cr = CostRecord(agent_id="test-agent", model="gpt-4o", cost_usd=0.01)
        assert cr.agent_id == "test-agent"
        assert cr.model == "gpt-4o"
        assert cr.cost_usd == 0.01
        assert cr.tokens.total == 0

    def test_timestamp_auto_set(self) -> None:
        cr = CostRecord(agent_id="a", model="m")
        assert cr.timestamp is not None
        assert cr.timestamp.tzinfo is not None


class TestTaskStep:

    def test_default_values(self) -> None:
        step = TaskStep(agent="test-agent", action="do_something")
        assert step.step_id  # auto-generated
        assert step.status == StepStatus.PENDING
        assert step.depends_on == []
        assert step.retries == 0
        assert step.max_retries == 3
        assert step.timeout_seconds == 60.0

    def test_custom_values(self) -> None:
        step = TaskStep(
            step_id="custom-id",
            agent="analytics-v1",
            action="run_analyses",
            params={"key": "value"},
            depends_on=["step-1"],
            timeout_seconds=120.0,
        )
        assert step.step_id == "custom-id"
        assert step.agent == "analytics-v1"
        assert step.params == {"key": "value"}
        assert step.depends_on == ["step-1"]


class TestTaskLedgerEntry:

    def test_creation(self) -> None:
        entry = TaskLedgerEntry(original_request="Test query")
        assert entry.task_id  # auto-generated
        assert entry.original_request == "Test query"
        assert entry.status == TaskStatus.PENDING
        assert entry.total_cost_usd == 0.0
        assert entry.plan == []

    def test_status_transition(self) -> None:
        entry = TaskLedgerEntry(original_request="Test")
        entry.status = TaskStatus.IN_PROGRESS
        assert entry.status == TaskStatus.IN_PROGRESS


class TestAgentCard:

    def test_creation(self) -> None:
        card = AgentCard(
            agent_id="test-v1",
            name="Test Agent",
            description="A test agent",
            capabilities=["cap1", "cap2"],
            mcp_server="test-server",
        )
        assert card.agent_id == "test-v1"
        assert len(card.capabilities) == 2
        assert card.health == "healthy"
        assert card.version == "1.0.0"


class TestGuardianReport:

    def test_creation(self) -> None:
        report = GuardianReport(
            step_id="step-1",
            overall_score=0.9,
            verdict=QualityVerdict.AUTO_APPROVE,
        )
        assert report.step_id == "step-1"
        assert report.overall_score == 0.9
        assert report.verdict == QualityVerdict.AUTO_APPROVE
        assert report.checks == []

    def test_with_checks(self) -> None:
        check = ValidationCheck(
            check_name="integrity",
            passed=True,
            score=0.95,
            details="All good",
        )
        report = GuardianReport(
            step_id="step-1",
            overall_score=0.95,
            verdict=QualityVerdict.AUTO_APPROVE,
            checks=[check],
        )
        assert len(report.checks) == 1
        assert report.checks[0].check_name == "integrity"


class TestValidationCheck:

    def test_creation(self) -> None:
        vc = ValidationCheck(
            check_name="pii_scan",
            passed=True,
            score=1.0,
            details="No PII found",
        )
        assert vc.passed is True
        assert vc.warnings == []


class TestHITLRequest:

    def test_creation(self) -> None:
        req = HITLRequest(
            task_id="task-1",
            step_id="step-1",
            reason="Quality score below threshold",
        )
        assert req.request_id  # auto-generated
        assert req.decision is None
        assert req.resolved_at is None


class TestWorkflowDef:

    def test_creation(self) -> None:
        wf = WorkflowDef(name="test_workflow")
        assert wf.name == "test_workflow"
        assert wf.steps == []
        assert wf.version == "1.0"

    def test_with_steps(self) -> None:
        step = WorkflowStepDef(
            id="s1",
            agent="agent-v1",
            action="do_thing",
        )
        wf = WorkflowDef(name="wf", steps=[step])
        assert len(wf.steps) == 1
        assert wf.steps[0].timeout == "60s"


class TestEnums:

    def test_task_status_values(self) -> None:
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"

    def test_step_status_values(self) -> None:
        assert StepStatus.IN_PROGRESS.value == "in_progress"
        assert StepStatus.REPROCESSING.value == "reprocessing"

    def test_quality_verdict_values(self) -> None:
        assert QualityVerdict.AUTO_APPROVE.value == "auto_approve"
        assert QualityVerdict.ESCALATE.value == "escalate"

    def test_orchestrator_state_values(self) -> None:
        assert OrchestratorState.PLANNING.value == "planning"
        assert OrchestratorState.DELEGATING.value == "delegating"


class TestAPIModels:

    def test_task_submit_request(self) -> None:
        req = TaskSubmitRequest(query="Analyze sales data")
        assert req.query == "Analyze sales data"
        assert req.workflow is None
        assert req.sources == []
        assert req.budget_limit_usd is None

    def test_task_submit_response(self) -> None:
        resp = TaskSubmitResponse(
            task_id="abc123",
            status=TaskStatus.PENDING,
            message="Task accepted",
        )
        assert resp.task_id == "abc123"

    def test_ws_event(self) -> None:
        evt = WSEvent(
            event_type="step_update",
            task_id="task-1",
            data={"step_id": "s1", "status": "completed"},
        )
        assert evt.event_type == "step_update"
        assert evt.timestamp is not None


class TestHelpers:

    def test_new_id_uniqueness(self) -> None:
        ids = {_new_id() for _ in range(100)}
        assert len(ids) == 100  # all unique

    def test_new_id_length(self) -> None:
        assert len(_new_id()) == 12

    def test_utcnow_is_aware(self) -> None:
        now = _utcnow()
        assert now.tzinfo is not None
        assert now.tzinfo == timezone.utc
