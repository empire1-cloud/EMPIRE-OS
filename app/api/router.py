from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

from app.engine.orchestrator import run_empire_cycle

api_router = APIRouter(prefix="/api")


class RepoIngestRequest(BaseModel):
    repo_url: HttpUrl


@api_router.get("/health")
def api_health():
    return {
        "status": "ok",
        "service": "Empire OS Cofounder",
        "time": datetime.now(timezone.utc).isoformat(),
    }


@api_router.get("/status")
def status():
    return {
        "status": "operational",
        "mode": "cofounder-control-plane",
        "capabilities": [
            "repo_ingest",
            "module_analysis",
            "drift_detection",
            "rule_checks",
        ],
        "execution": "analysis-first",
    }


@api_router.post("/ingest/repo")
def ingest_repo(payload: RepoIngestRequest):
    try:
        result = run_empire_cycle(str(payload.repo_url))
        return {"status": "processed", "result": result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Repository analysis failed: {str(exc)[:240]}") from exc
