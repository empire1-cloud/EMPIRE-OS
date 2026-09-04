from __future__ import annotations

import pytest

from empire_os.governance.models import (
    ActionRequest,
    ActionState,
    ApprovalDecision,
    ExecutionResult,
    IdentityContext,
)
from empire_os.governance.service import GovernanceConflict, GovernanceEngine, GovernanceForbidden
from empire_os.governance.store import GovernanceStore, digest


def actor(actor_id: str = "agent-1", role: str = "agent") -> IdentityContext:
    return IdentityContext(actor_id=actor_id, role=role, scopes=[])


def build_engine(tmp_path) -> GovernanceEngine:
    return GovernanceEngine(GovernanceStore(tmp_path / "governance.json"))


def test_low_risk_request_runs_to_sealed_receipt(tmp_path):
    engine = build_engine(tmp_path)
    record = engine.run(
        ActionRequest(
            action_type="demo.echo",
            actor=actor(),
            parameters={"message": "governed execution"},
            idempotency_key="echo-1",
        )
    )

    assert record.state == ActionState.SEALED
    assert record.receipt_id
    assert record.verification and record.verification.passed
    assert record.reconciliation and record.reconciliation.balanced
    assert engine.store.verify_chain().valid is True

    replay = engine.run(
        ActionRequest(
            action_type="demo.echo",
            actor=actor(),
            parameters={"message": "this must not execute twice"},
            idempotency_key="echo-1",
        )
    )
    assert replay.request_id == record.request_id
    assert len(engine.store.list_receipts()) == 1


def test_medium_risk_waits_for_founder_then_continues(tmp_path):
    engine = build_engine(tmp_path)

    def send_message(request: ActionRequest) -> ExecutionResult:
        output = {"sent": True, "recipient": request.target.get("recipient")}
        return ExecutionResult(
            status="success",
            executor_name="test.external.send_message",
            output=output,
            evidence={"output_digest": digest(output)},
        )

    engine.register_executor("external.send_message", send_message)
    record = engine.intake(
        ActionRequest(
            action_type="external.send_message",
            actor=actor("operator-1", "operator"),
            target={"recipient": "customer-7"},
            parameters={"message": "Approved update"},
        )
    )
    assert record.state == ActionState.PENDING_APPROVAL

    with pytest.raises(GovernanceForbidden):
        engine.approve(record.request_id, actor("operator-2", "operator"))

    approved = engine.approve(
        record.request_id,
        actor("manda", "founder"),
        decision=ApprovalDecision.APPROVED,
        reason="Founder approved customer communication.",
    )
    assert approved.state == ActionState.APPROVED
    completed = engine.continue_request(record.request_id)
    assert completed.state == ActionState.SEALED


def test_destructive_action_is_blocked_even_for_founder(tmp_path):
    engine = build_engine(tmp_path)
    record = engine.intake(
        ActionRequest(
            action_type="system.delete",
            actor=actor("manda", "founder"),
            target={"system": "production"},
        )
    )
    assert record.state == ActionState.BLOCKED
    assert record.policy and record.policy.allowed is False
    assert "hard-blocked" in (record.failure_reason or "")


def test_execution_cannot_skip_approval(tmp_path):
    engine = build_engine(tmp_path)
    record = engine.intake(
        ActionRequest(
            action_type="repo.create_branch",
            actor=actor("operator-1", "operator"),
            target={"repo": "empire1-cloud/EMPIRE-OS"},
            parameters={"branch": "agent/demo"},
        )
    )
    assert record.state == ActionState.PENDING_APPROVAL
    with pytest.raises(GovernanceConflict):
        engine.execute(record.request_id)


def test_secret_material_is_rejected_at_policy_boundary(tmp_path):
    engine = build_engine(tmp_path)
    record = engine.intake(
        ActionRequest(
            action_type="demo.echo",
            actor=actor(),
            parameters={"api_key": "must-never-enter-request"},
        )
    )
    assert record.state == ActionState.BLOCKED
    assert record.policy and "secret_material_block" in record.policy.matched_rules


def test_receipt_chain_detects_tampering(tmp_path):
    engine = build_engine(tmp_path)
    record = engine.run(
        ActionRequest(
            action_type="demo.echo",
            actor=actor(),
            parameters={"message": "original"},
        )
    )
    assert record.state == ActionState.SEALED
    assert engine.store.verify_chain().valid

    engine.store._data["receipts"][0]["payload"]["request"]["parameters"]["message"] = "tampered"
    verification = engine.store.verify_chain()
    assert verification.valid is False
    assert verification.broken_at_sequence == 1
