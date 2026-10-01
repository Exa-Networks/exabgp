# Bugs reported by agents

**Status:** ✅ Done 2026-10-01, fixed on main only (no 5.0 backport)
**Created:** 2026-10-01
**From:** agent reports, to look at the week of 2026-10-05

None of these has been reproduced yet. Each one is a claim to check against main first,
then fix with the test that fails without the fix, or close as not a bug.

## Reports

1. [x] 6.0 refuses an as-path containing a 4-byte ASN; 5.0 accepts it.
2. [x] `md5-password include "..."` sets the MD5 password to the literal word `include`.
3. [x] `configuration validate -nrv` crashes on a route with an AS_SET.
4. [x] In the environment file, `ack = true  # comment` is read as false.
5. [x] A program subscribed to `send { update; }` received an outgoing announce rendered as
   `withdraw`.
6. [x] The Graceful Restart capability JSON prints two flags swapped.
7. [x] `origin:65001:100` is printed as `origin:65001:0.0.0.100`.
8. [x] `family { ipv6 multicast; }` is refused, although `all;` negotiates it.
9. [x] `group start` and `group end` are unknown commands under API v4.

## Steps

1. [x] Reproduce each report on main, note the command and output under Progress
2. [x] Mark each one confirmed or not a bug
3. [x] Fix the confirmed ones, one test per fix, `./qa/bin/test_everything`

## Progress

Step 1 done 2026-10-01 on `e2142a435`. Configs used were written to `$TMPDIR`, recreate
them from the commands below.

1. ✅ Confirmed, worse than reported: a crash, not a refusal.
   `./sbin/exabgp encode "route 10.0.0.0/24 next-hop 1.2.3.4 as-path [65000 70000]"`
   raises `struct.error: 'H' format requires 0 <= number <= 65535` in `ASN.pack_asn`,
   from `AS2Path.make_aspath` (`configuration/grammar/types/bgp.py:477`), which packs with
   asn4 False. `[65000 65001]` encodes.
2. ✅ Confirmed, but there is no `include` directive in main or 5.0. The bug is that a
   one-word leaf drops extra words without an error: `md5-password include "secret";`
   validates and prints `md5-password "include";`. Look at how the engine hands words to
   `text()` (`grammar/types/word.py:171`), probably every single-word leaf is affected.
3. ✅ Confirmed. A neighbor with `route 10.0.0.0/24 next-hop 1.2.3.4 as-path [ 65000 ] ( 65002 65003 );`
   crashes `configuration validate -nrv` in `check_generation` (`configuration/check.py:221`):
   `ValueError: announce requires nexthop`. `as-path [ 65000 65002 ]` exits 0. Likely
   cause: the recode re-parses with receive rules, RFC 9774 (`as-set withdraw`) turns the
   route into a withdraw. Same family as 5.
4. ✅ Confirmed. `[exabgp.log] parser = true  # comment` gives False, `parser = true`
   gives True. `ConfigParser()` in `environment/config.py:435` has no
   `inline_comment_prefixes`, and `parsing.boolean` returns False for any unknown word
   instead of raising.
5. 🔶 Mechanism confirmed, not run in a live session. `Protocol.send()`
   (`reactor/protocol.py:218`) re-parses our own outgoing UPDATE with
   `Update.parse(self.negotiated)`, which applies the receive-side rules (RFC 7606,
   enforce-first-as, RFC 9774). An eBGP announce from local-as 65000 to peer-as 65001 with
   `as-path [65000]`, decoded with that neighbor's config, comes out as
   `"withdraw": { "ipv4 unicast": [ { "nlri": "10.0.0.0/24" } ] }`. So every eBGP
   `send { update; }` probably shows withdraws. Fix: parse sent messages without the
   receive-side checks, or hand the API the collection we sent.
6. ✅ Confirmed against RFC 4724 3. `capability/graceful.py` `json()`: the per-family bit
   0x80 is F (forwarding state) but prints `"restart"`; the header bit 0x8 is R (restart
   state) but prints `"forwarding"` under `restart-flags`. Same code in 5.0. Changes JSON
   API output: decide whether 6.0 only.
7. ✅ Confirmed. `extended-community [ origin:65001:100 ]` encodes right (type 0x00
   subtype 0x03, AS 65001, value 100) but prints `origin:65001:0.0.0.100`: `OriginASNIP`
   (`community/extended/origin.py:57`) reads the 4-byte local value as IPv4. RFC 4360 says
   it is a number. Same in 5.0. Check whether the parser also takes `origin:65001:1.2.3.4`.
