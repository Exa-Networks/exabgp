# Close the testing gaps issues 1425 and 1426 exposed

**Status:** ✅ Completed
**Started:** 2026-09-08
**Last Updated:** 2026-09-29

## Why

Four bugs were found in one session. None was caught by an example test.

| bug | how it was found | what was missing |
|---|---|---|
| #1426 traffic-rate NaN | reported by a user | no "what decodes must render" property for attributes |
| the fuzz coin-toss | noticed while porting to 5.0 | `st.binary()` reached the case in 54% of runs |
| bgp-ls-vpn idempotence | `fuzz_hunt`, a random seed | the derandomised gate had never drawn it |
| #1425 reload leaks | reported by a user | nothing tests what `reload()` does to reactor state |

Signal *delivery* is thoroughly tested in `tests/unit/test_reactor_signal.py`. What a
reload does to the peers and the listening sockets was not tested at all.

## Tasks

| # | task | status |
|---|---|---|
| 1 | reload invariant at unit level: peers and bound sockets match the configuration | ✅ |
| 2 | leftover process and descriptor audit in the functional harness | ✅ |
| 3 | `reactor/loop.py` and `reactor/listener.py` under mutmut | ✅ |
| 4 | audit `tests/fuzz` for `st.binary()` draws which reach their case by luck | ✅ |
| 5 | a real reload scenario, as `qa/bin/check_reload_cleanup` | ✅ |
| 6 | `test_otc_parsing` fails after `test_configuration_export` on the same worker | ✅ |
| 7 | `tests/unit/test_util.py::TestDNS` flakes under xdist | ✅ |
| 8 | `test_api_terminate` respawn limit flakes on a bucket boundary | ✅ |

## Decisions

- Order is cheapest and highest value first. 1 and 2 cover the whole #1425 class without
  needing a running daemon in the unit suite.
- 3 is the check on 1: `reactor/loop.py` and `reactor/listener.py` are now defended by
  exactly one test file, written the same day as the fix. Mutation testing is the only
  thing which says whether it defends them or merely runs them. `[tool.mutmut]` already
  warns to count the mutants after adding a module, because a module producing none is a
  false claim of coverage.
- 4 has a measured number behind it: a uniform byte draw is a non-finite float 0.39% of the
  time, so the gate's 200 examples find it 54% of the time. Any decoder gated on a narrow
  byte pattern has the same problem.

## Branch

Main first. 5.0 gets whatever applies; its reactor is the generator engine, so 1 and 5
differ in shape and 3 and 4 should port unchanged.

## Recent failures

### 2026-09-08 the first red for task 1 was the wrong red

`assert_invariants` asked `peer.stopping()`, a method the #1425 fix added, so reverting
the fix failed all seven tests with `AttributeError: no attribute 'stopping'` rather than
on the invariant. A test which cannot run against the broken code proves nothing about it.

**Resolution:** the invariant now asks `reactor.active_peers()`, which both versions have.
Reverting the fix then fails on what is actually wrong: `peers held for neighbours which
are gone and will never be dropped: {'a'}` and `bound {(127.0.0.1, 179)} but the
configuration asks for {(127.0.0.1, 1179), (127.0.0.1, 179)}`.

## Blockers

_none yet_

## What each task turned into

**1** `tests/unit/test_reload_invariants.py`, 12 tests. Red check on the invariant itself,
not on anything the fix added.

**2** `audit_after_run()` in `qa/bin/functional`, at the one exit point every suite goes
through. A leftover process now fails the run instead of being killed silently.

**3** Adding the two modules found that `./qa/bin/mutmut_run` was broken for **every**
module, including ones already configured. Two causes, both in `test_gates_are_wired.py`
and both correct statements about mutmut's copy rather than about this tree: a gate run as
a subprocess dies on `KeyError: MUTANT_UNDER_TEST` inside the instrumentation, and the
workflow walk finds no forge because `also_copy` does not bring `.github` or `.forgejo`.
Baseline collection failing means mutmut refuses to run anything. The file now skips
wholesale in an instrumented tree.

Then the counts, which `[tool.mutmut]` demands: listener 419 mutants, loop 797, so both
are genuinely reachable. And the verdict was not flattering. `active_peers` had three
survivors and `_listen_for_neighbors` thirty eight: the tests ran that code without
defending it. Six tests later `active_peers` is at zero and `_listen_for_neighbors` at the
log lines and one equivalent mutant.

**4** `tests/fuzz/strategies.py` holds the boundary draw with the measurement written down,
and the three property files use it. Most `st.binary()` sites in the suite are the right
draw and were left alone: where the property is "arbitrary bytes must Notify", every input
exercises it.

**5** `qa/bin/check_reload_cleanup`, wired into `test_everything` as stage 22 of 24. Drives
a real daemon over a real socket. With the #1425 fix reverted it reports the two symptoms
from the report and exits 1.

**6** Moved from `done-message-interface.md`.
`tests/unit/test_otc_parsing.py::test_inline_encode_literal_otc[ipv4...]` fails whenever
`tests/unit/configuration/test_configuration_export.py` (or `config_grammar/test_roundtrip.py`)
ran before it on the same worker. Reproduced on a HEAD worktree during the message interface
work: a test isolation bug, some state one leaves behind which the other reads.

Bisected to one test: `test_configuration_can_be_serialized[conf-no-asn4.conf]`. The state
is `RIB._cache`, which keeps each neighbour's RIB by name for the life of the process so a
reloading daemon keeps the routes the API gave it. That file configures neighbour
127.0.0.1 with a static route; the in-process `exabgp encode` of the OTC test builds a
neighbour of the same name, inherited the route, printed two UPDATEs, and the test decoded
the second as garbage ("invalid mask 255"). Not a production defect: `exabgp encode` is its
own process. `tests/conftest.py` now gives every test back the cache it started with, and
`tests/unit/test_rib_cache_isolation.py` runs the failing pair in a fresh process. The
`config_grammar/test_roundtrip.py` ordering passes too.

**7** Seen in `done-message-interface.md` and `done-notification-text.md`.
`tests/unit/test_util.py::TestDNS` fails intermittently under xdist, before and after
unrelated changes.

`host()` and `domain()` cache the resolver's answer in module globals, and nothing reset
them. `test_host_empty` and `test_domain_with_mock` patched the resolver with a bare
MagicMock and no return value; when one ran first on a worker the MagicMock was cached as
the host name, for the class and for anything later building a default `HostName`.
Reproduced every time with `test_host_empty` then `test_host`, `-p no:randomly`. The class
now empties the cache per test with `monkeypatch`, and the mocked tests set a return value
and assert what comes back. Five `-n 4` runs clean.

Found doing it: `domain()` returns the **first** label of the FQDN, the host again, and
has since 2015. It is the default domain name of the Hostname capability. Pinned with a
strict xfail; the fix changes what every installation without a configured
`domain-name` sends, so it has its own plan, `plan-dns-domain-name.md`.

**8** Found by the full suite run which verified 6 and 7.
`test_api_terminate.py::test_a_helper_past_its_respawn_limit_is_lost` failed once and
passed alone. `Processes` counts respawns per time bucket, `int(time.time()) &
respawn_timemask`, so six deaths straddling a bucket boundary split the count and the
helper was never lost. Shown with a stepped clock across the boundary: `lost()` is `[]`.
The test now holds the clock. The production behaviour is as designed: a limit per window.

## Resume point

All eight done. `./qa/bin/test_everything` passes with 25 stages.
