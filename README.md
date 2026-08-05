# Personal Knowledge Garden

A self-hosted knowledge store for notes, PDFs, and code. The data plane is local SQLite with FTS5 and a vector index; content is sanitized at ingestion and retrieval before agents can see it.

## Install

```sh
uv sync --all-groups
```

For an offline demo use `KG_EMBED_BACKEND=fake`. The default SentenceTransformer backend uses `BAAI/bge-small-en-v1.5` from the local Hugging Face cache.

## Five-minute demo

```sh
export KG_DATA_DIR=/tmp/kg-demo
export KG_EMBED_BACKEND=fake
kg add notes/example.md --tag demo
kg search example
kg recent
kg digest
kg reindex
kg serve
```

Start `kg serve` before using `kg-mcp`; it is bound to `127.0.0.1` by default.

## Security

All external text is untrusted data. Raw text remains quarantined in SQLite and is never part of public DTOs. Retrieved text carries an explicit envelope and operative instructions are neutralized. The MCP server is loopback-only and has no authentication because it must not be rebound to a network interface.

## Documentation

| Document | Purpose |
| --- | --- |
| [`docs/README.md`](docs/README.md) | Index of all documentation |
| [`docs/user-guide.md`](docs/user-guide.md) | Install, configure, use day-to-day, troubleshooting |
| [`docs/design.md`](docs/design.md) | Product vision, design principles, requirements mapping |
| [`docs/architecture.md`](docs/architecture.md) | Module map, data flow, concurrency, MCP boundary |
| [`docs/implementation.md`](docs/implementation.md) | Schema, sanitizer, chunker, RRF, agent layer, tests, CI |
| [`docs/cli.md`](docs/cli.md) | Every `kg` and `kg-mcp` command and flag |
| [`docs/security.md`](docs/security.md) | Threat model + sanitizer contract |
| [`docs/framework-decision.md`](docs/framework-decision.md) | PydanticAI rationale, LangGraph migration path |
| [`docs/scheduling.md`](docs/scheduling.md) | Cron and systemd timer examples |

Start with the user guide if you're using the product; start with design /
architecture / implementation if you're modifying it.
