"""A BGP-LS node or prefix route is identified by its descriptors, not by its family.

`NODE`, `PREFIXv4` and `PREFIXv6` each did

    self._pack = packed

in `__init__`, where the base class reads `self._packed` in `pack_nlri`, `__len__` and
`index`. So `_packed` stayed at the `b''` the base set, and `pack_nlri` answered a four octet
header announcing a length of zero:

    a.pack_nlri()  00010000
    b.pack_nlri()  00010000

identical for every route of that type. `index()` is family plus `pack_nlri()`, and the RIB
keys on `index()`, so every BGP-LS node route in a session shared one key and the RIB held one
of them however many the peer advertised.

Nothing raised, because `_pack` is not a name these classes inherit: it is a method on
`GenericBGPLS`, which is a sibling and not an ancestor.

The identity was incoherent as well. `NODE.__hash__` read `(proto_id, node_ids)` while its
`__eq__` read neither, which breaks the rule that equal objects hash equal, and the two
prefix classes compared and hashed on `(CODE, domain, proto_id, route_d)` alone, so two
different prefixes of one domain were equal and hashed alike. Both now read one `_identity()`,
which carries the wire, so equality agrees with what the RIB uses.
"""

from __future__ import annotations

from typing import Any

import pytest

from exabgp.bgp.message.update.nlri.bgpls.node import NODE
from exabgp.bgp.message.update.nlri.bgpls.prefixv4 import PREFIXv4
from exabgp.bgp.message.update.nlri.bgpls.prefixv6 import PREFIXv6

# the fixed part of a node NLRI: protocol id, then a 64 bit identifier
NODE_WIRE = b'\x03' + b'\x00' * 7 + b'\x01'
LOCAL_NODE = b'\x01\x00\x00\x08\x02\x00\x00\x04\x00\x00\xff'


def node(last: int) -> Any:
    return NODE.unpack_nlri(NODE_WIRE + LOCAL_NODE + bytes([last]), rd=None)


def build(klass: Any, packed: bytes, descriptor: str = 'a', route_d: Any = None) -> Any:
    """NODE names its descriptors node_ids, the two prefix classes name theirs local_node."""
    common = {'domain': 1, 'proto_id': 3, 'packed': packed, 'route_d': route_d}
    if klass is NODE:
        return klass(node_ids=[descriptor], **common)
    return klass(local_node=descriptor, **common)


CLASSES = [NODE, PREFIXv4, PREFIXv6]


@pytest.mark.parametrize('klass', CLASSES)
def test_the_wire_is_recorded_where_the_base_class_reads_it(klass: Any) -> None:
    """The defect in one assertion: the wire went to a name nothing reads."""
    built = build(klass, b'\xaa' * 20)

    assert built._packed == b'\xaa' * 20, 'the wire was written somewhere the base class does not read'


@pytest.mark.parametrize('klass', CLASSES)
def test_pack_nlri_carries_the_body_and_its_real_length(klass: Any) -> None:
    body = b'\xaa' * 20
    built = build(klass, body)

    packed = built.pack_nlri()

    assert packed[2:4] == bytes([0, len(body)]), 'the announced length was not the body length'
    assert packed[4:] == body
    assert len(built) == len(body) + 2


@pytest.mark.parametrize('klass', CLASSES)
def test_two_routes_which_differ_do_not_share_a_rib_key(klass: Any) -> None:
    """index() is what the RIB keys on, so this is the route loss, stated directly."""
    a = build(klass, b'\xaa' * 20, 'a')
    b = build(klass, b'\xbb' * 30, 'b')

    assert a.index() != b.index(), 'two different routes would occupy one RIB entry'
    assert a != b
    assert hash(a) != hash(b)


@pytest.mark.parametrize('klass', CLASSES)
def test_equal_routes_hash_equal(klass: Any) -> None:
    """The contract NODE broke: __hash__ read node_ids where __eq__ read none of it."""
    a = build(klass, b'\xaa' * 20, 'a')
    b = build(klass, b'\xaa' * 20, 'a')

    assert a == b
    assert hash(a) == hash(b), 'equal objects must hash equal, or a dict holds both'
    assert len({a, b}) == 1


@pytest.mark.parametrize('klass', CLASSES)
def test_a_route_distinguisher_is_part_of_the_identity(klass: Any) -> None:
    """Two routes alike but for their VPN are two routes."""
    a = build(klass, b'\xaa' * 20, 'a', route_d='one')
    b = build(klass, b'\xaa' * 20, 'a', route_d='two')

    assert a != b
    assert len({a, b}) == 2, 'two VPNs collapsed into one entry'


def test_a_decoded_node_keeps_the_wire_it_arrived_on() -> None:
    """Through the real decoder, not the constructor."""
    decoded = node(0xFD)

    assert decoded._packed, 'the decoder recorded no wire at all'
    assert decoded.pack() == NODE_WIRE + LOCAL_NODE + bytes([0xFD])


def test_two_decoded_nodes_which_differ_are_two_routes() -> None:
    first, second = node(0xFD), node(0xFE)

    assert first != second
    assert first.index() != second.index()
    assert len({first, second}) == 2


def test_a_node_and_a_prefix_are_never_equal() -> None:
    """NODE.__eq__ accepted any BGPLS, which is looser than the prefix classes were."""
    a = build(NODE, b'\xaa' * 20)
    b = build(PREFIXv4, b'\xaa' * 20)

    assert a != b
    assert b != a
