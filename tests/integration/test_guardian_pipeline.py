"""Integration tests for the full Guardian validation pipeline.

Tests the complete flow from raw agent output through integrity,
hallucination, and quality scoring checks.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.core.config import settings
from src.core.models import (
    GuardianReport,
    QualityVerdict,
    ValidationCheck,
)
from src.mcp_servers.eval_guards.tools.check_data_integrity import check_data_integrity


@pytest.mark.asyncio
class TestGuardianPipeline:

    async def test_clean_data_passes_all_checks(self) -> None:
        """Clean, well-formed data should pass integrity checks."""
        data = [
            {"name": "Widget Pro", "revenue": 50000.0, "units": 100},
            {"name": "Gadget X", "revenue": 75000.0, "units": 150},
            {"name": "Sensor V1", "revenue": 25000.0, "units": 200},
        ]

        integrity_result = await check_data_integrity({"data": data})

        assert integrity_result["passed"] is True
        assert integrity_result["score"] > 0.8

    async def test_dirty_data_fails_integrity(self) -> None:
        """Data with significant quality issues should fail."""
        data = [
            {"name": None, "revenue": None, "units": None},
            {"name": "", "revenue": None, "units": None},
            {"name": "Widget", "revenue": 1000, "units": 10},
        ]

        integrity_result = await check_data_integrity({"data": data})

        # Should have warnings about nulls
        assert len(integrity_result["warnings"]) > 0
        assert integrity_result["score"] < 1.0

    async def test_mixed_types_fail_consistency(self) -> None:
        """Mixed types in a column should be flagged."""
        data = [
            {"value": 100},
            {"value": "not a number"},
            {"value": 200},
        ]

        result = await check_data_integrity({"data": data})
        consistency_check = next(
            c for c in result["checks"] if c["name"] == "consistency"
        )
        assert consistency_check["passed"] is False

    async def test_pipeline_produces_guardian_report(self) -> None:
        """Simulates the full guardian pipeline producing a report."""
        # Step 1: Run integrity check
        data = [
            {"product": "Widget Pro", "revenue": 50000.0, "date": "2025-10-15"},
            {"product": "Gadget X", "revenue": 75000.0, "date": "2025-11-20"},
        ]
        integrity_result = await check_data_integrity({"data": data})

        # Step 2: Build validation checks from results
        checks: list[ValidationCheck] = []

        checks.append(ValidationCheck(
            check_name="data_integrity",
            passed=integrity_result["passed"],
            score=integrity_result["score"],
            details=str(integrity_result.get("checks", [])),
            warnings=integrity_result.get("warnings", []),
        ))

        # Simulate PII check (no PII in this data)
        checks.append(ValidationCheck(
            check_name="pii_scan",
            passed=True,
            score=1.0,
            details="No PII detected",
        ))

        # Simulate hallucination check
        checks.append(ValidationCheck(
            check_name="hallucination",
            passed=True,
            score=0.95,
            details="All claims verified against source data",
        ))

        # Step 3: Aggregate scores
        weights = {
            "data_integrity": 0.35,
            "pii_scan": 0.25,
            "hallucination": 0.40,
        }
        overall_score = sum(
            c.score * weights.get(c.check_name, 0.25)
            for c in checks
        )

        # Step 4: Determine verdict
        if overall_score >= settings.guardian_auto_approve_threshold:
            verdict = QualityVerdict.AUTO_APPROVE
        elif overall_score >= settings.guardian_warning_threshold:
            verdict = QualityVerdict.FLAG_WARNINGS
        elif overall_score >= settings.guardian_reprocess_threshold:
            verdict = QualityVerdict.REPROCESS
        else:
            verdict = QualityVerdict.ESCALATE

        # Step 5: Build report
        report = GuardianReport(
            step_id="step-analytics",
            overall_score=round(overall_score, 4),
            verdict=verdict,
            checks=checks,
        )

        assert report.overall_score > 0.8
        assert report.verdict == QualityVerdict.AUTO_APPROVE
        assert len(report.checks) == 3

    async def test_pipeline_with_schema_validation(self) -> None:
        """Full pipeline with schema-based type checking."""
        data = [
            {"name": "Alice", "age": 30, "score": 85.5},
            {"name": "Bob", "age": 25, "score": 92.0},
        ]
        schema = {"name": "str", "age": "int", "score": "float"}

        result = await check_data_integrity({
            "data": data,
            "expected_schema": schema,
        })

        assert result["passed"] is True
        consistency_check = next(
            c for c in result["checks"] if c["name"] == "consistency"
        )
        assert consistency_check["passed"] is True

    async def test_pipeline_escalation_on_empty_data(self) -> None:
        """Empty data should trigger escalation path."""
        result = await check_data_integrity({"data": []})

        assert result["passed"] is False
        assert result["score"] == 0.0

        # This score would trigger escalation
        assert result["score"] < settings.guardian_reprocess_threshold
