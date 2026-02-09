"""Tests for the Guardian agent validation pipeline.

The Guardian agent validates step outputs through a series of checks
(integrity, hallucination, PII, etc.) and produces a GuardianReport
with a quality verdict.

Since the Guardian agent module may not yet be fully implemented,
these tests focus on the data structures and validation logic that
are expected to be in place.
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


class TestGuardianReport:

    def test_auto_approve_verdict(self) -> None:
        report = GuardianReport(
            step_id="step-1",
            overall_score=0.95,
            verdict=QualityVerdict.AUTO_APPROVE,
            checks=[
                ValidationCheck(check_name="integrity", passed=True, score=0.95),
                ValidationCheck(check_name="pii", passed=True, score=1.0),
            ],
        )
        assert report.verdict == QualityVerdict.AUTO_APPROVE
        assert report.overall_score >= settings.guardian_auto_approve_threshold

    def test_flag_warnings_verdict(self) -> None:
        report = GuardianReport(
            step_id="step-2",
            overall_score=0.70,
            verdict=QualityVerdict.FLAG_WARNINGS,
            checks=[
                ValidationCheck(
                    check_name="integrity", passed=True, score=0.80,
                    warnings=["Some fields have high null rates"],
                ),
                ValidationCheck(check_name="hallucination", passed=False, score=0.60),
            ],
            recommendations=["Review hallucination detection results"],
        )
        assert report.verdict == QualityVerdict.FLAG_WARNINGS
        assert len(report.recommendations) == 1
        assert report.overall_score >= settings.guardian_warning_threshold

    def test_reprocess_verdict(self) -> None:
        report = GuardianReport(
            step_id="step-3",
            overall_score=0.50,
            verdict=QualityVerdict.REPROCESS,
        )
        assert report.verdict == QualityVerdict.REPROCESS
        assert report.overall_score >= settings.guardian_reprocess_threshold

    def test_escalate_verdict(self) -> None:
        report = GuardianReport(
            step_id="step-4",
            overall_score=0.20,
            verdict=QualityVerdict.ESCALATE,
        )
        assert report.verdict == QualityVerdict.ESCALATE
        assert report.overall_score < settings.guardian_reprocess_threshold


class TestValidationCheck:

    def test_passed_check(self) -> None:
        check = ValidationCheck(
            check_name="data_integrity",
            passed=True,
            score=0.98,
            details="All data integrity checks passed.",
        )
        assert check.passed is True
        assert check.score > 0.9
        assert check.warnings == []

    def test_failed_check_with_warnings(self) -> None:
        check = ValidationCheck(
            check_name="pii_scan",
            passed=False,
            score=0.0,
            details="PII detected in output.",
            warnings=["Email address found", "Phone number found"],
        )
        assert check.passed is False
        assert len(check.warnings) == 2


class TestGuardianVerdictThresholds:
    """Verify that verdict thresholds from settings are properly ordered."""

    def test_threshold_ordering(self) -> None:
        assert settings.guardian_auto_approve_threshold > settings.guardian_warning_threshold
        assert settings.guardian_warning_threshold > settings.guardian_reprocess_threshold

    def test_auto_approve_score_range(self) -> None:
        """Scores above auto_approve_threshold should get AUTO_APPROVE."""
        threshold = settings.guardian_auto_approve_threshold
        assert threshold > 0.5

    def test_escalation_score_range(self) -> None:
        """Scores below reprocess_threshold warrant ESCALATE."""
        threshold = settings.guardian_reprocess_threshold
        assert threshold > 0.0
        assert threshold < 0.5


class TestGuardianPipeline:
    """Test the expected guardian validation pipeline structure."""

    def test_report_aggregation(self) -> None:
        """Multiple check results should aggregate into a single report."""
        checks = [
            ValidationCheck(check_name="integrity", passed=True, score=0.95),
            ValidationCheck(check_name="pii", passed=True, score=1.0),
            ValidationCheck(check_name="hallucination", passed=True, score=0.88),
            ValidationCheck(check_name="statistics", passed=True, score=0.92),
        ]

        # Simulate weighted average
        weights = {"integrity": 0.30, "pii": 0.20, "hallucination": 0.30, "statistics": 0.20}
        overall = sum(c.score * weights.get(c.check_name, 0.25) for c in checks)

        report = GuardianReport(
            step_id="step-1",
            overall_score=round(overall, 4),
            verdict=QualityVerdict.AUTO_APPROVE if overall >= settings.guardian_auto_approve_threshold else QualityVerdict.FLAG_WARNINGS,
            checks=checks,
        )

        assert len(report.checks) == 4
        assert report.overall_score > 0.85
        assert all(c.passed for c in report.checks)

    def test_pipeline_with_failures(self) -> None:
        """A pipeline with failures should produce appropriate verdict."""
        checks = [
            ValidationCheck(check_name="integrity", passed=True, score=0.90),
            ValidationCheck(check_name="pii", passed=False, score=0.0, warnings=["PII detected"]),
            ValidationCheck(check_name="hallucination", passed=False, score=0.40),
        ]

        # Simulate weighted average
        weights = {"integrity": 0.30, "pii": 0.30, "hallucination": 0.40}
        overall = sum(c.score * weights.get(c.check_name, 0.33) for c in checks)

        verdict = QualityVerdict.ESCALATE if overall < settings.guardian_reprocess_threshold else QualityVerdict.REPROCESS

        report = GuardianReport(
            step_id="step-1",
            overall_score=round(overall, 4),
            verdict=verdict,
            checks=checks,
            recommendations=["Remove PII from output", "Verify claims against source data"],
        )

        assert not all(c.passed for c in report.checks)
        assert report.overall_score < settings.guardian_auto_approve_threshold
        assert len(report.recommendations) == 2
