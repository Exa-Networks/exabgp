# In depth review: testing, quality, mypy coverage

**Status:** ✅ Done, the rest moved to its own plans
**Started:** 2026-09-24
**Last Updated:** 2026-09-29

## Goal

Thomas asked for an in depth review of the code, improving testing, quality and mypy
coverage, with each identified improvement committed as it lands. Findings come from six
bounded review agents; every finding is verified against the code (and the RFC where one
applies) before any change is made.

## Baseline (2026-09-24, historical)

`./qa/bin/test_everything` on this machine: 23/24 pass, `reload-cleanup` skips because
127.0.0.2 is not configured as a loopback alias. `mypy --strict` clean over 392 files.
5968 unit tests.

Ratchets at the start of the session:

| Rule | Count |
|---|---|
| `bare_except` | 0 |
| `input_assert` | 0 |
| `long_function` | 89 (ceiling said 91) |
| `silent_except` | 100 |

## Done

| # | Commit | What |
|---|---|---|
| 1 | `0cdb26ddc` | `test_everything` can report a stage as skipped rather than failed. `reload-cleanup` returning 2 ("this machine will not let me look") was read as a failure, which both claimed something about the code the run had no evidence for and stopped `renders-json` and `documentation` from ever executing here. Both pass now they run. |
| 2 | `8ab0c1b2f` | RFC 7606 7.8/7.14/7.15. `Communities`, `ExtendedCommunities` and `ExtendedCommunitiesIPv6` carried no `TREAT_AS_WITHDRAW`, so one malformed optional transitive attribute reset the session instead of withdrawing the route. New `tests/unit/test_rfc7606_prescribed_action.py` pins the action the RFC names per attribute, not merely that nothing raw escapes. |
| 3 | `0946b78c0` | RFC 8669 6. `PrefixSid` gains `DISCARD`; `SrGb` raises `Notify` from `unpack_attribute` instead of letting a `ValueError` escape and be laundered into `Notify(1, 0)`, a Message Header Error reported for an attribute fault. |
| 4 | `792337cd7` | Tiger Style renamed to Exa Style. 5 artefacts renamed, 24 files substituted by script, the TigerBeetle credit line excluded by pattern. `long_function` ceiling lowered 91 → 89, which it had been asking for. |
| 5 | `51049611c` | `ttl-security` on IPv4 installed no inbound GTSM check on a platform without `IP_MINTTL` (macOS) and said nothing, because the `AttributeError` it raised against itself was swallowed. Warns now. The asymmetry which hid it: `min_ttlv6` hardcodes its constant and so fails loudly for the same configuration. |
| 6 | `4c2542d34` | `exabgp cli reset` exited 0 on every failure path, including no socket, no fifo, connection refused, and a failed write. Each now names the fault on stderr and exits 1. The write path also leaked its descriptor. |
| 7 | `47156d510` | `_get_section_schema` was ten copies of import/assign/`except ImportError: pass`; `_get_root_schema` three more. Both are a table plus a loop now. |
| 8 | `a57f0ea98` | Three swallowed errors which changed behaviour: `_notify_error` hung the client silently, `SO_REUSEADDR` and `IPV6_V6ONLY` shared one `try` so one failure skipped the other, and `Cache.in_cache` returned "already advertised" for a route it could not compare, which drops it. |
| 9 | `2142b4cc1` | **ADD-PATH path identifier never consumed in EVPN, BGP-LS, MVPN, MUP and SR-Policy.** Found by typing item 16. Each read its first field out of the identifier, so the NLRI after it in the same UPDATE was parsed from the wrong offset. ~~Reachable with `add-path { l2vpn evpn; }`.~~ Not from a live session, see Corrections. `tests/unit/test_evpn.py::test_evpn_with_addpath` had asserted the broken behaviour. |

## Outcome of the queue, 2026-09-29

Every queued item was checked against the tree on 2026-09-29, with `plan-mypyc.md` in
mind: typing which mypyc can compile to native calls was worth doing now, work on modules
mypyc will not compile was not urgent. Each item is done, closed, or has its own plan.

