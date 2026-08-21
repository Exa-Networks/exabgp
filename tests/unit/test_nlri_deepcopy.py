"""A copy of an NLRI must be a copy, not a second name for the same object.

Ten NLRI classes implement __deepcopy__ by hand, copying slot by slot, and nothing in the
tree calls deepcopy on one: every deepcopy in src/ is of a configuration Validator. So the
facility is maintained, reachable by anyone using this as a library, and until now entirely
untested. Mutation testing found sixteen survivors in INETBase.__deepcopy__ alone, which is
what a method nobody exercises looks like.

What has to hold is the same for every family: the copy carries the same route, it is not
the original, and nothing mutable is shared between them. A deepcopy which shares state is
a route which changes under whoever is holding it.
"""

from __future__ import annotations

from copy import deepcopy

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI

# one decodable NLRI per family, hand built rather than fuzzed: a copy is only interesting
# for something which decoded
SEEDS: list[tuple[AFI, SAFI, bytes, str]] = [
    (AFI.ipv4, SAFI.unicast, bytes([24, 10, 0, 0]), 'ipv4 unicast'),
    (AFI.ipv6, SAFI.unicast, bytes([32, 0x20, 0x01, 0x0D, 0xB8]), 'ipv6 unicast'),
    (AFI.ipv4, SAFI.multicast, bytes([24, 10, 0, 0]), 'ipv4 multicast'),
    (AFI.ipv4, SAFI.nlri_mpls, bytes([48, 0x00, 0x00, 0x11, 10, 0, 0]), 'ipv4 labelled'),
    (AFI.ipv4, SAFI.mpls_vpn, bytes([112]) + bytes([0, 0, 0x11]) + bytes(8) + bytes([10, 0, 0]), 'ipv4 mpls-vpn'),
    (AFI.ipv4, SAFI.rtc, bytes([96]) + bytes(12), 'rtc'),
    (AFI.l2vpn, SAFI.vpls, bytes([0, 17]) + bytes(17), 'vpls'),
]


def decoded(afi: AFI, safi: SAFI, data: bytes) -> NLRI | None:
    try:
        nlri, _ = NLRI.unpack_nlri(afi, safi, data, Action.ANNOUNCE, None, None)
    except Notify:
        return None
    return None if nlri is NLRI.INVALID else nlri


@pytest.mark.parametrize('afi, safi, data, name', SEEDS, ids=[s[3] for s in SEEDS])
def test_a_deepcopy_is_the_same_route_and_a_different_object(afi: AFI, safi: SAFI, data: bytes, name: str) -> None:
    original = decoded(afi, safi, data)
    assert original is not None, f'{name} seed does not decode, so it pins nothing'

    copy = deepcopy(original)

    assert copy is not original, 'a deepcopy which returns the original copies nothing'
    assert type(copy) is type(original)
    assert copy.index() == original.index(), 'the copy is the same route'
    assert copy.json() == original.json()
    assert str(copy) == str(original)


@pytest.mark.parametrize('afi, safi, data, name', SEEDS, ids=[s[3] for s in SEEDS])
def test_a_deepcopy_shares_no_container(afi: AFI, safi: SAFI, data: bytes, name: str) -> None:
    """A slot holding a container must be copied, or the two routes move together.

    Only containers: an NLRI is immutable by design, so its packed bytes, its path
    information and its route distinguisher are shared on purpose, and sharing them is what
    makes a copy cheap. What must not be shared is anything which can be appended to or
    assigned into behind the holder's back.
    """
    original = decoded(afi, safi, data)
    assert original is not None

    copy = deepcopy(original)

    for owner in type(original).__mro__:
        for slot in getattr(owner, '__slots__', ()):
            if not hasattr(original, slot):
                continue
            mine, theirs = getattr(original, slot), getattr(copy, slot)
            if not isinstance(mine, (list, dict, set, bytearray)):
                continue
            assert mine is not theirs, f'{name} shares its {slot} container with its copy'


@pytest.mark.parametrize('afi, safi, data, name', SEEDS, ids=[s[3] for s in SEEDS])
def test_a_deepcopy_survives_a_cycle(afi: AFI, safi: SAFI, data: bytes, name: str) -> None:
    """The memo must be honoured, or a structure holding one route twice copies it twice.

    Each __deepcopy__ writes memo[id(self)] before copying its slots. A route reached twice
    has to come back as one object, which is what makes a RIB holding it consistent.
    """
    original = decoded(afi, safi, data)
    assert original is not None

    held = {'first': original, 'again': original}
    copied = deepcopy(held)

    assert copied['first'] is copied['again'], f'{name} was copied twice from one route'
