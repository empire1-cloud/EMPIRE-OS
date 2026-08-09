import json
import os
from pathlib import Path

import httpx


def _local_summary(path: str, code: str) -> dict:
    """Deterministic fallback so Empire OS still works without an LLM key."""
    lines = [line.strip() for line in code.splitlines() if line.strip()]
    imports = [line for line in lines if line.startswith(("import ", "from "))][:8]
    symbols = [
        line.split("(", 1)[0].replace("def ", "").replace("async ", "").strip()
        for line in lines
        if line.startswith(("def ", "async def "))
    ][:12]
    classes = [line.split("(", 1)[0].split(":", 1)[0].replace("class ", "").strip()
               for line in lines if line.startswith("class ")][:12]
    return {
        "purpose": f"Code module {Path(path).name}",
        "responsibilities": symbols + classes,
        "inputs": imports,
        "outputs": ["module behavior inferred locally"],
        "source": "local",
    }


def summarize_module(path: str, code: str):
    """Return a structured module summary; never make boot depend on an API key."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return _local_summary(path, code)

    prompt = (
        "You are a system architecture analyzer. Return strict JSON with keys: "
        "purpose, responsibilities, inputs, outputs.\n\n"
        f"FILE: {path}\nCODE:\n{code[:16000]}"
    )
    try:
        with httpx.Client(timeout=45.0) as client:
            response = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": os.getenv("EMPIRE_OS_MODEL", "gpt-4o-mini"),
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            text = response.json()["choices"][0]["message"]["content"]
            result = json.loads(text)
            result["source"] = "openai"
            return result
    except Exception as exc:
        fallback = _local_summary(path, code)
        fallback["llm_error"] = str(exc)[:240]
        return fallback