| # | Item | Outcome |
|---|---|---|
| 5, 6, 7, 9, 10, 12, 13, 16 | see Done | done; the Done table numbers commits, not queue items (queue 7, 9, 10 are commit 8, 12 and 13 are commit 7, 16 led to commit 9). Commits 5, 8 and 9: see Corrections |
| 8 | SR-Policy endpoint | closed: `configuration/static/` is gone; `grammar/tree/sr_policy.py` refuses a malformed endpoint (`illegal IP address string passed to inet_pton`) |
| 11, 24 | `Attributes.__iter__` unchecked reads | done 2026-09-29: each header and value length checked, Notify 3/1; `tests/unit/test_attributes_wire_iterator.py`, 5 of 7 fail before. The dead `flag_attribute_content`, same unchecked reads, removed. Nothing in `src/` constructs `Attributes` |
| 14, 15 | `contextlib.suppress` sweep, ceilings | done: `silent_except` 0, `long_function` 69 |
| 17 | `Neighbor.eor` typing | done: `deque[Family]` |
| 18 | comparison dunders on `Any` | done 2026-09-29: `object` everywhere. Found two bugs doing it: `IPVPN` and the MUP routes answered `!=` with `not NotImplemented` (TypeError from Python 3.14), and `Attribute` ordering read `other.ID` unchecked. `tests/unit/test_comparison_against_other_types.py`, 4 fail before |
| 19, 20 | `tuple[Any, Any]`, `new_routes: Any` | done |
| 21 | `Attribute.json(*args, **kwargs)` | done 2026-09-29, `done-attribute-json-signature.md` |
| 22 | dead `Connection.reader()` | `plan-connection-reader-removal.md`: 68 test calls, not the ~20 estimated (mypyc relevant, phase 7) |
| 23 | `Negotiated.validate()` rejections | done: `tests/unit/rfc/test_rfc4271_open.py` |
| 25 | MP End-of-RIB detection | done: `tests/unit/rfc/test_rfc4724_graceful_restart.py` decodes it per family |
| 26 | `Listener.new_connections` | done: under mutmut, see `done-testing-gaps.md` item 3 |
| 27 to 30 | agent instructions, housekeeping | `plan-agent-instructions.md`: agreed but conflicts with the global `ai/rules/` layout and with sessions still writing to `.claude/backups/` |
| 31 | RFC ledger | done, see below; 32 RFCs now |
| 32 | three largest functions | `plan-large-function-decomposition.md` (not mypyc relevant: uncompiled modules) |
| 33 | ADD-PATH encode | `plan-addpath-nlri.md`, updated with the per family state |
| GTSM | shared listening socket | `plan-gtsm-shared-listener.md` |

## Decisions taken

- Commits go directly on `main`, not a branch. A branch was created and reverted at
  Thomas's instruction.
- `silent_except` is cleared by `contextlib.suppress` plus a why-comment, not by changing
  the checker to accept comments.
- A non-finite FlowSpec traffic-rate is now treat-as-withdraw rather than a NOTIFICATION,
  following RFC 7606 7.14 uniformly. This reverses the end-to-end outcome of `d2cc6e83d`
  while keeping the defect that commit fixed: the rate is still judged in the decoder
  rather than in a renderer downstream, and the outcome still does not depend on the log
  level.
- Dead `Connection.reader()` is to be deleted and its tests retargeted, not kept.

## Notes

- The sandbox blocks `bind()`, writes under `.claude/commands/`, and gpg-agent, so the test
  suite, some doc edits and every commit have to run unsandboxed. A sandboxed run reports
  20 spurious socket failures.
- `UV_CACHE_DIR` must be set to a writable path for any sandboxed `uv` call.

## Corrections after review (2026-09-24)

A second pass checked every fix against the code before it and the RFCs. Items 1 to 3
(RFC 7606 communities, RFC 8669 Prefix-SID discard, CLI reset) stand as written. These
did not:

