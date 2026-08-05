from __future__ import annotations

from pathlib import Path

from ..models import DecodeError, UnsupportedTypeError
from .chunker import TextPart

CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".go",
    ".rs",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".rb",
    ".php",
    ".sh",
    ".sql",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".css",
    ".html",
    ".xml",
}


def detect_type(path: Path, data: bytes) -> str:
    if data.startswith(b"%PDF") or path.suffix.lower() == ".pdf":
        return "pdf"
    if path.suffix.lower() in {".md", ".markdown"}:
        return "markdown"
    if path.suffix.lower() in {".txt", ".text"}:
        return "text"
    if path.suffix.lower() in CODE_EXTENSIONS:
        return "code"
    raise UnsupportedTypeError(f"unsupported file type: {path.suffix or 'no extension'}")


def extract_text(path: Path, data: bytes, kind: str) -> list[TextPart]:
    if kind == "pdf":
        from .pdf import extract_pdf

        return extract_pdf(data)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DecodeError(f"{path} is not valid UTF-8") from exc
    heading = None
    if kind == "markdown":
        for line in text.splitlines():
            if line.startswith("#"):
                heading = line.lstrip("# ").strip()
                break
    return [TextPart(text, heading=heading)]
