# Messenger query API (`omw serve`)

`omw serve` runs a small, token-authenticated, **retrieve-only** HTTP API over a
local omw vault. It returns ranked wiki page hits — it does **not** synthesize an
answer (no LLM in the server). Any messenger (Slack, Telegram, Discord) becomes a
thin webhook adapter that POSTs to this core and formats the hits into a message.

## Start the server

```bash
omw setup serve --generate-token      # writes OMW_SERVE_TOKEN to ~/.omw/.env (0600)
omw serve                             # http://127.0.0.1:8765 (localhost only)
omw serve --host 0.0.0.0 --port 9000 --vault my-wiki   # explicit exposure
```

Binding is localhost by default. For public/TLS exposure, front it with a reverse
proxy (e.g. Caddy) — the server itself does not terminate TLS.

## Endpoints

### `POST /query` (auth required)

```
Authorization: Bearer <OMW_SERVE_TOKEN>
Content-Type: application/json

{ "text": "what is attention?", "user": "U123", "channel": "C45",
  "vault": "<optional, default=active>", "limit": 5 }
```

- `text` (required): the natural-language query. An adapter strips the bot mention first.
- `user`, `channel` (optional): passthrough context for your logs; not used for retrieval.
- `vault` (optional): vault name; defaults to the pinned (`--vault`) or active vault.
- `limit` (optional): requested hit count (default 5, capped by the server's `--limit`).

Response `200`:

```json
{
  "query": "what is attention?",
  "vault": "ai-research",
  "count": 1,
  "hits": [
    {
      "relpath": "wiki/concepts/attention.md",
      "title": "Attention",
      "summary": "...",
      "tags": ["nlp"],
      "score": 12.3
    }
  ]
}
```

`hits` are the ranker's results unchanged (`relpath, title, summary, tags, score`).

### `GET /health` (no auth)

```json
{ "status": "ok" }
```

## Errors (all JSON)

| Status | Meaning                                                     |
| ------ | ----------------------------------------------------------- |
| 401    | missing/invalid bearer token                                |
| 400    | malformed JSON, missing `text`, or invalid `Content-Length` |
| 404    | unknown vault name / unknown path                           |
| 409    | no active vault (and none named)                            |
| 405    | wrong method for the path                                   |
| 500    | internal error (no traceback leaked)                        |

## curl examples

```bash
TOKEN=$(grep OMW_SERVE_TOKEN ~/.omw/.env | cut -d= -f2)

curl -s http://127.0.0.1:8765/health
# {"status":"ok"}

curl -s -X POST http://127.0.0.1:8765/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"what is attention?","limit":3}'
```

## Writing a thin adapter (sketch)

A messenger adapter is a tiny webhook receiver. It does **not** reimplement omw —
it translates between the messenger and `POST /query`:

1. Receive the platform webhook (Slack slash-command / mention, Telegram update,
   Discord interaction). Verify the platform's own signature.
2. Extract the user's text (strip the bot mention).
3. `POST /query` with `{ "text": <text>, "user": <id>, "channel": <id> }` and the
   shared `OMW_SERVE_TOKEN`.
4. Format `hits` into a reply — e.g. one line per hit: **title** (link to `relpath`)
   - `summary`. If `count == 0`, reply "no matching wiki pages."

No messenger-specific code ships with omw today; this contract is the integration point.
