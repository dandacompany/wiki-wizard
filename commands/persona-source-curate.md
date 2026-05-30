# persona-source-curate

Run the **source-curator** persona over a list of candidate sources. Prints a
JSON triage verdict (keep/drop) to stdout — nothing is written or fetched.

## When to invoke

User says: "are these sources any good?", "triage these links", "이 출처들 믿을 만해?",
or before an ingest/research run.

## Inputs you need

- The source list → `--text "<urls/citations>"` or `--file <path>`.

## Procedure

1. **Show the persona spec** (`personas/source-curator.md`).
2. **Run the persona** to produce the JSON verdict:
   ```bash
   python3 -m scripts.personas run source-curator \
     --text "<sources>" --output-file /tmp/source-curate-<ts>.json
   ```
   (output_kind is stdout — the command prints the verdict; capture it.)
3. **Report** the keep/drop lists. Recommend feeding `keep` into `ingest` or the
   `research-to-wiki` team. This persona never fetches or writes — it only judges.
