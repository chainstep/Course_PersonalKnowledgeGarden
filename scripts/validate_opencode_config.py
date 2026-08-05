from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    sys.exit("jsonschema is required to validate opencode.json")

CONFIG = Path(__file__).resolve().parents[1] / "opencode.json"
SCHEMA_URL = "https://opencode.ai/config.json"

config = json.loads(CONFIG.read_text())
try:
    jsonschema.validate(instance=config, schema={"$ref": SCHEMA_URL})
except jsonschema.ValidationError as exc:
    sys.exit(f"opencode.json validation failed: {exc.message}")
print("opencode.json ok")
