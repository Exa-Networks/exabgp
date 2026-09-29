# Decompose the three largest functions

**Status:** 📋 Planning (needs sign-off per MANDATORY_REFACTORING_PROTOCOL)
**Created:** 2026-09-29
**From:** `done-review-quality-sweep.md` item 32

## Why

Exa Style caps a function at 70 lines. `long_function` is ratcheted at 69 sites; these
three are the largest, measured by AST on 2026-09-29, and all three grew since 2026-09-24:

| Function | Lines | 2026-09-24 |
|---|---|---|
| `cli/completer.py` `_get_completions` | 570 | 567 |
| `application/unixsocket.py` `loop` | 365 | 358 |
| `configuration/command.py` `decode_to_api_command` | 304 | 285 |

mypyc: none of these modules is on the compile list in `plan-mypyc.md` (`cli/`,
`application/` and `configuration/` stay interpreted), so this is maintainability work
with no performance motive.

## Steps

One function at a time, following TESTING_BEFORE_REFACTORING_PROTOCOL.md then
MANDATORY_REFACTORING_PROTOCOL.md:

1. [ ] `decode_to_api_command`: pin its output over the encoding corpus, then split by family
2. [ ] `loop`: pin the socket protocol with the CLI tests, then split by state
3. [ ] `_get_completions`: pin completions per context, then split by context
4. [ ] Lower the `long_function` ceiling by what each removes

## Progress

## Failures

## Blockers

Sign-off on the split of each function before it starts.

## Resume Point

Step 1, after sign-off.
