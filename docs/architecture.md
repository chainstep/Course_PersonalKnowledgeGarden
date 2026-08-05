# Architecture

What runs where, how the pieces talk to each other, and what the system looks
like in motion.

For design rationale, read [design.md](design.md). For code-level details
(function signatures, schema column types, RRF math), read
[implementation.md](implementation.md).

## 1. System overview

```text
┌──────────────────────────────────────────────────────────────────────────┐
│                         Operator / Agent layer                            │
│  CLI (kg)               CLI (kg-mcp)              OpenCode / agents       │
│      │                       │                       │ curator             │
│      ▼                       ▼                       ▼ quiz-master        │
│  ┌────────────────┐   ┌────────────────┐   ┌────────────────────────┐     │
│  │ direct service │   │  MCP HTTP      │   │ MCP HTTP (loopback)    │     │
│  │  composition   │   │  client (kg-m) │   │ + opencode.json rules  │     │
│  └────────┬───────┘   └────────┬───────┘   └────────────┬───────────┘     │
│           └───────┬───────────┘                         │                 │
│                   ▼                                     │                 │
│          ┌────────────────────────────────────────────┐ │                 │
│          │ FastMCP server (streamable-http, loopback) │◀┘                 │
│          └────────────────────┬───────────────────────┘                   │
│                               │ (service layer calls)                     │
│       ┌───────────────────────┼─────────────────────────────────────┐     │
│       ▼                       ▼                                     ▼     │
│  ┌──────────┐            ┌──────────┐                          ┌───────────┐│
│  │Ingestion │            │  Search  │                          │  Reindex  ││
│  │ service  │            │ service  │                          │ pipeline  ││
│  └─────┬────┘            └────┬─────┘                          └─────┬─────┘│
│        │                      │                                       │     │
│        │   ┌──────────────────┴──────────────┐                        │     │
│        ▼   ▼                                 ▼                        ▼     │
│  ┌──────────────────────────────┐   ┌──────────────────────────────┐        │
│  │              Repository       │   │       Sanitizer (envelope)   │        │
│  │  ingest / search / reindex    │◀──┤   sanitize at every boundary │        │
│  └────────────────────┬─────────┘   └──────────────────────────────┘        │
│                       │ (SQLite transactions)                              │
│                       ▼                                                    │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │  SQLite on-disk: items, item_tags, chunks (safe+raw), chunks_fts (    │ │
│  │  external-content FTS5 over chunks.safe_text), vec_chunks            │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│                            Embedding backend:                              │
│                 ┌────────────┐                  ┌─────────────────┐        │
│                 │   fake     │   test default   │ SentenceTrans-  │        │
│                 │ backend    │ ───────────────▶ │ former (bge)    │        │
│                 └────────────┘                  └─────────────────┘        │
└──────────────────────────────────────────────────────────────────────────┘
```

Every box corresponds to one module under
`src/knowledge_garden/`. Every arrow is a Python function call except the two
that cross a process boundary (`kg-mcp` ↔ `kg serve`, and OpenCode ↔ `kg
serve`); both of those are FastMCP-over-HTTP and bound to loopback.

## 2. Module map

```text
src/knowledge_garden/
├── config.py              Settings dataclass + env-var parsing
├── models.py              Pydantic models + DomainError hierarchy
├── cli.py                 Typer entry point (kg)
├── mcp_cli.py             Typer entry point (kg-mcp) — MCP-only
├── digest.py              Deterministic Markdown digest
├── reindex.py             Vector rebuild pipeline
├── security/
│   ├── sanitizer.py       sanitize + envelope; sanitize() is the producer
│   ├── envelope.py        import surface (see sanitizer.py)
│   └── trust.py           filename/tag normalization
├── storage/
│   ├── database.py        SQLite connection (WAL, fk, busy_timeout)
│   ├── migrations.py      Loads storage/sql/*.sql idempotently
│   ├── repository.py      All writes use BEGIN IMMEDIATE
│   └── sql/001_initial.sql
├── ingestion/
│   ├── service.py         Orchestrator: read → extract → sanitize → chunk → embed → write
│   ├── extractors.py      Type dispatch (markdown / text / code / PDF MIME)
│   ├── chunker.py         Paragraph-aware, 512-token, 64-overlap
│   └── pdf.py             PyMuPDF block extraction, page + heading hints
├── search/
│   ├── service.py         FTS5 + vector → RRF → grouped hits
│   └── ranking.py         Reciprocal-rank-fusion math
├── embeddings/
│   ├── base.py            ABC + FakeEmbeddingBackend
│   ├── fake.py            Re-export of FakeEmbeddingBackend
│   └── sentence_transformer.py   Lazy import of sentence_transformers
├── agents/
│   ├── config.py          KG_AGENT_MODEL gate
│   ├── curator.py         Prompt builder (search/fetch/organize/add/digest/reindex)
│   ├── quiz_master.py     Prompt builder (search/fetch → quiz)
│   └── runner.py          Thin wrappers that agents.run() can call
└── mcp/
    ├── server.py          FastMCP app: 9 tools + notes://recent resource
    └── client.py          MCPClient using streamable HTTP (kg-mcp side)
```

