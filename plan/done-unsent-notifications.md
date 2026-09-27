# NOTIFICATIONs exabgp never sends: (2, 7) and (6, 1)

**Status:** ✅ Completed 2026-09-27
**Created:** 2026-09-27
**Follows:** `plan/done-notification-text.md` (commits `3434e5323`, `cbacb1b61`, `ecfa3bf52`)

## Why this exists

The notification work made every NOTIFICATION we send carry the Data field its RFC
defines.  Two subcodes with a defined Data field are never sent at all, so there was
nothing to fix, only a decision to record.  Neither should be built for its own sake: each
belongs to a feature, and this file says what the feature would owe when it arrives.

## (2, 7) Unsupported Capability, RFC 5492

**Today:** nothing raises it.  `qa/rfc/rfc5492.toml` records
`rfc5492#3-notification-must-name-the-capabilities` as `not-applicable`: the MAY before it
(a speaker may refuse a peer lacking a capability it needs) is declined.  A family the
peer did not advertise goes to `Negotiated.mismatch`, is logged, and the session runs
without it.

**What would trigger it:** an operator option such as "refuse the session unless the peer
advertises X" (a family, ADD-PATH, ASN4, extended message).  The nearest thing in the tree
is RFC 9234 strict role mode, which refuses with its own subcode (2, 11),
`negotiated.py:268`.  Multisession uses (2, 9) for the same shape of rule.

**What it owes (RFC 5492 3 and 5):**
- "The Data field in the NOTIFICATION message MUST list the set of capabilities that
  causes the speaker to send the message.  Each such capability is encoded in the same way
  as it would be encoded in the OPEN message."  So `data=` is the concatenation of the
  capability TLVs we wanted, packed as in our own OPEN (`Capability` classes already pack).
- It must never be sent for a capability we do not understand (entries
  `rfc5492#3-no-notification-for-an-unknown-capability` and
  `rfc5492#5-unsupported-capability-not-for-unknown-codes`, both tested today).
- "If terminated, such peering SHOULD NOT be re-established automatically"
  (`rfc5492#3-terminated-peering-not-re-established`): check how that entry is recorded
  before building, it constrains the reconnect loop in `peer.py`.

**Where:** `Negotiated.validate()` (`negotiated.py`, the tuple it returns becomes
`Notify(*error)` in `protocol.py:validate_open`).  The tuple would need a fourth element or
`validate` would return a `Notify` directly; the second is cleaner now that `Notify` takes
`data=`.

**Ledger work:** flip `rfc5492#3-notification-must-name-the-capabilities` from
`not-applicable` to `required`, with a positive test on the Data field.

## (6, 1) Maximum Number of Prefixes Reached, RFC 4486

**Today:** exabgp has no received prefix limit (`grep -rn 'prefix.limit\|max.prefix' src`
finds nothing), so there is nothing to send it from.

**What would trigger it:** a per-neighbor, per-family limit on received prefixes.  That is
a feature request in its own right (RIB size limits are listed as medium priority in
`plan/README.md`, "RIB Size Limits").

**What it owes (RFC 4486 4):** the Data field "MAY optionally include the Address Family
information [BGP-MP] and the upper bound": AFI (2 octets), SAFI (1 octet), prefix upper
bound (4 octets).  A MAY, so enrol RFC 4486 when the feature lands and record it as
followed.  RFC 4486 is not enrolled today; enrolling it would also cover the Cease
subcodes the teardown command now sends.

**Where:** wherever the limit is enforced on receipt, most likely the update handler in
`reactor/peer/handlers/`, raising `Notify(6, 1, detail, data=pack('!HBI', afi, safi, limit))`.

## Not in scope

- (3, 3) Missing Well-known Attribute: RFC 7606 replaced it with treat-as-withdraw, and
  `rfc4271#6.3-missing-well-known-attribute` is `not-applicable` with that reason.

## Resume point

Nothing to do until a feature needs either subcode.  When one does, read this file, then
`qa/rfc/README.md`, and add the ledger entries before the code.

## Review (2026-09-27)

References checked against the tree: `negotiated.py:268` (role, (2, 11)), `negotiated.py:257`
(multisession, (2, 9)), `protocol.py:332` (`Notify(*error)`), `Notify(..., *, data=)` in
`notification.py:237`, the rfc5492 and rfc4271 entry ids and their tests, the
`reactor/peer/handlers/update.py` path, "RIB Size Limits" in `plan/README.md`.  All hold.

Corrections:
- `rfc5492#3-terminated-peering-not-re-established` is already recorded `not-applicable`,
  for the same reason as the Data field entry.  Building (2, 7) makes it binding, so it
  flips to `required` (or `gap` with a reason) in the same change, not only "check it".
