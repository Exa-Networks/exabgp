# Audit bugs not covered by tests, checked against the RFCs

**Status:** 🔄 WIP
**Created:** 2026-10-07
**Base:** `c0c50ee35`

Six read-only audits (2026-10-06) found bugs that no test covers, each reproduced. Three more
(2026-10-07) checked the RFC-based ones against the RFC text. Reproduction scripts were left in
`$TMPDIR/audit/`, `$TMPDIR/aud/` and `$TMPDIR/v/`; they are scratch and may be gone, so each item
below carries enough to rebuild its reproduction.

## Decisions (Thomas, 2026-10-07)

- A peer that sends no Multiprotocol capability gets IPv4 unicast implicitly, when we have it.
- `inherit` inside a template is supported: nested, with a depth bound and cycle detection.
- Numbers in the configuration are ASCII digits only: no `_`, no sign, no other Unicode digits.
- One commit per area, nothing pushed.

Not changed, the RFC allows what we do:
- Cisco route refresh (code 128) alone negotiates no refresh (RFC 2918 defines only code 2).
- Bytes after the OPEN optional parameters (no RFC sentence makes them an error).

## Rules for every fix

- A test which fails without the fix (EXA_STYLE). RFC-backed ones carry `@pytest.mark.rfc(...)`,
  with `polarity='negative'` where the RFC forbids something. Read `qa/rfc/README.md` first.
- Correct the ledger notes found wrong, add the missing ledgers.
- Malformed peer input raises `Notify`. Bound every loop. Functions under 70 lines.

## Area 1: negotiation, OPEN, NOTIFICATION, timers

1. [ ] `negotiated.py:318` router-id collision uses `received_open.asn` (AS_TRANS for 4-octet). Use the
   negotiated peer AS. RFC 6793 4.1 MUST, RFC 6286 2.2. Also with `peer-as auto`.
2. [ ] `negotiated.py:178` no MP capability from the peer: IPv4 unicast implicit (decision above).
3. [ ] `negotiated.py:271` multisession compares MultiProtocol lists in order: compare as sets.
   Draft section 7 item 1.
4. [ ] AS 0 from the peer (My AS 0, or AS_TRANS with ASN4 capability 0) must be refused 2/2.
   RFC 7607 2 MUST. New `qa/rfc/rfc7607.toml`.
5. [ ] `negotiated.py:552` ADD-PATH Send/Receive outside 1..3 used as bitmask: ignore that entry.
   RFC 7911 4 SHOULD, the ledger entry has no test.
6. [ ] `notification.py:163` non-printable check runs on `str(bytes)`: control characters reach
   the log. `:195` decodes as ASCII, so RFC 9003 UTF-8 text is logged as hex. RFC 9003 2.
7. [ ] `protocol/ip/address.py:189/209` `IP.__eq__` ignores the class, `__hash__` uses it.
8. [ ] Graceful restart time inferred from hold-time is masked with 0x0FFF (5000 -> 904):
   clamp to 4095 (`neighbor.py:241`, `graceful.py`). RFC 4724 3.
9. [ ] Hold time 0: the second KEEPALIVE received raises Notify(2,6) (`bgp/timer.py` check_ka).
   RFC 4271 8.2.2 says restart the hold timer only if non-zero, remain Established.
10. [ ] Ledger: `rfc4271#6.2-bad-bgp-identifier` note misquotes RFC 6286; `rfc9003#2` note.

## Area 2: reactor, FSM, API

1. [ ] `peer.py:694` no hold timer in OpenConfirm. RFC 4271 8.2.2: Hold Timer Expired 4/0.
2. [ ] `peer.py:612` collision: the existing connection is closed without Cease, the running task is
   orphaned and later acts on the new proto (4/0 on a connection we never sent OPEN on). RFC 4271
   6.8 and RFC 4486 (6/7 Connection Collision Resolution). Collision only in OpenSent/OpenConfirm.
3. [ ] Process shutdown and `peer.remove()` send no Cease: `_stop` clears `proto` before the 6/3
   is set. RFC 4486: 6/2 Administrative Shutdown on shutdown, 6/3 Peer De-configured on removal.
4. [ ] `api/command/limit.py:171` `neighbor * peer-as X` ignores the qualifiers.
5. [ ] `limit.py:181` empty selector `peer [ ]` selects every peer: refuse it.
6. [ ] `peer delete <selector>` / v4 `neighbor X delete` can never succeed (`dispatch/v6.py:103`,
   `command/peer.py:365`).
7. [ ] `reactor/loop.py:271` `signal.rearm()` runs before the pending adj-rib-out `continue`:
   reload/SIGUSR dropped.
8. [ ] `api/command/reactor.py:88,98,108` `daemon reload/restart` overwrite a pending shutdown.
9. [ ] `reactor/asynchronous.py:158/169/179` coroutine popped on the 50th iteration is lost, and the
   generator branch skips `applying_commands`.
