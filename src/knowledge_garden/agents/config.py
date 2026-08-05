from __future__ import annotations

import os


def model_name() -> str:
    value = os.environ.get("KG_AGENT_MODEL")
    if not value:
        raise RuntimeError(
            "KG_AGENT_MODEL is unset; configure a PydanticAI model before using agents"
        )
    return value
