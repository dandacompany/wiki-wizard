# Wizard flow (decision tree)

```
user input
  │
  ▼
scripts/wizard.py status
  → { vault_count, active, needs }
  │
  ▼
┌────────────────┐
│ needs="setup"  │──► commands/vault-setup.md
└────────────────┘
┌────────────────┐
│ needs="select" │──► commands/vault-use.md
└────────────────┘
┌────────────────┐
│ needs="op"     │──► op named in input? ──yes──► commands/<op>.md
└────────────────┘                       └─no──► Op Wizard
                                                    │
                                                    ▼
                                          mode == "memo"?
                                            │
                                ┌───────────┴───────────┐
                                │                       │
                          memo Op Wizard          wiki Op Wizard
                          1 new                   1 ingest
                          2 find                  2 query
                          3 open                  3 find
                          4 manage                4 maintain
```

## Sticky active

`vaults.last_used` is updated whenever a command runs against a vault. The active flag itself only changes via `vault-use`.

## "needs" semantics

| `needs` | Trigger condition |
|---------|-------------------|
| `setup` | `vault_count == 0` OR registry.db missing |
| `select` | `vault_count ≥ 1` and `active is None` |
| `op` | `vault_count ≥ 1` and `active` set |
