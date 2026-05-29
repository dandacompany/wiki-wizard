# `find` — natural-language search across the active vault

**Mode:** memo or wiki (any active vault)
**Underlying script:** `scripts.search.query` (Plan A weighted ranker)

## Preconditions

Active vault must exist. Run `python3 -m scripts.wizard status` first.

## Flow

1. Ask the user for a query string (or take it directly from the original prompt if already given).
2. Call:

```bash
python3 -c "
from scripts.paths import registry_path
from scripts import search, registry
db = registry_path()
vault = registry.get_active(db)
hits = search.query(db, vault_id=vault['id'], query='<query>', limit=5)
import json; print(json.dumps(hits, ensure_ascii=False, indent=2))
"
```

3. Format the top-5 hits as a table:

```
# | score | relpath                      | title
1 | 8.5   | inbox/karpathy-wiki.md       | Karpathy LLM Wiki Gist
2 | 5.0   | concepts/compounding.md      | Compounding Knowledge
...
```

4. Ask whether to `open` a hit (route to the `open` op), `find` again with a refined query, or stop.

## Post-conditions

- No state mutation. Read-only.

## Error handling

- Empty query → ask again.
- Zero hits → suggest relaxing terms or running `lint` (in case index is stale).
