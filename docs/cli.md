# Command-line reference

Two CLI surfaces share semantics:

- **`kg`** — talks to the service layer in-process.
- **`kg-mcp`** — talks to the running MCP server over loopback HTTP.

Both honour the same exit-code contract:

| Code | Meaning |
| --- | --- |
| `0` | success |
| `2` | usage error (unknown flag, missing argument) |
| `3` | typed domain error: unsupported file type, encrypted PDF, OCR required, embedding-model mismatch, `KG_AGENT_MODEL` unset, sanitizer invariant failure |
| `1` | unexpected error (a `typer`/`SQLite`/transport problem the caller should report) |

With `--json`, errors are emitted as a one-line JSON object on stderr where
the command's Python model allows; otherwise a single-line `error: …`
message is printed before exit.

`scripts/reindex.sh` and the README's demo flow depend on these codes.
Don't change them without updating `scripts/reindex.sh` and CI.

---

## `kg` (direct entry point)

```sh
kg [--help]
```

### `kg add FILE`

Ingest a single file. Idempotent on (path, hash): a repeated call with the
same content is a no-op and prints the existing item id.

| Flag | Description |
| --- | --- |
| `--tag TAG` (repeat) | attach tags; normalised (NFC, lowercase, no whitespace) |
| `--type TYPE` | force type (`pdf`, `markdown`, `text`, `code`) when extension is missing |
| `--json` | print a JSON object describing the ingest result |

Examples:

```sh
kg add README.md --tag docs --tag project
kg add notes/q3.md
kg add report.pdf
echo '{"msg":"hi"}' | pv > /tmp/msg.txt; kg add /tmp/msg.txt --type text   # force type
```

Output:

```
<item-uuid> chunks=<count> neutralized_spans=<count>
```

JSON form:

```json
{
  "created": true,
  "chunk_count": 4,
  "neutralized_spans": 0,
  "item": { "id": "…", "source_path": "…", "type": "markdown", … }
}
```

Exit codes: `0` success · `2` invalid args · `3` unsupported type /
non-UTF-8 / unknown `--type`.

### `kg search QUERY`

Hybrid RRF search over keyword + vector.

| Flag | Description |
| --- | --- |
| `--limit N` | number of items to return (default 20) |
| `--json` | print JSON list of `SearchHit` objects |

Examples:

```sh
kg search "knowledge garden"
kg search sqlite --limit 5 --json
```

Output (default mode): one block per item with the enveloped excerpt and
route metadata. Agents should never strip the envelope.

Exit codes: `0` always (zero hits is success). The FTS5 engine is quote-safe;
special characters in `QUERY` are accepted as-is and the CLI ignores them
gracefully (no match ⇒ empty result, not an error).

### `kg recent`

List items added in the last `N` hours.

| Flag | Description |
| --- | --- |
| `--hours N` | look-back window (default 24) |
| `--limit N` | max results (default 20) |
| `--json` | print JSON list of `Item` |

Exit codes: `0` always.

### `kg fetch ITEM_ID`

Return the full safe body of an item, **enveloped**.

| Flag | Description |
| --- | --- |
| `--json` | print `{"item": …, "chunks": …}` |

Exit codes: `0` success · `3` item not found (when JSON mode would
matter for tooling — the CLI prints `item not found` and exits `3`).

### `kg digest`

Render the daily Markdown digest.

| Flag | Description |
| --- | --- |
| `--hours N` | look-back window (default 24) |
| `--output PATH` | write to file in addition to stdout |

Output is deterministic: same items + same generated-at ⇒ byte-identical
output. Empty digest prints `[no items added]` and exits `0`.

### `kg reindex`

Rebuild vectors from stored safe text and re-run the sanitizer.

| Flag | Description |
| --- | --- |
| `--force` | allow embedding-model changes (unsafe if you don't know why) |
| `--json` | print JSON `{"vectors": N, "status": "ok"}` |
| `--quiet` | suppress output entirely (use in cron / CI) |

Exit codes: `0` success · `3` embedding-model mismatch (without `--force`).

`scripts/reindex.sh` wraps `kg reindex --json --quiet` for cron.

### `kg serve`

Start the FastMCP server (streamable HTTP) bound to loopback.

| Flag | Description |
| --- | --- |
| `--port PORT` | override `KG_MCP_PORT` (default `8765`) |

This is the only long-running command. Run it under your service manager
of choice; bind it to `127.0.0.1`, never to a network interface.

Exit codes: `0` on graceful shutdown; non-zero on bind failure / OOM.

### `kg curate REQUEST`

Invoke the curator agent.

Requires `KG_AGENT_MODEL` to be set. Otherwise exits `3` with
`KG_AGENT_MODEL is unset; configure a PydanticAI model before using agents`.

### `kg quiz TOPIC`

Invoke the quiz-master agent.

Same `KG_AGENT_MODEL` requirement as `kg curate`.

### `kg version`

Print the product version and exit `0`.

---

## `kg-mcp` (MCP-only entry point)

Every command mirrors a `kg` command and produces equivalent output.
The data plane is reached exclusively through the FastMCP server: the
direct-import guard in `tests/test_no_direct_storage_import.py` enforces
this on every CI run.

`kg-mcp` requires that `kg serve` is running on `KG_MCP_PORT` (default
`8765`). Connection refused / unknown tool = the server isn't running or
the tool name changed. The CLI surfaces this as a non-zero exit.

### `kg-mcp add FILE`

```sh
kg-mcp add FILE [--tag TAG]… [--type TYPE] [--json]
```

### `kg-mcp search QUERY`

```sh
kg-mcp search QUERY [--limit N] [--json]
```

### `kg-mcp recent`

```sh
kg-mcp recent [--hours N] [--limit N] [--json]
```

### `kg-mcp fetch ITEM_ID`

```sh
kg-mcp fetch ITEM_ID [--json]
```

### `kg-mcp digest`

```sh
kg-mcp digest [--hours N] [--output PATH]
```

### `kg-mcp reindex`

```sh
kg-mcp reindex [--force] [--json]
```

### `kg-mcp curate REQUEST`

```sh
kg-mcp curate REQUEST
```

### `kg-mcp quiz TOPIC`

```sh
kg-mcp quiz TOPIC
```

### `kg-mcp version`

```sh
kg-mcp version
```

---

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `KG_DATA_DIR` | `~/.local/share/knowledge-garden` | database directory |
| `KG_MCP_PORT` | `8765` | port `kg serve` binds to |
| `KG_EMBED_BACKEND` | `st` | `st` (SentenceTransformers) or `fake` |
| `KG_EMBED_MODEL` | `BAAI/bge-small-en-v1.5` | only meaningful for `st` |
| `KG_EMBED_DIM` | `384` (`st`) / `32` (`fake`) | pinned dimension |
| `KG_AGENT_MODEL` | *unset* | required for `curate` / `quiz` |

---

## Observability notes

- Every CLI invocation prints structured output (`--json` form) suitable
  for piping into `jq`.
- Every command's exit code is meaningful (see the table at the top).
- `scripts/reindex.sh` is the canonical cron-wrapped command and gives
  a non-zero exit on failure — so cron reports a failed run.
- The five-minute demo (`docs/user-guide.md` §3) is deterministic given
  the fake backend and a fixed clock; CI exercises it on every push.
