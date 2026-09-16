"""RFC 9234 OTC wire boundaries and per-session semantic resolution."""

from struct import pack

import pytest

from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.open.capability.role import RoleValue
from exabgp.bgp.message.update import Update
from exabgp.bgp.message.update.attribute import Attribute, AttributeCollection, OTC, OTCNone, OTCSelf
from exabgp.bgp.neighbor import Neighbor


def session(local_as: int = 65000) -> Negotiated:
    negotiated = Negotiated(Neighbor(), Direction.OUT)
    negotiated.local_as = ASN(local_as)
    negotiated.peer_as = ASN(65001)
    negotiated.asn4 = False
    negotiated.msg_size = 4096
    return negotiated


@pytest.mark.parametrize('value', [0, ASN.MAX_4BYTE])
def test_numeric_otc_roundtrip_uses_four_octets_without_asn4(value: int) -> None:
    negotiated = session()
    attribute = OTC.make_otc(value)
    wire = b'\xc0\x23\x04' + pack('!L', value)
    assert attribute.pack_attribute(negotiated) == wire
    decoded = AttributeCollection.unpack(memoryview(wire), negotiated)[Attribute.CODE.OTC]
    assert isinstance(decoded, OTC)
    assert decoded.asn == value
    assert decoded.pack_attribute(negotiated) == wire


@pytest.mark.parametrize('value', [-1, ASN.MAX_4BYTE + 1])
def test_otc_factory_rejects_out_of_range_asns(value: int) -> None:
    with pytest.raises(ValueError):
        OTC.make_otc(value)


def test_dotted_asn_renders_as_decimal() -> None:
    attribute = OTC.make_otc(ASN.from_string('1.1'))
    assert str(attribute) == '65537'
    assert attribute.json() == '65537'
    assert attribute.pack_attribute(session()) == b'\xc0\x23\x04\x00\x01\x00\x01'


@pytest.mark.parametrize('length', [0, 3, 5])
def test_bad_otc_length_raises_notify(length: int) -> None:
    with pytest.raises(Notify):
        OTC.unpack_attribute(memoryview(bytes(length)), session())


@pytest.mark.parametrize('length', [0, 3, 4, 5])
def test_only_malformed_otc_withdraws_announced_prefix(length: int) -> None:
    negotiated = session()
    mandatory = bytes.fromhex('40010100 4002040201fde8 400304c0000201')
    attribute = mandatory + bytes([0xC0, 35, length]) + bytes(length)
    prefix = b'\x18\x0a\x00\x00'
    payload = b'\x00\x00' + pack('!H', len(attribute)) + attribute + prefix
    parsed = Update.unpack_message(payload, negotiated).parse(negotiated)
    if length == ASN.SIZE_4BYTE:
        assert [str(routed.nlri.cidr) for routed in parsed.announces] == ['10.0.0.0/24']
        assert parsed.withdraws == []
    else:
        assert parsed.announces == []
        assert [str(nlri.cidr) for nlri in parsed.withdraws] == ['10.0.0.0/24']


def test_partial_otc_is_recognized_and_duplicate_keeps_first() -> None:
    first = b'\xe0\x23\x04\x00\x00\xfd\xe8'
    second = OTC.make_otc(65001).pack_attribute(session())
    attributes = AttributeCollection.unpack(first + second, session())
    decoded = attributes[Attribute.CODE.OTC]
    assert isinstance(decoded, OTC)
    assert decoded.asn == 65000
    assert Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW not in attributes


@pytest.mark.parametrize('role', [RoleValue.NO_ROLE, RoleValue.PROVIDER])
def test_self_resolves_per_session_without_mutating_instruction(role: RoleValue) -> None:
    attribute = OTCSelf(role)
    original_hash = hash(attribute)
    assert attribute.pack_attribute(session(65000)) == OTC.make_otc(65000).pack_attribute(session())
    assert attribute.pack_attribute(session(65537)) == OTC.make_otc(65537).pack_attribute(session())
    assert attribute == OTCSelf(role)
    assert attribute != OTC.make_otc(65000)
    assert hash(attribute) == original_hash
    assert str(attribute) == ('self' if role == RoleValue.NO_ROLE else 'provider')


def test_role_assertions_remain_distinct_from_plain_self() -> None:
    assert OTCSelf() != OTCSelf(RoleValue.PROVIDER)
    assert OTCSelf(RoleValue.PROVIDER) != OTCSelf(RoleValue.CUSTOMER)


def test_self_refuses_unresolved_local_as() -> None:
    with pytest.raises(ValueError):
        OTCSelf().pack_attribute(session(0))


def test_suppression_marker_cannot_emit_wire_bytes() -> None:
    assert OTCNone().pack_attribute(session()) == b''
    assert OTCNone() == OTCNone()
    assert OTCNone() != OTCSelf()
