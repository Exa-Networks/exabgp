"""Equal NLRI must hash equally, and two classes read the two halves from different places.

Python's data model requires a == b to imply hash(a) == hash(b).  Break it and a set holding
both keeps two entries while a dict lookup can miss, which at the NLRI level is the RIB
holding one route under two keys.

Nothing here asserted it.  Session 5.0 broke exactly this on their branch by masking the
reserved bits of a Multi-Topology identifier: their __eq__ compared the masked topologies
and their __hash__ hashed the rendered packed bytes, so the fix made a wrong-but-coherent
object into an incoherent one.  Before it, both halves said "different" for the same wrong
reason, together.  Their mutation showed no test in the file could have caught it.

main survives that particular change because both halves reach the packed bytes, which is
luck rather than design: INET takes __eq__ from NLRI and __hash__ from INETBase, and BGPLS
takes __eq__ from NLRI and __hash__ from BGPLS.  Two classes where the halves are defined
apart is two chances to move one and not the other, and normalising _packed - which is the
open question behind the MT-ID reserved bits - would do precisely that.
"""

from __future__ import annotations

from copy import deepcopy
from struct import pack

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI

MULTI_TOPOLOGY_TLV = 263
RESERVED_BITS = 0xF000
# a ratchet: raise it as families are added, never lower it
MIN_REGISTERED_FAMILIES = 10


def bgpls_prefix_vpn() -> bytes:
    """A BGP-LS VPN prefix, which is the only shape where route_d is not NORD.

    The route distinguisher is an instance attribute rather than a slot, and the base
    class copy methods did not carry it, so a copied route lost it and then raised
    AttributeError when compared.  A plain BGP-LS seed cannot show that: its route_d is
    NORD, which copies to NORD by being absent.
    """
    body = bytes([3]) + bytes(8) + pack('!HH', 265, 4) + bytes([24, 192, 0, 2])
    rd = bytes([0, 0]) + bytes([0, 0, 0, 42]) + bytes(2)
    return pack('!HH', 3, len(body) + 8) + rd + body


def bgpls_link(mtid: int) -> bytes:
    body = bytes([3]) + bytes(8) + pack('!HH', MULTI_TOPOLOGY_TLV, 2) + pack('!H', mtid)
    return pack('!HH', 2, len(body)) + body


# name, afi, safi, wire bytes
SEEDS: list[tuple[str, AFI, SAFI, bytes]] = [
    ('ipv4 unicast', AFI.ipv4, SAFI.unicast, bytes([24, 10, 0, 0])),
    ('ipv6 unicast', AFI.ipv6, SAFI.unicast, bytes([32, 0x20, 0x01, 0x0D, 0xB8])),
    ('ipv4 multicast', AFI.ipv4, SAFI.multicast, bytes([24, 10, 0, 0])),
    ('ipv4 labelled', AFI.ipv4, SAFI.nlri_mpls, bytes([48, 0, 0, 0x11, 10, 0, 0])),
    ('ipv4 mpls-vpn', AFI.ipv4, SAFI.mpls_vpn, bytes([112, 0, 0, 0x11]) + bytes(8) + bytes([10, 0, 0])),
    ('rtc', AFI.ipv4, SAFI.rtc, bytes([96]) + bytes(12)),
    ('vpls', AFI.l2vpn, SAFI.vpls, bytes([0, 17]) + bytes(17)),
    ('ipv4 flow', AFI.ipv4, SAFI.flow_ip, bytes([3, 0x03, 0x81, 0x06])),
    ('bgp-ls link', AFI.bgpls, SAFI.bgp_ls, bgpls_link(2)),
    ('bgp-ls vpn', AFI.bgpls, SAFI.bgp_ls_vpn, bgpls_prefix_vpn()),
]

IDS = [row[0] for row in SEEDS]


def decoded(afi: AFI, safi: SAFI, data: bytes) -> NLRI | None:
    try:
        nlri, _ = NLRI.unpack_nlri(afi, safi, data, Action.ANNOUNCE, None, None)
    except Notify:
        return None
    return None if nlri is NLRI.INVALID else nlri


