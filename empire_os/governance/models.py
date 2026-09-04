from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def model_to_dict(model: BaseModel) -> Dict[str, Any]:
    """Return a JSON-safe dict across Pydantic v1 and v2."""
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")  # type: ignore[attr-defined]
    return model.dict()  # type: ignore[no-any-return]


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActionState(str, Enum):
    REQUESTED = "requested"
    IDENTIFIED = "identified"
    AUTHORIZED = "authorized"
    RISK_ASSESSED = "risk_assessed"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    EXECUTED = "executed"
    VERIFIED = "verified"
    RECONCILED = "reconciled"
    RESOLVED = "resolved"
    SEALED = "sealed"
    BLOCKED = "blocked"
    FAILED = "failed"


class ApprovalDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


class IdentityContext(BaseModel):
    actor_id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    universe: str = "empire1"
    scopes: List[str] = Field(default_factory=list)


class ActionRequest(BaseModel):
    action_type: str = Field(min_length=1)
    actor: IdentityContext
    target: Dict[str, Any] = Field(default_factory=dict)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    requested_impact: Optional[str] = None
    idempotency_key: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PolicyDecision(BaseModel):
    allowed: bool
    risk: RiskLevel
    approval_required: bool
    required_approver_role: Optional[str] = None
    reasons: List[str] = Field(default_factory=list)
    matched_rules: List[str] = Field(default_factory=list)


class ApprovalRecord(BaseModel):
    decision: ApprovalDecision
    approver: IdentityContext
    reason: str
    approved_at: datetime = Field(default_factory=utc_now)


class ExecutionResult(BaseModel):
    status: str
    executor_name: str
    mode: str = "internal"
    output: Dict[str, Any] = Field(default_factory=dict)
    evidence: Dict[str, Any] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime = Field(default_factory=utc_now)


class VerificationResult(BaseModel):
    passed: bool
    checks: List[str] = Field(default_factory=list)
    evidence_digest: Optional[str] = None
    reason: Optional[str] = None
    verified_at: datetime = Field(default_factory=utc_now)


class ReconciliationResult(BaseModel):
    balanced: bool
    ledger_entries: List[Dict[str, Any]] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    reconciled_at: datetime = Field(default_factory=utc_now)


class StateEvent(BaseModel):
    state: ActionState
    at: datetime = Field(default_factory=utc_now)
    actor_id: str
    reason: str


class ActionRecord(BaseModel):
    request_id: str = Field(default_factory=lambda: new_id("req"))
    request: ActionRequest
    state: ActionState = ActionState.REQUESTED
    risk: Optional[RiskLevel] = None
    policy: Optional[PolicyDecision] = None
    approval: Optional[ApprovalRecord] = None
    execution: Optional[ExecutionResult] = None
    verification: Optional[VerificationResult] = None
    reconciliation: Optional[ReconciliationResult] = None
    receipt_id: Optional[str] = None
    failure_reason: Optional[str] = None
    history: List[StateEvent] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SealedReceipt(BaseModel):
    receipt_id: str = Field(default_factory=lambda: new_id("receipt"))
    sequence: int
    request_id: str
    previous_hash: str
    payload: Dict[str, Any]
    receipt_hash: str
    sealed_at: datetime = Field(default_factory=utc_now)


class ChainVerification(BaseModel):
    valid: bool
    receipt_count: int
    broken_at_sequence: Optional[int] = None
    reason: Optional[str] = None
