from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Callable, Dict, Iterable

from .models import (
    ActionRecord,
    ActionRequest,
    ActionState,
    ApprovalDecision,
    ApprovalRecord,
    ExecutionResult,
    IdentityContext,
    ReconciliationResult,
    StateEvent,
    VerificationResult,
)
from .policy import PolicyEngine
from .store import GovernanceStore, digest

Executor = Callable[[ActionRequest], ExecutionResult]


class GovernanceError(RuntimeError):
    pass


class GovernanceNotFound(GovernanceError):
    pass


class GovernanceConflict(GovernanceError):
    pass


class GovernanceForbidden(GovernanceError):
    pass


class GovernanceEngine:
    """Canonical Phase 21 loop: AUTHORIZE → APPROVE → EXECUTE → RECONCILE → RESOLVE."""

    def __init__(self, store: GovernanceStore | None = None, policy: PolicyEngine | None = None):
        self.store = store or GovernanceStore()
        self.policy = policy or PolicyEngine()
        self.executors: Dict[str, Executor] = {}
        self.register_executor("demo.echo", self._execute_echo)
        self.register_executor("evidence.attest", self._execute_attestation)

    def register_executor(self, action_type: str, executor: Executor) -> None:
        normalized = action_type.strip().lower()
        if not normalized:
            raise ValueError("action_type may not be blank")
        self.executors[normalized] = executor

    def intake(self, request: ActionRequest) -> ActionRecord:
        if request.idempotency_key:
            existing = self.store.find_by_idempotency_key(request.idempotency_key)
            if existing:
                return existing

        request.action_type = request.action_type.strip().lower()
        request.actor.role = request.actor.role.strip().lower()
        record = ActionRecord(request=request)
        self._transition(record, ActionState.REQUESTED, request.actor.actor_id, "Governance request received.")
        self._transition(record, ActionState.IDENTIFIED, request.actor.actor_id, "Actor identity context attached.")

        decision = self.policy.evaluate(request)
        record.policy = decision
        record.risk = decision.risk

        if not decision.allowed:
            record.failure_reason = "; ".join(decision.reasons)
            self._transition(record, ActionState.BLOCKED, "policy", record.failure_reason)
            return self.store.save_record(record)

        self._transition(record, ActionState.AUTHORIZED, "policy", "Identity and action scope authorized.")
        self._transition(record, ActionState.RISK_ASSESSED, "policy", f"Risk classified as {decision.risk.value}.")

        if decision.approval_required:
            self._transition(
                record,
                ActionState.PENDING_APPROVAL,
                "policy",
                f"Approval required from role '{decision.required_approver_role}'.",
            )
        else:
            record.approval = ApprovalRecord(
                decision=ApprovalDecision.APPROVED,
                approver=IdentityContext(actor_id="policy:auto", role="policy", scopes=[request.action_type]),
                reason="Deterministic policy authorized low-risk execution without human approval.",
            )
            self._transition(record, ActionState.APPROVED, "policy:auto", "Low-risk request auto-approved by policy.")

        return self.store.save_record(record)

    def approve(
        self,
        request_id: str,
        approver: IdentityContext,
        decision: ApprovalDecision = ApprovalDecision.APPROVED,
        reason: str = "Founder authorization recorded.",
    ) -> ActionRecord:
        record = self._require_record(request_id)
        if record.state != ActionState.PENDING_APPROVAL:
            raise GovernanceConflict(f"Request is in '{record.state.value}', not pending approval.")

        required_role = record.policy.required_approver_role if record.policy else "founder"
        if approver.role.strip().lower() != required_role:
            raise GovernanceForbidden(f"Approval requires role '{required_role}'.")

        record.approval = ApprovalRecord(decision=decision, approver=approver, reason=reason)
        if decision == ApprovalDecision.REJECTED:
            record.failure_reason = reason
            self._transition(record, ActionState.BLOCKED, approver.actor_id, f"Approval rejected: {reason}")
        else:
            self._transition(record, ActionState.APPROVED, approver.actor_id, reason)
        return self.store.save_record(record)

    def execute(self, request_id: str) -> ActionRecord:
        record = self._require_record(request_id)
        if record.state != ActionState.APPROVED:
            raise GovernanceConflict("Execution requires an approved request.")

        executor = self.executors.get(record.request.action_type)
        if executor is None:
            record.failure_reason = f"No executor is registered for '{record.request.action_type}'."
            self._transition(record, ActionState.FAILED, "executor", record.failure_reason)
            return self.store.save_record(record)

        try:
            result = executor(record.request)
            if result.status.lower() != "success":
                record.execution = result
                record.failure_reason = f"Executor returned status '{result.status}'."
                self._transition(record, ActionState.FAILED, "executor", record.failure_reason)
            else:
                record.execution = result
                self._transition(record, ActionState.EXECUTED, result.executor_name, "Registered executor completed.")
        except Exception as exc:
            record.failure_reason = f"Executor raised {type(exc).__name__}: {exc}"
            self._transition(record, ActionState.FAILED, "executor", record.failure_reason)
        return self.store.save_record(record)

    def verify(self, request_id: str) -> ActionRecord:
        record = self._require_record(request_id)
        if record.state != ActionState.EXECUTED or record.execution is None:
            raise GovernanceConflict("Verification requires a completed execution result.")

        checks = []
        expected_digest = digest(record.execution.output)
        supplied_digest = record.execution.evidence.get("output_digest")
        if supplied_digest != expected_digest:
            record.verification = VerificationResult(
                passed=False,
                checks=["output_digest"],
                reason="Executor evidence digest does not match its output.",
            )
            record.failure_reason = record.verification.reason
            self._transition(record, ActionState.FAILED, "verifier", record.failure_reason)
            return self.store.save_record(record)
        checks.append("output_digest")

        if record.request.action_type == "demo.echo":
            expected_message = record.request.parameters.get("message")
            if record.execution.output.get("echo") != expected_message:
                record.verification = VerificationResult(
                    passed=False,
                    checks=checks + ["echo_matches_request"],
                    reason="Echo output did not match the governed request.",
                )
                record.failure_reason = record.verification.reason
                self._transition(record, ActionState.FAILED, "verifier", record.failure_reason)
                return self.store.save_record(record)
            checks.append("echo_matches_request")

        record.verification = VerificationResult(
            passed=True,
            checks=checks,
            evidence_digest=expected_digest,
            reason="Execution evidence matched the governed request and output.",
        )
        self._transition(record, ActionState.VERIFIED, "verifier", "Execution evidence verified.")
        return self.store.save_record(record)

    def reconcile(self, request_id: str) -> ActionRecord:
        record = self._require_record(request_id)
        if record.state != ActionState.VERIFIED or record.execution is None:
            raise GovernanceConflict("Reconciliation requires verified execution.")

        ledger_entries = record.execution.evidence.get("ledger_entries", [])
        balanced = self._ledger_is_balanced(ledger_entries)
        notes = ["No financial entries declared; operational reconciliation complete."]
        if ledger_entries:
            notes = ["Declared ledger entries balance." if balanced else "Declared ledger entries do not balance."]

        record.reconciliation = ReconciliationResult(
            balanced=balanced,
            ledger_entries=ledger_entries,
            notes=notes,
        )
        if not balanced:
            record.failure_reason = "Reconciliation failed: ledger entries are not balanced."
            self._transition(record, ActionState.FAILED, "reconciler", record.failure_reason)
        else:
            self._transition(record, ActionState.RECONCILED, "reconciler", notes[0])
        return self.store.save_record(record)

    def resolve(self, request_id: str) -> ActionRecord:
        record = self._require_record(request_id)
        if record.state != ActionState.RECONCILED:
            raise GovernanceConflict("Resolution requires successful reconciliation.")
        self._transition(record, ActionState.RESOLVED, "governance", "Governed action closed with verified evidence.")
        return self.store.save_record(record)

    def seal(self, request_id: str) -> ActionRecord:
        record = self._require_record(request_id)
        if record.state != ActionState.RESOLVED:
            raise GovernanceConflict("A receipt may only be sealed after resolution.")

        receipt = self.store.seal(record)
        record.receipt_id = receipt.receipt_id
        self._transition(record, ActionState.SEALED, "receipt-sealer", f"Receipt sequence {receipt.sequence} sealed.")
        return self.store.save_record(record)

    def continue_request(self, request_id: str) -> ActionRecord:
        """Advance until sealed or until a human, block, or failure boundary is reached."""
        record = self._require_record(request_id)
        while True:
            if record.state in {
                ActionState.PENDING_APPROVAL,
                ActionState.BLOCKED,
                ActionState.FAILED,
                ActionState.SEALED,
            }:
                return record
            if record.state == ActionState.APPROVED:
                record = self.execute(request_id)
            elif record.state == ActionState.EXECUTED:
                record = self.verify(request_id)
            elif record.state == ActionState.VERIFIED:
                record = self.reconcile(request_id)
            elif record.state == ActionState.RECONCILED:
                record = self.resolve(request_id)
            elif record.state == ActionState.RESOLVED:
                record = self.seal(request_id)
            else:
                raise GovernanceConflict(f"Cannot continue request from state '{record.state.value}'.")

    def run(self, request: ActionRequest) -> ActionRecord:
        record = self.intake(request)
        return self.continue_request(record.request_id)

    def _require_record(self, request_id: str) -> ActionRecord:
        record = self.store.get_record(request_id)
        if record is None:
            raise GovernanceNotFound(f"Governance request '{request_id}' was not found.")
        return record

    @staticmethod
    def _transition(record: ActionRecord, state: ActionState, actor_id: str, reason: str) -> None:
        record.state = state
        record.history.append(StateEvent(state=state, actor_id=actor_id, reason=reason))

    @staticmethod
    def _ledger_is_balanced(entries: Iterable[dict]) -> bool:
        debit = Decimal("0")
        credit = Decimal("0")
        try:
            for entry in entries:
                debit += Decimal(str(entry.get("debit", 0)))
                credit += Decimal(str(entry.get("credit", 0)))
        except (InvalidOperation, TypeError, ValueError):
            return False
        return debit == credit

    @staticmethod
    def _execute_echo(request: ActionRequest) -> ExecutionResult:
        output = {
            "echo": request.parameters.get("message"),
            "target": request.target,
            "universe": request.actor.universe,
        }
        return ExecutionResult(
            status="success",
            executor_name="builtin.demo.echo",
            output=output,
            evidence={"output_digest": digest(output), "claim": "Echo executed inside registered adapter."},
        )

    @staticmethod
    def _execute_attestation(request: ActionRequest) -> ExecutionResult:
        claim = request.parameters.get("claim")
        artifact_digest = request.parameters.get("artifact_digest")
        output = {"claim": claim, "artifact_digest": artifact_digest, "attested": bool(claim and artifact_digest)}
        return ExecutionResult(
            status="success" if output["attested"] else "failed",
            executor_name="builtin.evidence.attest",
            output=output,
            evidence={"output_digest": digest(output), "source": "caller-supplied-artifact-digest"},
        )