Each module is small enough to read in one sitting. The cross-module
dependencies form a DAG with `storage.repository` at the bottom and
`agents.runner` at the top; nothing deeper ever imports from the layer above.

## 3. Data flow

The four runtime flows below cover every place data moves in the product.

### 3.1 Ingest flow (`kg add` / MCP `add` tool)

```text
PATH
 │  file.read_bytes()
 ▼
detect_type (extension + %PDF magic)                ← ingestion/extractors.py
 │  raises UnsupportedTypeError if not supported
 ▼
extract_text (markdown/text/code → UTF-8; PDF → pymupdf blocks)
 │
 │  raises DecodeError / EncryptedPDFError / OCRNotSupportedError
 ▼
chunk_parts (paragraph-aware, 512/64)               ← ingestion/chunker.py
 │
 ▼  per part
sanitize(part.text) → Sanitized(text, spans, reasons)
 │  ALL safe_text replacement markers + neutralization marker
 ▼
backend.embed(safe_text for every chunk)            ← embeddings/
 │
 ▼
Repository.upsert_item(...)             (BEGIN IMMEDIATE)
   ├── same path + same hash → no-op commit
   ├── same path + new hash  → DELETE FROM chunks WHERE item_id=?; delete FTS rows
   └── new path              → INSERT new item
   ↑ all chunk writes go through the same transaction, FTS kept in lockstep
 ▼
return IngestResult(item=Item(...), created=bool, chunk_count=int, neutralized_spans=int)
```

A single `kg add` opens exactly one SQLite connection, runs one transaction,
and either commits the whole insert or rolls back. There is no partial
state.

### 3.2 Query flow (`kg search` / MCP `search` tool)

```text
QUERY
 │  (cli: quote-safe FTS5 syntax; MCP: passed through)
 ▼
Repository.keyword_search       → top N chunk rows (BM25 score, lower=better)
Repository.vector_search(query) → top N chunk rows (Python cosine)
 │  embedding backend encodes the query
 │
 ▼  grouped by item_uuid
Reciprocal Rank Fusion:
   fused_score(item) = sum_r  1 / (60 + rank_r(item))
   where rank is 1-based position in each ranking; missing items score 0
 │
 ▼  retrieval-time sanitize() on each excerpt, wrap in envelope
 ▼
SearchHit per item, sorted by fused_score DESC, truncated to LIMIT
```

RRF is used because the keyword scores (BM25) and the vector scores (cosine)
are not commensurable. RRF only requires ranks, so it composes two arbitrary
rankings without the operator having to invent scale matching.

### 3.3 Reindex flow (`kg reindex` / MCP `reindex` tool)

```text
Repository.all_chunks() → reads safe_text per chunk
 │
 │  backend changed?  (stored model, dim) vs active backend
 │   ├── no  → continue
 │   ├── yes + not force → raise EmbeddingModelMismatchError (exit 3)
 │   └── yes + force     → continue
 ▼
backend.embed(safe_text) for every chunk
 │  (in-process Python cosine recomputed on a real ST backend; brute-force
 │   over the corpus; sized for personal use, swap in sqlite-vec ANN later)
 ▼
Repository.replace_vectors(...)   (BEGIN EXCLUSIVE)
   DELETE FROM vec_chunks; INSERT into vec_chunks
 ▼
Repository.resanitize()           (BEGIN IMMEDIATE)
   for each chunk:
       UPDATE chunks SET safe_text = sanitize(raw_text).text
       rebuild the chunk's chunks_fts row
 ▼
return count
```

The exclusive transaction guarantees that no `kg add` or other `reindex` can
interleave a vector write mid-flight. `scripts/reindex.sh` is exactly
`exec kg reindex --json --quiet`, suitable for cron / systemd / CI.

