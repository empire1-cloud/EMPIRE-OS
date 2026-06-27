from pathlib import Path
from pydantic import BaseModel
import os


class Settings(BaseModel):
    name: str = os.getenv("EMPIRE_OS_NAME", "Empire OS")
    mode: str = os.getenv("EMPIRE_OS_MODE", "local")
    host: str = os.getenv("EMPIRE_OS_HOST", "0.0.0.0")
    port: int = int(os.getenv("EMPIRE_OS_PORT", "8787"))
    root: Path = Path(os.getenv("EMPIRE_ROOT", "./workspace"))
    memory_dir: Path = Path(os.getenv("EMPIRE_MEMORY_DIR", "./memory"))
    repo_registry: Path = Path(os.getenv("EMPIRE_REPO_REGISTRY", "./config/repos.json"))


settings = Settings()
