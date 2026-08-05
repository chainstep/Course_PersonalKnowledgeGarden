from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

VERSION = "v1"
_PATTERNS = (
    (re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions?", re.IGNORECASE), "role override"),
    (re.compile(r"(?:system\s+prompt|system\s+message)\s*:", re.IGNORECASE), "role override"),
    (
        re.compile(r"(?:reveal|show|print| disclose)\s+(?:the\s+)?system\s+prompt", re.IGNORECASE),
        "data exfiltration",
    ),
    (re.compile(r"\b(?:run|execute)\s+[`\"']?[^\n]{1,160}", re.IGNORECASE), "tool action"),
    (
        re.compile(r"send\s+(?:this|it|the\s+data)\s+to\s+[^\n]{1,120}", re.IGNORECASE),
        "data exfiltration",
    ),
    (re.compile(r"```(?:json|system)[\s\S]*?```", re.IGNORECASE), "embedded system message"),
)


@dataclass(frozen=True)
class Sanitized:
    text: str
    neutralized_spans: int
    reasons: tuple[str, ...]


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    return "".join(
        ch for ch in value if ch in "\n\t" or not unicodedata.category(ch).startswith("C")
    )


def sanitize(text: str) -> Sanitized:
    result = normalize(text)
    count = 0
    reasons: list[str] = []
    for pattern, reason in _PATTERNS:
        result, replacements = pattern.subn("[UNTRUSTED OPERATIVE INSTRUCTION NEUTRALIZED]", result)
        if replacements:
            count += replacements
            reasons.extend([reason] * replacements)
    return Sanitized(result, count, tuple(reasons))


def envelope(text: str, source: str = "unknown") -> str:
    safe_source = normalize(source).replace("\n", " ")
    safe = sanitize(text).text
    return f"===== BEGIN UNTRUSTED CONTENT (source={safe_source}, trust=untrusted, sanitizer={VERSION}) =====\n{safe}\n===== END UNTRUSTED CONTENT ====="