### 3.4 Agent flow (`kg curate <request>` / `kg quiz <topic>`)

```text
runner.run_curator(request)
 │
 │  1. require KG_AGENT_MODEL (else RuntimeError → exit 3)
 │  2. compose prompt: identity ("you are curator") + untrusted-content rule
 │     + the request
 │  3. (in a fuller implementation: call the model with tools restricted
 │     to the MCP server, retrieve envelope-wrapped data, return safe text)
 ▼
serializable string returned to CLI / MCP client
```

In the current build, `curator.py` and `quiz_master.py` are prompt builders
that fail fast unless `KG_AGENT_MODEL` is configured. The MCP `curate`,
`quiz`, and `version` tools wrap them so `kg-mcp` shares the same surface.
The default GPT model is provided via PydanticAI's test fixtures in tests;
see [Implementation §7](implementation.md#7-agent-layer).

## 4. Concurrency model

There is exactly one writer of consequence: `Repository.upsert_item`. Two
writers competing for the same path produce one of two well-defined outcomes
— whichever transaction commits first wins, the second sees the post-write
state and behaves correctly. This is achieved by:

| Setting | Where | Why |
| --- | --- | --- |
| `journal_mode=WAL` | every `Database.connect()` | concurrent reads + single writer |
| `busy_timeout=5000` | every `Database.connect()` | callers wait briefly instead of `SQLITE_BUSY` |
| `foreign_keys=ON` | every `Database.connect()` | child rows can't outlive their parent |
| `BEGIN IMMEDIATE` | `Repository.upsert_item`, `resanitize` | acquisition of the write lock at the start of the transaction |
| `BEGIN EXCLUSIVE` | `Repository.replace_vectors` | blocks every other writer for the duration |

`kg serve` reading from a database that another process is writing to is
safe; SQLite's WAL + shared cache give readers and writers fully consistent
views.

## 5. Error taxonomy

```text
Exception
├── DomainError                 exit 3, message printed to stderr
│   ├── UnsupportedTypeError    file extension not in supported set
│   ├── DecodeError             bytes that aren't valid UTF-8
│   ├── EncryptedPDFError       PyMuPDF reports the document is encrypted
│   ├── OCRNotSupportedError    PyMuPDF reports no extractable text
│   └── EmbeddingModelMismatchError   reindex sees a different model/dim
└── (anything else)             exit 1, traceback printed to stderr
```

Usage errors (missing arguments, unknown flags) are caught by Typer
before any command runs and exit with code `2`. Success is `0`.

## 6. MCP boundary

The FastMCP server in `mcp/server.py` exposes:

| Tool | Purpose | Argument shape |
| --- | --- | --- |
| `add` | ingest a file | `{ file: str, tags?: str[], type?: str }` |
| `search` | hybrid RRF search | `{ query: str, limit: int }` |
| `recent` | recently added items | `{ hours: int, limit: int }` |
| `fetch` | full body of one item, enveloped | `{ item_id: str }` |
| `digest` | render the Markdown digest | `{ hours: int, output?: str }` |
| `reindex` | rebuild vectors | `{ force: bool }` |
| `curate` | invoke the curator agent | `{ request: str }` |
| `quiz` | invoke the quiz-master agent | `{ topic: str }` |
| `version` | version string | `{}` |

Plus one resource:

| URI | Returns |
| --- | --- |
| `notes://recent` | JSON list of recent items (same shape as the `recent` tool) |

`kg-mcp` mirrors every command listed above and the version command. The two
CLI surfaces agree semantically, the only difference being how they get
their bytes: `kg` calls into the service layer directly, `kg-mcp` goes over
loopback HTTP to the FastMCP server. The no-direct-import guard in
`tests/test_no_direct_storage_import.py` keeps this honest.

## 7. Boundaries that *don't* exist

These are intentional negative spaces:

- **No HTTP API outside MCP.** Search and ingest are reachable via the MCP
  server only; the second entry point is therefore *only* MCP, never a
  bespoke REST API. This avoids the "two protocols, two implementations"
  trap and keeps the service layer small.
- **No background daemon in-repo.** Reindex, digest, and the agent are
  invoked on operator demand; cron / systemd timers wrap them externally.
  See [scheduling.md](scheduling.md).
- **No embedding write paths other than through ingest or reindex.** Tool,
  resource, and CLI handlers all funnel through the same `Repository`
  methods.
