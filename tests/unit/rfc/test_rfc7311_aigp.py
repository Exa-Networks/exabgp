"""RFC 7311: what an AIGP attribute carries, and what a receiver does with a broken one."""

from __future__ import annotations

from struct import pack

import pytest

from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.aigp import AIGP

from rfc.rfc7606_wire import (
    MANDATORY,
    OPTIONAL,
    OPTIONAL_TRANSITIVE,
    announced,
    attribute,
    parse,
    session,
    update,
)

CODE = Attribute.CODE


def aigp_tlv(metric: int) -> bytes:
    return bytes([1]) + pack('!H', 11) + pack('!Q', metric)


# a TLV type RFC 7311 does not define, with a two octet value
UNKNOWN_TLV = bytes([7]) + pack('!H', 5) + b'\xaa\xbb'


def aigp_session() -> Negotiated:
    negotiated = session()
    negotiated.aigp = True
    return negotiated


def decoded(value: bytes, flag: int = OPTIONAL) -> tuple[list[str], Attribute | None]:
    parsed = parse(update(MANDATORY + attribute(flag, CODE.AIGP, value)), aigp_session())
    return announced(parsed), parsed.attributes.get(CODE.AIGP)


# ------------------------------------------------------------------ 3


@pytest.mark.rfc('rfc7311#3-other-tlvs-passed-along')
def test_every_tlv_of_the_attribute_is_sent_on() -> None:
    value = aigp_tlv(10) + UNKNOWN_TLV + aigp_tlv(20)
    _, aigp = decoded(value)
    assert aigp is not None
    packed = bytes(aigp.pack_attribute(aigp_session()))
    assert packed.endswith(value), 'a TLV after the first AIGP TLV was dropped on the way out'


@pytest.mark.rfc('rfc7311#3-other-tlvs-passed-along', polarity='negative')
def test_the_tlvs_carried_along_do_not_change_the_metric() -> None:
    _, aigp = decoded(UNKNOWN_TLV + aigp_tlv(10) + aigp_tlv(20))
    assert isinstance(aigp, AIGP)
    assert aigp.aigp == 10, 'the value of the AIGP TLV is the value of the first AIGP TLV'


# ------------------------------------------------------------------ 3.2


@pytest.mark.rfc('rfc7311#3.2-malformed-is-attribute-discard')
def test_a_malformed_aigp_is_dropped_and_the_route_kept() -> None:
    broken = bytes([1]) + pack('!H', 10) + bytes(7)
    routes, aigp = decoded(broken)
    assert routes == ['10.0.0.0/24'], 'a malformed AIGP withdrew the route, RFC 7311 3.2 says discard'
    assert aigp is None


@pytest.mark.rfc('rfc7311#3.2-malformed-is-attribute-discard', polarity='negative')
def test_a_well_formed_aigp_is_kept() -> None:
    routes, aigp = decoded(aigp_tlv(10))
    assert routes == ['10.0.0.0/24']
    assert isinstance(aigp, AIGP) and aigp.aigp == 10


@pytest.mark.rfc('rfc7311#3.2-repeated-or-unknown-tlvs-not-malformed')
def test_repeated_and_unknown_tlvs_leave_the_attribute_well_formed() -> None:
    routes, aigp = decoded(aigp_tlv(10) + aigp_tlv(20) + UNKNOWN_TLV)
    assert routes == ['10.0.0.0/24']
    assert isinstance(aigp, AIGP) and aigp.aigp == 10


@pytest.mark.rfc('rfc7311#3.2-repeated-or-unknown-tlvs-not-malformed', polarity='negative')
def test_a_truncated_tlv_still_makes_it_malformed() -> None:
    routes, aigp = decoded(aigp_tlv(10) + UNKNOWN_TLV[:4])
    assert routes == ['10.0.0.0/24']
    assert aigp is None


@pytest.mark.rfc('rfc7311#3.2-transitive-bit-is-malformed')
def test_an_aigp_with_the_transitive_bit_is_discarded() -> None:
    routes, aigp = decoded(aigp_tlv(10), flag=OPTIONAL_TRANSITIVE)
    assert routes == ['10.0.0.0/24'], 'a transitive AIGP withdrew the route, RFC 7311 3.2 says discard'
    assert aigp is None


@pytest.mark.rfc('rfc7311#3.2-transitive-bit-is-malformed', polarity='negative')
def test_an_aigp_without_the_transitive_bit_is_kept() -> None:
    _, aigp = decoded(aigp_tlv(10), flag=OPTIONAL)
    assert isinstance(aigp, AIGP)