10. [ ] `api/command/rib.py:113` `exabgp_api_chunk` 0 or negative loops forever: validate >= 1.
11. [ ] `application/server.py:104` `--once` sets `tcp.once` after setup, never read. Env file
   `tcp.once` ignored. `exabgp_tcp_connections=abc` raw ValueError (`environment/config.py:484`).
12. [ ] `reactor/protocol.py:71` reads `os.environ` for the port, not the environment: env file
   `tcp.port` moves only the listener.
13. [ ] `processes._command_queue` unbounded: cap it with a named constant.

## Area 3: MP_REACH, next hops, attributes

1. [ ] `attribute/mprnlri.py:282` extended next hop: gate per negotiated (AFI, SAFI, NH AFI) and the
   lengths RFC 8950 3 allows (16/32, VPN 24/48); EVPN/VPLS/BGP-LS raise KeyError. RFC 8950 3 MUST,
   RFC 7606 7.11 MUST. New `qa/rfc/rfc8950.toml`.
2. [ ] VPNv6 next hop: RFC 4659 3.2.1.1 is 24 or 48 (RD+global+RD+link-local), not 40
   (`protocol/family.py:387`, send side `nlri/collection.py` `_encode_nexthop`). Check both RDs zero.
   Fix the `rfc4659#3.2.1.1` note.
3. [ ] Send side: an IPv4 route with an IPv6 next hop needs extended next hop negotiated for it
   (RFC 8950 4 MUST). An IPv6 route with an IPv4 next hop goes out as IPv4-mapped IPv6, 16 octets
   (RFC 2545 3, RFC 8950 4 / RFC 4798). New `qa/rfc/rfc2545.toml`.
4. [ ] `attribute/collection.py:735` RFC 7606 3(g): a malformed first copy (stored as Discard /
   TreatAsWithdraw under its own ID) lets a later copy through. Track seen attribute codes.
5. [ ] `aigp.py` keeps only the first TLV: every TLV must be passed along unchanged. RFC 7311 3, 3.2.
   New `qa/rfc/rfc7311.toml`.
6. [ ] SR Policy sub-TLV decoders return defaults on wrong lengths (srv6_binding_sid, enlp, priority,
   binding_sid, segment_list weight and types A..K): MalformedSubTLV / treat-as-withdraw. RFC 9012
   13, RFC 9830 lengths and 5.
7. [ ] TunnelEncap / SR Policy equality and `AttributeCollection.index()` built from `str()`, which
   drops SIDs, algorithm, flags: a changed policy is never re-sent. `GenericTunnelTLV.__str__` has
   no payload, `GenericSubTLV` has no `__str__`. Make str complete, or compare on packed bytes.
8. [ ] `sr/srv6/sidinformation.py:141` unknown sub-sub-TLV makes invalid JSON; flags hard-coded 0.
9. [ ] `sr/prefixsid.py:133` str drops TLVs (affects index, so routes may share attributes wrongly).
10. [ ] Route-origin extended communities define `__eq__` without `__hash__` (`ec.py`).

## Area 4: NLRI

1. [ ] `inet.py` / `ipvpn.py` label loop cuts a two-label stack after the first label; `mprnlri.py:146`
   passes `Negotiated.UNSET`. Honour Multiple Labels (RFC 8277 2.1, 2.3 MUST) and read to the S bit.
   Fix `rfc8277#2.1` note and file header.
2. [ ] Host bits past the prefix length kept in index/str/eq (RFC 4271 4.3, RFC 4760 5): mask them.
3. [ ] `vpls.py:240` `len(data) != length + 2` refuses a second VPLS NLRI.
4. [ ] `configuration/grammar/tree/l2vpn.py:43` VPLS label base capped at 16 bits, RFC 4761 says 20.
5. [ ] EVPN `index()` includes labels, ESI (type 2), gateway (type 5): use the RFC 7432 7.1/7.2/7.4
   and RFC 9136 3.1 route keys. Type 1 and type 4 `__eq__`/`__hash__` ignore the ESI.
6. [ ] EVPN MAC/IP Label2 missing from JSON/str; MAC str always `/48`.
7. [ ] EVPN type 5 prefix length beyond the family accepted (RFC 9136 3.1 MUST NOT > 128, 0..32 v4).
8. [ ] MUP T1ST str uses `prefix_ip_len` for the endpoint, JSON `"source_ip": "b''"` (and
   `qa/encoding/conf-srv6-mup.ci:22` expects it); T2ST `__eq__` compares `endpoint_len` with itself.
9. [ ] Label / IPVPN `__hash__` on `_packed` (labels) while `__eq__` uses `index()`.
10. [ ] Flow protocol, icmp-type, icmp-code, next-header > 255, traffic-class > 63 (RFC 8956 type 11 is
   DSCP), tcp-flags >= 0x1000 (data offset nibble): refuse at parse. Fix `rfc8955#4.2.2.9` note.
