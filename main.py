from fastapi import FastAPI
from app.api.router import api_router

app = FastAPI(title="Empire OS")

app.include_router(api_router)

@app.get("/")
def health():
    return {"status": "Empire OS online"}
