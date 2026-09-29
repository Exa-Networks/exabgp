# Decompose the largest functions

**Status:** ✅ Complete (all steps done 2026-09-29)
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
3. [x] `_get_completions`: 570 → 64 lines (half of it the docstring and dispatch comments), eighteen helpers, largest 69 (signed off 2026-09-29)
4. [x] The other six from the RFC 9234 table, one at a time, same protocol: `configuration`
       175 → 25, `_main` 145 → 33, `_serialize_value` 128 → 53, `cmdline` 112 → 29,
       `read_message` 94 → 39, `_update` 74 → 32
5. [x] Lower the `long_function` ceiling by what each removes: 64 → 58

## Progress

**Step 4, 2026-09-29.** Five agents in parallel, one file set each, same method: branch
coverage first, a pin test file for every reachable path the existing tests missed (passing
on the unsplit code), a golden corpus outside the tree where outputs could be enumerated, then
one extraction per step with ruff, mypy, the pins and the module's tests after each.

| Function | Lines | Pins | Corpus |
|---|---|---|---|
| `Neighbor.configuration` | 175 → 25, 8 helpers | `test_neighbor_configuration_paths.py`, 12 | 133 neighbors of 112 configs, identical |
| `Peer._main` | 145 → 33, 10 helpers, largest 64 | `test_peer_main_paths.py`, 17 | none: collaborators recorded, loop order pinned |
| `_serialize_value` | 128 → 53, 5 helpers | `test_serialize_value_paths.py`, 37 | 60 values and 112 configs, identical |
| `encode.cmdline` | 112 → 29, 6 helpers | `test_encode_cmdline_paths.py`, 26 | 118 `exabgp encode` runs, identical |
| `Protocol.read_message` | 94 → 39, 4 helpers | `test_read_message_paths.py`, 26 | none: mutants checked red |
| `JSON._update` | 74 → 32, 3 helpers | `test_json_update_paths.py`, 12 | API encode 385/0 and 411/0 |

`_main` and `read_message` are on mypyc's phase 7 list: their helpers are plain methods, no
closures, no `Any`. `_main` now builds its two handlers at the top of the loop helper, after
the session up announce rather than before; their constructors only set attributes.

The completer's unreachable lines went too, each with the assert or comment which says why:
the options of `show neighbor` (no registry metadata), the tree walk's filters on `announce`
and `show`, and the walk's final `return []`. The list branches of the walk stayed: typing the
literal `__options__` walks onto an options list, which the corpus had not tried, and
`test_typing_the_options_key_walks_onto_the_options_list` now pins it.

Oddities pinned rather than fixed, each a candidate for its own change:

- `_main` is declared `-> int` and never returns: every path raises.
- `read_message` answers a body which failed to decode with `Notify(1, 0, 'can not decode update
  message of type "N"')`, "update" whatever the type and a header error for a body; a header
  NotifyError without data puts its text in the NOTIFICATION data field, where the code comment
  says it stays in the log.
- `JSON._update` keeps an End-of-RIB return no real UPDATE reaches, which would write invalid JSON.
- `Neighbor.configuration` is display text, not configuration which reads back: blank lines
  before `passive`, `listen` and `connect`, `static { ` closed on the neighbor's `}}`, routes
  without the `route` keyword, empty `host-name ;` and `source-interface ;`.
- `_serialize_value` leaves Counter values and dict keys unconverted, and passes bytearray, set
  and frozenset through, on which `config_to_json` raises.
- `exabgp encode`: `-c /nonexistent.conf` reports "Is a directory", everything after the first
  `route` of `"route A; route B"` is dropped, a route argument is ignored with `-c`, and `-n`
  overrides `--no-header`.

**Step 3, 2026-09-29.** Branch coverage of the completer tests showed the rib, system and set
sub-completions, the command tree walk, the neighbor filters, the AFI/SAFI and route refresh
hand-offs and the multi-character abbreviation never ran. `tests/unit/cli/test_completer_contexts.py`
pins them, 38 tests on a completer whose neighbor list is a fixed table. Alongside, a golden
corpus kept out of the tree (120492 token/text inputs: every pair of 61 words, triples and
quadruples of the likeliest ones, and every command tree path with one or two words more),
recording the matches and every metadata field, was compared after each step: 0 differences
throughout. It caught one slip, a `token` left behind by the extraction of the tree walk,
which the committed tests caught as well.

Steps: `_offer` (thirteen filter-and-describe blocks), `_first_word_completions` with the
groups as module constants, `_display_prefix_completions`, the `peer <ip|*>` block which ended
in `pass` removed, `_noun_first_completions`, `_peer_completions` split by word count into
three, `_route_context_completions`, `_set_completions`, `_show_neighbor_completions`,
`_trailing_keyword_completions`, `_V4_BLOCKED_COMMANDS`, and the tree walk as
`_tree_completions`, `_tree_partial_token`, `_tree_level_completions` and `_tree_options`.
Unit suite 11452 passed. `long_function` 65 → 64.

Lines no input reaches with today's registry, left for a commit of their own: `show neighbor`
has no metadata, so its options branch never runs; `announce` is in the tree only under `peer`,
which never reaches the walk, and `show` is refused before it, so the walk's four filters on
them never run; and the tree has no list leaves, so neither list branch runs.

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

None: the plan is complete. The oddities above are the follow-up.