11. [ ] `RTC.__len__` returns bits.

## Area 5: configuration and environment

1. [ ] `grammar/tree/static.py:386` `split` unbounded: cap the number of routes; refuse split
   shorter than the prefix.
2. [ ] `_check_routes` (`grammar/tree/neighbor.py:347`): refuse a link-local next hop without the
   link-local next-hop capability; refuse an IPv4 route for a non-negotiated family (like IPv6);
   refuse an IPv4 route with an IPv6 next hop without `nexthop` for that family.
3. [ ] `Neighbor.__eq__` ignores md5-base64, tcp-ao, add-path, nexthop block, prefix-limit, so
   reload does not re-establish.
4. [ ] `next-hop self` with `local-address auto` resolves to the router-id on an IPv4 session
   (`bgp/neighbor/session.py:205`).
5. [ ] Repeated attribute statement silently first-wins (extended-community merges): merge list
   attributes (community, large-community, extended-community), refuse repeats of single ones.
6. [ ] Scoped IPv6 (`fe80::1%en0`) silently rewritten on macOS: refuse `%`.
7. [ ] Numbers: ASCII digits only everywhere (decision above), `grammar/types/word.py:108`.
8. [ ] Template lists shared between neighbours (`grammar/tree/resolve.py` `transfer`).
9. [ ] Nested `inherit` in templates (decision above).
10. [ ] Explicit next-hop for IPv6 route given as IPv4 address: see area 3.3 for wire encoding.

## Area 6: RIB, CLI, application, logger

1. [ ] `rib/outgoing.py` A, B, A in one batch leaves the peer with B when no role negotiated.
2. [ ] `rib/__init__.py` `RIB.enable()` cached branch and `make_rib()` never update the cache flags
   on reload.
3. [ ] `configuration/setup.py:93` `decode -i` / `encode -i` never set the add-path capability.
4. [ ] `application/shortcuts.py` `a r` -> router-id, `a v` -> vps, `a o` -> operation,
   `announce r r`, watchdog names and trailing `n`/`ne` expanded.
5. [ ] `configuration/check.py:315/343` `raw[18]` on a short header; KEEPALIVE reported unknown.
6. [ ] `healthcheck.py:357/378` enumerates every address of `--ip` prefix; removes pre-existing
   addresses on exit; `--path-id 0` dropped.
7. [ ] `logger/option.py` `host:` destination writes a local file: implement remote syslog.
8. [ ] `application/encode.py:41` `-a` / `-z` out of range: argparse error, not traceback.
9. [ ] `RIB.clear()` in `check_generation` wipes the original neighbour cache / KeyError.

## Progress

2026-10-07: every area fixed in its own worktree, cherry-picked onto main:
- area 1 `9ef3a6787`, area 2 `4ff4bd294`, area 3 `ce61dc283`, area 5 `ca8a123d7`, area 4 `880b376ac`,
  area 6 `dec08b1c0`. Worktrees removed.
- `legacy.json` conflicted twice (areas 3+5, 4); regenerated on the merged tree each time, the diff
  matched the area's own. `l2vpn.py`: kept area 5 `decimal()` with area 4 `maximum`.

Decisions taken by the agents, against or beyond the plan wording:
- 1.5 ADD-PATH: an out-of-range value ignores the whole capability (RFC 7911 4 "the capability").
- 2.x OpenConfirm with hold time 0 is bounded by `bgp.openwait`; Cease only once our OPEN is out;
  shutdown with GR established closes without Cease; collision in OpenSent keeps the incoming one.
- 3.6 malformed SR Policy sub-TLV kept as unrecognised (RFC 9012 13), not treat-as-withdraw
  (RFC 9830 5). Open question for Thomas.
- 3.3 receive: a 4-octet next hop on IPv6 still accepted when both sides negotiated `<2,x,1>`.
- 5.3 prefix-limit left out of `Neighbor.__eq__`: pinned by an RFC 4486 test, applies on reload.
- 5.4 `next-hop self` with `local-address auto` on IPv4 is refused (cannot resolve at load).
- 4.10 traffic-class 101 changed to 46 in `etc/exabgp/conf-flow.conf` and `qa/encoding/conf-flow.ci`.

Left over, found while fixing:
- `rib/cache.py` `in_cache`: a labelled route re-announced with only a new label is skipped.
- an incoming connection accepted while our outgoing connect is in progress is overwritten when
  the connect completes (pre-existing leak, area 2 noted).
- RFC 7607 UPDATE rules (AS 0 in AS_PATH, AGGREGATOR, AS4_*) recorded as `gap`.

## Failures

## Resume point

Area agents run in worktrees, one branch each; merged onto main area by area, then
`./qa/bin/test_everything`.
