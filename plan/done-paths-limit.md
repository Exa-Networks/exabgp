# PATHS-LIMIT (issue #1218)

**Status:** ✅ Completed
**Last Updated:** 2026-09-09
**Draft:** [draft-abraitis-idr-addpath-paths-limit-04](https://www.ietf.org/archive/id/draft-abraitis-idr-addpath-paths-limit-04.txt)
**Issue:** https://github.com/Exa-Networks/exabgp/issues/1218

Support for the PATHS-LIMIT capability: advertise how many paths per prefix we are willing
to receive for a family, and respect the number a peer advertises when sending.

## What landed

| Commit | What |
|--------|------|
| `f2cc9c838` | First implementation of the capability |
| `d33d4dc44` | Config moved into the `add-path` block as `limit N`; `prefix_index()` added to Label and IPVPN; audit changed from a counter to a set |
| `c2ea96aaf` | Capability wire variant recorded per instance rather than on the shared class |
| (this work) | Enforcement across batches, the review findings below |

## Review findings and how each was resolved

### Stale announce survived a withdraw

`del_from_rib` only unhooks the announce filed under the attribute set currently in
`_new_nlri`. The same NLRI queued earlier under different attributes stayed in
`_new_attr_af_nlri` and was announced *after* the withdraw, leaving the peer holding a
route ExaBGP had withdrawn.

The gate is `index in latest_routes`: an NLRI still in `_new_nlri` has not been withdrawn,
whatever attributes it now carries.

**A first attempt got this wrong and the functional suite caught it.** The gate was written
as `latest_routes.get(index) is route`, which drops every attribute set but the last, not
just the withdrawn ones. That broke `conf-l2vpn` and `conf-flow-redirect`, both of which
announce one NLRI twice with different attributes and expect both on the wire. Announcing a
redefinition twice is deliberate, tested at the wire level, and unrelated to the bug.

The lesson is the one this file records twice over: the unit test
`test_announce_then_announce_same_nlri_different_attrs` had been deleted, and deleting it
removed the only cheap signal that the first attempt was too broad. The functional suite
found it instead, four minutes into a run.

Tests: `test_announce_replaced_then_withdrawn_sends_no_stale_announce` (new) and
`test_announce_then_announce_same_nlri_different_attrs` (restored unchanged) in
`tests/unit/test_rib_outgoing.py`.

### Two passing tests had been deleted

`test_announce_then_announce_same_nlri_different_attrs` and `test_flush_interleaving` were
removed while neither had been made obsolete; both still passed against the new code. Both
are restored exactly as they were. The first one's assertion was correct as written; an
earlier pass of this work changed it to match the too-broad fix above, which was the wrong
way round.

### The incoming audit was unbounded

`IncomingRIB._path_sets` grew one entry per received path with no cap. A peer which ignores
the limit, which is the only peer the audit exists to catch, was also the peer deciding how
much memory watching it costs.

`track_path` now saturates at one path beyond the limit, which is all the audit needs to
answer its question. The trade, documented in `doc/user/paths-limit.md`: once a prefix has
saturated, withdrawals can take the tracked count below what the peer holds, and a later
violation on that prefix can go unreported until the session restarts.

### The capability could be stuffed

A capability instance carries at most 51 tuples, because a capability's length is a single
byte, but a peer may repeat the capability and every instance merges into the same object.
The draft tells a speaker to describe all of its families in one instance, so one instance
is the most a conforming peer can ask for: `PathsLimit.MAX_FAMILIES` is `0xFF // ENTRY_SIZE`
and an OPEN past it is rejected with a NOTIFICATION.

This was first written as a round 512, which is a number nobody can defend. The bound the
wire already gives is the one to use.

### Promoted paths ignored grouping

A path promoted after a withdrawal was emitted in its own `UpdateCollection` even for the
families where announces are grouped. Promotions now go through `_announce_updates` like any
other announce.

### MUP was offered for ADD-PATH without an encoder for it

This started as a documentation note, that a limit configured for MUP is advertised but
never enforced, and turned out to be a wire bug underneath.

`Capabilities._ADD_PATH` offered `ipv4 mup` and `ipv6 mup`, and `MUP.pack_nlri` writes no
path identifier (its TODO says as much). So `add-path { ipv4 mup; }` put
`AddPath(send/receive ipv4 mup)` on the wire, verified, and a peer which accepted it was
told to expect four octets ahead of every MUP NLRI which ExaBGP then never sent. RFC 7911
section 3. The peer does not lose one path, it mis-frames the rest of the NLRI field.

MUP is out of `_ADD_PATH` until its encoder writes a path identifier, and
`tests/unit/test_addpath_families_encode_path_id.py` now holds that list to what the
encoders can do: it packs one NLRI of every offered family under both negotiations and
requires exactly four more octets with ADD-PATH than without. Six families pass, MUP was
the only failure, and a family added to the list without an encoder fails there rather
than at a peer.

This is not a PATHS-LIMIT bug and predates this work. It surfaced because the PATHS-LIMIT
documentation had to say which families a limit applies to, which meant reading what
ADD-PATH actually offers rather than what the list claims.

### No functional coverage

Two tests now cover PATHS-LIMIT on the wire rather than only in unit tests.

`qa/encoding/conf-cap-paths-limit.ci` drives `etc/exabgp/conf-cap-paths-limit.conf` and
compares the OPEN byte for byte, so the capability we advertise is checked. Falsified by
changing the configured limit and requiring the test to fail.

`qa/encoding/conf-paths-limit-enforce.ci` covers enforcement, which needed a way for the
peer to advertise a limit *to us*: the functional peer echoes our own OPEN back, so a
neighbour configured with `add-path ipv4 unicast limit 2` is offered that limit in return.
Three paths are configured for one prefix and only two may reach the wire. Falsified twice,
by raising the limit to 3 and by removing the admission check, and red both times.

The `.ci` format made this look impossible at first: each line reads like a command paired
with the message it produces, and suppression is the absence of a message. It is not a
pairing. `Checker.group_messages` skips `cmd:` lines outright, they exist for
`test_api_encode` generation, and only `raw:` lines are matched. So a test may list fewer
messages than the configuration has routes, which is exactly what this one does.

### A limit quietly re-enabled adj-rib-out for its family

`resend()` and `withdraw()` used to fall back to `_path_selection` when there was no cache,
so `adj-rib-out false` meant one thing for a family with a limit and another for a family
without one, in the same neighbour: the limited one replayed and withdrew its paths, the
unlimited one did neither. A limit is meant to decide how many paths go out, not whether
ExaBGP keeps a copy of them.

Both fallbacks are gone, and `_path_selection` was narrowed to what enforcement needs:
`advertised` is an index rather than routes, and `candidates` holds only the *withheld*
paths, which are the one thing written down nowhere else. Admitting a path removes it from
`candidates`, promoting one removes it too, and `_PathSelection.empty()` is what retires a
prefix. With no cache the retained state is now proportional to the paths actually held
back, not to every path in the family.

Test: `test_without_a_cache_a_limit_does_not_change_what_refresh_and_withdraw_do`, run for
a limited and an unlimited family so the two are held to the same answer.

Both halves of the narrowing were falsified by widening the state again, and in both cases
the *only* test which noticed was the property test. Every hand written test stayed green.

### Withholding a path left no trace

The code being replaced logged `rib.paths_limit.exceeded` when a path went over the limit.
The replacement logged nothing, so a route the operator configured stopped reaching the peer
with nothing anywhere to say so, while `show adj-rib out` went on listing it. That is worse
than a missing log line: the one place they would look says the opposite of what happened.

`rib.paths_limit.withheld` and `rib.paths_limit.promoted` now record both halves, under the
`rib` category. Test: `test_withholding_and_promoting_a_path_are_both_reported`.

### The capacity bound should not have closed the session

The first version answered an over-long capability with a NOTIFICATION. A truncated entry is
malformed and closing the session is right; a well formed list which is merely longer than
we want to hold is not. RFC 5492 has a speaker ignore capability content it cannot use, and
a peering is worth more than the families past our capacity. It now stops recording, logs,
and the session lives. Truncation still raises.

## Kept as it is, with the reasoning

### The incoming audit stays on by default

Considered defaulting `exabgp.bgp.paths_limit_audit` to false, on the grounds that it is a
diagnostic which costs peer driven state. It is already opt-in: `_audit_announce` returns
immediately unless `advertised_paths_limit` is populated, which happens only where the
operator configured a limit. Configuring a limit is the opt-in, the memory it costs is now
bounded, and a flag nobody knows about helps nobody. Left on.

### `show adj-rib out` still lists a withheld path

The cache records what the configuration and the API asked for, and the limit is applied
when updates are generated, so for a limited family the cache reads as "what ExaBGP would
send if the peer would take it". Marking held paths there would be a change to the output
format and its consumers, which is a product decision rather than a fix. The two log lines
above and the note in `doc/user/paths-limit.md` are the answer for now.

## Deliberate gap: withheld paths are not capped

`OutgoingRIB._path_selection` keeps a `Route` for every path held back, so that withdrawing
an advertised path can promote one.

It is not capped, and that is deliberate. Nothing here is peer driven: the size follows the
configuration and the API, and it is now bounded by the paths actually held back rather than
by every path in the family. Capping it would mean dropping a path the operator asked for and
being unable to promote it later, which is the "a wrong route is worse than no route" trade
Tiger Style tells us not to make.

Revisit if a limit is ever driven by something the peer controls.

## Verification

- `./qa/bin/test_everything`
- `./qa/bin/mutmut_run exabgp.rib.outgoing` and `exabgp.rib.incoming`, which is why both
  are now listed under `[tool.mutmut]` in `pyproject.toml`.
- Each new test was required to go red first: the bound removed, the guard deleted, the
  grouping key narrowed, promotion disabled, the configured limit changed. The property
  test in `tests/unit/test_paths_limit_properties.py` did not notice promotion being
  disabled on its first draft, because a flat list of random operations almost never
  reaches the shape where a suppressed path needs promoting. It generates rounds which
  always drain, and now goes red for both.
