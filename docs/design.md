# Design

This document describes **what** the Personal Knowledge Garden is, **why** it
is shaped the way it is, and how the product requirements in `../SPEC.md`
become design decisions in the code.

For *how* the code achieves these decisions, read
[Architecture](architecture.md) and [Implementation](implementation.md). For
day-to-day usage, read the [User guide](user-guide.md).

## 1. Product vision

A self-hosted, local-first knowledge store for notes, PDFs, and code. Users
ingest content into a single on-disk SQLite database, search it semantically
and by keyword, retrieve it safely through a loopback MCP server, and run a
small team of specialised agents on top.

The product is local on three axes:

- **Local data plane** — SQLite + FTS5 + a vector table in `~/.local/share/knowledge-garden/`
  by default. No cloud, no remote calls.
- **Local compute plane** — embeddings run on this machine; the default model
  (`BAAI/bge-small-en-v1.5`) is downloaded once and cached.
- **Local network** — MCP binds to `127.0.0.1` only; no LAN/internet exposure.

The product is safe on one axis above all others:

- **The defensive boundary** — every byte of external content (file body,
  filename, tag, metadata) is untrusted data. Sanitization runs at ingest
  *and* at retrieval. `AGENTS.md` and the untrusted-content envelope are
  contractual guarantees, not just code.

## 2. Confirmed decisions (from `PLAN.md`)

| Concern | Decision |
| --- | --- |
| Language / tooling | Python 3.12, `uv`, `typer`, `fastmcp`, `pydantic`, `pydantic-ai` |
| Storage | SQLite + FTS5 + a packed-float vector table (`sqlite-vec` is the dep, brute-force cosine in-process at personal scale) |
| Embeddings | `BAAI/bge-small-en-v1.5` (SentenceTransformers) + deterministic `fake` backend for tests & offline demos |
| PDF | PyMuPDF; encrypted PDFs rejected; image-only PDFs rejected ("OCR not supported") |
| MCP transport | Streamable HTTP on `127.0.0.1` |
| Digest | Deterministic local Markdown (no LLM required) |
| Agents | Two named agents — `curator` (primary), `quiz-master` (subagent) — via PydanticAI, model configured by `KG_AGENT_MODEL`, tests use PydanticAI's deterministic test model |
| CLI | Two entry points: `kg` (direct) and `kg-mcp` (MCP-over-HTTP client); each command on `kg` has a `--json` form |
| Add semantics | Idempotent upsert: same path + same SHA-256 = no-op; same path + different hash = atomic replacement of chunks/FTS/vectors; new path = insert |

## 3. Design principles

These are the rules that were used to choose between competing approaches
during planning.

### 3.1 Local-first by default

There is exactly one runtime data dependency: the filesystem. SQLite, FTS5,
and the vector storage live in a single directory. Operators can `tar` the
data directory, move it to a new machine, and have the same product working.

### 3.2 Defensive boundary is a contract, not a feature

The sanitizer is the primary defense against prompt-injection via ingested
content. Two non-negotiable rules:

1. **Every byte that is not produced by the user typing into the system**
   passes through `security/sanitizer.py` *twice*: once at ingest into
   `chunks.safe_text` (and into `chunks.raw_text` for quarantine and
   re-sanitization), and once at retrieval when an excerpt or full body is
   returned to a caller. The neutralized marker is a stable string:
   `[UNTRUSTED OPERATIVE INSTRUCTION NEUTRALIZED]`.
2. **Raw text never appears in any DTO, CLI output, resource, MCP result,
   agent prompt, or skill output.** It exists only as quarantined bytes in
   the SQLite schema. The agent boundary is enforced by `AGENTS.md` and the
   explicit `===== BEGIN UNTRUSTED CONTENT ===== … ===== END UNTRUSTED CONTENT =====`
   envelope.

### 3.3 Idempotency everywhere an external event repeats

