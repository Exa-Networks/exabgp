"""The names in the JSON stream are a contract, and nothing was holding us to them.

Mutation testing renamed RTC's members from "origin" and "route-target" to "ORIGIN" and
"ROUTE-TARGET" and the whole suite stayed green. Every consumer reads these names: a
controller looking for "route-target" finds nothing, silently, with no error to tell anyone.

The advisory this work follows is about what a peer can put IN the stream. This is the other
half of the same contract: what we promise is in it at all.

SEVERAL seeds per family, and the assertion is on their UNION. One example per family is not
enough and the reason is worth stating, because both this tree and the 5.0 one wrote the
weaker version first: RTC renders `route-target` from two different lines, one for a
wildcard and one for a real target, so a test which happens to decode the wildcard leaves
the other line renameable while looking green. A flow shows only the components its seed
carries. A family is its branches, not its first example.
"""

from __future__ import annotations

import json as jsonlib

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI

# family -> the members it promises, and every seed which reaches a different branch of it
CONTRACT: list[tuple[str, AFI, SAFI, set[str], list[bytes]]] = [
    (
        'ipv4 unicast',
        AFI.ipv4,
        SAFI.unicast,
        {'nlri'},
        [bytes([24, 10, 0, 0]), bytes([0]), bytes([32, 10, 0, 0, 1])],
    ),
    ('ipv6 unicast', AFI.ipv6, SAFI.unicast, {'nlri'}, [bytes([32, 0x20, 0x01, 0x0D, 0xB8]), bytes([0])]),
    ('ipv4 multicast', AFI.ipv4, SAFI.multicast, {'nlri'}, [bytes([24, 10, 0, 0]), bytes([0])]),
    (
        'ipv4 labelled',
        AFI.ipv4,
        SAFI.nlri_mpls,
        {'nlri', 'label'},
        [bytes([48, 0, 0, 0x11, 10, 0, 0]), bytes([72, 0, 0, 0x10, 0, 0, 0x11, 10, 0, 0])],
    ),
    (
        'ipv4 mpls-vpn',
        AFI.ipv4,
        SAFI.mpls_vpn,
        {'nlri', 'label', 'rd'},
        [bytes([112, 0, 0, 0x11]) + bytes(8) + bytes([10, 0, 0])],
    ),
    (
        'rtc',
        AFI.ipv4,
        SAFI.rtc,
        {'origin', 'route-target'},
        [bytes([0]), bytes([96]) + bytes(12), bytes([64]) + bytes(12)],  # wildcard AND specific
    ),
    ('vpls', AFI.l2vpn, SAFI.vpls, {'rd', 'endpoint', 'base', 'offset', 'size'}, [bytes([0, 17]) + bytes(17)]),
    (
        'ipv4 flow',
        AFI.ipv4,
        SAFI.flow_ip,
        {'string', 'protocol', 'destination-ipv4', 'destination-port'},
        [
            bytes([3, 0x03, 0x81, 0x06]),  # protocol alone
            bytes([11, 0x01, 0x18, 0x0A, 0x00, 0x00, 0x03, 0x81, 0x06, 0x05, 0x81, 0x50]),  # and more
        ],
    ),
]

IDS = [row[0] for row in CONTRACT]


def members(afi: AFI, safi: SAFI, data: bytes, announced: bool = True) -> set[str] | None:
    try:
        nlri, _ = NLRI.unpack_nlri(afi, safi, data, Action.ANNOUNCE if announced else Action.WITHDRAW, None, None)
    except Notify:
        return None
    if nlri is NLRI.INVALID:
        return None
    rendered = nlri.json(announced=announced)
    decoded = jsonlib.loads(rendered if rendered.lstrip().startswith('{') else '{' + rendered + '}')
    return set(decoded)


@pytest.mark.parametrize('name, afi, safi, expected, seeds', CONTRACT, ids=IDS)
def test_a_family_emits_the_members_the_api_promises(
    name: str, afi: AFI, safi: SAFI, expected: set[str], seeds: list[bytes]
) -> None:
    seen: set[str] = set()
    decoded = 0
    for seed in seeds:
        found = members(afi, safi, seed)
        if found is None:
            continue
        decoded += 1
        seen |= found

    assert decoded, f'{name}: not one seed decoded, so this pins nothing'
    assert seen == expected, f'{name} changed what it puts in the API stream'


@pytest.mark.parametrize('name, afi, safi, expected, seeds', CONTRACT, ids=IDS)
def test_a_withdraw_says_no_more_than_an_announce(
    name: str, afi: AFI, safi: SAFI, expected: set[str], seeds: list[bytes]
) -> None:
    """json(announced=False) is how a withdrawal is rendered.

    Mutation testing flipped that default on several families and nothing failed, so what a
    withdrawal carries had never been stated.
    """
    for seed in seeds:
        found = members(afi, safi, seed, announced=False)
        if found is None:
            continue
        assert found <= expected, f'{name} puts more in a withdraw than in an announce'


# Every family which has a decoder but no entry above.  A CONTRACT of eight families says
# nothing about the other fifteen, and nothing said so: a family added later renders into
# the API stream and no test here notices, which is the same stale-hand-written-table
# failure this repository has now found in workflow paths, gate lists and wire parameters.
#
# Named individually rather than counted, so adding a family means deciding which list it
# belongs in.  This is a debt list and it must only shrink: move a family up into CONTRACT
# with its seeds, do not add one here.
#
# Session 5.0 has the floor with no debt list, because their table covers every decodable
# family.  Ours does not, and asserting the number honestly is better than asserting a
# clean rule that would have to be skipped.
UNPINNED = {
    'ipv6/nlri-mpls',
    'ipv6/mpls-vpn',
    'ipv6/multicast',
    'ipv6/flow',
    'ipv6/flow-vpn',
    'ipv4/flow-vpn',
    'ipv4/mcast-vpn',
    'ipv6/mcast-vpn',
    'ipv4/mup',
    'ipv6/mup',
    'ipv4/sr-policy',
    'ipv6/sr-policy',
    'l2vpn/evpn',
    'bgp-ls/bgp-ls',
    'bgp-ls/bgp-ls-vpn',
}


def test_every_decodable_family_is_pinned_or_named_as_debt() -> None:
    """A family added later must be given its members rather than silently skipped.

    The failure this exists for: someone registers a family, it renders into the API
    stream, and a contract test which parametrises over a hand written list stays green
    because it never heard of it.
    """
    registered = {str(family) for family in NLRI.registered_nlri}
    pinned = {f'{afi}/{safi}' for _name, afi, safi, _expected, _seeds in CONTRACT}
    unaccounted = sorted(registered - pinned - UNPINNED)
    assert not unaccounted, f'these families render JSON nobody has pinned or acknowledged: {unaccounted}'


def test_the_debt_list_does_not_name_a_family_which_is_pinned() -> None:
    """An entry which is also in CONTRACT is an excuse nothing needs, and hides the next one."""
    pinned = {f'{afi}/{safi}' for _name, afi, safi, _expected, _seeds in CONTRACT}
    both = sorted(UNPINNED & pinned)
    assert not both, f'these are pinned AND listed as debt: {both}'


def test_the_debt_list_does_not_name_a_family_which_does_not_exist() -> None:
    """A family renamed or removed leaves an entry which excuses nothing and outlives it."""
    registered = {str(family) for family in NLRI.registered_nlri}
    gone = sorted(UNPINNED - registered)
    assert not gone, f'these are named as debt but are not registered families: {gone}'
