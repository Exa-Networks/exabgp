"""The names in the JSON stream are a contract, and nothing was holding us to them.

Mutation testing renamed RTC's members from "origin" and "route-target" to "ORIGIN" and
"ROUTE-TARGET" and the whole suite stayed green. Every consumer of the API reads these
names: a controller looking for "route-target" gets nothing, silently, and there is no
error anywhere to tell anyone.

The advisory this work follows is about what a peer can put IN the stream. This is the
other half of the same contract: what we promise is there at all.

These are deliberately exact. A member added to a family should fail here and be added
here, because that is the moment to ask whether the consumers can cope with it.
"""

from __future__ import annotations

import json as jsonlib

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI

CONTRACT: list[tuple[AFI, SAFI, bytes, set[str], str]] = [
    (AFI.ipv4, SAFI.unicast, bytes([24, 10, 0, 0]), {'nlri'}, 'ipv4 unicast'),
    (AFI.ipv6, SAFI.unicast, bytes([32, 0x20, 0x01, 0x0D, 0xB8]), {'nlri'}, 'ipv6 unicast'),
    (AFI.ipv4, SAFI.multicast, bytes([24, 10, 0, 0]), {'nlri'}, 'ipv4 multicast'),
    (AFI.ipv4, SAFI.nlri_mpls, bytes([48, 0, 0, 0x11, 10, 0, 0]), {'nlri', 'label'}, 'ipv4 labelled'),
    (
        AFI.ipv4,
        SAFI.mpls_vpn,
        bytes([112, 0, 0, 0x11]) + bytes(8) + bytes([10, 0, 0]),
        {'nlri', 'label', 'rd'},
        'ipv4 mpls-vpn',
    ),
    (AFI.ipv4, SAFI.rtc, bytes([96]) + bytes(12), {'origin', 'route-target'}, 'rtc'),
    (
        AFI.l2vpn,
        SAFI.vpls,
        bytes([0, 17]) + bytes(17),
        {'rd', 'endpoint', 'base', 'offset', 'size'},
        'vpls',
    ),
    (AFI.ipv4, SAFI.flow_ip, bytes([3, 0x03, 0x81, 0x06]), {'protocol', 'string'}, 'ipv4 flow'),
]


def members(nlri: NLRI) -> set[str]:
    rendered = nlri.json()
    decoded = jsonlib.loads(rendered if rendered.lstrip().startswith('{') else '{' + rendered + '}')
    return set(decoded)


@pytest.mark.parametrize('afi, safi, data, expected, name', CONTRACT, ids=[row[4] for row in CONTRACT])
def test_a_family_emits_the_members_the_api_promises(
    afi: AFI, safi: SAFI, data: bytes, expected: set[str], name: str
) -> None:
    nlri, _ = NLRI.unpack_nlri(afi, safi, data, Action.ANNOUNCE, None, None)
    assert nlri is not NLRI.INVALID, f'{name} seed does not decode, so it pins nothing'

    emitted = members(nlri)
    assert emitted == expected, f'{name} changed what it puts in the API stream'


@pytest.mark.parametrize('afi, safi, data, expected, name', CONTRACT, ids=[row[4] for row in CONTRACT])
def test_a_withdraw_emits_the_same_members(afi: AFI, safi: SAFI, data: bytes, expected: set[str], name: str) -> None:
    """json(announced=False) is what a withdraw is rendered with.

    Mutation testing flipped that default on several families and nothing failed, so which
    members a withdrawal carries was never stated anywhere.
    """
    nlri, _ = NLRI.unpack_nlri(afi, safi, data, Action.WITHDRAW, None, None)
    assert nlri is not NLRI.INVALID

    rendered = nlri.json(announced=False)
    decoded = jsonlib.loads(rendered if rendered.lstrip().startswith('{') else '{' + rendered + '}')
    assert set(decoded) <= expected, f'{name} puts more in a withdraw than in an announce'
