# Implementation

Code-level, function-by-function notes for anyone modifying the system.

For the *why*, read [design.md](design.md). For the runtime mental model,
read [architecture.md](architecture.md). For commands and flags, read
[cli.md](cli.md).

## 1. Technology stack

| Tool | Version (in `pyproject.toml`) | Role |
| --- | --- | --- |
| Python | `>=3.12` | runs on the CPython 3.12+ reference interpreter |
| `uv` | latest | dependency manager; `uv sync --all-groups` to install |
| `typer` | `>=0.12` | `kg` and `kg-mcp` CLI surface |
| `fastmcp` | `>=2.0` | FastMCP server (`streamable-http`) |
| `pydantic` | `>=2.7` | DTO models + validation |
| `pydantic-ai` | `>=0.0.14` | agent layer |
| `pymupdf` | `>=1.24` | PDF extraction |
| `sentence-transformers` | `>=3.0` | embedding backend (lazy-loaded) |
| `sqlite-vec` | `>=0.1.6` | bundled vector extension (dependency; brute-force cosine in-process today) |

The `.venv` is 5 GB; that disk footprint is dominated by PyTorch and CUDA
libraries pulled in by `sentence-transformers`. The disk cost is paid once
and is offline from runtime — the *runtime* imports are lazy and only fire
when `KG_EMBED_BACKEND` is `st`. The CI default is the hermetic `fake`
backend, so CI cost stays low.

## 2. Configuration

`config.py` exposes a frozen `Settings` dataclass constructed via
`Settings.from_env()`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `KG_DATA_DIR` | `~/.local/share/knowledge-garden` | root directory for `knowledge.db` and side-files |
| `KG_MCP_PORT` | `8765` | port `kg serve` binds to (loopback) |
| `KG_EMBED_BACKEND` | `st` | `st` = SentenceTransformers, `fake` = deterministic hash-based |
| `KG_EMBED_MODEL` | `BAAI/bge-small-en-v1.5` | only meaningful when `KG_EMBED_BACKEND=st` |
| `KG_EMBED_DIM` | `384` for `st`, `32` for `fake` | pinned dimension for reindex guard |
| `KG_AGENT_MODEL` | *unset* | required by `kg curate` and `kg quiz` |

`Settings.ensure_dirs()` creates the data directory at construction time
(which is why `replace(settings, mcp_port=…)` in tests must not lose the
`Path` object on `data_dir`).

## 3. Database schema

File: `src/knowledge_garden/storage/sql/001_initial.sql`.

```sql
CREATE TABLE meta       (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE items      (id TEXT PRIMARY KEY, source_path TEXT NOT NULL UNIQUE,
                         source_hash TEXT NOT NULL, type TEXT NOT NULL,
                         created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                         sanitizer_version TEXT NOT NULL);
CREATE TABLE item_tags  (item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
                         tag TEXT NOT NULL, PRIMARY KEY(item_id, tag));
CREATE TABLE chunks     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                         item_id TEXT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
                         ordinal INTEGER NOT NULL, safe_text TEXT NOT NULL,
                         raw_text TEXT NOT NULL,
                         page INTEGER, heading TEXT,
                         embedding_dim INTEGER NOT NULL,
                         embedding_model TEXT NOT NULL,
                         embedding_version TEXT NOT NULL,
                         UNIQUE(item_id, ordinal));
CREATE VIRTUAL TABLE chunks_fts
                         USING fts5(safe_text, content='chunks',
                                    content_rowid='id', tokenize='unicode61');
CREATE TABLE vec_chunks (chunk_id INTEGER PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE,
                         embedding BLOB NOT NULL);
```

Notes:

- `items.source_path` is `UNIQUE` so the idempotency contract keys off path.
  Same bytes under two different paths create two items — by design.
- `chunks.safe_text` and `chunks.raw_text` are both kept. The first is what
  the world sees; the second is the quarantine copy used to re-sanitize on
  reindex after a sanitizer upgrade.
- `chunks_fts` is **external content** over `chunks.safe_text`. Maintained
  by explicit `INSERT INTO chunks_fts(rowid, safe_text) ...` and
  `'delete'` commands inside the same transaction as the chunk write. No
  triggers.
- `vec_chunks.embedding` is a packed `float32` array (little-endian),
  produced by `struct.pack(f"{len(vector)}f", *vector)`. We compute cosine
  in-process — fine for personal-scale corpora; `sqlite-vec` ships as a
  dependency so a future change can switch to native ANN without rippling
  through the rest of the code.

### 3.1 Pragmas

Set on every `Database.connect()`:

- `journal_mode=WAL` — readers don't block the writer; writer doesn't
  block readers.
