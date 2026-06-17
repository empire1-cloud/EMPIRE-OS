def check_rules(modules):
    """
    MVP rule system:
    just detects obvious architectural violations
    """

    violations = []

    for m in modules:
        summary = str(m.get("summary", "")).lower()

        if "payment" in summary and "empirepayments" not in summary:
            violations.append({
                "module": m["file"],
                "issue": "Payment logic not routed through EmpirePayments"
            })

    return {
        "violation_count": len(violations),
        "violations": violations,
        "status": "ok" if len(violations) == 0 else "warning"
    }
