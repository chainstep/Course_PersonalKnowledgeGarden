from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .models import Item


def render_digest(items: list[Item], hours: int = 24, generated_at: datetime | None = None) -> str:
    generated = generated_at or datetime.now(UTC)
    generated_text = generated.astimezone(UTC).isoformat().replace("+00:00", "Z")
    start = (generated - timedelta(hours=hours)).astimezone(UTC).isoformat().replace("+00:00", "Z")
    lines = [
        "# Knowledge Garden Digest",
        "",
        f"Generated: {generated_text}",
        f"Range: {start} to {generated_text}",
        "",
        f"Items: {len(items)}",
    ]
    if not items:
        lines.extend(["", "[no items added]"])
        return "\n".join(lines) + "\n"
    types = Counter(item.type for item in items)
    tags = Counter(tag for item in items for tag in item.tags)
    lines.extend(["", "## By type"])
    lines.extend(f"- {key}: {types[key]}" for key in sorted(types))
    lines.extend(["", "## By tag"])
    lines.extend(f"- {key}: {tags[key]}" for key in sorted(tags) if key)
    lines.extend(["", "## Items"])
    for item in items:
        lines.append(f"- `{item.id}` — {item.source_path} ({item.type}, {item.chunk_count} chunks)")
    return "\n".join(lines) + "\n"


def write_digest(items: list[Item], hours: int, output: str | None = None) -> str:
    text = render_digest(items, hours)
    if output:
        Path(output).expanduser().write_text(text, encoding="utf-8")
    return text
