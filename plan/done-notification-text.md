# NOTIFICATION text and Data field in line with the RFCs

**Status:** ✅ Completed
**Created:** 2026-09-27
**Last Updated:** 2026-09-27 (implementation session)
**Baseline:** `868a4b3a9` (line numbers below are from this commit)

## Why

261 places build a `Notify` or `NotifyError`. 250 pass their own text, and `Notify`
puts that text on the wire as the NOTIFICATION Data field.  Two problems:

- the default text (`_str_code`, `_str_subcode`) has drifted from the IANA registry
- for several subcodes the RFC defines the Data field, and we send English instead

While checking, six places were found that send the wrong code/subcode, or send a
NOTIFICATION where the RFC says not to.

## Target design

```python
Notify(code, subcode, detail: str = '', *, data: bytes = b'')
```

- text (log, API, `str()`): `"<IANA code> / <IANA subcode>: <detail>"`, same ` / ` as
  `Notification.__str__`; subcode 0 renders the code name only
- `data`: the octets the RFC defines for that subcode; when set, it is the wire Data field
- (6,2) and (6,4): `detail` is the operator's Shutdown Communication, UTF-8, length
  prefixed, capped at `SHUTDOWN_COMM_MAX_EXTENDED` (255, RFC 9003), no prefix added
- `bytes` passed positionally keep today's meaning (raw Data) during the migration, so
  `protocol.py:244` and the three (1,2) sites keep working

## Phases

Each phase: ledger entries first (`qa/rfc/README.md`), tests that fail without the fix,
then the code.  `./qa/bin/test_everything` between phases.

### Phase 1: names against IANA (registry updated 2026-09-09)

`src/exabgp/bgp/message/notification.py:40-102`

| entry | now | IANA / RFC |
|---|---|---|
| code 2, 3 | `OPEN message error`, `UPDATE message error` | `OPEN Message Error`, `UPDATE Message Error` |
| code 4 | `Hold timer expired` | `Hold Timer Expired` |
| code 5 | `State machine error` | `Finite State Machine Error` |
| code 7 | missing | `ROUTE-REFRESH Message Error` (RFC 7313) |
| code 8 | missing | `Send Hold Timer Expired` (RFC 9687) |
| code 9 | missing | `Loss of LSDB Synchronization` (RFC 9815) |
| 2,5 | `Authentication Notification (Deprecated)` | `[Deprecated]` |
| 2,8 / 2,9 / 2,10 | draft names | `Deprecated` (RFC 9234), keep draft name in brackets |
| 3,7 | `AS Routing Loop` | `[Deprecated]` |
| 5,0 | `Unspecific` | `Unspecified Error` (RFC 6608) |
| 6,0 | `Unspecific` | `Reserved` |
| 6,9 | missing | `Hard Reset` (RFC 8538) |
| 6,10 | missing | `BFD Down` (RFC 9384) |
| 7,0 | missing | `Reserved` |
| 7,2 | `Malformed Message Subtype` | unassigned (expired draft), remove |

Deprecated values keep the old name in brackets, e.g. `[Deprecated] Grouping Conflict`,
so a notification received from an old peer still reads usefully.

⚠️ `__str__` output changes: grep tests and functional `.ci` expectations for the old
strings before editing.

### Phase 2: wrong code or subcode

