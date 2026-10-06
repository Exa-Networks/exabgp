# Multisession: one session per family, and the Cisco code

**Status:** ✅ 3.19 committed in both trees (main `ff2e545f7`, 5.0 `e1ca58e85`); 3.18 fixed in main, won't fix in 5.0. The draft's collision procedure stays a gap, see the ledger.
~~**Status:** 🚧 3.19 fixed in both trees (uncommitted); 3.18 fixed in main, won't fix in 5.0~~
**Created:** 2026-09-29
**Trees:** main and 5.0. 3.18 is fixed in main already (`f644fa735`, 2026-09-28).
**Background:** `plan/wip-two-tree-parity.md` §19 and §24.
**Priority:** low. The draft (draft-ietf-idr-bgp-multisession-07) expired in 2013 and is not
deployed; exabgp may be its only implementation.

---

## 3.19: exabgp never sends Cisco code 131 (fixed 2026-09-29, uncommitted)

`Capabilities._session()` only ever adds code 68 (`MULTISESSION`). A Cisco router offers 131
alone. `Negotiated` then finds neither code on both sides, and because we announced 68 it
answers `Notify(2, 9)` "multisession is mandatory with this peer". Inferred from
`negotiated.py:226-269`, not reproduced against a router.

What Cisco sends, from a real capture (PacketLife `4-byte_AS_numbers_Full_Support.cap`, frames
2 and 3, see §24): `02 03 83 01 00`, capability 131, length 1, one flags octet, no Session ID.

### Proposed fix

- `_session()` offers both codes: 68 with its Session ID as today, and 131 in Cisco's layout
  (the flags octet alone). The instance carries `ID = MULTISESSION_CISCO` so `json()` and
  `__str__` report the Cisco variant.
- `Negotiated` needs no change: it already prefers 68 when both sides have it and falls back
  to 131.
- A peer which does not know 131 ignores it (RFC 5492 section 3), so RFC-style peers are not
  affected. Our OPEN grows by 3 octets for every neighbour with `multi-session` enabled.

### Tests

- Unit: an OPEN carrying only `02 03 83 01 00` (the capture) negotiates multisession instead
  of `Notify(2, 9)`. Fails at HEAD.
- Unit: our OPEN with `multi-session` enabled carries both 68 and 131.
- Functional: every capture of an OPEN with multisession changes (`api-multisession` and any
  `conf-*` using it). Re-record against a read-only HEAD control, as §23 describes.
- 5.0: same fix and regression test. Allowed under maintenance mode as a bug fix.

---

## 3.18: multisession with N families keeps one neighbour, not N (main fixed, 5.0 open)

With `capability { multi-session enable; }` and two families,
`configuration/neighbor/__init__.py` deep-copies the neighbour per family and narrows only
`rib.outgoing.families`. `Neighbor.name()` is built from `families()`, which is unchanged, so
every copy has the same name and `self.neighbors[name]` keeps the last one. Measured: one
neighbour, outgoing families `{ipv6 unicast}`, OPEN still announcing both families.

5.0 has the same code (`neighbor.py:180`, `configuration/neighbor/__init__.py:351`).

**main: fixed** in `f644fa735` (2026-09-28), option 1 below: `session_of()` in
`configuration/grammar/install.py` narrows each copy to its family (families, ADD-PATH, next-hop
families) and its name ends `family-allowed <afi>-<safi>`. Still missing on the passive side:
the listener gives an incoming connection to the first neighbour whose addresses match, before
its OPEN is read.

### 5.0: won't fix (Thomas, 2026-09-29)

Multisession is not used and is niche; no point changing it on a maintenance branch. The
options considered are kept below for the record.


A fix changes how many TCP sessions a configuration opens: one per family instead of one.
Options:

1. **Fix it as the draft intends.** Each per-family copy gets its own name (the family in
   `name()`), its own OPEN announcing only its family, and its own session. Needs the
   listener to route an incoming connection by OPEN rather than by address, which §24 lists
   as a gap (§6 collision handling).
2. **Refuse the configuration.** `multi-session` with more than one family is rejected at
   parse time with a message saying it is not supported. Honest, and small.
3. **Leave it.** Document that multisession opens one session carrying the last family.

Recommendation for 5.0: 2, the smallest change a stable branch can take, and it replaces silent
misbehaviour with an error. Porting main's `f644fa735` is option 1, but it changes how many
sessions a 5.0 configuration opens.

---

## Progress

- [x] 3.19 5.0: `capabilities._session()` offers 131 too; 3 tests in
      `tests/unit/test_multisession_session_id.py`, 2 failing at HEAD; 5.0.14 changelog entry.
      Full 5.0 suite green (pytest 8260, functional encoding/decoding/parsing, gates).
- [x] 3.19 main: same fix; 2 tests in `tests/unit/rfc/test_draft_multisession.py`, both
      failing at HEAD, the second on the real Cisco OPEN from the capture.
- [x] 3.18 main: fixed in `f644fa735`
- [x] 3.18 5.0: won't fix (Thomas, 2026-09-29)
