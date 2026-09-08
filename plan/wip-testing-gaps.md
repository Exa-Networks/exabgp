# Close the testing gaps issues 1425 and 1426 exposed

**Status:** ✅ Completed
**Started:** 2026-09-08
**Last Updated:** 2026-09-08

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

## Resume point

All five done. Nothing committed yet. `./qa/bin/test_everything` passes with 24 stages.
