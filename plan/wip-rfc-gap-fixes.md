# Closing the RFC ledger gaps

🔄 **Status:** In progress, 3 of 8 areas done (3 uncommitted, awaiting review)
**Branch:** ~~`claude/pensive-rubin-95pg84` (merged with main at `afe4003`)~~ squash-merged as
#1432 (`acbcf24`). From 2026-09-28 the work continues on the local machine, on `main`,
uncommitted until Thomas asks.
**Started:** 2026-09-28
**Out of scope:** the multisession draft, handled elsewhere

---

## Goal

Every `status = "gap"` entry in `qa/rfc/*.toml` (the multisession draft aside), and every
`required` entry which only a strict xfail shows, is implemented, so its test passes and the
ledger says `required`.

## How the work is shaped

- Each gap already has a test carrying `@pytest.mark.rfc('<id>')` and
  `@pytest.mark.xfail(strict=True, ...)` in `tests/unit/rfc/`. It asserts the RFC
  behaviour and fails today. `qa/bin/check_rfc_compliance` accepts a test on a gap only
  when it carries xfail.
- To close a gap:
  1. implement the behaviour in `src/`
  2. remove the `xfail` from its test(s)
  3. flip the ledger entry from `gap` to `required`, rewrite its `note`
  4. a binding (MUST/SHALL) entry with polarity `both` needs a positive AND a negative
     non-xfail test: add the missing side
  5. `./qa/bin/check_rfc_compliance --update-baseline` (a count may fall, never rise)
- If a test's premise turns out wrong (it contradicts the RFC or another RFC), fix the test,
  not the code, and say so in the commit. This happened for RFC 4456 (see Progress).
- Behaviour a user can see changing (a route dropped, an attribute discarded) goes in
  `doc/CHANGELOG.rst`; a new neighbour option also goes in `doc/man/exabgp.conf.5`.
- A new neighbour option lives in the grammar: a `Leaf` in
  `src/exabgp/configuration/grammar/tree/neighbor.py`, its keyword in `POLICY` of
  `grammar/tree/codecs.py`, its accepted/refused forms in
  `tests/unit/config_grammar/forms_neighbor.py`, then regenerate the frozen outcomes (below).

List what is still open:

```bash
env exabgp_log_enable=false uv run pytest tests/unit/rfc -q -rx | grep XFAIL
./qa/bin/check_rfc_compliance --report     # the gaps column: demonstrated/total per RFC
```

---

## Progress

