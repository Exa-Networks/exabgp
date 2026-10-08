"""RFC 9252 section 7: what a receiver does with an SRv6 Service TLV which is wrong.

The SRv6 Service TLVs (L3, type 5, and L2, type 6) live inside the BGP Prefix-SID
attribute, whose own RFC 8669 answer to a malformation is attribute discard: the label
information goes, the route stays.  RFC 9252 7 overrides that for these two TLVs, and for
a reason it states itself: "The SRv6 overlay service requires the Service SID for
forwarding."  A route kept without its SID is a route nobody can forward on, so a
malformed SRv6 Service TLV withdraws the routes of the UPDATE.

That makes one attribute answer two ways, and these tests hold both: a malformed SRv6
Service TLV withdraws, a malformed Label-Index (see test_rfc8669_prefix_sid.py) still
only discards.

The same section narrows what "malformed" may mean: lengths which disagree with what
encloses them, and nothing else.  A SID Structure sub-sub-TLV of the wrong size for its
fields is a semantic failure, which neither withdraws the route nor loses the attribute.
"""

from __future__ import annotations

from struct import pack

import pytest

from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.sr.prefixsid import PrefixSid

from rfc import rfc7606_wire as wire

pytestmark = pytest.mark.timeout(10)

PREFIX_SID = int(Attribute.CODE.BGP_PREFIX_SID)

LABEL_INDEX_TLV = 1
SRV6_L3_SERVICE_TLV = 5
SRV6_L2_SERVICE_TLV = 6
SID_INFORMATION_SUB_TLV = 1
SID_STRUCTURE_SUB_SUB_TLV = 1

# Section 3.1: RESERVED1(1) + SID(16) + Flags(1) + Endpoint Behavior(2) + RESERVED2(1)
SID_INFORMATION_FIXED = 21
SID = bytes.fromhex('20010db8000000000000000000000001')
END_DT4 = 0x0013

ROUTE = '10.0.0.0/24'


def tlv(code: int, value: bytes) -> bytes:
    """Every level of RFC 9252 nesting has the same header: one octet type, two of length."""
    return bytes([code]) + pack('!H', len(value)) + value


def sid_information(sub_sub_tlvs: bytes = b'') -> bytes:
    """Section 3.1: a SID Information sub-TLV carrying SID, behaviour and sub-sub-TLVs."""
    return tlv(SID_INFORMATION_SUB_TLV, bytes(1) + SID + bytes(1) + pack('!H', END_DT4) + bytes(1) + sub_sub_tlvs)


def service(code: int, sub_tlvs: bytes) -> bytes:
    """Section 2: an SRv6 Service TLV, a reserved octet then its sub-TLVs."""
    return tlv(code, bytes(1) + sub_tlvs)


def update_with_prefix_sid(value: bytes) -> bytes:
    """An UPDATE announcing ROUTE with the mandatory attributes and this Prefix-SID value."""
    return wire.update(wire.MANDATORY + wire.attribute(wire.OPTIONAL_TRANSITIVE, PREFIX_SID, value))


def received(value: bytes) -> tuple[list[str], list[str], PrefixSid | None]:
    """Announced routes, withdrawn routes, and the Prefix-SID the routes kept."""
    session = wire.session()
    parsed = wire.parse(update_with_prefix_sid(value), session)
    kept = parsed.attributes.get(PREFIX_SID)
    assert kept is None or isinstance(kept, PrefixSid)
    return wire.announced(parsed), wire.withdrawn_routes(parsed), kept


# A SID Information sub-TLV whose length is under 21, the first shape section 7 names.
SHORT_SID_INFORMATION = tlv(SID_INFORMATION_SUB_TLV, bytes(10))

MALFORMED_SERVICES = {
    'l3-short-sid-information': service(SRV6_L3_SERVICE_TLV, SHORT_SID_INFORMATION),
    'l2-short-sid-information': service(SRV6_L2_SERVICE_TLV, SHORT_SID_INFORMATION),
    # "The TLV Length is less than 1."
    'l3-empty': tlv(SRV6_L3_SERVICE_TLV, b''),
    # "The Sub-TLV Length is inconsistent with the length of the enclosing SRv6 Service TLV."
    'l3-sub-tlv-overruns': service(SRV6_L3_SERVICE_TLV, bytes([SID_INFORMATION_SUB_TLV]) + pack('!H', 40)),
    # "The TLV Length is inconsistent with the length of the BGP Prefix-SID attribute."
    'l3-overruns-the-attribute': bytes([SRV6_L3_SERVICE_TLV]) + pack('!H', 200) + bytes(1) + sid_information(),
}


# ============================================== section 7, treat-as-withdraw for the services


