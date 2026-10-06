# FlowSpec: a one-octet component decoded from a wider value cannot be sent again

**Status:** ✅ Done, committed in `c7b78df37` (fix: refuse a flow component value too large for its field)
~~**Status:** ✅ Fix and tests done, test_everything passes (25/25), not committed~~
**Last Updated:** 2026-09-29
**Created:** 2026-09-29
**Tree:** main only. 5.0 has the same bug and keeps it (maintenance mode, not reachable from
anything seen so far).
**Background:** `plan/wip-two-tree-parity.md` §12, "Latent, or blocked".

---

## The defect

RFC 8955 section 4.2.1.1 lets the operator octet announce a 1, 2, 4 or 8 octet value, and
main's decoder reads whichever width is announced (`flow.py:1207-1230`, deliberately, since
`e7781454b`: refusing a wide encoding silently dropped a port 80 sent in four octets).

Six components encode one octet only, through `IOperationByte.encode()` (`flow.py:503`):
`FlowIPProtocol`, `FlowNextHeader`, `FlowICMPType`, `FlowICMPCode`, `FlowDSCP`,
`FlowTrafficClass`. A value above 255 sent in two or more octets decodes, renders as text, and
then raises on `pack()`:

```
>>> FlowIPProtocol(0x01, NumericValue(262)).pack()
ValueError: bytes must be in range(0, 256)
```

Reproduced 2026-09-29. `str()` gives `=262`.

DSCP is narrower still: six bits, so anything above 63 is meaningless even when it fits.

## To find out first

Which paths re-pack a received flow route. If received NLRI keep their wire bytes
(packed-bytes-first), the crash needs a re-encode: route reflection of a received flow, the API
echoing a received route back as a command, or `configuration validate` on a route written
from received JSON. The fix is the same either way; reachability decides how the regression
test is written.

## Options

1. **Refuse on decode.** A value that does not fit the component's field (above 255, or above
   63 for DSCP) is a malformed component, answered the way main already answers other
   malformed flow components (check the RFC 8955 error-handling text before choosing
   between treat-as-withdraw and `Notify(3, 10)`). Nothing unencodable gets into the RIB.
2. **Encode wide.** Let the six components write two octets when the value needs it. Keeps
   the route, but sends a value no protocol field can carry.
3. **Refuse on configuration only.** Leaves the received-route path as it is.

Recommendation: 1. Protocol, next header, ICMP type and code are one octet on the wire of the
packet being matched, so a larger value can never match anything; accepting it helps no one.

## Tests

- Unit, per component: a two-octet value above the field width is refused on decode
  (fails at HEAD by decoding, then raising on `pack()`).
- Unit: the same value in range but sent in two octets still decodes (the `e7781454b`
  behaviour stays).
- RFC ledger: tie the tests to the RFC 8955 section 4.2.1.1 entries.

## Progress

- [x] Reachability traced
- [x] Fix + tests
- [x] `./qa/bin/test_everything` (25/25, 2026-09-29)

## Findings (2026-09-29)

- **Wider than six components.** Probing every operation class with a value one past its
  encodable width: 13 of 14 raise on `pack()`. `IOperationByteShort` (ports, packet-length,
  tcp-flags) raises `struct.error` for a four octet value above 65535, `IOperationLong`
  (flow-label) for an eight octet value above 2^32. Only DSCP and fragment are safe, because
  their decoders mask.
- **Reachability: latent crash, live disagreement.** `Flow.unpack_nlri` keeps the wire bytes
  and `pack_nlri` echoes them while `_packed_stale` is false, so a received flow never goes
  through `IOperation.pack()` and does not crash today. Nothing outside the configuration
  calls `add()` or the `rd` setter on a received flow. What does happen: the route is
  accepted, held, reflected verbatim, and rendered to the API as `protocol =262`, which the
  configuration grammar refuses (checked with `exabgp encode` for protocol, icmp-type,
  destination-port, packet-length, tcp-flags, traffic-class, flow-label). Option 3 already
  exists: the grammar bounds every one.
- **Error handling.** RFC 8955 section 10 defers to RFC 7606. `_parse_operations` raising
  `Notify(3, 10)` becomes `NLRI.INVALID` in `unpack_nlri` (treat-as-withdraw), the same
  answer every other malformed component gets. No session reset.
- **Ledger.** No RFC 2119 keyword covers it (section 4.2's "not encoded as specified" is
  keyword-less, and the 4.2.1.1 entries are the AND bit and the reserved bit), so the tests
  carry no `rfc()` marker, like the section 4.1 tests. A line was added to the no-keyword
  list at the top of `qa/rfc/rfc8955.toml`.

## Decision

Option 1, generalised: `IOperation.value_limit()` is `1 << 8 * max(VALUE_SIZES)`, so the
bound is whatever the class can encode, one source for both directions.
`_parse_operations` refuses a decoded value at or above it with `Notify(3, 10)`.

Not done, deliberately: bounds narrower than the encoding (flow label is 20 bits, RFC 8956
3.7; TCP flags 12). A flow label of 2^20 in four octets still decodes and re-packs fine, so
it is only the grammar disagreement, not the crash. Separate plan if wanted.

## Tests

`tests/unit/rfc/test_rfc8955_flowspec.py`, section "4.2.1.1, a value wider than its field",
parametrised over the 11 unmasked components of both families:
- `test_a_value_too_large_for_its_field_is_refused`: 11 failed at HEAD, pass with the fix.
- `test_the_largest_value_of_a_field_sent_wide_still_decodes_and_packs`: the `e7781454b`
  behaviour, passed before and after.