- ~~The RFC 5492 wording quoted above under "What it owes" does not match the ledger's quote
  ("The message MUST contain the capability or capabilities that cause the speaker to send
  the message.").  Check `qa/rfc/text/` for the exact sentence before writing the entry.~~
  SUPERSEDED: both quotes are verbatim.  The one under "What it owes" is section 5
  (`rfc5492.txt:216`), the ledger's is section 3 (`rfc5492.txt:127`).
- "Ledger work" names one entry to flip; there are three.  Section 5's Data field MUST has
  its own entry, `rfc5492#5-data-field-lists-the-capabilities` (`rfc5492.toml:214`), also
  `not-applicable`.  The (2, 7) change flips
  `rfc5492#3-notification-must-name-the-capabilities`,
  `rfc5492#5-data-field-lists-the-capabilities` and
  `rfc5492#3-terminated-peering-not-re-established` together.  The Data field test can
  carry both of the first two markers.

## Implementation (2026-09-27)

Thomas asked for both subcodes to be built.  Decisions, from him:

- (2, 7) syntax: a third value on the capability leaf, `asn4 require;`, not a separate
  `require [...]` list.  Accepted for asn4, route-refresh, extended-message, operational,
  software-version, nexthop, link-local-nexthop.  Refused (config error) for add-path,
  graceful-restart, multi-session (has (2, 9)), aigp, link-local-prefer.
- (6, 1) syntax: `ipv4 unicast prefix-limit N;` on the family line, N in 1..2^32-1.
- After (2, 7) the peer is stopped (no automatic restart, back on reload).  After (6, 1)
  the normal reconnect backoff applies.
- Worked in the main tree, alongside the uncommitted BoRR work of another session.

What was built:

| Piece | Where |
|---|---|
| `RequirableValidator` (enable, disable, require) | `configuration/validator.py` |
| `ParseCapability.requirable` name to code map, schema leaves | `configuration/capability.py` |
| `NeighborCapability.required: frozenset[int]` (in copy and `__eq__`) | `bgp/neighbor/capability.py` |
| `_post_capa_required` turns require into enabled + required | `configuration/neighbor/__init__.py` |
| `Capabilities.tlvs(code)` | `open/capability/capabilities.py` |
| `Negotiated.unsupported_capability()` builds (2, 7), Data = our TLVs in OPEN order | `open/capability/negotiated.py` |
| `validate_open` raises it after `validate()` | `reactor/protocol.py` |
| peer `stop()` on (2, 7) | `reactor/peer/peer.py` |
| `Notify.UNSUPPORTED_CAPABILITY`, `MAXIMUM_NUMBER_OF_PREFIXES_REACHED` | `bgp/message/notification.py` |
| `prefix-limit` parsing (`FamilyLineValidator`), stored as a list of pairs in scope | `configuration/neighbor/family.py` |
| `Neighbor.prefix_limit` (not in `__eq__`: a reload applies it live), dump | `bgp/neighbor/neighbor.py` |
| `IncomingRIB.count_prefix` / `uncount_prefix`, independent of adj-rib-in | `rib/incoming.py` |
| `_limit_announce` / `_limit_withdraw` raise (6, 1), Data = `!HBI` | `reactor/peer/handlers/update.py` |
| Ledger: rfc5492 3 entries flipped + new MAY entry; rfc4486 enrolled (MUST + MAY) | `qa/rfc/` |
| Tests | `tests/unit/rfc/test_rfc5492_unsupported_capability.py`, `tests/unit/rfc/test_rfc4486_prefix_limit.py` |

Side effects worth knowing:

- A family line with a trailing token (`ipv4 unicast foo;`) used to be accepted silently.
  It is now refused, since the only thing allowed after a family is `prefix-limit N`.
- `validate()` still returns a tuple; the (2, 7) check is a separate method so the
  existing callers and tests of `validate()` did not change.  Three mocks in
  `test_protocol_handler.py` now also mock `unsupported_capability`.
- RFC 4486 is enrolled for section 4's subcode 1 sentences only.  The SHOULDs for the
  other Cease subcodes are not recorded yet.
- No functional (qa/encoding) test was added; the peer simulator is being edited by the
  BoRR session.

## Recent Failures

### 2026-09-27 Review finding: assert in `_limit_announce`

**Error:** `assert count == limit + 1` fails when a reload lowers a family's limit below
what the peer already holds: the neighbor is replaced live, the count is already past it.
**Cause:** the assertion assumed the limit never changes during a session.
**Status:** ✅ Fixed, assertion removed; any count past the limit raises (6, 1).
Test: `test_a_limit_lowered_by_a_reload_below_what_the_peer_holds_ends_the_session_cleanly`,
which failed with AssertionError before the fix.

## Resume point (2026-09-27)

`./qa/bin/test_everything`: all 25 steps pass (run outside the sandbox, which cannot bind
127.0.0.2).  Nothing committed.  The tree also holds the BoRR session's uncommitted work,
so a commit of this plan must stage only its own hunks: `peer.py`, `update.py`,
`incoming.py`, `plan/README.md` and `qa/rfc_compliance.json` carry both.  Suggested
split: one commit for (2, 7), one for (6, 1).  Then `git mv` this file to `done-`.

## Completed (2026-09-27)

Committed as two commits on main: `132f476c9` for (2, 7), and the (6, 1) commit after it.
Staged hunk by hunk, the BoRR session's changes to `peer.py`, `update.py`, `incoming.py`
and `plan/README.md` were left in the working tree.  Commit 1 was checked on its own in a
temporary worktree: unit tests, ruff and the RFC ledger pass.

Left for later, none of it owed by this plan:
- a functional (qa/encoding) test for either NOTIFICATION
- the RFC 4486 SHOULDs for the other Cease subcodes
- `doc/RFC_COMPLIANCE.md` regeneration, which the BoRR session also touches
