from fastapi import APIRouter
from app.api.routes.ingest import router as ingest_router
from app.api.routes.report import router as report_router
from app.api.routes.drift import router as drift_router
from app.api.routes.decisions import router as decision_router

api_router = APIRouter()

api_router.include_router(ingest_router, prefix="/ingest")
api_router.include_router(report_router, prefix="/report")
api_router.include_router(drift_router, prefix="/drift")
api_router.include_router(decision_router, prefix="/decisions")
