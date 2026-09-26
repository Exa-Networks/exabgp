"""RTC is negotiated when asked for, not because a neighbor has no family block.

A neighbor without a `family` block advertises the default family set. RTC (RFC 4684, AFI 1
SAFI 132) was in it, because every family ExaBGP decodes was. That is not harmless for this one:
RFC 4684 section 6 says a VPN route "should be advertised to a peer that participates in the
exchange of Route Target membership information if that peer has advertised either the default
Route Target membership NLRI or a Route Target membership NLRI containing any of the targets".
With RTC negotiated and no membership announced, a route reflector which follows it sends no VPN
routes at all, and nothing tells the operator why.

So RTC is only negotiated when it is listed: `ipv4 rtc`, or `all`, which asks for every family
ExaBGP knows and is what `exabgp decode` uses.
"""

from __future__ import annotations

import os
import pathlib
import subprocess

import pytest

from exabgp.configuration.configuration import Configuration
from exabgp.protocol.family import AFI, SAFI

ROOT = pathlib.Path(__file__).parent.parent.parent
RTC = (AFI.ipv4, SAFI.rtc)

NEIGHBOUR = """
neighbor 127.0.0.1 {
  router-id 1.2.3.4; local-address 127.0.0.2; local-as 1; peer-as 1;
  %s
}
"""


def families(tmp_path, block: str) -> list:
    conf = tmp_path / 'test.conf'
    conf.write_text(NEIGHBOUR % block)
    configuration = Configuration([str(conf)])
    assert configuration.reload(), configuration.error
    (neighbor,) = configuration.neighbors.values()
    return list(neighbor.families())


def test_a_neighbor_without_a_family_block_does_not_negotiate_rtc(tmp_path) -> None:
    """The defect: RTC came with the default set, and with it the empty VPN feed."""
    found = families(tmp_path, '')
    assert RTC not in found
    assert (AFI.ipv4, SAFI.unicast) in found
    assert (AFI.ipv4, SAFI.mpls_vpn) in found


@pytest.mark.parametrize('block', ['family { ipv4 rtc; }', 'family { all; }'])
def test_rtc_is_negotiated_when_asked_for(tmp_path, block) -> None:
    assert RTC in families(tmp_path, block)


def test_decode_still_reads_rtc_without_being_told_the_family() -> None:
    """`exabgp decode` builds its neighbor with `family { all; }`."""
    capture = (ROOT / 'qa' / 'encoding' / 'conf-rtc.ci').read_text().splitlines()
    update = next(line.split('raw:', 1)[1] for line in capture if 'raw:' in line and '0001840' in line)
    environ = dict(os.environ)
    environ.pop('PYTHONPATH', None)
    result = subprocess.run(
        [str(ROOT / 'sbin' / 'exabgp'), 'decode', update],
        capture_output=True,
        text=True,
        env=environ,
        cwd=str(ROOT),
        timeout=180,
    )
    assert '"ipv4 rtc"' in result.stdout, result.stdout[-1500:] + result.stderr[-1500:]
