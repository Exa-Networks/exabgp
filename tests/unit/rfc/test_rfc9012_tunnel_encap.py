"""RFC 9012: the Tunnel Encapsulation attribute, read through section 13.

Section 13 is a list of tolerances.  An unrecognised tunnel type is not an error, an
unrecognised sub-TLV is not an error, a *malformed* sub-TLV is not an error either: it is
to be treated as if it had not been recognised.  Only two things are errors, and both get
treat-as-withdraw rather than a session reset - a TLV which does not end where its final
sub-TLV ends, and an attribute with no valid TLV or without the transitive bit.

So every test here is about a decoder being too strict rather than too lax, which is the
opposite of the usual shape.  `TunnelEncap` sets neither `TREAT_AS_WITHDRAW` nor
`DISCARD`, so every `Notify` its sub-TLV walk raises leaves `AttributeCollection.parse`
and ends the session.  The tests which show that carry xfail.
"""

from __future__ import annotations

from struct import pack

import pytest

from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.collection import AttributeCollection
from exabgp.bgp.message.update.attribute.tunnel_encap import TunnelEncap

pytestmark = pytest.mark.timeout(10)

TUNNEL_ENCAP = int(Attribute.CODE.TUNNEL_ENCAP)
TREAT_AS_WITHDRAW = Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW

OPTIONAL_TRANSITIVE = 0xC0
OPTIONAL_ONLY = 0x80

SR_POLICY_TUNNEL = 15
# 1 is VXLAN in the IANA registry but exabgp registers no decoder for it, so from this
# implementation's point of view it is an unrecognised tunnel type, which is the case
# section 13 legislates for.
UNRECOGNISED_TUNNEL = 1

PREFERENCE_SUBTLV = 12
# sub-TLV type numbers below 128 carry a one octet length, 128 and above carry two
LOW_UNRECOGNISED_SUBTLV = 60
HIGH_UNRECOGNISED_SUBTLV = 200


def subtlv(subtype: int, value: bytes) -> bytes:
    if subtype < 128:
        return pack('!BB', subtype, len(value)) + value
    return pack('!BH', subtype, len(value)) + value


def preference(value: int) -> bytes:
    """Flags(1) + Reserved(1) + Preference(4)."""
    return subtlv(PREFERENCE_SUBTLV, pack('!BBI', 0, 0, value))


def tunnel(tunnel_type: int, value: bytes) -> bytes:
    return pack('!HH', tunnel_type, len(value)) + value


def attribute(value: bytes, flag: int = OPTIONAL_TRANSITIVE) -> bytes:
    return bytes([flag, TUNNEL_ENCAP, len(value)]) + value


def parse(wire: bytes) -> AttributeCollection:
    return AttributeCollection().parse(wire, Negotiated.UNSET)


def decoded(wire: bytes) -> TunnelEncap:
    attr = parse(wire)[TUNNEL_ENCAP]
    assert isinstance(attr, TunnelEncap)
    return attr


# --------------------------------------------------------------------------------------
# 13 a TLV must end where its final sub-TLV ends


@pytest.mark.rfc('rfc9012#13-tlv-ends-with-final-subtlv')
def test_a_subtlv_running_past_the_end_of_its_tlv_withdraws_rather_than_resets() -> None:
    # a Preference sub-TLV claiming six octets of value with only four to give
    overrun = tunnel(SR_POLICY_TUNNEL, subtlv(PREFERENCE_SUBTLV, b'')[:2] + b'\x06' + b'\x00' * 4)
    assert TREAT_AS_WITHDRAW in parse(attribute(overrun))


@pytest.mark.rfc('rfc9012#13-tlv-ends-with-final-subtlv')
@pytest.mark.xfail(strict=True, reason='an unregistered tunnel type keeps its value as opaque bytes, unchecked')
def test_a_short_final_subtlv_is_caught_in_an_unrecognised_tunnel_type_too() -> None:
    # the same malformation, under tunnel type 1: nothing looks inside, so nothing notices
    short = tunnel(UNRECOGNISED_TUNNEL, subtlv(LOW_UNRECOGNISED_SUBTLV, b'\x01\x02\x03')[:-1])
    assert TREAT_AS_WITHDRAW in parse(attribute(short))


