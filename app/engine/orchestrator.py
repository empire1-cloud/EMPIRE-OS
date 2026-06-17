
from app.services.repo_parser import ingest_repo
from app.engine.drift_engine import run_drift_check
from app.engine.rule_engine import check_rules

def run_empire_cycle(repo_url: str):
    """
    THIS is the system brain loop.
    Everything flows through here.
    """

    # 1. STATE: ingest repo
    repo_data = ingest_repo(repo_url)
    modules = repo_data["modules"]

    # 2. DRIFT: compare modules
    drift = run_drift_check(modules)

    # 3. RULES: validate system constraints
    rules = check_rules(modules)

    # 4. FINAL OUTPUT (co-founder view)
    return {
        "repo": repo_data["repo"],
        "module_count": len(modules),
        "drift": drift,
        "rules": rules
    }
