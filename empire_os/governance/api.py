from __future__ import annotations

import os
from typing import List

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from .models import (
    ActionRecord,
    ActionRequest,
    ApprovalDecision,
    ChainVerification,
    IdentityContext,
    SealedReceipt,
)
from .service import GovernanceConflict, GovernanceEngine, GovernanceForbidden, GovernanceNotFound
from .store import GovernanceStore


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


store = GovernanceStore(persist=_env_bool("EMPIRE_GOVERNANCE_PERSIST", True))
engine = GovernanceEngine(store=store)
router = APIRouter(prefix="/v1/governance", tags=["governance"])


class ApprovalInput(BaseModel):
    approver: IdentityContext
    decision: ApprovalDecision = ApprovalDecision.APPROVED
    reason: str = Field(default="Founder authorization recorded.", min_length=1)


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, GovernanceNotFound):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, GovernanceForbidden):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, GovernanceConflict):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get("/health")
def governance_health():
    chain = store.verify_chain()
    return {
        "status": "online",
        "phase": 21,
        "loop": ["authorize", "approve", "execute", "reconcile", "resolve"],
        "receipt_chain_valid": chain.valid,
        "receipt_count": chain.receipt_count,
    }


@router.post("/requests/run", response_model=ActionRecord)
def run_request(request: ActionRequest):
    try:
        return engine.run(request)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/requests", response_model=ActionRecord, status_code=status.HTTP_201_CREATED)
def create_request(request: ActionRequest):
    try:
        return engine.intake(request)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/requests", response_model=List[ActionRecord])
def list_requests():
    return store.list_records()


@router.get("/requests/{request_id}", response_model=ActionRecord)
def get_request(request_id: str):
    record = store.get_record(request_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Governance request not found.")
    return record


@router.post("/requests/{request_id}/approve", response_model=ActionRecord)
def approve_request(request_id: str, approval: ApprovalInput):
    try:
        return engine.approve(
            request_id,
            approver=approval.approver,
            decision=approval.decision,
            reason=approval.reason,
        )
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/requests/{request_id}/continue", response_model=ActionRecord)
def continue_request(request_id: str):
    try:
        return engine.continue_request(request_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/requests/{request_id}/execute", response_model=ActionRecord)
def execute_request(request_id: str):
    try:
        return engine.execute(request_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/requests/{request_id}/verify", response_model=ActionRecord)
def verify_request(request_id: str):
    try:
        return engine.verify(request_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/requests/{request_id}/reconcile", response_model=ActionRecord)
def reconcile_request(request_id: str):
    try:
        return engine.reconcile(request_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/requests/{request_id}/resolve", response_model=ActionRecord)
def resolve_request(request_id: str):
    try:
        return engine.resolve(request_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/requests/{request_id}/seal", response_model=ActionRecord)
def seal_request(request_id: str):
    try:
        return engine.seal(request_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/receipts/verify-chain", response_model=ChainVerification)
def verify_receipt_chain():
    return store.verify_chain()


@router.get("/receipts", response_model=List[SealedReceipt])
def list_receipts():
    return store.list_receipts()


@router.get("/receipts/{receipt_id}", response_model=SealedReceipt)
def get_receipt(receipt_id: str):
    receipt = store.get_receipt(receipt_id)
    if receipt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found.")
    return receipt
