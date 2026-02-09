"""Tests for src.core.workflow_engine -- YAML workflow parsing."""

from __future__ import annotations

import pytest

from src.core.exceptions import WorkflowError
from src.core.models import WorkflowDef, WorkflowStepDef
from src.core.workflow_engine import WorkflowEngine, parse_timeout


class TestParseTimeout:

    def test_seconds(self) -> None:
        assert parse_timeout("30s") == 30.0

    def test_minutes(self) -> None:
        assert parse_timeout("5m") == 300.0

    def test_hours(self) -> None:
        assert parse_timeout("1h") == 3600.0

    def test_combined_hours_minutes(self) -> None:
        assert parse_timeout("1h30m") == 5400.0

    def test_plain_number(self) -> None:
        assert parse_timeout("90") == 90.0

    def test_plain_float(self) -> None:
        assert parse_timeout("30.5") == 30.5

    def test_empty_string_raises(self) -> None:
        with pytest.raises(WorkflowError, match="Empty timeout"):
            parse_timeout("")

    def test_invalid_format_raises(self) -> None:
        with pytest.raises(WorkflowError, match="Invalid timeout"):
            parse_timeout("abc")

    def test_zero_timeout_raises(self) -> None:
        with pytest.raises(WorkflowError, match="zero seconds"):
            parse_timeout("0h0m0s")


class TestWorkflowEngine:

    def test_load_workflow(self, sample_workflow_yaml: str) -> None:
        engine = WorkflowEngine()
        wf = engine.load_workflow(sample_workflow_yaml)
        assert wf.name == "test_workflow"
        assert len(wf.steps) == 3

    def test_load_workflow_not_found(self) -> None:
        engine = WorkflowEngine()
        with pytest.raises(WorkflowError, match="not found"):
            engine.load_workflow("/nonexistent/path.yaml")

    def test_match_workflow(self, sample_workflow_yaml: str) -> None:
        engine = WorkflowEngine()
        engine.load_workflow(sample_workflow_yaml)

        matched = engine.match_workflow("Please test and analyze this data")
        assert matched is not None
        assert matched.name == "test_workflow"

    def test_match_workflow_no_match(self, sample_workflow_yaml: str) -> None:
        engine = WorkflowEngine()
        engine.load_workflow(sample_workflow_yaml)

        matched = engine.match_workflow("completely unrelated query about cooking")
        assert matched is None

    def test_match_workflow_case_insensitive(self, sample_workflow_yaml: str) -> None:
        engine = WorkflowEngine()
        engine.load_workflow(sample_workflow_yaml)

        matched = engine.match_workflow("Please ANALYZE my data")
        assert matched is not None

    def test_to_task_steps(self, sample_workflow_yaml: str) -> None:
        engine = WorkflowEngine()
        wf = engine.load_workflow(sample_workflow_yaml)
        steps = engine.to_task_steps(wf)

        assert len(steps) == 3
        assert steps[0].step_id == "step-ingest"
        assert steps[0].agent == "data-ingestion-v1"
        assert steps[0].timeout_seconds == 30.0
        assert steps[0].max_retries == 2

        assert steps[1].step_id == "step-analyze"
        assert steps[1].depends_on == ["step-ingest"]
        assert steps[1].timeout_seconds == 120.0  # 2m

        assert steps[2].depends_on == ["step-analyze"]

    def test_validate_workflow_valid(self, sample_workflow_yaml: str) -> None:
        engine = WorkflowEngine()
        wf = engine.load_workflow(sample_workflow_yaml)
        errors = engine.validate_workflow(wf)
        assert errors == []

    def test_validate_workflow_empty_name(self) -> None:
        engine = WorkflowEngine()
        wf = WorkflowDef(
            name="",
            steps=[WorkflowStepDef(id="s1", agent="a", action="x")],
        )
        errors = engine.validate_workflow(wf)
        assert any("name" in e.lower() for e in errors)

    def test_validate_workflow_no_steps(self) -> None:
        engine = WorkflowEngine()
        wf = WorkflowDef(name="empty", steps=[])
        errors = engine.validate_workflow(wf)
        assert any("at least one step" in e.lower() for e in errors)

    def test_validate_workflow_duplicate_step_ids(self) -> None:
        engine = WorkflowEngine()
        wf = WorkflowDef(
            name="dup",
            steps=[
                WorkflowStepDef(id="s1", agent="a", action="x"),
                WorkflowStepDef(id="s1", agent="b", action="y"),
            ],
        )
        errors = engine.validate_workflow(wf)
        assert any("duplicate" in e.lower() for e in errors)

    def test_validate_workflow_unknown_dependency(self) -> None:
        engine = WorkflowEngine()
        wf = WorkflowDef(
            name="bad_dep",
            steps=[
                WorkflowStepDef(
                    id="s1", agent="a", action="x",
                    depends_on=["nonexistent"],
                ),
            ],
        )
        errors = engine.validate_workflow(wf)
        assert any("unknown step" in e.lower() for e in errors)

    def test_validate_workflow_circular_dependency(self) -> None:
        engine = WorkflowEngine()
        wf = WorkflowDef(
            name="circular",
            steps=[
                WorkflowStepDef(id="s1", agent="a", action="x", depends_on=["s2"]),
                WorkflowStepDef(id="s2", agent="b", action="y", depends_on=["s1"]),
            ],
        )
        errors = engine.validate_workflow(wf)
        assert any("circular" in e.lower() for e in errors)

    def test_validate_workflow_missing_agent(self) -> None:
        engine = WorkflowEngine()
        wf = WorkflowDef(
            name="no_agent",
            steps=[WorkflowStepDef(id="s1", agent="", action="x")],
        )
        errors = engine.validate_workflow(wf)
        assert any("agent" in e.lower() for e in errors)

    def test_load_workflows_dir(self, sample_workflow_yaml: str) -> None:
        import os
        engine = WorkflowEngine()
        dir_path = os.path.dirname(sample_workflow_yaml)
        loaded = engine.load_workflows_dir(dir_path)
        assert "test_workflow" in loaded
