"""Shared data models for the MCP Agent Mesh."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid4().hex[:12]


# --- Enums ---

class TaskStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    VALIDATING = "validating"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REPROCESSING = "reprocessing"
    SKIPPED = "skipped"


class OrchestratorState(str, Enum):
    PLANNING = "planning"
    DELEGATING = "delegating"
    MONITORING = "monitoring"
    VALIDATING = "validating"
    DELIVERING = "delivering"
    REPLANNING = "replanning"
    ESCALATING = "escalating"


class QualityVerdict(str, Enum):
    AUTO_APPROVE = "auto_approve"
    FLAG_WARNINGS = "flag_warnings"
    REPROCESS = "reprocess"
    ESCALATE = "escalate"


# --- Token & Cost ---

class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


class CostRecord(BaseModel):
    agent_id: str
    model: str
    tokens: TokenUsage = TokenUsage()
    cost_usd: float = 0.0
    timestamp: datetime = Field(default_factory=_utcnow)


# --- Agent Card ---

class AgentCard(BaseModel):
    agent_id: str
    name: str
    description: str
    capabilities: list[str]
    mcp_server: str
    input_schema: dict = {}
    output_schema: dict = {}
    cost_per_call_estimate: str = "$0.00"
    avg_latency_ms: int = 0
    version: str = "1.0.0"
    health: str = "healthy"
    registered_at: datetime = Field(default_factory=_utcnow)
    last_heartbeat: datetime = Field(default_factory=_utcnow)


# --- Task & Step ---

class TaskStep(BaseModel):
    step_id: str = Field(default_factory=_new_id)
    agent: str
    action: str
    params: dict = {}
    depends_on: list[str] = []
    status: StepStatus = StepStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    tokens: TokenUsage = TokenUsage()
    cost_usd: float = 0.0
    quality_score: float | None = None
    output_ref: str | None = None
    error: str | None = None
    retries: int = 0
    max_retries: int = 3
    timeout_seconds: float = 60.0


class TaskLedgerEntry(BaseModel):
    task_id: str = Field(default_factory=_new_id)
    user_id: str = ""
    original_request: str
    plan: list[TaskStep] = []
    status: TaskStatus = TaskStatus.PENDING
    total_cost_usd: float = 0.0
    total_tokens: TokenUsage = TokenUsage()
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    completed_at: datetime | None = None
    result_ref: str | None = None
    metadata: dict = {}


# --- Guardian ---

class ValidationCheck(BaseModel):
    check_name: str
    passed: bool
    score: float
    details: str = ""
    warnings: list[str] = []


class GuardianReport(BaseModel):
    step_id: str
    overall_score: float
    verdict: QualityVerdict
    checks: list[ValidationCheck] = []
    recommendations: list[str] = []
    timestamp: datetime = Field(default_factory=_utcnow)


# --- HITL ---

class HITLRequest(BaseModel):
    request_id: str = Field(default_factory=_new_id)
    task_id: str
    step_id: str
    reason: str
    context: dict = {}
    guardian_report: GuardianReport | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    resolved_at: datetime | None = None
    decision: str | None = None  # "approved", "rejected", "edited"
    reviewer_notes: str = ""


# --- Workflow ---

class WorkflowStepDef(BaseModel):
    id: str
    agent: str
    action: str
    params: dict = {}
    depends_on: list[str] = []
    timeout: str = "60s"
    retry: int = 3
    on_fail: str | None = None


class ApprovalGate(BaseModel):
    after: str
    condition: str


class WorkflowDef(BaseModel):
    name: str
    description: str = ""
    version: str = "1.0"
    triggers: list[dict] = []
    steps: list[WorkflowStepDef] = []
    approval_gates: list[ApprovalGate] = []
    notifications: dict = {}


# --- API ---

class TaskSubmitRequest(BaseModel):
    query: str
    workflow: str | None = None
    sources: list[str] = []
    params: dict = {}
    budget_limit_usd: float | None = None


class TaskSubmitResponse(BaseModel):
    task_id: str
    status: TaskStatus
    message: str


class AgentHealthResponse(BaseModel):
    agent_id: str
    name: str
    health: str
    uptime_seconds: float
    avg_latency_ms: float
    error_rate: float
    last_heartbeat: datetime


# --- WebSocket Events ---

class WSEvent(BaseModel):
    event_type: str  # "agent_activity", "step_update", "hitl_request", "task_complete"
    task_id: str
    data: dict
    timestamp: datetime = Field(default_factory=_utcnow)
