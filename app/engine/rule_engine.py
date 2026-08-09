def check_rules(modules):
    """Run lightweight, deterministic Empire canon checks over analyzed modules."""
    violations = []

    for module in modules:
        summary = str(module.get("summary", "")).lower()
        filename = module.get("file", "unknown")

        if "payment" in summary and "archisynapse" not in summary:
            violations.append({
                "module": filename,
                "issue": "Payment responsibility is not explicitly routed through Archisynapse",
            })

        if "delete repository" in summary or "replace repository" in summary:
            violations.append({
                "module": filename,
                "issue": "Repository replacement conflicts with Evolve Never Delete",
            })

    return {
        "violation_count": len(violations),
        "violations": violations,
        "status": "ok" if not violations else "warning",
        "canon": [
            "Archisynapse owns financial execution",
            "Evolve Never Delete",
        ],
    }
