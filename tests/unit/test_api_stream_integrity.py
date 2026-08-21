"""What a peer sends must never corrupt or crash the JSON API stream.

GHSA-jcrv-p53f-v5w5 was a peer choosing what appeared in the stream ExaBGP writes to
every subscribed API subprocess.  Escaping closed that.  These are the cases found by
the property tests in tests/fuzz afterwards, where a peer instead makes ExaBGP write a
line no JSON parser accepts, or makes the encoder raise on its way there.

Both matter to the same consumer: a DDoS mitigation or FlowSpec controller reading the
stream is equally broken by an injected member, by a line it cannot parse, and by a
session that died mid-write.  TIGER_STYLE.md 1.1: validate once, at the boundary, and
what decoded must survive json(), str() and index().
"""

import json as jsonlib
import struct

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability import Capability
from exabgp.bgp.message.open.capability.capability import CapabilityCode
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.collection import AttributeCollection
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI

FLOW_FAMILIES = [
    (AFI.ipv4, SAFI.flow_ip),
    (AFI.ipv4, SAFI.flow_vpn),
    (AFI.ipv6, SAFI.flow_ip),
    (AFI.ipv6, SAFI.flow_vpn),
]


FLOW_FAMILIES = [
    (AFI.ipv4, SAFI.flow_ip),
    (AFI.ipv4, SAFI.flow_vpn),
    (AFI.ipv6, SAFI.flow_ip),
    (AFI.ipv6, SAFI.flow_vpn),
]


def parsed(fragment: str) -> dict[str, object]:
    """Parse a json() result the way the API consumer parses the line holding it.

    Some json() methods return a complete object, others a member of the object their
    caller is building.  Both have to be readable; which one it is, is not the point.
    """
    for candidate in (fragment, '{' + fragment + '}'):
        try:
            decoded: dict[str, object] = jsonlib.loads(candidate)
            return decoded
        except ValueError:
            continue
    raise AssertionError(f'json() returned something no JSON parser accepts: {fragment[:200]}')


@pytest.mark.parametrize('family', FLOW_FAMILIES, ids=lambda f: f'{f[0]}/{f[1]}')
def test_flow_fragment_with_a_two_byte_value_does_not_crash(family: tuple[AFI, SAFI]) -> None:
    """The fragment component is an IOperationByteShort, so it may carry two bytes.

    Its decoder was ord(), which takes one, so a two byte fragment raised TypeError out
    of unpack_nlri and killed the process instead of closing the session.
    """
    afi, safi = family
    # component 0x0C (fragment), operator 0x90: end of list, two byte value
    payload = b'\x0c\x90\x00\x01'
    if safi == SAFI.flow_vpn:
        payload = bytes(8) + payload
    data = bytes([len(payload)]) + payload
    nlri, _ = NLRI.unpack_nlri(afi, safi, data, Action.ANNOUNCE, None, None)
    assert nlri is not NLRI.INVALID, 'a fragment component may carry a two byte value'
    assert 'fragment' in parsed(nlri.json())


def _addpath(data: bytes) -> Capability:
    code: CapabilityCode = CapabilityCode.ADD_PATH
    klass = Capability.klass(code)
    return klass.unpack_capability(klass(), data, code)


def _decode_attribute(code: int, data: bytes) -> Attribute:
    klass = Attribute.klass_by_id(code)
    assert klass is not None, f'attribute {code} is not registered'
    return klass.unpack_attribute(data, Negotiated.UNSET)


def _pmsi(data: bytes) -> Attribute:
    return _decode_attribute(Attribute.CODE.PMSI_TUNNEL, data)


def _linkstate(data: bytes) -> Attribute:
    return _decode_attribute(Attribute.CODE.BGP_LS, data)


def _tlv(code: int, payload: bytes) -> Attribute:
    return _linkstate(struct.pack('!HH', code, len(payload)) + payload)


def keys_anywhere(decoded: object) -> set[str]:
    """Every key in the structure, however deep.

    Checking only the top level would miss a member injected inside a nested object, and
    checking whether the payload text appears anywhere is the wrong test: correctly
    escaped text appears as a value, which is exactly what should happen.
    """
    if isinstance(decoded, dict):
        found = set(decoded)
        for value in decoded.values():
            found |= keys_anywhere(value)
        return found
    if isinstance(decoded, list):
        found: set[str] = set()
        for item in decoded:
            found |= keys_anywhere(item)
        return found
    return set()
