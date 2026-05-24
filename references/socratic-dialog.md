# Socratic dialog patterns

The wizard asks the minimum number of questions. These patterns are conventions, not enforced by code.

## Tone

- Plain, present-tense, second person.
- One question per `AskUserQuestion` (max 4 options).
- Recommended option is first and labeled `(recommended)` / `(추천)`.

## Destructive op confirmations

Always show the target by name plus the consequence:

> "You're about to delete `ai/2026-05-12-karpathy-llm-wiki.md` (moves to `.trash/`, recoverable). Continue?"

For hard deletes:

> "Permanently delete `ai/2026-05-12-karpathy-llm-wiki.md`? This cannot be undone."

For `vault-forget`:

> "Remove `personal` from the registry? Files at `/path/to/vault` are preserved on disk."

## Inferred-target confirmation

When context implies a single target, state the inference and ask for one-click confirm:

> "방금 작성한 `ai/2026-05-15-hermes-honcho-memory-setup.md` 을(를) 여시는 거 맞나요?"

## Empty search results

Suggest broader keywords or alternate language:

> "No matches for 'Karpathy'. Try shorter keywords, English/Korean variants, or `vault-list` to confirm you're in the right vault."

## Question-grouping rule

If you have > 4 options, group them. Example: 6 memo ops → 3 visible categories (new / find+open / manage), then a follow-up for the third.
