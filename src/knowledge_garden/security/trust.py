from __future__ import annotations

import re
import unicodedata


def normalize_tag(tag: str) -> str:
    value = unicodedata.normalize("NFC", tag).strip().lower()
    value = re.sub(r"\s+", "-", value)
    return re.sub(r"[^\w-]", "", value, flags=re.UNICODE)


def normalize_tags(tags: list[str] | tuple[str, ...]) -> list[str]:
    return list(dict.fromkeys(filter(None, (normalize_tag(tag) for tag in tags))))


def safe_filename(path: str) -> str:
    return unicodedata.normalize("NFC", path).replace("\x00", "").replace("\n", " ")
