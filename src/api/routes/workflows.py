"""Workflow management routes.

Provides endpoints for listing available workflows, inspecting individual
workflow definitions, and validating workflow structure before deployment.
Workflow definitions are managed by the ``WorkflowEngine`` and loaded from
YAML files at startup.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from src.api.routes.auth import require_role, verify_token
from src.core.exceptions import WorkflowError
from src.core.models import WorkflowDef
from src.core.workflow_engine import WorkflowEngine

router = APIRouter(prefix="/workflows", tags=["Workflows"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_workflow_engine(request: Request) -> WorkflowEngine:
    """Retrieve the WorkflowEngine from application state.

    Falls back to a fresh instance if none has been registered on
    ``app.state`` (useful during early development).
    """
    engine = getattr(request.app.state, "workflow_engine", None)
    if engine is None:
        # Return an empty engine rather than erroring, so the endpoints
        # remain reachable even before startup is fully wired.
        return WorkflowEngine()
    return engine


def _workflow_to_dict(wf: WorkflowDef) -> dict[str, Any]:
    """Serialise a ``WorkflowDef`` to a JSON-friendly dict."""
    return wf.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Request / response helpers
# ---------------------------------------------------------------------------

class WorkflowValidationRequest(BaseModel):
    """Payload for the workflow validation endpoint."""
    name: str
    description: str = ""
    version: str = "1.0"
    triggers: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []
    approval_gates: list[dict[str, Any]] = []
    notifications: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/")
async def list_workflows(
    request: Request,
    payload: dict[str, Any] = Depends(verify_token),
) -> dict[str, Any]:
    """List all available workflow definitions.

    Returns the name, description, version, and step count for each
    loaded workflow.
    """
    engine = _get_workflow_engine(request)

    # Access the internal workflow store.  The WorkflowEngine stores
    # loaded workflows in ``_workflows``.
    workflows = engine._workflows

    items: list[dict[str, Any]] = []
    for name, wf in workflows.items():
        items.append({
            "name": wf.name,
            "description": wf.description,
            "version": wf.version,
            "step_count": len(wf.steps),
            "triggers": wf.triggers,
        })

    return {
        "count": len(items),
        "workflows": items,
    }


@router.get("/{workflow_name}")
async def get_workflow(
    workflow_name: str,
    request: Request,
    payload: dict[str, Any] = Depends(verify_token),
) -> dict[str, Any]:
    """Get the full definition of a workflow by name.

    Returns every detail of the workflow including steps, dependencies,
    approval gates, and notification configuration.
    """
    engine = _get_workflow_engine(request)

    wf: WorkflowDef | None = engine._workflows.get(workflow_name)
    if wf is None:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow '{workflow_name}' not found.",
        )

    return _workflow_to_dict(wf)


@router.post("/validate")
async def validate_workflow(
    workflow: WorkflowValidationRequest,
    request: Request,
    payload: dict[str, Any] = Depends(verify_token),
) -> dict[str, Any]:
    """Validate a workflow definition without persisting it.

    Parses the provided workflow definition and runs the ``WorkflowEngine``
    validation suite (dependency checks, cycle detection, timeout parsing,
    etc.).  Returns validation results with any errors found.
    """
    engine = _get_workflow_engine(request)

    # Attempt to build a WorkflowDef from the request payload.
    try:
        wf = WorkflowDef(**workflow.model_dump())
    except Exception as exc:
        return {
            "valid": False,
            "errors": [f"Failed to parse workflow definition: {exc}"],
        }

    # Run structural validation.
    errors = engine.validate_workflow(wf)

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "workflow_name": wf.name,
        "step_count": len(wf.steps),
    }