8. ✅ Confirmed. `family { ipv6 multicast; }` gives "'multicast' is not valid for ipv6"
   (`grammar/tree/family.py`, only ipv4 has it, 5.0 too), while `all` lists it, so
   `validate -nrv` prints a config with `ipv6 multicast;` which cannot be read back.
9. ✅ Confirmed, by design in `e2142a435`: `dispatch_for` sends `group` to v6 only, under
   v4 `group start`/`group end` raise `UnknownCommand`. 5.0 had no `group`, so no 5.x
   helper breaks, but `done-api-group-command.md` targeted v4. Suspected real bug, not yet
   run: `group start` is API_AUTO, so `group start` / `announce route ...` (locks v4) /
   `group end` would refuse the `group end`. Decide with Thomas: allow `group` in v4.

### Step 3, 2026-10-01: fixes on main (Thomas: "fix on main only", no 5.0 backport)

Decisions taken from that answer: 6 is changed in 6.0 (CHANGELOG "Incompatible"), 9 lets
`group start`/`group end` through under API 4.

- 5 ✅ `Negotiated.outbound()` (direction OUT, own attribute cache off) and
  `Negotiated.from_peer`. `_parse_payload` skips the receiver's checks (next-hop-is-ours
  warning, RFC 7606 5.2 reset, treat-as-withdraw context, semantic filters) and
  `AttributeCollection._dropped_on_receipt` drops nothing when not `from_peer`.
  `Protocol.send()` parses with `self.negotiated.outbound()`, which also reads ADD-PATH as
  sent rather than as received. Test `tests/unit/test_sent_update_reported.py` (real
  Protocol, socket pair). Two tests built a `Direction.OUT` session to decode peer input
  (`test_otc_attribute.session`, `test_rfc9012_tunnel_encap.configured_session`): now IN.
- 3 ✅ `check_generation` decodes with `negotiated_out`. Test
  `tests/unit/test_validate_route_with_as_set.py`.
- 1 ✅ `grammar/types/bgp._as_path` packs four octet ASNs when one is above 65535.
  Test `test_as_path_syntax.test_a_four_octet_asn_is_read`.
- 4 ✅ `ConfigParser(inline_comment_prefixes=('#',))`. Test
  `tests/unit/test_environment_file_comments.py`. Not done: `parsing.boolean` still turns
  any unknown word into False without an error; refusing it is a separate change.
- 2 ✅ engine `_leaf` refuses words a value did not use. Accident row struck in
  `done-config-grammar.md` section 6; forms pinning it flipped to refused; frozen
  fixture regenerated (only test documents changed, no file in etc/ or qa/).
  Test `tests/unit/test_config_leftover_words.py`.
- 8 ✅ `ipv6 multicast` in `tree/family.SAFIS`. Test `tests/unit/test_family_ipv6_multicast.py`.
- 7 ✅ `OriginASNIP` renamed `OriginASN2Number`, `number` instead of `ip`. Expected outputs
  in `qa/encoding/conf-extended-attributes.ci` and `conf-flow-redirect.ci` rewritten; the
  dotted input form still parses. Test in `test_extended_community_four_octet_as.py`.
- 6 ✅ names swapped back in `Graceful.json()`. Tests in `test_rfc4724_graceful_restart.py`.
  The wiki (`Features/Graceful-Restart.md` line 603) documents the swap, needs updating.
- 9 ✅ `dispatch_for` sends `group` to v6 under every version. Tests in
  `test_api_version_detection.py`. The inline `group announce ...` is not a command in
  either dispatcher (v6 has `peer * group ...`); `qa/encoding/conf-mvpn.ci` only prints it.

## Failures

### 2026-10-01 `test_unread_bytes_counts_what_the_reader_left` fails on macOS

**Error:** `assert 0 in (15, -1)`, FIONREAD on the write end of a pipe answers 0.
**Cause:** not these changes, the test came with `e2142a435`.
**Status:** ⏸️ reported to Thomas, not fixed here.

### 2026-10-01 `test_everything` refuses to start

**Error:** 127.0.0.2 cannot be bound, needs `sudo ifconfig lo0 alias 127.0.0.2 up`.
**Status:** ⏸️ every step run one by one instead.

## Blockers

~~Decisions for Thomas: 6 (JSON change, 6.0 only?), 9 (`group` in v4?).~~ Answered: fix on main only.

## Resume Point

~~Step 3. Suggested order: 5 and 3 (same root, 5 hits every eBGP send), 1, 4, 2, 8, 7.~~

All nine fixed, uncommitted. Remaining: full `test_everything` once 127.0.0.2 is aliased, then commit when Thomas asks.
