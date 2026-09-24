# In depth review: testing, quality, mypy coverage

**Status:** 🔄 Active
**Started:** 2026-09-24
**Last Updated:** 2026-09-24 (10 commits landed)

## Goal

Thomas asked for an in depth review of the code, improving testing, quality and mypy
coverage, with each identified improvement committed as it lands. Findings come from six
bounded review agents; every finding is verified against the code (and the RFC where one
applies) before any change is made.

## Baseline

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
| ~~5~~ DONE | `51049611c` | `ttl-security` on IPv4 installed no inbound GTSM check on a platform without `IP_MINTTL` (macOS) and said nothing, because the `AttributeError` it raised against itself was swallowed. Warns now. The asymmetry which hid it: `min_ttlv6` hardcodes its constant and so fails loudly for the same configuration. |
| ~~6~~ DONE | `4c2542d34` | `exabgp cli reset` exited 0 on every failure path, including no socket, no fifo, connection refused, and a failed write. Each now names the fault on stderr and exits 1. The write path also leaked its descriptor. |
| ~~7~~ DONE | `47156d510` | `_get_section_schema` was ten copies of import/assign/`except ImportError: pass`; `_get_root_schema` three more. Both are a table plus a loop now. |
| 8 | `a57f0ea98` | Three swallowed errors which changed behaviour: `_notify_error` hung the client silently, `SO_REUSEADDR` and `IPV6_V6ONLY` shared one `try` so one failure skipped the other, and `Cache.in_cache` returned "already advertised" for a route it could not compare, which drops it. |
| ~~9~~ DONE | `68f2ce53b` | **ADD-PATH path identifier never consumed in EVPN, BGP-LS, MVPN, MUP and SR-Policy.** Found by typing item 16. Each read its first field out of the identifier, so the NLRI after it in the same UPDATE was parsed from the wrong offset. Reachable with `add-path { l2vpn evpn; }`. `tests/unit/test_evpn.py::test_evpn_with_addpath` had asserted the broken behaviour. |

## In progress

Nothing. The next item is the `contextlib.suppress` sweep.

## Queued

Ordered by value over risk. Each is its own commit with a full suite run.

### Correctness

| # | Item | Source | Verified |
|---|---|---|---|
| 5 | `min_ttl` falls back to `IP_TTL` when `IP_MINTTL` is missing, so a `ttl-security` neighbour gets no inbound GTSM check and no warning. Fix is a warning log, not a raise: raising would break platforms that work today. | silent-except audit | yes, code read |
| 6 | `exabgp cli reset` exits 0 when the reset never happened. Broader than reported: it also exits 0 when no socket or fifo is found at all, and leaks `writer` when `os.write` throws. | silent-except audit | yes, code read |
| 7 | `reactor/asynchronous.py:38` `_notify_error` swallows every exception, so a client waiting for `done`/`error` hangs forever with nothing logged. | silent-except audit | no |
| 8 | `configuration/static/__init__.py:286` a malformed `endpoint` silently builds the SR-Policy NLRI for the wrong address family. | silent-except audit | no |
| 9 | `reactor/listener.py:149` `SO_REUSEADDR` and `IPV6_V6ONLY` share one `try`, so a failure on the first skips the second. | silent-except audit | no |
| ~~10~~ DONE | `rib/cache.py:83` an `AttributeError` in the next-hop comparison falls through to `return True`, meaning "already advertised", so the announce is dropped. Latent today. | silent-except audit | no |
| 11 | `Attributes.__iter__` reads wire bytes with no length checks. Unreachable from a peer today; a loaded gun for the first caller who wires it up. | decoder fuzz | no |

### Mechanical reduction of the two ratchets

51 of the 100 `silent_except` sites sit inside `long_function` sites, so these move both.

| # | Item | Effect |
|---|---|---|
| ~~12~~ DONE | `application/schema.py:_get_section_schema` → table plus `importlib` loop | 91 → ~25 lines, −10 silent, −1 long |
| ~~13~~ DONE | `configuration/example.py:302-320`, same shape | −3 silent |
| 14 | 92 clean `contextlib.suppress` conversions with hand written why-comments. A comment alone does NOT clear the ratchet: `check_exa_style` is pure AST, so `pass  # why` still counts. | −~86 silent |
| 15 | Lower both ceilings once 12 to 14 land | ratchet |

### Typing

