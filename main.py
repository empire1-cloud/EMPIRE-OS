from fastapi import FastAPI

from empire_os.governance.api import router as governance_router

app = FastAPI(
    title="Empire OS",
    version="21.0.0",
    description="Governed autonomous execution with verifiable receipts.",
)
app.include_router(governance_router)

# Preserve the original early API surface when its optional modules are present.
try:
    from router import api_router as legacy_api_router
except (ImportError, ModuleNotFoundError):
    legacy_api_router = None

if legacy_api_router is not None:
    app.include_router(legacy_api_router, prefix="/legacy")


@app.get("/")
def health():
    return {
        "status": "Empire OS online",
        "phase": 21,
        "governance": "/v1/governance/health",
        "docs": "/docs",
    }