- `foreign_keys=ON` — child rows can't outlive their parents.
- `busy_timeout=5000` — `SQLITE_BUSY` becomes a wait rather than a hard
  error.

### 3.2 Migrations

`storage/migrations.py:migrate(connection)` executes every
`storage/sql/*.sql` file idempotently inside a single transaction during
`Database.connect()`. Failed migration aborts startup. The current
migration sets `meta.schema_version = '1'`. Future schema changes go into
numbered `.sql` files added to the same directory.

### 3.3 Add semantics

`Repository.upsert_item` runs `BEGIN IMMEDIATE` and does exactly one of:

| Existing path? | Same hash? | Action |
| --- | --- | --- |
| no | — | INSERT new item + chunks |
| yes | yes | no-op `COMMIT`; return `created=False` |
| yes | no | DELETE old chunks (FTS rows first), UPDATE the item, INSERT new chunks |

## 4. Sanitizer pipeline

`security/sanitizer.py` is the source of truth for the defensive boundary.

```text
input (file body / filename / tag / metadata)
 │
 │  normalize(value)               # NFC + strip control chars
 ▼
for each (pattern, reason) in _PATTERNS:
   pattern.subn("[UNTRUSTED OPERATIVE INSTRUCTION NEUTRALIZED]", text)
 │  pattern flags are re.IGNORECASE
 ▼
envelope(text, source)             # wraps safe text in BEGIN/END UNTRUSTED CONTENT
```

Patterns grouped by category:

- **Role overrides** — `ignore previous instructions`, `system prompt:`, `system message:`.
- **Tool/action requests** — `run `…`` / `execute …`, anything fenced in `\`\`\``.
- **Data exfiltration** — `reveal the system prompt`, `send … to <url>`.
- **Embedded system messages** — code fences tagged `json` or `system`.

Each match increments `neutralized_spans` and adds a `reason` to the
result. The same `sanitize()` function is called at ingest (input → safe
text) and at retrieval (stored safe text → envelope). Both code paths share
the same patterns, so a sanitizer upgrade flags both old and new content
with the same shape.

`security/trust.py` does companion normalization for filenames and tags
(Unicode NFC, lowercase, no whitespace, no control characters) so that
metadata can't smuggle instructions back via path or tag comparisons.

`envelope()` adds a stable, machine-recognizable wrapper:

```
===== BEGIN UNTRUSTED CONTENT (source=<path>, trust=untrusted, sanitizer=v1) =====
<safe text>
===== END UNTRUSTED CONTENT =====
```

This envelope is the agent-side sentinel: `AGENTS.md` instructs agents to
treat everything between `BEGIN UNTRUSTED CONTENT` and `END UNTRUSTED CONTENT`
as data, never as instructions.

## 5. Chunker

`ingestion/chunker.py` defines:

```python
MAX_TOKENS = 512
OVERLAP_TOKENS = 64
```

`chunk_parts(parts)` splits a list of `TextPart` (text + page + heading)
into paragraph-aware chunks:

1. Split text on blank lines into paragraphs.
2. Accumulate paragraphs until adding the next would exceed `MAX_TOKENS`.
3. When that happens, emit the current chunk, then keep the last
   `OVERLAP_TOKENS` words as a soft prefix in the next chunk.
4. If a single paragraph exceeds `MAX_TOKENS` on its own, it is still
   emitted (we do not silently truncate). The chunk is allowed to be
   slightly larger than the cap so we never lose content.

For PDFs, `TextPart` carries `page` (1-based) and `heading` (first short
title-like line, or `# …` heading for Markdown), which the chunk surfaces in
search hits and in `kg fetch`.

## 6. Search — RRF math

`search/service.py` performs hybrid retrieval. The actual combination is
two rank lists produced by:

- `Repository.keyword_search` — FTS5 `bm25()` over `chunks.safe_text`. Lower
  is better; we keep BM25 for diagnostics in the `keyword_score` field of
  `SearchHit`.
- `Repository.vector_search` — cosine similarity on packed `float32`
  embeddings, computed in Python.

Reciprocal rank fusion turns both into a single ordering:

```text
fused_score(item) = Σ_r  1 / (60 + rank_r(item))
```

with `rank_r(item)` being the 1-based position of `item` in ranking `r`.
Items present in only one ranking still contribute via the other ranking.
This is why mixing BM25 with cosine doesn't require scale matching — the
formula only uses ranks.

The constant `60` is the standard RRF default and is the only knob in
`search/ranking.py:reciprocal_rank_fusion()`. Tuning it is intentionally
left as a future exercise; the current value gives empirically good
results across small corpora.

