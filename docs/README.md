# Personal Knowledge Garden — Documentation

This directory contains the full design, architecture, implementation, and user
documentation for the Local Personal Knowledge Garden.

## Read this first

1. **[User guide](user-guide.md)** — install, configure, ingest, search, digest,
   MCP server, agents, troubleshooting. Start here.
2. **[Design](design.md)** — what the system is, what it's *not*, the
   design principles, and the mapping from product requirements to
   implementation choices.
3. **[Architecture](architecture.md)** — modules, layers, data flow, transactions,
   error taxonomy, and a mental model of the system at runtime.
4. **[Implementation](implementation.md)** — concrete details: the SQLite
   schema, sanitizer pipeline, chunker, RRF math, MCP tool/resource surface,
   agent layer, and test strategy.

## Command-line reference and supporting docs

- **[cli.md](cli.md)** — every `kg` and `kg-mcp` command, every flag, exit codes.
- **[security.md](security.md)** — threat model and sanitizer contract.
- **[framework-decision.md](framework-decision.md)** — why PydanticAI
  (curator + quiz-master), and the migration path to LangGraph.
- **[scheduling.md](scheduling.md)** — cron and systemd user timer examples for
  the digest.

## Layout

```text
docs/
├── README.md              ← you are here (index)
├── user-guide.md          ← install + day-to-day usage
├── design.md              ← product vision, requirements, decisions
├── architecture.md        ← module map, data flow, concurrency
├── implementation.md      ← schema, algorithms, code-level details
├── cli.md                 ← command/flag reference
├── security.md            ← threat model + sanitizer contract
├── framework-decision.md  ← agent framework choice + migration path
└── scheduling.md          ← cron / systemd timer examples
```

All documents are written against the code in `src/knowledge_garden/` at the
same Git revision. If a command, flag, or exit code in these documents disagrees
with the CLI, the CLI (and the test `tests/test_exit_codes.py`) is the source
of truth.