@pytest.mark.rfc('rfc9012#13-tlv-ends-with-final-subtlv', polarity='negative')
def test_a_tlv_whose_final_subtlv_ends_exactly_at_its_end_is_accepted() -> None:
    attr = decoded(attribute(tunnel(SR_POLICY_TUNNEL, preference(100) + preference(200))))
    assert len(attr.tunnel_tlvs) == 1


# --------------------------------------------------------------------------------------
# 13 no valid TLV, or no transitive bit


@pytest.mark.rfc('rfc9012#13-no-valid-tlv-or-not-transitive')
def test_an_empty_tunnel_encapsulation_attribute_is_treated_as_withdraw() -> None:
    assert TREAT_AS_WITHDRAW in parse(attribute(b''))


@pytest.mark.rfc('rfc9012#13-no-valid-tlv-or-not-transitive')
def test_an_attribute_without_the_transitive_bit_is_treated_as_withdraw() -> None:
    wire = attribute(tunnel(SR_POLICY_TUNNEL, preference(100)), flag=OPTIONAL_ONLY)
    assert TREAT_AS_WITHDRAW in parse(wire)


@pytest.mark.rfc('rfc9012#13-no-valid-tlv-or-not-transitive', polarity='negative')
def test_an_optional_transitive_attribute_with_one_tlv_is_not_withdrawn() -> None:
    collection = parse(attribute(tunnel(SR_POLICY_TUNNEL, preference(100))))
    assert TREAT_AS_WITHDRAW not in collection
    assert TUNNEL_ENCAP in collection


# --------------------------------------------------------------------------------------
# 13 an unrecognised tunnel type is not malformed and must survive propagation


@pytest.mark.rfc('rfc9012#13-unknown-tunnel-type-not-malformed')
def test_an_attribute_of_nothing_but_an_unrecognised_tunnel_type_decodes() -> None:
    attr = decoded(attribute(tunnel(UNRECOGNISED_TUNNEL, b'\x01\x02\x03\x04')))
    assert len(attr.tunnel_tlvs) == 1
    assert attr.json() == '{"tunnel-type-1": "0x01020304"}'


@pytest.mark.rfc('rfc9012#13-unknown-tunnel-type-not-malformed', polarity='negative')
def test_an_unrecognised_tunnel_type_is_not_dropped_when_the_attribute_is_re_packed() -> None:
    value = tunnel(SR_POLICY_TUNNEL, preference(100)) + tunnel(UNRECOGNISED_TUNNEL, b'\x01\x02\x03\x04')
    attr = decoded(attribute(value))
    assert bytes(attr.pack_attribute(Negotiated.UNSET)) == attribute(value)


# --------------------------------------------------------------------------------------
# 13 a repeated single-occurrence sub-TLV: all but the first disregarded, none removed


@pytest.mark.rfc('rfc9012#13-duplicate-subtlv-first-wins')
@pytest.mark.xfail(strict=True, reason='both Preference sub-TLVs are kept and both reach the json')
def test_a_repeated_preference_subtlv_keeps_only_the_first() -> None:
    attr = decoded(attribute(tunnel(SR_POLICY_TUNNEL, preference(100) + preference(200))))
    assert attr.json() == '{"sr-policy": {"preference": 100}}'


@pytest.mark.rfc('rfc9012#13-duplicate-subtlv-first-wins', polarity='negative')
def test_a_repeated_preference_subtlv_does_not_make_the_tlv_malformed() -> None:
    value = tunnel(SR_POLICY_TUNNEL, preference(100) + preference(200))
    collection = parse(attribute(value))
    assert TREAT_AS_WITHDRAW not in collection
    # and the sentence's other half: every sub-TLV is still there to be propagated
    attr = collection[TUNNEL_ENCAP]
    assert isinstance(attr, TunnelEncap)
    assert bytes(attr.pack_attribute(Negotiated.UNSET)) == attribute(value)