- **Item 5, `51049611c`.** The diagnosis was wrong. CPython exports `socket.IP_MINTTL` on
  no platform at all, so the IPv4 inbound GTSM check was never installed anywhere, Linux
  included, since `a004cc260`. The warning that commit added fired on Linux with the false
  reason "this platform has no IP_MINTTL". Fixed by taking the option number from the
  kernel headers (Linux 21, FreeBSD 66) when `socket` does not export it, as `min_ttlv6`
  already does. Still open: `min_ttl` also sets `IP_TTL` to the configured minimum, where
  RFC 5082 has the sender use 255.
- **Item 8, `a57f0ea98`.** Not the behaviour changes it claimed. `SO_REUSEADDR` is not
  refused on any supported platform, and an unknown peer is closed with NOTIFICATION 6/3
  whatever the socket accepted. The `Cache.in_cache` `AttributeError` is unreachable:
  every `IP`, `NoNextHop` included, has `index()`. The async notifier change adds a log
  line and does not stop the hang. The code is kept as hygiene; the comments now say so.
- **Item 9, `2142b4cc1`.** Not reachable from a live session. `Capabilities._ADD_PATH`
  only offers ADD-PATH for unicast, labelled unicast and VPN, and `Negotiated` needs our
  own OPEN to carry the family, so `add-path { l2vpn evpn; }` never negotiates it. Only
  `configuration/check.py`, which builds the capability unfiltered, reached the decoders.
  FlowSpec, VPLS and RTC ignore the identifier the same way and were left alone. The
  commit message of `2142b4cc1` carried the wrong claim; it has been reworded.
- **Item 33.** Follows from item 9: exabgp cannot negotiate ADD-PATH for these families,
  so no peer misparses what we send. It is a feature gap, and adding one of them to
  `_ADD_PATH` must wait for the encoder.
- **Follow-up to the corrections.** FlowSpec, VPLS and RTC now consume the path
  identifier too. GTSM is fixed in both directions: `min_ttl` sets only the minimum,
  sessions we open install `incoming-ttl`, sessions the peer opens get `outgoing-ttl`, and
  with `incoming-ttl` alone we send 255 as RFC 5082 asks. Still open: the listening
  socket is shared per address and port, so two neighbours on it with different
  `incoming-ttl` values get whichever was set last.

## Item 31 done: the RFC requirement ledger

`a98fd39a7`. The undecided item is decided and built. `qa/rfc/<rfc>.toml` holds one
entry per normative sentence, `qa/rfc/text/` holds the RFC, `@pytest.mark.rfc()` marks
the test which proves it, and `./qa/bin/check_rfc_compliance` fails when the three
disagree. It is a stage of `test_everything` and `qa/rfc_compliance.json` ratchets the
untested count per RFC.

The design came from looking at how `ze` does it. Three things worth having were taken
and the rest left:

- the link lives in the test, not in the ledger, so the ledger cannot drift from what
  runs
- a MUST wants a positive and a negative test, because a decoder which accepts
  everything passes every positive test ever written
- "we do not do this" is a first-class state with a mandatory reason, split into
  `not-applicable` (never bound us, closes) and `gap` (we owe it, stays published)

One thing was added that ze does differently, and it is the part that matters most:
every quote is checked against the published RFC on every run. ze learned by measurement
that extracted requirement lists are wrong in both directions, inventing MUSTs a
document does not contain and inverting the ones it does, and answered with a separate
sign-off artefact. Checking the quote against the text is cheaper and catches the same
class outright.

Not adopted: the extraction sign-off JSON, the discrimination records which re-prove
each test goes red under an injected break, six of ze's eight ratchets, and the
generated-but-uncommitted file scheme. `doc/RFC_COMPLIANCE.md` is generated and
committed so it can be diffed in review.

Seeded with RFC 7911. Ledgers for 4271, 4760, 5492, 6793, 7606, 9234, 5082, 4724, 1997,
4360, 8092 are being written.

## Resume Point

Done. Open work lives in the plans named in the outcome table.
