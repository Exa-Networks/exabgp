# Tests of earlier releases

A copy of the functional encoding tests of the 4.2 and 5.0 branches: their configurations
and API helpers (`etc/exabgp/`), the tests themselves (`qa/ci/` for 4.2, `qa/encoding/`
for 5.0) and the test peer which checks them (`qa/sbin/bgp`). Nothing here is edited: it is
what a 4.2 or 5.0 deployment runs, and `./qa/bin/test_old_scripts` runs it against this
tree's code to show those configurations and helpers still announce and withdraw what
they did.

Only the files an encoding test uses are kept, and a 4.2 test whose every file is the same
in 5.0 is left out of `4.2/`: the 5.0 copy runs it already.

| Copy | Branch | Commit |
|------|--------|--------|
| `4.2/` | `origin/4.2` | `ee02a9e87d3e0a10d33231bf9b67bc4c3a0e496b` |
| `5.0/` | `origin/5.0` | `b6b2f7441fa57b1169b65f8572e433f16770b773` |

To take a newer copy of a branch:

    rm -rf qa/old/5.0 && mkdir qa/old/5.0
    git archive origin/5.0 qa/encoding qa/sbin/bgp etc/exabgp | tar -x -C qa/old/5.0

and update the commit above. 4.2 keeps its tests in `qa/ci` instead of `qa/encoding`.
