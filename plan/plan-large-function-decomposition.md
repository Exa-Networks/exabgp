# Decompose the largest functions

**Status:** 🔄 In progress (steps 0 to 2 done)
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

0. [x] `UpdateCollection.messages`: 282 → 55 lines, six helpers, all under 70 (signed off
       2026-09-29)
1. [x] `decode_to_api_command`: 304 → 52 lines, fifteen helpers, largest 51 (signed off
       2026-09-29)
2. [x] `loop`: 365 → 47 lines, twenty-two helpers, largest 23 (signed off 2026-09-29)
3. [ ] `_get_completions`: pin completions per context, then split by context
4. [ ] The other six from the RFC 9234 table, one at a time, same protocol
5. [ ] Lower the `long_function` ceiling by what each removes

## Progress

**Step 2, 2026-09-29.** `./qa/bin/functional cli` drives the single client mode only, and no
test ran the multi client one, so `tests/unit/test_unixsocket_loop.py` pins both first: 10
tests running the helper as a subprocess, with its stdin and stdout as the daemon's end and a
real Unix socket for the clients. Then nine steps, each followed by ruff, mypy, the pin tests,
the other unixsocket tests and `functional cli`: `forget` (three copies of the buffer
clean-up), `_turn_away` (the two identical refusals), the buffers onto `self` with `_grow`,
`_consume` and `_forget` as methods, `_enable_ack`, the readers and writers as methods,
`_reading_list`, `_accept` with `_accept_multi` and `_accept_single`, `_read_multi` and
`_read_single`, and the write side as `_route_daemon_output`, `_flush_client_queues`,
`_forward_client_commands`, `_write_single` and the `_forward_lines` they share. Unit suite
11414 passed. `long_function` 66 → 65.

Pinning found two defects, left as they are because a split changes no behaviour:

- single client mode stops polling the listening socket while a client is connected, so the
  "another CLI client is already connected" refusal (`_accept_single`) never runs: a second
  CLI hangs, unanswered, until the first leaves. Fixed after the split: the server socket
  stays polled, and `test_a_second_client_is_turned_away` fails without it.
- multi client mode never sets `ClientConnection.uuid`, so `_disconnect_client` never tells
  the daemon `bye <uuid>`. Removed rather than repaired: `bye` released the daemon's one CLI
  slot, which the multi client commit (075004e89) replaced by a list of clients nothing reads,
  and the `done` answering it is routed to whichever client asked last. The helper sends no
  `bye` in either mode, the daemon keeps no client list, and its `bye` command only answers
  `done`, for the CLI which sends it on quit.

**Step 1, 2026-09-29.** Coverage of `./qa/bin/test_api_encode --self-check`, the 411 vectors
which decode through this function, showed it never ran the End-of-RIB forms, RTC, SR-Policy
or ungrouped FlowSpec/MUP/MCAST-VPN withdrawals, a flat label, a string withdrawal or an
attributes-only UPDATE. `tests/unit/test_decode_to_api_command_paths.py` pins those first,
23 tests on hand built JSON with the formatters stubbed, all passing on the unsplit code.
Then one change per step, unit suite, both API encode runs and the new tests after each:
`_label_argument` (the label logic was copied into announce and withdraw), the announce
side (dispatch plus seven family helpers), the withdraw side (dispatch plus
`_formatted_withdraws`, which replaces three identical FlowSpec, MUP and MCAST-VPN blocks,
and four family helpers). `long_function` 68 → 67.

**Step 0, 2026-09-29.** Split into `_classify_announces` (56), `_classify_withdraws` (33),
`_attribute_sets` (55), `_v4_withdraw_messages` (28), `_v4_announce_messages` (54) and
`_mp_family_messages` (67), one extraction per step, each followed by ruff, mypy, the unit
suite and both API encode runs: 11364 unit passed, 385/0 and 411/0 at every step, the same
as the baseline plus the two tests added first. Those pin the attributes-only UPDATE (an
Empty NLRI), the one path of the method no test built.

The two early `return`s in the IPv4 passes still end the whole method; the generators return
False for them. They look as if they could drop an MP family which would fit, and cannot:
an MP UPDATE always needs more room than the IPv4 one (the MP attribute header, AFI/SAFI and
next hop outweigh the seven octets of NEXT_HOP it saves), so a budget too small for IPv4 is
too small for MP too. `long_function` ceiling 69 → 68.

`./qa/bin/test_everything`: 25/25 in 10m32s. A first run failed only at exa-style with 69
long functions against 68, while another session was editing `capabilities.py`; the
checker counted 68 again straight after, and the rerun passed.

## Failures

## Blockers

Sign-off on the split of each function before it starts.

## Resume Point

Step 3, `_get_completions`, after sign-off of its split.
