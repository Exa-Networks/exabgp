"""RFC 7311: what an AIGP attribute carries, what a receiver does with a broken one, and where it goes."""

from __future__ import annotations

from struct import pack

import pytest

from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute import aigp as aigp_module
from exabgp.bgp.message.update.attribute.aigp import AIGP
from exabgp.util.enumeration import TriState

from rfc.rfc7606_wire import (
    MANDATORY,
    NEXT_HOP,
    OPTIONAL,
    OPTIONAL_TRANSITIVE,
    ORIGIN_IGP,
    WELL_KNOWN_TRANSITIVE,
    announced,
    attribute,
    internal_session,
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
    negotiated.aigp = TriState.TRUE
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


# ------------------------------------------------------------------ 3.3

# RFC 5065: our Member-AS, another member of the same confederation, and its identifier
MEMBER = 65001
OTHER_MEMBER = 65002
IDENTIFIER = 65000


def configured(negotiated: Negotiated, aigp: TriState) -> Negotiated:
    """The session with AIGP_SESSION as the operator configured it, UNSET for the default.

    Configured on the neighbor, and read back the way a session made from it reads it.
    """
    negotiated.neighbor.capability.aigp = aigp
    negotiated.aigp = Negotiated.make_negotiated(negotiated.neighbor, Direction.IN).aigp
    return negotiated


def confederation_member() -> Negotiated:
    """An EBGP session to another Member-AS of our confederation."""
    negotiated = session(peer_as=OTHER_MEMBER)
    neighbor = negotiated.neighbor.session
    neighbor.local_as = ASN(MEMBER)
    neighbor.peer_as = ASN(OTHER_MEMBER)
    neighbor.confederation = ASN(IDENTIFIER)
    neighbor.confederation_members = (ASN(OTHER_MEMBER),)
    negotiated.local_as = ASN(MEMBER)
    return negotiated


def sent_on(negotiated: Negotiated) -> bool:
    return bytes(AIGP.from_int(10).pack_attribute(negotiated)) != b''


# RFC 5065 5.3: a route from another Member-AS starts with an AS_CONFED_SEQUENCE naming it
CONFED_SEQUENCE = 3
MEMBER_PATH = attribute(WELL_KNOWN_TRANSITIVE, CODE.AS_PATH, bytes([CONFED_SEQUENCE, 1]) + pack('!L', OTHER_MEMBER))
FROM_A_MEMBER = ORIGIN_IGP + MEMBER_PATH + NEXT_HOP


def received_on(negotiated: Negotiated, mandatory: bytes = MANDATORY) -> Attribute | None:
    parsed = parse(update(mandatory + attribute(OPTIONAL, CODE.AIGP, aigp_tlv(10))), negotiated)
    assert announced(parsed) == ['10.0.0.0/24'], 'the AIGP attribute cost the route it came with'
    return parsed.attributes.get(CODE.AIGP)


@pytest.mark.rfc('rfc7311#3.3-aigp-session-configurable')
def test_aigp_session_enabled_by_the_operator_holds_on_an_external_session() -> None:
    negotiated = configured(session(), TriState.TRUE)
    assert sent_on(negotiated)
    assert isinstance(received_on(negotiated), AIGP)


@pytest.mark.rfc('rfc7311#3.3-aigp-session-configurable', polarity='negative')
@pytest.mark.rfc('rfc7311#3.3-not-sent-when-disabled')
def test_aigp_session_disabled_by_the_operator_holds_on_an_internal_session() -> None:
    """Being internal used to send the attribute whatever the configuration said."""
    assert not sent_on(configured(internal_session(), TriState.FALSE))


@pytest.mark.rfc('rfc7311#3.3-not-sent-when-disabled', polarity='negative')
def test_the_attribute_is_sent_on_an_internal_session_left_at_its_default() -> None:
    assert sent_on(configured(internal_session(), TriState.UNSET))


@pytest.mark.rfc('rfc7311#3.3-default-disabled-external')
def test_an_external_session_left_at_its_default_neither_sends_nor_keeps_it() -> None:
    negotiated = configured(session(), TriState.UNSET)
    assert not sent_on(negotiated)
    assert received_on(negotiated) is None


@pytest.mark.rfc('rfc7311#3.3-default-disabled-external', polarity='negative')
@pytest.mark.rfc('rfc7311#3.3-default-enabled-internal')
def test_a_session_to_another_confederation_member_is_enabled_by_default() -> None:
    """EBGP, but inside the confederation: the default is the one of an internal session."""
    negotiated = configured(confederation_member(), TriState.UNSET)
    assert negotiated.confed_member, 'the session built is not to another Member-AS'
    assert sent_on(negotiated)
    assert isinstance(received_on(negotiated, FROM_A_MEMBER), AIGP)


@pytest.mark.rfc('rfc7311#3.3-default-enabled-internal')
def test_an_internal_session_left_at_its_default_keeps_what_it_receives() -> None:
    """It sent the attribute by default, and threw away the same attribute coming back."""
    assert isinstance(received_on(configured(internal_session(), TriState.UNSET)), AIGP)


@pytest.mark.rfc('rfc7311#3.3-ignored-when-disabled')
def test_an_aigp_received_on_a_disabled_internal_session_is_ignored() -> None:
    assert received_on(configured(internal_session(), TriState.FALSE)) is None


@pytest.mark.rfc('rfc7311#3.3-ignored-when-disabled', polarity='negative')
def test_an_aigp_received_on_an_enabled_session_is_kept() -> None:
    assert isinstance(received_on(configured(internal_session(), TriState.TRUE)), AIGP)


@pytest.mark.rfc('rfc7311#3.3-log-when-disabled')
def test_an_aigp_ignored_on_a_disabled_session_is_logged_once_per_session(monkeypatch: pytest.MonkeyPatch) -> None:
    said: list[str] = []
    monkeypatch.setattr(aigp_module.log, 'info', lambda message, source='': said.append(message()))
    negotiated = configured(session(), TriState.FALSE)

    # the attribute cache is per session: a different metric each time is decoded again
    for metric in (10, 20, 30):
        parse(update(MANDATORY + attribute(OPTIONAL, CODE.AIGP, aigp_tlv(metric))), negotiated)

    assert len(said) == 1, f'expected one log line for the session, got {said}'
    assert 'aigp' in said[0]


@pytest.mark.rfc('rfc7311#3.3-log-when-disabled', polarity='negative')
def test_an_aigp_kept_on_an_enabled_session_is_not_logged(monkeypatch: pytest.MonkeyPatch) -> None:
    said: list[str] = []
    monkeypatch.setattr(aigp_module.log, 'info', lambda message, source='': said.append(message()))

    received_on(configured(session(), TriState.TRUE))

    assert said == []
