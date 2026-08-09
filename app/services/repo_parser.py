import os
import shutil
from pathlib import Path
from urllib.parse import urlparse

import git

from app.engine.change_engine import process_file

_ALLOWED_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".md")
_SKIP_DIRS = {".git", "node_modules", ".next", "dist", "build", ".venv", "venv", "__pycache__"}


def _validate_repo_url(repo_url: str) -> str:
    parsed = urlparse(repo_url)
    if parsed.scheme != "https" or parsed.hostname not in {"github.com", "www.github.com"}:
        raise ValueError("Empire OS currently accepts HTTPS GitHub repository URLs only")
    return repo_url.rstrip("/")


def ingest_repo(repo_url: str):
    repo_url = _validate_repo_url(repo_url)
    name = repo_url.split("/")[-1].replace(".git", "")
    path = Path("/tmp/empire-os") / name
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        try:
            repo = git.Repo(path)
            repo.remotes.origin.fetch()
            repo.git.reset("--hard", "origin/HEAD")
        except Exception:
            shutil.rmtree(path, ignore_errors=True)
            git.Repo.clone_from(repo_url, path, depth=1)
    else:
        git.Repo.clone_from(repo_url, path, depth=1)

    modules = []
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for filename in files:
            if not filename.endswith(_ALLOWED_SUFFIXES):
                continue
            full = Path(root) / filename
            try:
                modules.append(process_file(str(full)))
            except Exception as exc:
                modules.append({"file": str(full), "error": str(exc)[:240]})

    return {
        "repo": name,
        "repo_url": repo_url,
        "module_count": len(modules),
        "modules": modules,
    }