| # | Area | Status | Commit |
|---|------|--------|--------|
| 0 | Strict xfail test for every gap, checker change | ✅ | `91358c5` (#1431), `eee31dd` |
| 0 | Test BGP server falls back to IPv4 without IPv6 | ✅ | `6968bfc` |
| 1 | Received attributes | ✅ | `95dd8d8` |
| 2 | Received NLRI | ✅ | `df87c44` |
| 3 | Outgoing routes / adj-rib-out | ✅ uncommitted on main | |
| 4 | RFC 8277 Multiple Labels Capability | ❌ todo | |
| 5 | FlowSpec | ❌ todo | |
| 6 | Graceful Restart receiving procedures | ❌ todo | |
| 7 | EVPN and Prefix-SID | ❌ todo | |
| 8 | BGP-LS, capability retry, four-octet AS | ❌ todo | |

### Done, and the decisions taken

**1. Received attributes (`95dd8d8`)**
- RFC 7606 7.5/7.9/7.10: LOCAL_PREF, ORIGINATOR_ID, CLUSTER_LIST from an external neighbour
  are dropped before decoding. `Negotiated.is_internal_neighbor` = iBGP or confederation
  member (RFC 5065 5.2/5.3). Decision: a confederation member counts as internal for all
  three and for the tunnel-encapsulation default.
- RFC 9012 11: neighbour option `tunnel-encapsulation <auto | filter | accept>;`, default
  `auto` filters on eBGP only. Not done (not in the ledger): outgoing filtering, and the
  Encapsulation Extended Community.
- RFC 9234 5: OTC(remote AS) added on ingress from Provider/Peer/RS, on a copy of the
  attributes (the session attribute cache is shared).
- RFC 6514 5: every treat-as-withdraw / attribute-discard logs `attribute.malformed` at
  ERROR. Decision to review: a misbehaving peer can fill the log.
- RFC 4456: the xfail expecting two ORIGINATOR_IDs to withdraw the route was wrong, RFC 7606
  3(g) keeps the first and discards the rest; the test now proves that.

**2. Received NLRI (`df87c44`)**
- RFC 7606 5.2: treat-as-withdraw with no reachable NLRI resets the session. A zero length
  AGGREGATOR (7.7 attribute discard) is discarded, not withdrawn, so it does not reset.
- RFC 7606 5.4 / RFC 6514 4.5: `NLRI.discard_on_receipt()` drops an unknown EVPN/MVPN route
  type and an SSM-range Source Active route, logged; the configuration refuses to announce
  an SSM-range Source Active route (`grammar/tree/select.py` `mvpn_source_ad`).
- RFC 4271 4.3: a prefix withdrawn and announced in one UPDATE is only announced.
  RFC 4271 6.3: an IPv4 NLRI-field route with a 0.0.0.0 or multicast NEXT_HOP, or a
  multicast prefix, is ignored.
- `reactor/protocol.py`: an UPDATE carrying a Discard marker is no longer ignored whole.

---

## Remaining work (resume here)

Each area below is independent. Do one per commit. The xfail tests named are the spec.

### 3. Outgoing routes / adj-rib-out

**Session 2026-09-28 (2), decisions taken with Thomas:**
- Found: no real code path puts received attributes into another neighbour's outgoing RIB.
  Everything there comes from the configuration or from API text, which is re-parsed. Only
  the tests hand `Update.parse()` output to `rib.outgoing`.
- RFC 1997 and RFC 7911: `AttributeCollection` decoded off the wire records the peer it came
  from (`learned_from`); the outgoing RIB applies the well-known communities and generates
  its own Path Identifier only for those. Configured and API routes are originated by us and
  unchanged (`community no-export` towards a transit stays usable for RTBH and TE).
- RFC 4360 6: strip non-transitive extended communities at the AS boundary only on received
  routes. Configured link-bandwidth (0x40/0x04, non-transitive, meant for the eBGP DMZ) keeps
  going out. The xfail test built its route locally: rewrite it through a real decode.
- RFC 4684 5: a neighbour option, default off, so behaviour is unchanged. When on and rtc is
  negotiated, VPN routes are filtered by the peer's membership, and re-evaluated when the
  membership changes.

**Area 3 as implemented (uncommitted, 2026-09-28):**
- `AttributeCollection.learned_from` (set in `unpack` from `Negotiated.peer_address`, kept by
  `copy()`), `community_forbids()`, `route_targets()`.
- `OutgoingRIB._export_allowed` = community + OTC + membership. `_otc_advertised` renamed
  `_policy_advertised` (a route a policy may refuse later, so the refusal withdraws it);
  `_policy_may_refuse` decides which families record there.
- RFC 4360: `pack_attribute` strips non-transitive extended communities for a received
  route towards EBGP outside the confederation (`ExtendedCommunities.transitive_only`).
  IPv6 extended communities (RFC 5701) not touched.
- RFC 7911: `OutgoingRIB._readvertised` maps (peer, received route index) to a Path
  Identifier it allocates (free list, `PATH_IDENTIFIER_MAX`), on add and on withdraw;
  `NLRI.carries_path_info()` / `with_path_info()`, implemented by INET.
- RFC 4684: `route-target-filter <bool>` (grammar Leaf, POLICY, NeighborSettings, Neighbor,
  printed config), refused without adj-rib-in and adj-rib-out. `RTC.admits()` does the
  prefix match. Filtered families: IPv4/IPv6 mpls-vpn and EVPN
  (`MEMBERSHIP_FILTERED_FAMILIES`). `UpdateHandler._membership` calls
  `outgoing.membership_changed()` (a resend of those families) when an RTC NLRI arrives.
- Ledger: rfc1997 x4 and rfc7911 and rfc4360 -> required, positive-only (binds what we
  send, no peer input violates it). rfc4684#5 -> required.
- Frozen outcomes regenerated in two passes: pass 1, with `route_target_filter` excluded,
  added only the 26 new inputs (no line changed); pass 2 rewrote the neighbour digests.
- Docs: CHANGELOG (Feature + Change), exabgp.conf.5 (ROUTE TARGET CONSTRAINT,
  RE-ADVERTISED ROUTES).
- Each new behaviour was mutated and the tests went red, then restored.
- Found in self-review: `membership_changed()` first called `resend()` per RTC UPDATE, so a
  peer sending N membership UPDATEs queued the VPN table N times (unbounded). Now a flag
  (`_membership_replay`) replays the cached VPN routes once per generated batch; test
  `test_many_membership_updates_replay_the_vpn_routes_once`.
- Not done: matching is O(VPN routes x memberships) per batch; fine for now, an index by
  Route Target would be the fix if a large RT table shows up.
- Sandbox note: `test_storage` (/tmp) and listener tests (bind) fail inside the Claude
  Code sandbox only; run them unsandboxed.

- `tests/unit/rfc/test_rfc1997_communities.py`: the four well-known community tests
  (NO_EXPORT, NO_ADVERTISE, NO_EXPORT_SUBCONFED, operations-implemented). The tests hand a
  received route to another neighbour's `rib.outgoing` and expect it not to be sent.
  Care: an operator-configured route carrying NO_EXPORT towards eBGP is used deliberately
  by some; if applying the rule to locally originated routes breaks the functional
  encoding tests, restrict it to routes received from a peer and document it.
- `tests/unit/rfc/test_rfc7911_negotiation.py::test_a_readvertised_path_carries_an_identifier_we_chose`
- `tests/unit/rfc/test_rfc4684_rt_constraint.py::test_a_vpn_route_is_sent_only_for_a_route_target_the_peer_is_a_member_of`
  (MAY in the ledger; filter only when RT-Constraint was negotiated)
- `tests/unit/rfc/test_rfc4360_extended_communities.py::test_a_non_transitive_extended_community_is_not_sent_to_another_as`
  (keep inside the AS and the confederation; a companion test guards that)
- Where: `src/exabgp/rib/outgoing.py`, `UpdateCollection` generation.

### 4. RFC 8277 Multiple Labels Capability (code 8)
- Tests: the five in `tests/unit/rfc/test_rfc8277_labelled_unicast.py` marked
  `rfc8277#2-single-label-without-capability`, `#2.1-must-not-send-multiple-labels-uncapable`,
  `#2.1-duplicate-triple-ignored`, `#2.1-capability-length-multiple-of-four`,
  `#3.2.3-must-not-send-more-labels-than-peer-handles`.
- Register the capability (AFI/SAFI/Count triples, length a multiple of 4, first duplicate
  wins), a `capability { ... }` knob defaulting off (OPENs stay byte-identical), the
  negotiated count per family in `Negotiated`, and trim label stacks on send (one label
  without the capability). The tests expect `label [100 200]` to go out as `[[100]]`.

### 5. FlowSpec (RFC 8955, RFC 8956)
- `tests/unit/rfc/test_rfc8955_flowspec.py`: next-hop length 0 (§4, beware the redirect-to-IP
  use of the next-hop), DSCP masked with 0x3F on decode, eBGP leftmost AS (§6), feasibility
  against the unicast routes the same peer sent (§6 a/b/c), revalidation on unicast change,
  ICMP type plus port not propagated (§4.2 SHOULD NOT; refusing it in configuration is fine).
  Also the three xfails without an rfc() marker in that file (module docstring).
- `tests/unit/rfc/test_rfc8956_flowspec_ipv6.py`: flow label always 4 octets on encode.
- §6 validation changes behaviour for every flowspec user receiving flows without unicast
  routes: make it a neighbour option, default as the RFC says, and check the functional
  api suite. If the default has to be off to keep suites green, say so in the commit.

### 6. Graceful Restart, RFC 4724 4.2 receiving speaker
- `tests/unit/rfc/test_rfc4724_graceful_restart.py`: retain and mark stale on TCP loss (per
  family the peer advertised), expire after Restart Time, remove stale on End-of-RIB.
- Where: `Peer._main` clears the adj-RIB-in at session start; `rib/incoming.py`
  `record_end_of_rib`. Tell API processes when stale routes go (a withdrawal).
- Related: `plan/plan-llgr.md` (RFC 9494) builds on this.

### 7. EVPN (RFC 7432) and Prefix-SID (RFC 8669)
- `tests/unit/rfc/test_rfc7432_evpn.py`: ESI Label extended community (type 0x06 sub-type
  0x01), ES-Import Route Target (0x06/0x02), RD type 1 for type 4 routes (refuse in
  configuration; on receipt do not reset), next-hop is our own address (§11.1: exabgp is
  often a route injector for other PEs; propose rather than break).
- `tests/unit/rfc/test_rfc8669_prefix_sid.py`: the two xfails. The check needs the family,
  so it belongs after the NLRI are built (like `UpdateCollection.classify_otc`), for
  labelled unicast only, keeping RFC 9252 SRv6 service TLVs valid. Rewrite those two tests
  to go through a real UPDATE.

### 8. BGP-LS, capability retry, four-octet AS
- `tests/unit/rfc/test_rfc9552_bgpls.py`: NLRI TLVs in ascending order (§5.1), NLRI discard
  instead of session reset (§8.2.2). Also `tests/fuzz/test_bgpls_tlv_properties.py` has a
  related xfail.
- `tests/unit/rfc/test_rfc5492_unsupported_capability.py`: after Unsupported Optional
  Parameter (2/4), retry once without capabilities (SHOULD).
- `tests/unit/rfc/test_rfc6793_four_octet_as.py::test_the_capability_value_wins_when_my_as_disagrees_with_it`
  (its negative side is missing too).

---

## Verifying

```bash
uv run ruff format src tests && uv run ruff check src tests
uv run ./qa/bin/test_everything mypy
uv run python qa/bin/check_exa_style
./qa/bin/check_rfc_compliance
env exabgp_log_enable=false uv run pytest tests/unit tests/fuzz -q
uv run ./qa/bin/test_everything     # everything, before a push
```

Regenerating the frozen configuration outcomes, after adding a neighbour option:

```bash
cd tests/unit && env exabgp_log_enable=false ../../.venv/bin/python -m config_grammar.frozen
```

It rewrites every neighbour digest, because the new field is in every neighbour outcome.
Prove nothing else moved: first exclude the new field in `config_grammar/outcome.py`
`neighbor_state`, regenerate, check the diff only adds the new inputs, then restore
`outcome.py` and regenerate again. Say it in the commit message.

---

## Failures and gotchas met

- In a container without IPv6 (Claude Code on the web): 9 unit tests fail on main too
  (`test_network_tcp` IPv6, `test_cli_reports_reach_the_operator`, `test_source_interface`),
  functional encoding I, O, P fail, `reload-cleanup` fails, and the cli/api functional suites
  hang. None of these reproduce on a normal host: run the full `test_everything` there.
- Parallel agents in `isolation: worktree` got worktrees cut from `main`, not from the
  branch, so they did not have the xfail tests; fast-forwarding them was refused. Work in
  the checkout of the branch, one area at a time.
- Left-over worktrees under `.claude/worktrees/` make `check_documentation` report issues
  from their `plan/*.md`; remove them (`git worktree remove`) or pass explicit targets.
- `main` squash-merges: #1431 merged only `91358c5`, so later commits need a new PR, and a
  merge of `main` into the branch (a rebase was refused as destructive).

- 2026-09-28: two `test_everything` ran at once. The first had its `unit` step killed
  (exit 143) and the script carried on, which looked like the whole run had died, so a
  second was started. They share ports and functional servers and spoil each other. Before
  starting one, check none is running (`ps -eo command | grep qa/bin/test_everything`).

## Blockers

None.

## Resume point

**2026-09-28 (local):** on `main` after #1432, not on the web branch. Area 3 done and
uncommitted, waiting for Thomas's review. `test_everything`: all 25 passed (one clean
run, 10m29s). Next: area 4 (RFC 8277). Areas one after the
other, stopping for review between each.

~~Branch `claude/pensive-rubin-95pg84` at `afe4003` or later, pushed. Next: area 3 (outgoing
routes), or any of 3 to 8 in any order.~~
