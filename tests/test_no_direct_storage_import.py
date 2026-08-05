from __future__ import annotations

import importlib
import sys

PROTECTED = "knowledge_garden.storage.repository"


def _module_uses_protected(*names: str) -> list[str]:
    leaked = []
    for name in names:
        module = importlib.import_module(name)
        for attribute in dir(module):
            try:
                value = getattr(module, attribute)
            except AttributeError:
                continue
            if getattr(value, "__module__", None) == PROTECTED:
                leaked.append(f"{name}.{attribute}")
    return leaked


def test_kg_mcp_does_not_import_storage_repository_directly():
    for module in list(sys.modules):
        if module.startswith(("knowledge_garden.mcp_cli", "knowledge_garden.mcp.client")):
            sys.modules.pop(module, None)
    import knowledge_garden.mcp_cli  # noqa: F401

    leaked = _module_uses_protected("knowledge_garden.mcp_cli")
    assert leaked == []