| # | where | now | should be | source |
|---|---|---|---|---|
| 2a | `bgp/message/refresh.py:96` | `Notify(7, 2)` on subtype not 0/1/2 | ignore the message, log | RFC 7313: "it MUST ignore the received ROUTE-REFRESH message. It SHOULD log an error" |
| 2b | `reactor/peer/peer.py:513` | `Notify(5, 1)` when OPEN never arrives | `Notify(4, 0)` | RFC 4271 FSM, OpenSent: "If the HoldTimer_Expires (Event 10), the local system sends a NOTIFICATION message with the error code Hold Timer Expired" |
| 2c | `reactor/peer/peer.py:716` | `Notify(6, 0, 'ExaBGP Internal error, sorry.')` | a non-reserved subcode (6,8 Out of Resources?) | IANA: Cease 0 is Reserved |
| 2d | `reactor/api/command/neighbor.py:80` | `teardown <code>` accepts any int | reject 0 and unassigned Cease subcodes | IANA |
| 2e | `bgp/message/message.py:207` | `Notify(2, 4)` for unknown message type | `Notify(1, 3)` with the Type octet as data | RFC 4271 6.1 |
| 2f | `bgp/message/update/attribute/attribute.py:325`, `:352` | `Notify(2, 4)` for unknown attribute | prove unreachable and replace with `assert`, or the RFC 4271 6.3 / RFC 7606 action | RFC 4271 6.3 |
| 2g | `bgp/message/open/capability/capability.py:226` | `Notify(2, 4)` for unknown capability | prove unreachable (`unknown_capability` fallback) and `assert` | RFC 5492: "MUST NOT be generated" |
| 2h | `bgp/message/notification.py:154` (receive) | Shutdown Communication > 128 flagged invalid | accept up to 255 | RFC 9003 |

2a and 2b first: both are real, reachable, and change what a peer sees.

**Not in this plan:** (2,8) / (2,9) in `open/capability/negotiated.py:239,247,257`.
IANA lists them Deprecated, but `draft-ietf-idr-bgp-multisession-07` (being enrolled in
the working tree at the time of writing) prescribes (2,8) "Grouping Conflict".  Leave
them to the multisession work.

### Phase 3: the class and the call sites

- implement the design above in `Notify.__init__` (`notification.py:207`)
- `protocol.py:246` re-wraps `str(notify)`: must not get the prefix twice
- `listener.py:371,381` and `incoming.py:45` pass bytes then decode to ascii: route
  through `detail`
- drop the text where it only repeats the default:
  `refresh.py:94`, `igpmetric.py:59,64`, `srlg.py:50`, `cidr.py:262`,
  `sourcerouterid.py:38`, `ospfaddr.py:35`, `linkstate.py:371`,
  `node/localrouterid.py:37` (its text says "remote-te", copied from `remoterouterid.py`)
- trim text that restates the subcode: (1,3) `message.py:230`, (2,4)
  `capabilities.py:384`, (3,11) `aspath.py:230`, (5,1) `protocol.py:361`
- optional: `Notify.short(code, subcode, what, need, got)` for the 67 "need N, got M"
  messages; merge the 9 identical strings shared by `nlri/inet.py` and `nlri/ipvpn.py`

### Phase 4: RFC-defined Data octets

| subcode | Data | call site |
|---|---|---|
| 1,3 | the erroneous Type octet (MUST) | `message.py:230`, `protocol.py:268` |
| 2,1 | 2-octet highest supported version below the bid, or the lowest (4271 6.2) | `open/__init__.py:146` |
| 7,1 | the complete ROUTE-REFRESH message (MUST, RFC 7313) | `refresh.py:94` |
| 3,9 | the attribute, type + length + value (MUST, ledger: required) | `mprnlri.py`, `mpurnlri.py`, `collection.py:615`, `traffic.py:60,64` |
| 3,5 | the attribute, type + length + value (MUST) | 45 sites; needs the attribute header reachable from `unpack_attribute` |
| 6,2 / 6,4 | UTF-8, 255 cap | `peer.py:813` sends the subcode name as the communication today, send length 0 |

3,5 and 3,9 need the attribute header, which the per-attribute decoders do not see.
Likely approach: decoders raise with `detail` only, and `attribute/collection.py`
fills `data` from the header it just parsed.  Design this before starting.

## Ledger work

- enrol RFC 7313 (text + toml): covers 2a and 4 (7,1)
- enrol RFC 9003: covers 2h and the (6,2)/(6,4) send side
- RFC 4271 entries to add or check: `6.1` Bad Message Type data field, `6.2` Unsupported
  Version data field, `6.3` Optional Attribute Error data field
