def run_drift_check(modules):
    """
    MVP drift detection:
    detects duplicates via simple similarity
    """

    duplicates = []

    for i in range(len(modules)):
        for j in range(i + 1, len(modules)):

            a = str(modules[i].get("summary"))
            b = str(modules[j].get("summary"))

            if a and b and a == b:
                duplicates.append({
                    "module_a": modules[i]["file"],
                    "module_b": modules[j]["file"]
                })

    return {
        "duplicate_count": len(duplicates),
        "duplicates": duplicates,
        "risk": "high" if len(duplicates) > 0 else "low"
    }
