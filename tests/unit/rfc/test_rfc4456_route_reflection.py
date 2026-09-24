"""RFC 4456: the two attributes a route reflector adds, read by something which is not one.

exabgp is not a route reflector.  It never takes a route from one peer and sends it to
another, it has no local CLUSTER_ID, and it runs no decision process, so most of RFC 4456
is recorded in qa/rfc/rfc4456.toml as not-applicable.  What is left is the part which
still binds: ORIGINATOR_ID and CLUSTER_LIST arrive on the wire, are decoded, are reported
to the JSON API, and go back out unchanged.

Only one test pair below carries an `rfc()` marker.  The rest are deliberately unmarked,
because RFC 4456 states the wire format of both attributes with no RFC 2119 keyword
anywhere: "This attribute is 4 bytes long", "It is a sequence of CLUSTER_ID values".  A
test may not claim a requirement the document does not make, so the length rules are
tested as what they actually are here - RFC 7606 section 7 attribute length handling -
and the ledger says so in a comment rather than in an entry.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.clusterlist import ClusterList
from exabgp.bgp.message.update.attribute.collection import AttributeCollection
from exabgp.bgp.message.update.attribute.originatorid import OriginatorID

# RFC 4456 section 8 gives both attributes as optional non-transitive, so the flag octet
# of RFC 4271 section 4.3 is 0x80 and not the 0xC0 the community attributes carry.
OPTIONAL_NON_TRANSITIVE = 0x80

ORIGINATOR_ID = int(Attribute.CODE.ORIGINATOR_ID)
CLUSTER_LIST = int(Attribute.CODE.CLUSTER_LIST)
ORIGIN = int(Attribute.CODE.ORIGIN)
TREAT_AS_WITHDRAW = int(Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW)

CLUSTER_ID_SIZE_BYTES = 4
ORIGINATOR_ID_SIZE_BYTES = 4


def session() -> Any:
    """A negotiated session with the attribute cache off.

    The cache is keyed on the packed bytes, so leaving it on would let one test's parse
    answer another test's.
    """
    negotiated = Mock()
    negotiated.asn4 = False
    negotiated.families = []
    negotiated.nexthop = []
    negotiated.msg_size = 4096
    negotiated.direction = Action.ANNOUNCE
    negotiated.attribute_cache = None
    negotiated.attribute_cache_packed = b''
    negotiated.attribute_cache_enabled = False
    return negotiated


def attribute(code: int, value: bytes) -> bytes:
    """One optional non-transitive attribute carrying `value`, with an honest length."""
    return bytes([OPTIONAL_NON_TRANSITIVE, code, len(value)]) + value


def parse(wire: bytes) -> AttributeCollection:
    """Run an attribute section through the real parser, not through one decoder."""
    return AttributeCollection().parse(wire, session())


def withdrawn(collection: AttributeCollection) -> bool:
    """Did the parser decide this UPDATE takes the treat-as-withdraw approach?"""
    return TREAT_AS_WITHDRAW in collection


# ============================================ section 8, ORIGINATOR_ID is not invented


@pytest.mark.rfc('rfc4456#8-no-second-originator-id')
def test_a_received_originator_id_is_carried_back_out_unchanged() -> None:
    """The route already has one, so exabgp must not put its own there instead."""
    origin = bytes([10, 1, 2, 3])
    collection = parse(attribute(ORIGINATOR_ID, origin))

    decoded = collection[ORIGINATOR_ID]
    assert isinstance(decoded, OriginatorID)
    assert decoded.top() == '10.1.2.3'
    # the whole attribute, header and all, has to come back the way it arrived: a
    # substituted identifier would still be four octets and would still decode
    assert decoded.pack_attribute(session()) == attribute(ORIGINATOR_ID, origin)


@pytest.mark.rfc('rfc4456#8-no-second-originator-id', polarity='negative')
def test_an_update_without_an_originator_id_does_not_gain_one() -> None:
    """The other direction: creating one where none existed is the same defect."""
    # a lone ORIGIN attribute, well-formed, so the parse succeeds on its own terms
    collection = parse(bytes([0x40, ORIGIN, 1, 0]))

    assert not withdrawn(collection)
    assert ORIGINATOR_ID not in collection


@pytest.mark.rfc('rfc4456#8-no-second-originator-id', polarity='negative')
@pytest.mark.xfail(
    strict=True,
    reason='the parser keeps the first ORIGINATOR_ID and drops the second in silence, no treat-as-withdraw',
)
def test_two_originator_ids_in_one_update_are_not_merged_into_one() -> None:
    """A peer sending the attribute twice must not leave us picking one silently.

    RFC 7606 section 3 (g) makes a repeated attribute treat-as-withdraw.  What happens
    instead is that `AttributeCollection.add` keeps whichever came first, so the route is
    reported with one of the two identifiers and nothing says the other existed.  The
    'multiple attribute' Notify in collection.py is not on this path.
    """
    first = attribute(ORIGINATOR_ID, bytes([10, 1, 2, 3]))
    second = attribute(ORIGINATOR_ID, bytes([10, 9, 9, 9]))

    collection = parse(first + second)

    assert withdrawn(collection)


# ==================================== section 8, the lengths RFC 4456 never made normative
#
# RFC 4456 says ORIGINATOR_ID "is 4 bytes long" and CLUSTER_LIST "is a sequence of
# CLUSTER_ID values" in plain prose, with no RFC 2119 keyword, so these tests carry no
# rfc() marker.  They are still the tests which matter: both classes set
# TREAT_AS_WITHDRAW, and what they prove is that a bad length reaches that path instead of
# reaching the reactor as a NOTIFICATION.


@pytest.mark.parametrize('size', [0, 1, 3, 5, 8])
def test_an_originator_id_which_is_not_four_octets_is_treat_as_withdraw(size: int) -> None:
    collection = parse(attribute(ORIGINATOR_ID, bytes(size)))

    assert withdrawn(collection)
    assert ORIGINATOR_ID not in collection


@pytest.mark.parametrize('count', [1, 2, 5])
def test_a_cluster_list_of_whole_cluster_ids_decodes_in_order(count: int) -> None:
    value = b''.join(bytes([n + 1, n + 1, n + 1, n + 1]) for n in range(count))

    collection = parse(attribute(CLUSTER_LIST, value))

    decoded = collection[CLUSTER_LIST]
    assert isinstance(decoded, ClusterList)
    clusters = decoded.clusters
    assert len(clusters) == count
    # order is the reflection path, so a decoder which sorted or set-ified would be wrong
    assert [str(_) for _ in clusters] == ['{0}.{0}.{0}.{0}'.format(n + 1) for n in range(count)]
    assert decoded.pack_attribute(session()) == attribute(CLUSTER_LIST, value)


@pytest.mark.parametrize('size', [1, 2, 3, 5, 6, 7, 9])
def test_a_cluster_list_which_is_not_a_multiple_of_four_is_treat_as_withdraw(size: int) -> None:
    collection = parse(attribute(CLUSTER_LIST, bytes(size)))

    assert withdrawn(collection)
    assert CLUSTER_LIST not in collection


def test_an_empty_cluster_list_is_treat_as_withdraw() -> None:
    """Zero is a multiple of four, so this is the case the length check alone misses."""
    collection = parse(attribute(CLUSTER_LIST, b''))

    assert withdrawn(collection)
    assert CLUSTER_LIST not in collection