- RFC 4271 FSM (section 8) is not enrolled; 2b needs at least the OpenSent HoldTimer entry
- RFC 6608 / RFC 4486: decide whether to enrol, both are small

## Open decisions

1. When the RFC defines no Data content, does the peer get the `detail` text (today's
   behaviour) or an empty Data field?  Recommendation: keep the text.
2. 2c: which Cease subcode replaces the reserved (6,0)?
3. Phase 3 `Notify.short` helper: yes or no.

## Progress

SUPERSEDED: "Nothing started.  Waiting for the tests running on main before touching code."
Started 2026-09-27 once the multisession work was committed (`86fe09c4d`).

| item | status | notes |
|---|---|---|
| Phase 1 IANA names | ✅ | `test_notification_comprehensive.py` now compares whole tables to an IANA snapshot |
| 2a (7,2) ignored | ✅ | RFC 7313 enrolled (section 5 only); `RouteRefreshHandler._refresh` ignores and logs |
| 2b open wait (4,0) | ✅ | regression test in `tests/unit/rfc/test_rfc4271_timers.py`, unmarked (FSM text has no keyword) |
| 2c (6,0) reserved | ✅ | (6,8) Out of Resources, `Peer._announce_up_to_the_api`, `test_peer_api_up_failure.py` |
| 2d API teardown | ✅ | `teardown [<code>] [<subcode>] [<text>]`, `teardown_notification` in `api/command/neighbor.py`, `test_api_teardown.py`, functional `api-teardown` second teardown uses `6 4 "back soon"` (verified red when the bytes are wrong) |
| 2e `Message.klass` (1,3) | ✅ | |
| 2f attribute fallbacks | ⏭️ | see Decisions |
| 2g `Capability.klass` | ✅ | now RuntimeError, test in `test_rfc5492_capabilities.py` |
| 2h RFC 9003 receive 255 | ✅ | RFC 9003 enrolled, whole document |
| Phase 3 class | ✅ | `Notify(code, subcode, detail='', *, data=None)` |
| Phase 3 trims | ✅ | texts that repeated the name now say the TLV and size |
| Phase 3 `Notify.short` | ✅ | decision 3: yes. 55 sites migrated by script, every one guarded by a strict `<`; `short` asserts it |
| Phase 4 1,3 / 2,1 / 7,1 | ✅ | ledger `6.1-bad-message-type-data-field`; 2,1 unmarked (no keyword, and the sentence crosses a page break) |
| Phase 4 3,9 (and 3,2/3,4/3,5/3,6/3,8) | ✅ | `_with_the_attribute` in `attribute/collection.py`; ledger `6.3-optional-attribute-error-data-field` |
| Phase 4 6,2 / 6,4 | ✅ | UTF-8, cut to 128 on a character boundary, empty detail sends no communication |

## Decisions

- Decision 1 taken as recommended: when no RFC defines the Data field, the detail goes to
  the peer as text.  With no detail, the Data field is now empty (it used to carry the
  subcode name, which repeats the octet the peer just read).
- Wire text is ASCII with `backslashreplace`: a Notify is raised while handling an error and
  must not raise on its own text.  All data is capped at `Notify.DATA_MAX_OCTETS` (4075).
- 2f: `Attribute.unpack`'s `Notify(2, 4)` is reached only from the read-only attribute
  iterator in `collection.py` (around line 966), which catches it and logs.  It never
  reaches a peer.  Left alone.
- Found and not fixed (out of scope, needs its own RFC 7313 section 4 entries):
  `RouteRefreshHandler` resends on a received BoRR or EoRR as if it were a request.
- Found and fixed on the way: `protocol.py` logged a sent NOTIFICATION with
  `data.decode('utf-8')`, which would have raised on the 7,1 Data field (0xFF marker).
- `AttributeCollection.parse` is a grandfathered long function; the change added three
  lines and moved the logic into `_with_the_attribute` rather than growing it further.

