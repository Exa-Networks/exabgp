"""prefix_index() is what the paths-limit audit groups by, and one family exercised it.

IncomingRIB.track_path counts a peer's paths per prefix using prefix_index(), so a family
whose implementation is wrong is a family whose peer can exceed its advertised limit
unnoticed, or be warned about a limit it never crossed.

Instrumenting the suite: index() ran for eleven classes and prefix_index() for one. The
other ten had never been called by any test, which is the same shape as every other finding
in this series: a pair of methods where one is exercised and the other is not, and the one
that is is what makes the gap invisible.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI

SEEDS: list[tuple[str, AFI, SAFI, bytes, bytes]] = [
    # name, afi, safi, one route, a different route in the same family
    ('ipv4 unicast', AFI.ipv4, SAFI.unicast, bytes([24, 10, 0, 0]), bytes([24, 10, 1, 0])),
    ('ipv6 unicast', AFI.ipv6, SAFI.unicast, bytes([32, 0x20, 0x01, 0x0D, 0xB8]), bytes([32, 0x20, 0x01, 0x0D, 0xB9])),
    (
        'ipv4 labelled',
        AFI.ipv4,
        SAFI.nlri_mpls,
        bytes([48, 0, 0, 0x11, 10, 0, 0]),
        bytes([48, 0, 0, 0x11, 10, 1, 0]),
    ),
    (
        'ipv4 mpls-vpn',
        AFI.ipv4,
        SAFI.mpls_vpn,
        bytes([112, 0, 0, 0x11]) + bytes(8) + bytes([10, 0, 0]),
        bytes([112, 0, 0, 0x11]) + bytes(8) + bytes([10, 1, 0]),
    ),
    ('rtc', AFI.ipv4, SAFI.rtc, bytes([96]) + bytes(12), bytes([96]) + bytes(11) + bytes([1])),
    ('vpls', AFI.l2vpn, SAFI.vpls, bytes([0, 17]) + bytes(17), bytes([0, 17]) + bytes(16) + bytes([1])),
    ('ipv4 flow', AFI.ipv4, SAFI.flow_ip, bytes([3, 0x03, 0x81, 0x06]), bytes([3, 0x03, 0x81, 0x11])),
]

IDS = [row[0] for row in SEEDS]


def decode(afi: AFI, safi: SAFI, data: bytes, addpath: bool | None = None) -> NLRI | None:
    try:
        nlri, _ = NLRI.unpack_nlri(afi, safi, data, Action.ANNOUNCE, addpath, None)
    except Notify:
        return None
    return None if nlri is NLRI.INVALID else nlri


@pytest.mark.parametrize('name, afi, safi, one, other', SEEDS, ids=IDS)
def test_prefix_index_answers_for_every_family(name: str, afi: AFI, safi: SAFI, one: bytes, other: bytes) -> None:
    """It has to return something, and the same something every time it is asked."""
    nlri = decode(afi, safi, one)
    assert nlri is not None, f'{name} seed does not decode, so this pins nothing'

    first = nlri.prefix_index()
    assert isinstance(first, bytes) and first, f'{name} prefix_index is empty'
    assert nlri.prefix_index() == first, f'{name} prefix_index is not stable'


@pytest.mark.parametrize('name, afi, safi, one, other', SEEDS, ids=IDS)
def test_two_different_routes_do_not_share_a_prefix_index(
    name: str, afi: AFI, safi: SAFI, one: bytes, other: bytes
) -> None:
    """Two prefixes grouping together would count one peer's paths against the other's."""
    first, second = decode(afi, safi, one), decode(afi, safi, other)
    assert first is not None and second is not None, f'{name} needs two decodable seeds'
    assert first.index() != second.index(), f'{name} seeds are the same route, so this pins nothing'

    assert first.prefix_index() != second.prefix_index(), f'{name} groups two routes as one prefix'


@pytest.mark.parametrize(
    'name, afi, safi, prefix',
    [
        ('ipv4 unicast', AFI.ipv4, SAFI.unicast, bytes([24, 10, 0, 0])),
        ('ipv4 labelled', AFI.ipv4, SAFI.nlri_mpls, bytes([48, 0, 0, 0x11, 10, 0, 0])),
        ('ipv4 mpls-vpn', AFI.ipv4, SAFI.mpls_vpn, bytes([112, 0, 0, 0x11]) + bytes(8) + bytes([10, 0, 0])),
    ],
    ids=['ipv4 unicast', 'ipv4 labelled', 'ipv4 mpls-vpn'],
)
def test_two_paths_for_one_prefix_group_together(name: str, afi: AFI, safi: SAFI, prefix: bytes) -> None:
    """The property the paths-limit audit depends on, for the families which carry add-path.

    Two path identifiers for one prefix are two routes and one prefix. If prefix_index told
    them apart, every path would be its own group and a peer could never exceed a limit; if
    index() did not, the RIB would hold one of them.
    """
    first = decode(afi, safi, bytes([0, 0, 0, 1]) + prefix, addpath=True)
    second = decode(afi, safi, bytes([0, 0, 0, 2]) + prefix, addpath=True)
    assert first is not None and second is not None, f'{name} add-path seed does not decode'

    assert first.index() != second.index(), f'{name} treats two paths as one route'
    assert first.prefix_index() == second.prefix_index(), f'{name} treats two paths as two prefixes'
