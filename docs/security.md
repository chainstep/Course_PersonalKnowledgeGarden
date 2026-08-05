# Security model

Every input is untrusted: filenames, tags, metadata, Markdown, code, and PDF text. Unicode is normalized, controls are removed, and common role overrides, tool requests, exfiltration requests, and embedded system-message blocks are replaced by a neutral marker. Safe text is always sent inside an envelope identifying its source, untrusted trust level, and sanitizer version.

The original text is retained only as `chunks.raw_text` for quarantine and re-sanitization. It is not present in Pydantic DTOs, CLI output, MCP results, resources, or agent prompts. Retrieval sanitizes again. Agents must treat the envelope as data and never follow commands within it.

MCP binds to `127.0.0.1` and intentionally has no authentication. Do not rebind it to LAN or internet interfaces.