@pytest.mark.rfc('rfc9252#7-malformed-service-tlv-treat-as-withdraw', polarity='negative')
@pytest.mark.parametrize('value', list(MALFORMED_SERVICES.values()), ids=list(MALFORMED_SERVICES))
def test_a_malformed_srv6_service_tlv_withdraws_the_route(value: bytes) -> None:
    """It was attribute discard, so the route stayed announced with no SID to forward on."""
    announced, withdrawn, _ = received(value)

    assert announced == [], 'the route survived a malformed SRv6 Service TLV'
    assert withdrawn == [ROUTE]


@pytest.mark.rfc('rfc9252#7-malformed-service-tlv-treat-as-withdraw')
def test_a_well_formed_srv6_service_tlv_keeps_the_route_and_its_sid() -> None:
    """The positive side: a parser which withdrew every SRv6 route passes the test above."""
    announced, withdrawn, kept = received(service(SRV6_L3_SERVICE_TLV, sid_information()))

    assert announced == [ROUTE]
    assert withdrawn == []
    assert kept is not None and '2001:db8::1' in kept.json()


@pytest.mark.rfc('rfc9252#7-malformed-service-tlv-treat-as-withdraw')
def test_a_malformed_label_index_beside_the_services_is_still_only_discarded() -> None:
    """RFC 8669 6 still answers for every other TLV: the route stays, the attribute goes."""
    announced, withdrawn, kept = received(tlv(LABEL_INDEX_TLV, bytes(3)))

    assert announced == [ROUTE]
    assert withdrawn == []
    assert kept is None


@pytest.mark.rfc('rfc9252#7-malformed-service-tlv-treat-as-withdraw')
def test_a_sid_structure_of_the_wrong_size_is_not_malformed() -> None:
    """Section 7: a sub-sub-TLV is malformed only when its length disagrees with its sub-TLV.

    The six fields of section 3.2.1 not fitting in the value is semantic.  The decoder
    raised ValueError for it, which attribute discard turned into the loss of the SID.
    The sub-sub-TLV is kept, byte for byte, as one this decoder cannot read.
    """
    odd_structure = tlv(SID_STRUCTURE_SUB_SUB_TLV, bytes([32, 16, 16, 0, 0]))
    value = service(SRV6_L3_SERVICE_TLV, sid_information(odd_structure))

    announced, withdrawn, kept = received(value)

    assert announced == [ROUTE]
    assert withdrawn == []
    assert kept is not None
    assert bytes(kept.pack_attribute(wire.session()))[3:] == value


# ================================================= section 7, one instance of each service


@pytest.mark.rfc('rfc9252#7-l3-service-first-instance')
def test_only_the_first_srv6_l3_service_tlv_is_kept() -> None:
    first = service(SRV6_L3_SERVICE_TLV, sid_information())
    second = service(SRV6_L3_SERVICE_TLV, sid_information() + sid_information())

    _, _, kept = received(first + second)

    assert kept is not None
    assert [type(entry).__name__ for entry in kept.sr_attrs] == ['Srv6L3Service']
    assert len(kept.sr_attrs[0].subtlvs) == 1


@pytest.mark.rfc('rfc9252#7-l3-service-first-instance', polarity='negative')
def test_a_malformed_second_srv6_l3_service_tlv_is_ignored_not_withdrawn() -> None:
    """Ignored means not read: a broken second copy is no reason to withdraw the route."""
    first = service(SRV6_L3_SERVICE_TLV, sid_information())
    second = service(SRV6_L3_SERVICE_TLV, SHORT_SID_INFORMATION)

    announced, withdrawn, kept = received(first + second)

    assert announced == [ROUTE]
    assert withdrawn == []
    assert kept is not None and len(kept.sr_attrs) == 1


@pytest.mark.rfc('rfc9252#7-l2-service-first-instance')
def test_only_the_first_srv6_l2_service_tlv_is_kept() -> None:
    first = service(SRV6_L2_SERVICE_TLV, sid_information())
    second = service(SRV6_L2_SERVICE_TLV, sid_information() + sid_information())

    _, _, kept = received(first + second)

    assert kept is not None
    assert [type(entry).__name__ for entry in kept.sr_attrs] == ['Srv6L2Service']
    assert len(kept.sr_attrs[0].subtlvs) == 1


@pytest.mark.rfc('rfc9252#7-l2-service-first-instance', polarity='negative')
def test_a_malformed_second_srv6_l2_service_tlv_is_ignored_not_withdrawn() -> None:
    first = service(SRV6_L2_SERVICE_TLV, sid_information())
    second = service(SRV6_L2_SERVICE_TLV, SHORT_SID_INFORMATION)

    announced, withdrawn, kept = received(first + second)

    assert announced == [ROUTE]
    assert withdrawn == []
    assert kept is not None and len(kept.sr_attrs) == 1