Both CLI and `kg-mcp` are tolerant of repeated ingestion of the same file
(yielding the same item id), of reindex being run on an unchanged store,
and of `kg-mcp` / `kg` writes to the same database from multiple processes
(serialised by `BEGIN IMMEDIATE` + `busy_timeout`).

### 3.4 Typed error model

Every error that an operator or a script needs to recognise has a Python
type (`UnsupportedTypeError`, `EncryptedPDFError`, `OCRNotSupportedError`,
`EmbeddingModelMismatchError`, `DecodeError`) and an exit code
(`3` per the CLI contract; see [cli.md](cli.md)). Unexpected errors stay at
exit code `1` and surface as tracebacks.

### 3.5 Everything goes through MCP for the second entry point

`kg-mcp` is forbidden from importing `storage.repository` directly (enforced by
a guard test). All data movement after the first command goes through the MCP
server, even when the server is running on the same host. This keeps the
service boundary honest and makes parity testing meaningful.

### 3.6 Storage, retrieval, security, and MCP stay framework-independent

The agent layer is the only place where PydanticAI is used. Storage, search,
sanitization, ingestion, and the MCP server are framework-free Python so
that they remain testable, swappable, and migratable. The framework-decision
record at [framework-decision.md](framework-decision.md) makes this explicit:
a move to LangGraph is a local change to the agent runner.

## 4. Requirements → design mapping

This is the traceability from `../SPEC.md` to design surfaces.

| SPEC requirement | Design surface |
| --- | --- |
| Ingest notes, PDFs, code; structure-preserving PDF extraction | §3 sanitizer (filename-agnostic); `ingestion/` dispatch |
| Generate embeddings at ingest | `IngestionService.add()` calls the embedding backend once per chunk before write |
| Local SQLite + vector store, no cloud | `storage/database.py`, `KG_DATA_DIR` config |
| `kg add/search/recent/reindex` | `cli.py` (`app`) |
| Second entry point goes through MCP | `mcp_cli.py`; guard test forbids direct repository import |
| ≥3 MCP tools, ≥1 resource, streamable HTTP | MCP server exposes 9 tools + `notes://recent` resource |
| ≥2 named agents with distinct permissions, one subagent | `opencode.json`: `curator` (primary) + `quiz-master` (subagent with read-only MCP) |
| `AGENTS.md` with `untrusted-content` boundary | `../AGENTS.md` |
| ≥1 skill, ≥1 custom `.opencode/tools/*.ts` tool | `.opencode/skills/quiz-me/SKILL.md`, `.opencode/tools/knowledge_add.ts` |
| Defensive wrapper at ingest & retrieval | `security/sanitizer.sanitize()` at write & read time |
| Regression test against seeded prompt injection | `tests/test_injection_regression.py` + auto-generated malicious PDF fixture |
| Deterministic daily digest | `digest.py`, fixed-clock test in `tests/test_acceptance.py` |
| `scripts/reindex.sh` for cron/CI | `scripts/reindex.sh` calls `kg reindex --json --quiet` (exit 3 on model mismatch) |
| Framework decision documented | [framework-decision.md](framework-decision.md) |
| 5-minute demo, no crash, no LLM | The demo uses `KG_EMBED_BACKEND=fake` and exercises no MCP host networking; covered by `tests/test_acceptance.py` and `tests/test_exit_codes.py` |
| All external content untrusted | Quarantine column in schema + envelope at every boundary |

## 5. Out of scope (first release)

Decided in `PLAN.md §15` and intentionally deferred:

- OCR for scanned / image-only PDFs (a typed "OCR not supported" error is
  raised instead).
- URL ingestion, recursive directory ingestion, stdin ingestion.
- Item deletion (`kg remove`) and file-watching / auto-ingest.
- Cloud embeddings.
- LAN / internet exposure of the MCP server.
- Windows support.
- An in-repo scheduler daemon (a shell script is shipped; cron / systemd
  timers are configured by the operator).

These are not abandoned — they are sequenced after the data plane, the
defensive boundary, and the MCP contract are stable.
