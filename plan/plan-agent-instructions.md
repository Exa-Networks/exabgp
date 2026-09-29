# Agent instructions and repository housekeeping

**Status:** 📋 Planning (decisions needed before work)
**Created:** 2026-09-29
**From:** `done-review-quality-sweep.md` items 27 to 30, agreed 2026-09-24, none done

## Items

| # | Item | Conflict found 2026-09-29 |
|---|---|---|
| 27 | `AGENTS.md` at the root, so non-Claude agents see Exa Style and the Buffer rule | Thomas's global rule expects shared rules in `ai/rules/`, with `AGENTS.md` and `CLAUDE.md` generated from them. Decide: that layout, or a hand written `AGENTS.md` |
| 28 | The evidence rule: read the producer; zero grep hits is not absence, because NLRI and attributes are dispatched through registries | Goes wherever 27 decides |
| 29 | `plan/journal/` for defects found while doing something else | none |
| 30 | `git rm` `.claude/backups` and the `.claude/docs` archive (65 tracked files) | Sessions still write patches to `.claude/backups/` (`config-grammar-complete.patch`, untracked, 2026-09-29). Removing the tracked ones needs `.claude/backups/` in `.gitignore` too, or the habit moves somewhere else |

## Steps

1. [ ] Thomas: layout for 27 and 28
2. [ ] Thomas: where backup patches go from now on (30)
3. [ ] Do 27 to 30

## Progress

## Failures

## Blockers

Steps 1 and 2.

## Resume Point

Step 1.
