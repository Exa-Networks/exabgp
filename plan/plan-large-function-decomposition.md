# Decompose the largest functions

**Status:** 📋 Planning (needs sign-off per MANDATORY_REFACTORING_PROTOCOL)
**Created:** 2026-09-29
**From:** `done-review-quality-sweep.md` item 32, and the deferred structural cleanup of
`done-rfc9234-roles-otc.md`

## Why

Exa Style caps a function at 70 lines. `long_function` is ratcheted at 69 sites; these
three are the largest, measured by AST on 2026-09-29, and all three grew since 2026-09-24:

| Function | Lines | 2026-09-24 |
|---|---|---|
| `cli/completer.py` `_get_completions` | 570 | 567 |
| `application/unixsocket.py` `loop` | 365 | 358 |
| `configuration/command.py` `decode_to_api_command` | 304 | 285 |

mypyc: none of these three is on the compile list in `plan-mypyc.md` (`cli/`,
`application/` and `configuration/` stay interpreted), so they are maintainability work
with no performance motive.

The RFC 9234 work tried splitting seven more during the OTC feature and backed the splits
out, at Thomas's direction, so the feature commit did not carry them. Still over the limit
on 2026-09-29:

| Function | Lines | Compiled by mypyc |
|---|---|---|
| `bgp/message/update/collection.py` `UpdateCollection.messages` | 282 | yes, `bgp/message/` (phase 5) |
| `bgp/neighbor/neighbor.py` `configuration` | 175 | no |
| `reactor/peer/peer.py` `_main` | 145 | phase 7 |
| `configuration/encoder.py` `_serialize_value` | 128 | no |
| `application/encode.py` `cmdline` | 112 | no |
| `reactor/protocol.py` `read_message` | 94 | phase 7 |
| `reactor/api/response/json.py` `_update` | 74 | no |

`messages` comes first: it builds every UPDATE sent and will be compiled. The OTC work
learnt what its split must not change: family grouping, the attributes a withdrawal
carries (15 of 364 API encode vectors broke when a rewrite dropped them), the
fragmentation budget, and emission order. Keep the API encode vectors green, never
regenerate them to match.

## Steps

One function at a time, following TESTING_BEFORE_REFACTORING_PROTOCOL.md then
MANDATORY_REFACTORING_PROTOCOL.md:

0. [ ] `UpdateCollection.messages`: pin its output over the encoding corpus and the API
       encode vectors, then split by family, before mypyc phase 5 measures it
1. [ ] `decode_to_api_command`: pin its output over the encoding corpus, then split by family
2. [ ] `loop`: pin the socket protocol with the CLI tests, then split by state
3. [ ] `_get_completions`: pin completions per context, then split by context
4. [ ] The other six from the RFC 9234 table, one at a time, same protocol
5. [ ] Lower the `long_function` ceiling by what each removes

## Progress

## Failures

## Blockers

Sign-off on the split of each function before it starts.

## Resume Point

Step 0, after sign-off.