## Decisions (2026-09-27, second round)

- Decision 3: yes.  Per-entry and bit-length messages were left alone: they are not "fewer
  octets than needed" and the assertion in `short` would be false for them.
- API teardown: "should give the client the flexibility they need".  2c and 2d are to be
  proposed, not implemented.  Found: `teardown 300` raises ValueError inside the peer
  loop (`bytes([6, 300])`), the catch-all logs it, and no NOTIFICATION is sent.

## Decisions (2026-09-27, third round)

- Thomas chose `teardown <code> <subcode> [<text>]` over subcode only, and (6,8) for 2c.
- One number stays a Cease subcode (what the code always did, the docs were wrong), none
  means (6,2), 0..255 accepted with a warning when IANA does not assign it, >255 refused.
- `Peer._teardown` now holds the `Notify` to send.  As an int, a subcode of 0 was falsy and
  `while not self._teardown` never saw the teardown.
- Knock-on of Phase 3: `teardown 4` with no text now sends an empty Data field, where it
  sent "Administrative Reset" as the communication.  `qa/api/api-teardown.ci` updated.
- `doc/CHANGELOG.rst` entries drafted under 6.0.0 (Thomas to review the wording).

## Recent failures

### 2026-09-27 functional encoding h (unknown-message)

**Error:** expected Data `756E6B6E6F776E...` ("unknown message type 255"), got `FF`.
**Cause:** the test pinned the ASCII Data field RFC 4271 6.1 forbids.
**Status:** ✅ `qa/encoding/unknown-message.ci` now expects `0016:03:0103FF`.

### 2026-09-27 optimised step: 1 failed, 18 errors, unit step 12m41s (normally ~3m40s)

**Error:** `test_update_carrier_split.py::test_a_lone_mp_withdrawal_wider_than_the_budget...`
**Cause:** not established.  Passes 3/3 alone under -O and in a full parallel -O run.  The
disk was found at 100% (403 MB free) straight after, and the next run could not write its
output (ENOSPC), which fits both the slowness and the errors.
**Status:** ❌ Blocked on disk space; `test_everything` has not had a clean full run.

`test_util.py::TestDNS` fails intermittently in this environment, before and after these
changes; unrelated to notifications.

## Resume point

2026-09-27: `./qa/bin/test_everything` passes, all 25 steps (8m54s).  Everything in this
plan is implemented.  Waiting for Thomas to review, then commit (split per EXA_STYLE: one
change per commit) and rename the plan to done-.

SUPERSEDED (kept for history):

2026-09-27: free disk space, then `./qa/bin/test_everything`.  Then decisions 2 and 3.

SUPERSEDED (kept for history):

Phase 1, after checking the working tree is clean of the multisession work
(`ms.py`, `test_multisession_negotiation.py`, `draft-ietf-idr-bgp-multisession-07`) or
that it has been committed.  Re-run the call site scan first, line numbers will drift:

```bash
.venv/bin/python - <<'EOF'
import ast, pathlib
for p in pathlib.Path('src').rglob('*.py'):
    for n in ast.walk(ast.parse(p.read_text())):
        if isinstance(n, ast.Call):
            f = n.func
            name = getattr(f, 'id', None) or getattr(f, 'attr', None)
            if name in ('Notify', 'make_notify', 'NotifyError'):
                print(f'{p}:{n.lineno}', ', '.join(ast.unparse(a) for a in n.args))
EOF
```

## Follow-ups (2026-09-27, after completion)

- 2f resolved: `Attribute.klass` raises RuntimeError (only reached after `registered()`),
  `Attribute.unpack` raises ValueError for an unregistered code, which the read-only wire
  iterator already caught.  Neither is a Notify any more.  `tests/unit/test_attribute_unregistered.py`.
- `NotifyError` carries a Data field; `connection.py` fills it with the refused Length
  octets for a (1, 2), and `protocol.py` no longer rebuilds them.