| # | Item | Verified |
|---|---|---|
| ~~16~~ DONE | `addpath: Any` → `bool` in 16 `unpack_nlri` signatures. `negotiated.required()` and `addpath.send()` both return `bool`, and `MPRNLRI.__init__` already says `bool`. A non-bool passed here parses a path identifier that is not on the wire. | yes |
| 17 | `Neighbor.eor` declared `deque[FamilyTuple]`, actually holds `Family`; `inject_eor` takes `family: object` and the reader does `cast(Family, ...)`. Writing the obvious `for afi, safi in neighbor.eor` type-checks and crashes. | yes |
| 18 | `__eq__` and the four ordering dunders on `NLRI` and `Attribute` take `Any` where the rest of the tree uses `object`. NLRIs are sorted in the RIB. | no |
| 19 | `reactor/api/response/json.py:384` family-keyed dicts typed `tuple[Any, Any]`, so a transposed `(safi, afi)` type-checks. | no |
| 20 | `peer.py:595` `new_routes: Any  # AsyncGenerator`, where the `None` state is what `if not new_routes` actually tests. | no |
| 21 | `Attribute.json(*args, **kwargs)` makes ~40 incompatible overrides legal. Highest bug-class value, ~40 files, needs its own pass. | no |

### Testing

| # | Item |
|---|---|
| 22 | Delete `Connection.reader()`. It has no production caller; the daemon reads only through `reader_async()`. ~20 tests in `test_connection_advanced.py` exercise the dead generator, so the live async header validation (bad marker, bad length → NOTIFY 1/1, 1/2) is untested. Retarget those tests. |
| 23 | `Negotiated.validate()` rejection branches: peer-AS mismatch, zero router-id, iBGP router-id collision, hold-time below minimum. This is the whole of OPEN admission control and only its happy path runs. |
| 24 | `Attributes.__iter__` wire iterator: 0% covered, and it is the `len`/`offset` arithmetic on peer bytes. Pairs with item 11. |
| 25 | MP-based End-of-RIB detection (`update/__init__.py:190-202`): how EOR is recognised for every family that is not IPv4 unicast. Entirely uncovered, so graceful restart for IPv6/VPNv4/EVPN is undefended. |
| 26 | `Listener.new_connections`: which peer an inbound connection is bound to. Already singled out for mutation testing in `pyproject.toml` because it is thin. |

### Agent instructions and housekeeping

| # | Item | Decision |
|---|---|---|
| 27 | `AGENTS.md` at the repo root so non-Claude agents see Exa Style and the Buffer rule. Thomas: AGENTS.md only, since Claude Code reads it now. | agreed |
| 28 | The evidence rule: read the producer, and zero grep hits is not absence. Matters here because NLRI and attribute behaviour is registry-dispatched. | agreed |
| 29 | `plan/journal/` for drive-by defects found while doing something else. | agreed |
| 30 | `git rm` `.claude/backups` (1.9 MB, 5 tracked patches) and the `.claude/docs` archive (60 tracked files), inside a directory agents are told is authoritative. Also clears three dangling doc references. | agreed |

### Proposed, not agreed

| # | Item |
|---|---|
| 31 | RFC requirement ledger under `qa/rfc/`, `@pytest.mark.rfc(requirement, polarity)` on tests, `qa/bin/check_rfc_requirements` as an enrolment floor that only goes up. Pilot on RFC 7606. The design agent's own recommendation was to ship the table-driven test first and decide on the ledger afterwards; item 2 is that test, so the decision point is now. |
| 33 | **ADD-PATH is not implemented on the encode side** for EVPN, BGP-LS, MVPN, MUP and SR-Policy: `pack_nlri` returns the NLRI with no path identifier, under a TODO. Since commit 9 exabgp reads identifiers it does not write, so with add-path negotiated for one of these families the peer will misparse what we send. This is a feature rather than a defect (it was never claimed to work) but it is now the larger half of the gap. |
| 32 | Decomposing the genuinely large functions: `cli/completer.py:509 _get_completions` (567 lines), `application/unixsocket.py:444 loop` (358), `configuration/command.py:555 decode_to_api_command` (285). Not mechanical. Needs a plan and sign-off per MANDATORY_REFACTORING_PROTOCOL. |

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
- **Item 9, `68f2ce53b`.** Not reachable from a live session. `Capabilities._ADD_PATH`
  only offers ADD-PATH for unicast, labelled unicast and VPN, and `Negotiated` needs our
  own OPEN to carry the family, so `add-path { l2vpn evpn; }` never negotiates it. Only
  `configuration/check.py`, which builds the capability unfiltered, reached the decoders.
  FlowSpec, VPLS and RTC ignore the identifier the same way and were left alone. The
  commit message of `68f2ce53b` still carries the wrong claim.
- **Item 33.** Follows from item 9: exabgp cannot negotiate ADD-PATH for these families,
  so no peer misparses what we send. It is a feature gap, and adding one of them to
  `_ADD_PATH` must wait for the encoder.
- **Follow-up to the corrections.** FlowSpec, VPLS and RTC now consume the path
  identifier too. GTSM is fixed in both directions: `min_ttl` sets only the minimum,
  sessions we open install `incoming-ttl`, sessions the peer opens get `outgoing-ttl`, and
  with `incoming-ttl` alone we send 255 as RFC 5082 asks. Still open: the listening
  socket is shared per address and port, so two neighbours on it with different
  `incoming-ttl` values get whichever was set last.
