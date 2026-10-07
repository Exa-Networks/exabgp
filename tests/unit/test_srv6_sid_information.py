"""The SRv6 SID Information sub-TLV (RFC 9252 3.1) keeps what the peer sent.

Three things it did not keep: the SID Flags octet, which was read past and then written
and reported as 0; the header of a sub-sub-TLV it did not recognise, which `pack_tlv`
dropped so the re-encoded value was three octets short per unknown sub-sub-TLV; and the
JSON of such a sub-sub-TLV, a bare object inside an object, which no parser accepts.
"""

from __future__ import annotations

import json
from struct import pack

from exabgp.bgp.message.update.attribute.sr.srv6.generic import (
    GenericSrv6ServiceDataSubSubTlv,
    GenericSrv6ServiceSubTlv,
)
from exabgp.bgp.message.update.attribute.sr.srv6.sidinformation import Srv6SidInformation
from exabgp.protocol.ip import IPv6

SID = IPv6.pton('2001:db8::1')
FLAGS = 0x80
BEHAVIOR = 0x0013
UNKNOWN_SUBSUBTLV = bytes([9]) + pack('!H', 2) + b'\xab\xcd'
STRUCTURE = bytes([1]) + pack('!H', 6) + bytes([32, 16, 16, 0, 0, 0])


def value(*subsubtlvs: bytes) -> bytes:
    return bytes([0]) + SID + bytes([FLAGS]) + pack('!H', BEHAVIOR) + bytes([0]) + b''.join(subsubtlvs)


def decoded(*subsubtlvs: bytes) -> Srv6SidInformation:
    data = value(*subsubtlvs)
    return Srv6SidInformation.unpack_attribute(data, len(data))


def test_an_unknown_sub_sub_tlv_gives_valid_json() -> None:
    information = decoded(STRUCTURE, UNKNOWN_SUBSUBTLV)
    parsed = json.loads(information.json())
    assert parsed['sid'] == '2001:db8::1'
    assert 'structure' in parsed


def test_the_flags_octet_survives_decode_and_encode() -> None:
    information = decoded(STRUCTURE)
    assert json.loads(information.json())['flags'] == FLAGS
    assert 'flags:128' in str(information)
    assert information.pack_tlv()[3 + 1 + 16] == FLAGS


def test_the_encoding_is_the_value_that_arrived() -> None:
    information = decoded(STRUCTURE, UNKNOWN_SUBSUBTLV)
    packed = information.pack_tlv()
    assert packed[3:] == value(STRUCTURE, UNKNOWN_SUBSUBTLV), 'the re-encoded sub-TLV is not what the peer sent'


def test_a_generic_service_sub_tlv_keeps_its_header() -> None:
    assert GenericSrv6ServiceSubTlv(b'\x01\x02', 7).pack_tlv() == bytes([7]) + pack('!H', 2) + b'\x01\x02'
    assert GenericSrv6ServiceDataSubSubTlv(b'\x01', 9).pack_tlv() == bytes([9]) + pack('!H', 1) + b'\x01'