@pytest.mark.parametrize('name, afi, safi, data', SEEDS, ids=IDS)
def test_two_decodes_of_one_route_are_equal_and_hash_equally(name: str, afi: AFI, safi: SAFI, data: bytes) -> None:
    """The same bytes twice.  If these disagree, nothing downstream can be trusted."""
    first, second = decoded(afi, safi, data), decoded(afi, safi, data)
    assert first is not None and second is not None, f'{name} seed does not decode'

    assert first == second, f'{name} is not equal to another decode of the same bytes'
    assert hash(first) == hash(second), f'{name} hashes differently from an identical route'


@pytest.mark.parametrize('name, afi, safi, data', SEEDS, ids=IDS)
def test_a_copy_is_equal_and_hashes_equally(name: str, afi: AFI, safi: SAFI, data: bytes) -> None:
    """deepcopy is how the RIB holds a route it also hands out.

    A copy which compares equal and hashes differently puts the same route in a set twice.
    """
    original = decoded(afi, safi, data)
    assert original is not None, f'{name} seed does not decode'
    copy = deepcopy(original)

    assert original == copy, f'{name} does not equal its own copy'
    assert hash(original) == hash(copy), f'{name} hashes differently from its own copy'


@pytest.mark.parametrize('name, afi, safi, data', SEEDS, ids=IDS)
def test_a_set_holding_a_route_twice_holds_one(name: str, afi: AFI, safi: SAFI, data: bytes) -> None:
    """The consequence stated as the RIB sees it, rather than as two dunder methods."""
    first, second = decoded(afi, safi, data), decoded(afi, safi, data)
    assert first is not None and second is not None

    assert len({first, second}) == 1, f'{name} occupies two entries of a set for one route'
    assert {first: 'a'}[second] == 'a', f'{name} cannot be looked up by an equal route'


def test_the_reserved_bits_split_identity_but_do_so_consistently() -> None:
    """The open question behind the MT-ID mask, asserted as it currently stands.

    RFC 9552 5.2.2.1 says the reserved bits are ignored on receipt, and they are, for what
    the TLV renders.  Identity is the wire bytes, so the same link in the same topology
    still splits.  That is wrong, and it is at least COHERENT: both halves read the packed
    bytes, so they split together.

    This is the test which fails if anyone normalises _packed by halves.  Fixing __eq__ and
    leaving __hash__ on the wire bytes is what session 5.0 did to themselves, in the commit
    which fixed the other half.
    """
    clear = decoded(AFI.bgpls, SAFI.bgp_ls, bgpls_link(2))
    marked = decoded(AFI.bgpls, SAFI.bgp_ls, bgpls_link(RESERVED_BITS | 2))
    assert clear is not None and marked is not None

    assert clear.json() == marked.json(), 'the rendered topology should already ignore the reserved bits'

    # whichever way identity goes, the two halves must go together
    assert (clear == marked) == (hash(clear) == hash(marked)), (
        'identity and hashing disagree about the reserved bits: one half was changed alone'
    )


def test_no_registered_nlri_defines_equality_without_hashing() -> None:
    """A class defining __eq__ and inheriting object.__hash__ is unhashable in Python 3.

    Cheap, structural, and it catches the case where someone adds an __eq__ to a family and
    the RIB stops being able to hold it at all.
    """
    unhashable = [
        klass.__name__
        for klass in set(NLRI.registered_nlri.values())
        if '__eq__' in klass.__dict__ and klass.__dict__.get('__hash__') is None
    ]

    assert not unhashable, f'these define __eq__ and lose __hash__: {unhashable}'


def test_the_registry_sweep_had_a_registry_to_sweep() -> None:
    """test_no_registered_nlri_defines_equality_without_hashing walks registered_nlri.

    It reports the classes which lose __hash__, so an empty or thinned registry reports
    none and passes.  The seeded tests above fail on a thinned registry because the seeds
    stop decoding, which is the file falling over rather than the file noticing.
    """
    assert len(NLRI.registered_nlri) >= MIN_REGISTERED_FAMILIES, (
        f'only {len(NLRI.registered_nlri)} NLRI families are registered, so the hash sweep proves little'
    )