## 7. Agent layer

`agents/config.py:model_name()` returns `os.environ["KG_AGENT_MODEL"]` or
raises `RuntimeError` — which the runner surfaces as exit code 3. There
is **no implicit default**; this is deliberate so `kg curate` never runs
on a model the operator hasn't chosen.

`agents/curator.py` and `agents/quiz_master.py` build prompts that comply
with `AGENTS.md`:

- They state the agent's identity (curator / quiz-master).
- They restate the untrusted-content rule inline so even a model that
  ignores the system prompt can be tested against the inline guard.
- They treat the request as data, not as override.

`agents/runner.py` is the thin shim that `kg curate`, `kg quiz`, and the
`curate`/`quiz` MCP tools all call. Tests exercise this shim through
PydanticAI's deterministic test model (`pydantic_ai.models.test.TestModel`).

`opencode.json` declares the two agent profiles:

- `agent.curator` — primary; `permission.edit=deny`, `permission.bash=deny`,
  `webfetch=deny`, `tool.knowledge_add=allow`, MCP `knowledge-garden=allow`,
  `external_directory` scoped to `~/.local/share/knowledge-garden/**`.
- `agent.quiz-master` — subagent; read-only MCP permissions, all mutating
  tools denied.

`mcp.knowledge-garden` is **`enabled: false`** — it only lights up after
the operator runs `kg serve`. The URL is `http://127.0.0.1:<port>/mcp`.

## 8. OpenCode custom tool

`.opencode/tools/knowledge_add.ts` exposes `kg-mcp add` as a typed tool to
OpenCode:

- Imports Zod from the plugin's own schema namespace (`tool.schema`) so
  the type matches the plugin's Zod v4 expectations.
- Spawns the CLI via `Bun.spawn(argv, { stdout, stderr })` — **never via
  shell** — so the `file` argument is passed verbatim and cannot be used
  for shell injection.
- Returns the CLI stdout / stderr with the right `ToolResult` shape
  (`{ title, output, metadata }`).

Two dev dependencies are pinned at runtime by the project:

- `typescript` — `npx tsc --noEmit` runs in CI to type-check the tool.
- `@types/bun` — gives the tool access to `Bun.spawn` and `Response` types
  without depending on the host runtime.

## 9. Tests

`tests/` (32 tests, 1 skip, runs in ~5 s on a cold laptop):

| File | Coverage |
| --- | --- |
| `test_sanitizer.py` | role override / tool call / exfiltration patterns; tag normalization; type dispatch; chunker boundary + overlap |
| `test_injection_regression.py` | generated malicious PDF fixture, ingest → assert raw text quarantined, safe/envelope everywhere, CLI leakage check |
| `test_acceptance.py` | idempotent upsert; replace on content change; hybrid RRF ranking; deterministic digest with fixed clock; embedding-model mismatch guard (two fake backends with different dims); opt-in real-model smoke test |
| `test_mcp_server.py` | tool/resource registration; live HTTP roundtrip via the SDK client; parity for `recent`, `search`, `reindex`, `version` |
| `test_no_direct_storage_import.py` | `kg-mcp` is forbidden from importing `storage.repository` directly |
| `test_pdf_errors.py` | encrypted PDFs rejected; image-only PDFs rejected; unsupported extensions; non-UTF-8 content |
| `test_exit_codes.py` | the exit-code contract via subprocess: 0 success / 2 usage / 3 typed domain / 1 unexpected; `--json --quiet` flags |
| `test_config.py` | env-var override; data-dir construction |

The hermetic-test rule from `PLAN.md §10` is enforced structurally:

- The test `settings` fixture defaults to `KG_EMBED_BACKEND=fake` (m32
  vectors).
- The real ST backend is gated behind the env var `KG_REAL_EMBED_TEST=1`.
  Without it, `pytest` does not load torch.

`tests/conftest.py` regenerates the malicious PDF fixture on first
session start via `pytest_configure`, so the fixture is reproducible from
the plugin alone — no manual step.

## 10. CI matrix

`PLAN.md §10` calls for a GitHub Actions matrix across Ubuntu + macOS
with caches for `uv`, `HF_HOME`, and `npm`. The current local validation
that is wired up today:

```sh
uv sync --all-groups
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
cd .opencode/tools
npm install
npx tsc --noEmit
cd ../..
uv run python scripts/validate_opencode_config.py   # schema validation
scripts/reindex.sh                                  # smoke-test the cron path
```

All of these pass at HEAD with the test default `KG_EMBED_BACKEND=fake`
and `KG_AGENT_MODEL` unset, so CI never reaches for the network.
