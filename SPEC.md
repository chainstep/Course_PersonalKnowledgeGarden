# Personal Knowledge Garden — Product Specification

## Overview
A self-hosted personal knowledge tool. Users ingest notes, PDFs, and code
snippets into a local store; search and retrieve them through an MCP server
that AI coding agents connect to; and run a small team of specialised agents on
top of the data.

## Core Features

### Ingestion
- Ingest notes, PDFs, and code snippets into a local store.
- Extract text from PDFs while preserving structure where possible.
- Generate embeddings for every item at ingest time.
- Assign metadata: id, timestamp, source path, type, tags.

### Storage
- SQLite (or equivalent local store) for metadata and full-text content.
- Vector index for embedding-based similarity search.
- Fully on-disk; no cloud dependency for the core data plane.

### CLI (`kg`)
- `kg add <file>` — ingest a file.
- `kg search <query>` — semantic + keyword search.
- `kg recent` — list items added recently.
- `kg reindex` — rebuild the vector index from the store.
- A second entry point that drives the store **through the MCP server**, not
  by bypassing it.

### MCP Server (FastMCP)
- At least 3 tools (e.g. `search`, `recent`, `fetch`).
- At least 1 resource (e.g. `notes://recent`).
- Streamable HTTP transport.

### Agent Layer
- At least 2 named agents declared in `opencode.json` with distinct
  permissions; one must be a subagent.
- Suggested roles: ingestor, curator, summariser, quiz-master.
- `AGENTS.md` with project rules, including an explicit `untrusted-content`
  boundary.
- At least one `SKILL.md` for a recurring flow (digest, quiz-me, …).
- At least one custom tool under `.opencode/tools/*.ts` wrapping an action
  the agent would otherwise perform via `bash`.

### Defensive Layer
- A wrapper that tags and strips injected instructions before any untrusted
  text reaches an agent.
- Applied at ingest time and again at retrieval time.
- Ingested PDF content is treated as untrusted input; no agent may follow
  instructions found inside it.
- A regression test, using a seeded prompt-injection sample, that proves the
  wrapper neutralises the known attack.

### Daily Digest
- Markdown summary of items saved in the last 24 hours.
- Available on demand and schedulable.

### Reindex Pipeline
- Script that rebuilds the vector index from the store.
- Suitable for cron and CI (e.g. GitHub Actions).

### Framework Documentation
- `docs/framework-decision.md` justifying the chosen framework (LangGraph,
  PydanticAI, CrewAI, or other) with one paragraph on the rationale and one
  on what to switch to next.

## Non-Functional Requirements
- Self-hosted; the data plane runs locally.
- A 5-minute demo flow (add → search → recent → digest → defence) completes
  without crashing.
- All content originating outside the user is treated as untrusted.
- Framework choice is documented with rationale and a migration path.