# --------------------------------------------------------------------------------------
# 13 an unrecognised sub-TLV is skipped but kept


@pytest.mark.rfc('rfc9012#13-unrecognized-subtlv-ignored-and-kept')
def test_an_unrecognised_subtlv_does_not_stop_the_tlv_being_processed() -> None:
    value = tunnel(SR_POLICY_TUNNEL, subtlv(LOW_UNRECOGNISED_SUBTLV, b'\xaa\xbb') + preference(100))
    attr = decoded(attribute(value))
    assert '"preference": 100' in attr.json()


@pytest.mark.rfc('rfc9012#13-unrecognized-subtlv-ignored-and-kept', polarity='negative')
def test_an_unrecognised_subtlv_above_127_keeps_its_two_octet_length_on_re_encode() -> None:
    # the length field width follows the type number, so a decoder which re-encoded a
    # type 200 sub-TLV with a one octet length would shift everything after it
    value = tunnel(SR_POLICY_TUNNEL, subtlv(HIGH_UNRECOGNISED_SUBTLV, b'\xaa\xbb\xcc') + preference(100))
    attr = decoded(attribute(value))
    assert bytes(attr.pack_attribute(Negotiated.UNSET)) == attribute(value)


# --------------------------------------------------------------------------------------
# 13 a malformed sub-TLV must be treated as an unrecognised one


@pytest.mark.rfc('rfc9012#13-malformed-subtlv-as-unrecognized')
def test_a_one_byte_subtlv_tail_does_not_reset_the_session() -> None:
    value = tunnel(SR_POLICY_TUNNEL, preference(100) + bytes([LOW_UNRECOGNISED_SUBTLV]))
    assert TUNNEL_ENCAP in parse(attribute(value)) or TREAT_AS_WITHDRAW in parse(attribute(value))


@pytest.mark.rfc('rfc9012#13-malformed-subtlv-as-unrecognized')
def test_a_subtlv_above_127_with_a_truncated_length_field_does_not_reset_the_session() -> None:
    value = tunnel(SR_POLICY_TUNNEL, preference(100) + bytes([HIGH_UNRECOGNISED_SUBTLV, 0x00]))
    assert TUNNEL_ENCAP in parse(attribute(value)) or TREAT_AS_WITHDRAW in parse(attribute(value))


@pytest.mark.rfc('rfc9012#13-malformed-subtlv-as-unrecognized', polarity='negative')
def test_a_malformed_subtlv_no_longer_ends_the_session() -> None:
    """This used to pin the defect, so that the tests above could not pass by accident.

    Five bytes reached AttributeCollection.parse as a Notify(3,1) and became a
    NOTIFICATION: a peer could end the session with a one-byte sub-TLV tail. It is kept,
    inverted, because the assertion that matters is not that the session survives but
    that it survives *and* the route is withdrawn, which is what RFC 9012 13 asks for
    and is a different outcome from the attribute being quietly dropped.
    """
    value = tunnel(SR_POLICY_TUNNEL, preference(100) + bytes([LOW_UNRECOGNISED_SUBTLV]))

    parsed = parse(attribute(value))

    assert TREAT_AS_WITHDRAW in parsed, 'a malformed sub-TLV neither withdrew the route nor reset the session'


# --------------------------------------------------------------------------------------
# 13 a zero length sub-TLV must not make the walk spin


@pytest.mark.rfc('rfc9012#13-unrecognized-subtlv-ignored-and-kept')
def test_a_run_of_zero_length_tlvs_and_subtlvs_terminates() -> None:
    value = tunnel(UNRECOGNISED_TUNNEL, b'') * 4
    assert len(decoded(attribute(value)).tunnel_tlvs) == 4
    inner = subtlv(LOW_UNRECOGNISED_SUBTLV, b'') * 4
    assert len(decoded(attribute(tunnel(SR_POLICY_TUNNEL, inner))).tunnel_tlvs) == 1
