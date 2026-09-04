from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Set

from .models import ActionRequest, PolicyDecision, RiskLevel


@dataclass(frozen=True)
class ActionRule:
    risk: RiskLevel
    approval_required: bool
    allowed_roles: Set[str]
    approver_role: str | None = None


ACTION_RULES: Dict[str, ActionRule] = {
    "demo.echo": ActionRule(RiskLevel.LOW, False, {"founder", "operator", "agent"}),
    "evidence.attest": ActionRule(RiskLevel.LOW, False, {"founder", "operator", "agent", "auditor"}),
    "repo.run_tests": ActionRule(RiskLevel.LOW, False, {"founder", "operator", "agent"}),
    "repo.create_branch": ActionRule(RiskLevel.MEDIUM, True, {"founder", "operator"}, "founder"),
    "repo.open_pr": ActionRule(RiskLevel.MEDIUM, True, {"founder", "operator"}, "founder"),
    "external.send_message": ActionRule(RiskLevel.MEDIUM, True, {"founder", "operator"}, "founder"),
    "data.export": ActionRule(RiskLevel.HIGH, True, {"founder", "operator"}, "founder"),
    "deploy.preview": ActionRule(RiskLevel.HIGH, True, {"founder", "operator"}, "founder"),
    "deploy.production": ActionRule(RiskLevel.CRITICAL, True, {"founder"}, "founder"),
    "finance.payment": ActionRule(RiskLevel.CRITICAL, True, {"founder"}, "founder"),
    "finance.payout": ActionRule(RiskLevel.CRITICAL, True, {"founder"}, "founder"),
}

HARD_BLOCKED_ACTIONS = {
    "repo.delete",
    "system.delete",
    "ledger.rewrite",
    "audit.erase",
    "receipt.delete",
    "secret.exfiltrate",
}

SENSITIVE_PARAMETER_KEYS = {
    "secret",
    "password",
    "private_key",
    "access_token",
    "api_key",
}


class PolicyEngine:
    """Deterministic authority and risk policy. No model decides permissions."""

    def evaluate(self, request: ActionRequest) -> PolicyDecision:
        action = request.action_type.strip().lower()
        role = request.actor.role.strip().lower()

        if action in HARD_BLOCKED_ACTIONS:
            return PolicyDecision(
                allowed=False,
                risk=RiskLevel.CRITICAL,
                approval_required=False,
                reasons=["Action is hard-blocked by the canonical no-destruction policy."],
                matched_rules=["hard_blocked_action"],
            )

        rule = ACTION_RULES.get(action)
        if rule is None:
            return PolicyDecision(
                allowed=False,
                risk=RiskLevel.HIGH,
                approval_required=False,
                reasons=["Action type is not registered in the deterministic policy catalog."],
                matched_rules=["unregistered_action"],
            )

        if role not in rule.allowed_roles:
            return PolicyDecision(
                allowed=False,
                risk=rule.risk,
                approval_required=False,
                reasons=[f"Role '{role}' is not authorized for '{action}'."],
                matched_rules=["role_scope_denied"],
            )

        if self._contains_sensitive_material(request.parameters):
            return PolicyDecision(
                allowed=False,
                risk=RiskLevel.CRITICAL,
                approval_required=False,
                reasons=["Raw secret material may not enter the governance request payload."],
                matched_rules=["secret_material_block"],
            )

        risk = self._raise_risk_for_impact(rule.risk, request.requested_impact)
        approval_required = rule.approval_required or risk in {RiskLevel.HIGH, RiskLevel.CRITICAL}
        approver_role = rule.approver_role or ("founder" if approval_required else None)

        return PolicyDecision(
            allowed=True,
            risk=risk,
            approval_required=approval_required,
            required_approver_role=approver_role,
            reasons=["Identity scope and action policy matched."],
            matched_rules=["registered_action", "role_scope_allowed"],
        )

    @staticmethod
    def _contains_sensitive_material(parameters: Dict[str, object]) -> bool:
        def walk(value: object, path: Iterable[str] = ()) -> bool:
            if isinstance(value, dict):
                for key, nested in value.items():
                    normalized = str(key).lower().strip()
                    if normalized in SENSITIVE_PARAMETER_KEYS:
                        return True
                    if walk(nested, (*path, normalized)):
                        return True
            elif isinstance(value, list):
                return any(walk(item, path) for item in value)
            return False

        return walk(parameters)

    @staticmethod
    def _raise_risk_for_impact(base: RiskLevel, impact: str | None) -> RiskLevel:
        if not impact:
            return base
        normalized = impact.lower()
        if any(term in normalized for term in ("production", "customer money", "irreversible", "legal")):
            return RiskLevel.CRITICAL
        if any(term in normalized for term in ("external", "customer", "sensitive data")):
            return max(base, RiskLevel.HIGH, key=lambda item: list(RiskLevel).index(item))
        return base
