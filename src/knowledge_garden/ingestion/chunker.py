from __future__ import annotations

import re
from dataclasses import dataclass

MAX_TOKENS = 512
OVERLAP_TOKENS = 64


@dataclass(frozen=True)
class TextPart:
    text: str
    page: int | None = None
    heading: str | None = None


def chunk_parts(parts: list[TextPart]) -> list[TextPart]:
    result: list[TextPart] = []
    for part in parts:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", part.text) if p.strip()]
        if not paragraphs:
            paragraphs = [part.text.strip()]
        current: list[str] = []
        count = 0
        for paragraph in paragraphs:
            words = paragraph.split()
            if current and count + len(words) > MAX_TOKENS:
                text = "\n\n".join(current)
                result.append(TextPart(text, part.page, part.heading))
                overlap = text.split()[-OVERLAP_TOKENS:]
                current = [" ".join(overlap)] if overlap else []
                count = len(overlap)
            current.append(paragraph)
            count += len(words)
        if current:
            result.append(TextPart("\n\n".join(current), part.page, part.heading))
    return result
