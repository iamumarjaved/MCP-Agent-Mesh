"""Integration tests for the workflow engine.

Tests parsing YAML files, matching workflows to queries, converting
to executable task steps, and validating complete workflow definitions.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.core.exceptions import WorkflowError
from src.core.models import StepStatus, TaskStep, WorkflowDef
from src.core.workflow_engine import WorkflowEngine


@pytest.fixture
def workflow_dir(tmp_path: Path) -> str:
    """Create a temporary directory with multiple workflow YAML files."""

    (tmp_path / "sales_analysis.yaml").write_text("""
name: sales_analysis
description: Full sales analysis pipeline
version: "1.0"
triggers:
  - keywords: ["sales", "revenue", "quarterly"]
steps:
  - id: ingest
    agent: data-ingestion-v1
    action: ingest_and_clean
    params:
      source: sales_q4_2025.csv
    depends_on: []
    timeout: "60s"
    retry: 3
  - id: analyze
    agent: analytics-v1
    action: run_analyses
    params:
      analyses: ["statistics", "trend", "anomaly"]
    depends_on: ["ingest"]
    timeout: "5m"
    retry: 2
  - id: report
    agent: presentation-v1
    action: compile_report
    params: {}
    depends_on: ["analyze"]
    timeout: "2m"
    retry: 1
approval_gates:
  - after: analyze
    condition: "quality_score < 0.7"
""")

    (tmp_path / "market_research.yaml").write_text("""
name: market_research
description: Market research workflow
version: "1.0"
triggers:
  - keywords: ["market", "competitive", "landscape"]
steps:
  - id: gather
    agent: insight-generator-v1
    action: research
    params: {}
    depends_on: []
    timeout: "3m"
    retry: 2
  - id: summarize
    agent: presentation-v1
    action: compile_report
    params: {}
    depends_on: ["gather"]
    timeout: "2m"
    retry: 1
""")

    # Invalid YAML file to test error handling
    (tmp_path / "invalid.yaml").write_text("name: [broken yaml")

    return str(tmp_path)


class TestWorkflowEngineIntegration:

    def test_load_workflows_dir(self, workflow_dir: str) -> None:
        engine = WorkflowEngine()
        loaded = engine.load_workflows_dir(workflow_dir)
        # Should load 2 valid workflows and skip the invalid one
        assert len(loaded) >= 2
        assert "sales_analysis" in loaded
        assert "market_research" in loaded

    def test_match_sales_query(self, workflow_dir: str) -> None:
        engine = WorkflowEngine()
        engine.load_workflows_dir(workflow_dir)

        matched = engine.match_workflow("Analyze our quarterly sales revenue data")
        assert matched is not None
        assert matched.name == "sales_analysis"

    def test_match_market_query(self, workflow_dir: str) -> None:
        engine = WorkflowEngine()
        engine.load_workflows_dir(workflow_dir)

        matched = engine.match_workflow("Research the competitive landscape")
        assert matched is not None
        assert matched.name == "market_research"

    def test_match_no_match(self, workflow_dir: str) -> None:
        engine = WorkflowEngine()
        engine.load_workflows_dir(workflow_dir)

        matched = engine.match_workflow("What is the weather today?")
        assert matched is None

    def test_convert_to_task_steps(self, workflow_dir: str) -> None:
        engine = WorkflowEngine()
        engine.load_workflows_dir(workflow_dir)

        wf = engine._workflows["sales_analysis"]
        steps = engine.to_task_steps(wf)

        assert len(steps) == 3
        assert all(isinstance(s, TaskStep) for s in steps)

        # Check step properties
        ingest = steps[0]
        assert ingest.step_id == "ingest"
        assert ingest.agent == "data-ingestion-v1"
        assert ingest.timeout_seconds == 60.0
        assert ingest.max_retries == 3
        assert ingest.status == StepStatus.PENDING

        analyze = steps[1]
        assert analyze.depends_on == ["ingest"]
        assert analyze.timeout_seconds == 300.0  # 5m

    def test_validate_sales_workflow(self, workflow_dir: str) -> None:
        engine = WorkflowEngine()
        engine.load_workflows_dir(workflow_dir)

        wf = engine._workflows["sales_analysis"]
        errors = engine.validate_workflow(wf)
        assert errors == []

    def test_validate_market_workflow(self, workflow_dir: str) -> None:
        engine = WorkflowEngine()
        engine.load_workflows_dir(workflow_dir)

        wf = engine._workflows["market_research"]
        errors = engine.validate_workflow(wf)
        assert errors == []

    def test_full_pipeline(self, workflow_dir: str) -> None:
        """Load -> Match -> Convert -> Validate complete pipeline."""
        engine = WorkflowEngine()
        engine.load_workflows_dir(workflow_dir)

        # Match
        wf = engine.match_workflow("Analyze Q4 sales revenue trends")
        assert wf is not None

        # Validate
        errors = engine.validate_workflow(wf)
        assert errors == []

        # Convert
        steps = engine.to_task_steps(wf)
        assert len(steps) > 0

        # Verify dependency chain is valid
        completed_ids: set[str] = set()
        for step in steps:
            for dep in step.depends_on:
                assert dep in completed_ids, f"Step {step.step_id} depends on {dep} which hasn't been seen yet"
            completed_ids.add(step.step_id)
