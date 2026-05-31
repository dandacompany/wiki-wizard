# review — re-verify pages due for spaced-repetition review

**When to invoke:** "review my wiki", "what needs reviewing", "리뷰할 거 뭐 있어".

**Deterministic:** `omw review due [--vault <name>] [--scheduled-only]` → JSON list of
due pages (`relpath`, `due`, `interval_days`, `confidence`). Unscheduled pages (no
`review:` block yet) count as due so the whole vault enters a cadence over time.

**Procedure (propose → confirm → execute):**

1. Run `omw review due`. If the list is long, take the top pages (unscheduled / empty
   `due` first, then low `confidence` first).
2. For each due page, re-verify it in-session:
   - **fact-checker** persona (`input: vault_page` → `sibling_suffix`) — re-check claims.
   - **consistency-checker** persona (`input: vault_page` → `stdout`) — re-check against the vault.
3. Present each page's verdict. Let the human choose a grade:
   - `pass` — still accurate/consistent (interval grows).
   - `needs-work` — issues found (interval resets to the confidence floor, so it returns sooner).
4. After confirmation, record + reschedule per page:
   `omw review done <relpath> --grade pass|needs-work`.

You never write the schedule directly — `omw review done` is the deterministic execute step
(it updates the page's frontmatter `review:` block and reindexes).
