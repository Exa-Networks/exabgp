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

from copy import copy as shallow_copy, deepcopy

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


@pytest.mark.parametrize('afi, safi, data, name', SEEDS, ids=[s[3] for s in SEEDS])
def test_a_deepcopy_carries_every_slot(afi: AFI, safi: SAFI, data: bytes, name: str) -> None:
    """Each slot the original holds, the copy holds with the same value.

    __deepcopy__ is written by hand, slot by slot, in ten classes. Mutation testing set
    individual slots to None in the copy, dropping the route distinguisher and the add-path
    flag, and nothing failed: index() equality alone does not see a slot the key does not
    include, and a container check does not see a slot which is not a container.

    This is the whole promise of the method, stated once.
    """
    original = decoded(afi, safi, data)
    assert original is not None

    copy = deepcopy(original)

    checked = 0
    for owner in type(original).__mro__:
        for slot in getattr(owner, '__slots__', ()):
            if not hasattr(original, slot):
                continue
            checked += 1
            mine, theirs = getattr(original, slot), getattr(copy, slot)
            assert type(mine) is type(theirs), f'{name} copied {slot} as a different type'
            if isinstance(mine, (bytes, bytearray, memoryview)):
                assert bytes(mine) == bytes(theirs), f'{name} copied {slot} with different bytes'
            else:
                assert mine == theirs, f'{name} copied {slot} with a different value'

    assert checked, f'{name} has no slots to check, so this pins nothing'


def test_a_deepcopy_carries_the_flags_a_default_seed_leaves_unset() -> None:
    """A seed which leaves a slot at its default cannot show that dropping it matters.

    A labelled VPN route sets the ones which do: _has_rd, _has_labels and the label size are
    all true or non-zero, and the packed-bytes-first classes derive everything they render
    from them. A copy which loses one is a copy which renders a different route.
    """
    labelled_vpn = decoded(AFI.ipv4, SAFI.mpls_vpn, bytes([112, 0, 0, 0x11]) + bytes(8) + bytes([10, 0, 0]))
    assert labelled_vpn is not None
    assert labelled_vpn._has_rd, 'the seed has to set the flag for this to pin anything'
    assert labelled_vpn._has_labels
    assert labelled_vpn._label_size

    copy = deepcopy(labelled_vpn)

    assert copy._has_rd == labelled_vpn._has_rd
    assert copy._has_labels == labelled_vpn._has_labels
    assert copy._label_size == labelled_vpn._label_size
    assert copy.index() == labelled_vpn.index()
    assert copy.json() == labelled_vpn.json()


@pytest.mark.parametrize('afi, safi, data, name', SEEDS, ids=[s[3] for s in SEEDS])
def test_a_shallow_copy_is_the_same_route(afi: AFI, safi: SAFI, data: bytes, name: str) -> None:
    """copy.copy() is a second hook, with sixteen implementations, and its own way to break.

    The two are not interchangeable and the difference hides bugs: copy.copy(x) calls
    __copy__() with NO argument while deepcopy passes a memo, so a __copy__ written with an
    extra parameter raises TypeError on one path and works perfectly on the other. The 5.0
    branch had exactly that, and its deepcopy tests could not see it.

    Nothing in src copies an NLRI either way. Both are public dunders a library user reaches.
    """
    original = decoded(afi, safi, data)
    assert original is not None

    copy = shallow_copy(original)

    assert copy is not original
    assert type(copy) is type(original)
    assert copy.index() == original.index()
    assert copy.json() == original.json()


def test_the_copy_hooks_take_the_arguments_python_passes_them() -> None:
    """__copy__ takes only self, __deepcopy__ takes self and a memo.

    Getting this wrong raises on one path and not the other, which is why it survives: the
    RIB deep-copies on the withdraw path, so a broken __copy__ leaves the object looking
    perfectly copyable.
    """
    import inspect

    from exabgp.bgp.message.update.nlri.inet import INETBase

    for klass in (INETBase,):
        assert list(inspect.signature(klass.__copy__).parameters) == ['self'], f'{klass.__name__}.__copy__'
        assert list(inspect.signature(klass.__deepcopy__).parameters) == ['self', 'memo'], f'{klass.__name__}'
