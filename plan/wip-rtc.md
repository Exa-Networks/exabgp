# RTC: Route Target Constraint (RFC 4684, issue #1109)

**Status:** 🔄 Active
**Started:** 2026-09-26

## Goal

Let an operator or an API program announce and withdraw RT membership (AFI 1, SAFI 132),
and read what a peer sends, correctly. Signal only: ExaBGP does not filter the VPN routes
it sends by the membership it learns (RFC 4684 section 5 MAY, "discouraged").

## Decisions (agreed with Thomas)

- Scope: signal only. Outbound VPN filtering is recorded as a gap in the ledger.
- Syntax, keyword form, `origin-as` because `origin` is the ORIGIN attribute, which every
  RTC UPDATE carries (RFC 4760 section 3):

  ```
  family { ipv4 rtc; }
  announce ipv4 rtc origin-as 65001 route-target 65001:100 next-hop self
  announce ipv4 rtc default next-hop self
  withdraw ipv4 rtc origin-as 65001 route-target 65001:100
  ```

- JSON of a full RTC route is unchanged: `{ "origin": 65001, "route-target": "65001:100" }`.

## Found while surveying

- 🐛 `RTCBase.unpack_nlri` reads 13 octets for any length 32-96. RFC 4684 section 4 makes it
  a prefix of `ceil(length / 8)` octets, so a 32-95 bit prefix misreads every NLRI after it.
- The wiki page RT-Constraint.md documents `announce rtc 65001:100`, which never existed.
- End-of-RIB is already sent for every negotiated family unless manual-eor.

## Tasks

- [x] Fix prefix decode (32-95 bits), with its test
- [x] RTCSettings + RTC.from_settings
- [x] `ipv4 rtc` family keyword
- [x] `announce ipv4 rtc` (config announce block and API), schema-driven
- [x] `static { rtc ... }`
- [x] Functional encoding + decoding tests (conf-rtc.ci, bgp-rtc-1), test_api_encode taught rtc
- [x] qa/rfc/rfc4684.toml + text, enrolled
- [x] CHANGELOG, man page, etc/ example, wiki page (rewritten: the old one was mostly invented)
- [ ] Full ./qa/bin/test_everything clean run. Steps 1-14 passed (decoding: 23/23 incl. bgp-rtc-1);
  step 14 was marked failed only for six leftover processes from a concurrent 5.0 run, so steps
  15-25 (functional encoding incl. conf-rtc.ci) did not run. A clean run is being done from the
  other session.

## Found on the way

- 🐛 Fixed, own commit: `target:`/`origin:` with a four octet AS was encoded as the IPv4 address
  type (0x01). Now RFC 5668 type 0x02. Behaviour change, CHANGELOG Incompatible + wiki.
- RTC uses an MP-only next-hop leaf: the IP schema's `next-hop` also adds a NEXT_HOP attribute,
  which mpls-vpn (and other MP families built on AnnounceIP) still emit next to MP_REACH_NLRI,
  against RFC 4760 3 "SHOULD NOT". Not fixed here: follow-up.

## Recent Failures

(none yet)

## Resume Point

Committed: four octet AS fix, then RTC. Remaining:
- the clean full-suite run (above)
- decision pending with Thomas: keep RTC in the default family set? It is negotiated by default
  (5.0 too) and a route reflector filtering by membership then sends nothing to a speaker which
  announced none. Documented on the wiki RT-Constraint page ("Negotiated but Silent").
- follow-up: MP families built on AnnounceIP still emit NEXT_HOP beside MP_REACH_NLRI.
