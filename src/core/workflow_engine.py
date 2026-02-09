"""YAML workflow parser and executor for the MCP Agent Mesh.

Loads ``WorkflowDef`` definitions from YAML files, matches incoming
queries to workflows via keyword triggers, converts workflow steps to
executable ``TaskStep`` objects, and validates structural integrity.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

import yaml

from src.core.exceptions import WorkflowError
from src.core.models import (
    ApprovalGate,
    TaskStep,
    WorkflowDef,
    WorkflowStepDef,
    _new_id,
)

logger = logging.getLogger(__name__)

# Regex for timeout strings: e.g. "30s", "5m", "1h", "1h30m", "90"
_TIMEOUT_RE = re.compile(
    r"^(?:(?P<hours>\d+)h)?(?:(?P<minutes>\d+)m)?(?:(?P<seconds>\d+)s?)?$",
    re.IGNORECASE,
)


def parse_timeout(timeout_str: str) -> float:
    """Convert a human-friendly timeout string to seconds.

    Supported formats:
        - ``"30s"`` -- 30 seconds
        - ``"5m"`` -- 5 minutes (300 s)
        - ``"1h"`` -- 1 hour (3600 s)
        - ``"1h30m"`` -- 1 hour 30 minutes (5400 s)
        - ``"90"`` -- plain integer treated as seconds

    Returns:
        The timeout in seconds as a float.

    Raises:
        WorkflowError: If the string cannot be parsed.
    """
    if not timeout_str or not timeout_str.strip():
        raise WorkflowError(
            f"Empty timeout string",
            details={"timeout_str": timeout_str},
        )

    text = timeout_str.strip()

    # Fast path: plain numeric value.
    try:
        return float(text)
    except ValueError:
        pass

    match = _TIMEOUT_RE.match(text)
    if match is None:
        raise WorkflowError(
            f"Invalid timeout format: '{timeout_str}'",
            details={"timeout_str": timeout_str},
        )

    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)

    total = hours * 3600 + minutes * 60 + seconds
    if total == 0:
        raise WorkflowError(
            f"Timeout resolves to zero seconds: '{timeout_str}'",
            details={"timeout_str": timeout_str},
        )

    return float(total)


class WorkflowEngine:
    """Loads, matches, converts, and validates YAML workflow definitions."""

    def __init__(self) -> None:
        self._workflows: dict[str, WorkflowDef] = {}

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_workflow(self, path: str) -> WorkflowDef:
        """Parse a single YAML file into a ``WorkflowDef``.

        The YAML file must contain a top-level mapping whose keys align
        with the ``WorkflowDef`` schema.

        Raises:
            WorkflowError: On file-not-found, YAML parse errors, or
                validation failures.
        """
        filepath = Path(path)
        if not filepath.is_file():
            raise WorkflowError(
                f"Workflow file not found: {path}",
                details={"path": path},
            )

        try:
            raw = filepath.read_text(encoding="utf-8")
            data = yaml.safe_load(raw)
        except yaml.YAMLError as exc:
            raise WorkflowError(
                f"Failed to parse YAML in '{path}': {exc}",
                details={"path": path},
            ) from exc

        if not isinstance(data, dict):
            raise WorkflowError(
                f"Expected a YAML mapping at top level in '{path}', "
                f"got {type(data).__name__}",
                details={"path": path},
            )

        try:
            workflow = WorkflowDef(**data)
        except Exception as exc:
            raise WorkflowError(
                f"Invalid workflow definition in '{path}': {exc}",
                details={"path": path},
            ) from exc

        self._workflows[workflow.name] = workflow
        logger.info("Loaded workflow '%s' from %s", workflow.name, path)
        return workflow

    def load_workflows_dir(self, dir_path: str) -> dict[str, WorkflowDef]:
        """Load every ``.yaml`` / ``.yml`` file in a directory.

        Returns a mapping of workflow name to ``WorkflowDef``.  Files that
        fail to parse are logged as warnings and skipped.
        """
        directory = Path(dir_path)
        if not directory.is_dir():
            raise WorkflowError(
                f"Workflow directory not found: {dir_path}",
                details={"dir_path": dir_path},
            )

        loaded: dict[str, WorkflowDef] = {}
        for entry in sorted(directory.iterdir()):
            if entry.suffix.lower() in (".yaml", ".yml") and entry.is_file():
                try:
                    wf = self.load_workflow(str(entry))
                    loaded[wf.name] = wf
                except WorkflowError as exc:
                    logger.warning("Skipping %s: %s", entry, exc)

        logger.info(
            "Loaded %d workflow(s) from %s", len(loaded), dir_path,
        )
        return loaded

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------

    def match_workflow(self, query: str) -> WorkflowDef | None:
        """Match a user query against loaded workflow trigger keywords.

        Each workflow's ``triggers`` list contains dicts with a
        ``"keywords"`` key (a list of strings).  The query is matched
        case-insensitively against those keywords.

        Returns the first matching ``WorkflowDef`` or ``None`` if no
        workflow matches.
        """
        query_lower = query.lower()

        for workflow in self._workflows.values():
            for trigger in workflow.triggers:
                keywords = trigger.get("keywords", [])
                if any(kw.lower() in query_lower for kw in keywords):
                    logger.info(
                        "Matched query to workflow '%s' via trigger keywords",
                        workflow.name,
                    )
                    return workflow

        return None

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def to_task_steps(self, workflow: WorkflowDef) -> list[TaskStep]:
        """Convert a ``WorkflowDef``'s steps to executable ``TaskStep`` objects.

        The ``step_id`` from the workflow definition is preserved so that
        dependency references (``depends_on``) remain valid.  Timeout
        strings (e.g. ``"5m"``) are converted to seconds.
        """
        task_steps: list[TaskStep] = []

        for wf_step in workflow.steps:
            timeout_secs = parse_timeout(wf_step.timeout)

            task_step = TaskStep(
                step_id=wf_step.id,
                agent=wf_step.agent,
                action=wf_step.action,
                params=dict(wf_step.params),
                depends_on=list(wf_step.depends_on),
                timeout_seconds=timeout_secs,
                max_retries=wf_step.retry,
            )
            task_steps.append(task_step)

        logger.debug(
            "Converted workflow '%s' to %d task step(s)",
            workflow.name,
            len(task_steps),
        )
        return task_steps

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_workflow(self, workflow: WorkflowDef) -> list[str]:
        """Validate the structural integrity of a workflow definition.

        Returns a list of human-readable error strings.  An empty list
        means the workflow is valid.
        """
        errors: list[str] = []

        # Must have a name.
        if not workflow.name or not workflow.name.strip():
            errors.append("Workflow 'name' must be a non-empty string.")

        # Must have at least one step.
        if not workflow.steps:
            errors.append("Workflow must define at least one step.")
            return errors  # No point checking further.

        step_ids: set[str] = set()
        duplicate_ids: set[str] = set()

        for step in workflow.steps:
            # Check for duplicate step IDs.
            if step.id in step_ids:
                duplicate_ids.add(step.id)
            step_ids.add(step.id)

            # Agent must be specified.
            if not step.agent or not step.agent.strip():
                errors.append(f"Step '{step.id}' is missing an 'agent'.")

            # Action must be specified.
            if not step.action or not step.action.strip():
                errors.append(f"Step '{step.id}' is missing an 'action'.")

            # Timeout must be parseable.
            try:
                parse_timeout(step.timeout)
            except WorkflowError as exc:
                errors.append(
                    f"Step '{step.id}' has an invalid timeout "
                    f"'{step.timeout}': {exc}"
                )

            # Retry count must be non-negative.
            if step.retry < 0:
                errors.append(
                    f"Step '{step.id}' has a negative retry count ({step.retry})."
                )

        if duplicate_ids:
            errors.append(
                f"Duplicate step ID(s): {', '.join(sorted(duplicate_ids))}."
            )

        # Validate dependency references.
        for step in workflow.steps:
            for dep in step.depends_on:
                if dep not in step_ids:
                    errors.append(
                        f"Step '{step.id}' depends on unknown step '{dep}'."
                    )

        # Check for circular dependencies (simple DFS).
        adj: dict[str, list[str]] = {s.id: list(s.depends_on) for s in workflow.steps}
        visited: set[str] = set()
        in_stack: set[str] = set()

        def _has_cycle(node: str) -> bool:
            visited.add(node)
            in_stack.add(node)
            for neighbour in adj.get(node, []):
                if neighbour not in visited:
                    if _has_cycle(neighbour):
                        return True
                elif neighbour in in_stack:
                    return True
            in_stack.discard(node)
            return False

        for sid in step_ids:
            if sid not in visited:
                if _has_cycle(sid):
                    errors.append("Workflow contains a circular dependency.")
                    break

        # Validate approval gates reference existing steps.
        for gate in workflow.approval_gates:
            if gate.after not in step_ids:
                errors.append(
                    f"Approval gate references unknown step '{gate.after}'."
                )

        return errors
