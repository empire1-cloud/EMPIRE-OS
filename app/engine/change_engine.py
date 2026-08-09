from app.core.llm import summarize_module


def process_file(file_path: str):
    with open(file_path, "r", encoding="utf-8", errors="replace") as handle:
        code = handle.read()

    summary = summarize_module(file_path, code)
    return {
        "file": file_path,
        "summary": summary,
    }
