"""Property based tests covering every registered capability and attribute decoder.

The NLRI registry is covered by test_nlri_decoder_properties.py.  These tests hold the
other two registries a peer can reach to the same two rules from TIGER_STYLE.md 1.1:

1. Arbitrary bytes decode or raise Notify.  A raw Python exception out of a decoder
   closes the session with a traceback instead of a NOTIFICATION, and often takes the
   process, and every other peer on the box, with it.

2. What decoded must survive json(), str() and repr(), and what json() returns must be
   readable by the API subprocess it is written to.  GHSA-jcrv-p53f-v5w5 was a peer
   choosing what appeared in that stream; a line the consumer cannot parse at all is the
   same defect seen from the other side, and escaping alone does not close it.

The registries drive the parametrisation, so a capability or an attribute registered
tomorrow is covered the day it is added.

The number of examples and whether the seed varies come from the Hypothesis profiles in
conftest.py: derandomized for the gate, random and deeper for ./qa/bin/fuzz_hunt.
"""

import json as jsonlib
import struct

import pytest
from hypothesis import given, strategies as st

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability import Capability
from exabgp.bgp.message.open.capability.capability import CapabilityCode
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState

CAPABILITY_CODES = sorted(Capability.registered_capability, key=int)
CAPABILITY_IDS = [f'{int(code)}-{code}' for code in CAPABILITY_CODES]

ATTRIBUTE_KEYS = sorted(Attribute.registered_attributes, key=lambda key: (key[0], key[1]))
ATTRIBUTE_IDS = [f'{aid}-{Attribute.registered_attributes[(aid, flag)].__name__}' for aid, flag in ATTRIBUTE_KEYS]

# BGP-LS carries its own registry inside attribute 29, and a peer reaches it without
# negotiating BGP-LS: the attribute is dispatched by code, with no family gate
LSID_CODES = sorted(LinkState.registered_lsids)
LSID_IDS = [f'{code}-{LinkState.registered_lsids[code].__name__}' for code in LSID_CODES]


def parses(fragment: str) -> None:
    """A json() fragment must be readable by the API consumer it is written to.

    The fragments are members of a larger object, so they are wrapped before parsing.
    A fragment which needs no wrapping is already a complete object.
    """
    for candidate in (fragment, '{' + fragment + '}', '[' + fragment + ']'):
        try:
            jsonlib.loads(candidate)
            return
        except ValueError:
            continue
    raise AssertionError(f'json() returned something no JSON parser accepts: {fragment[:200]}')


def representations(decoded: object) -> None:
    """Everything the API and the logs ask of a decoded object must work.

    A decoder which validates in json() rather than at the boundary raises from the API
    writer, long after the message was accepted, where nothing treats it as a protocol
    error.  Validate once, at the boundary: TIGER_STYLE.md 1.1.
    """
    json_method = getattr(decoded, 'json', None)
    if callable(json_method):
        try:
            result = json_method()
        except NotImplementedError:
            # some attributes are rendered by AttributeCollection through str() and
            # never implement json(); that is a choice, not a failure to decode
            result = None
        if isinstance(result, str):
            parses(result)
    str(decoded)
    repr(decoded)


@pytest.mark.fuzz
@pytest.mark.parametrize('code', CAPABILITY_CODES, ids=CAPABILITY_IDS)
@given(data=st.binary(min_size=0, max_size=60))
def test_capability_decoders_only_raise_notify(code: CapabilityCode, data: bytes) -> None:
    """Arbitrary capability bytes decode into something usable, or Notify."""
    klass = Capability.klass(code)
    try:
        decoded = klass.unpack_capability(klass(), data, code)
    except Notify:
        return
    representations(decoded)


@pytest.mark.fuzz
@pytest.mark.parametrize('code', CAPABILITY_CODES, ids=CAPABILITY_IDS)
@given(
    length=st.integers(min_value=0, max_value=255),
    payload=st.binary(min_size=0, max_size=60),
)
def test_capability_lying_length_only_raises_notify(code: CapabilityCode, length: int, payload: bytes) -> None:
    """Several capabilities start with a length byte the peer chooses freely."""
    klass = Capability.klass(code)
    try:
        decoded = klass.unpack_capability(klass(), bytes([length]) + payload, code)
    except Notify:
        return
    representations(decoded)


@pytest.mark.fuzz
@pytest.mark.parametrize('key', ATTRIBUTE_KEYS, ids=ATTRIBUTE_IDS)
@given(data=st.binary(min_size=0, max_size=60))
def test_attribute_decoders_only_raise_notify(key: tuple[int, int], data: bytes) -> None:
    """Arbitrary attribute bytes decode into something usable, or Notify.

    ValueError is a decoder telling AttributeCollection.parse to treat the attribute as a
    withdraw, which that caller converts; it is a documented boundary, not an escape.
    """
    klass = Attribute.registered_attributes[key]
    try:
        decoded = klass.unpack_attribute(data, Negotiated.UNSET)
    except (Notify, ValueError):
        return
    if decoded is None:
        return
    representations(decoded)


@pytest.mark.fuzz
@pytest.mark.parametrize('code', LSID_CODES, ids=LSID_IDS)
@given(payload=st.binary(min_size=0, max_size=40))
def test_bgpls_tlv_decoders_only_raise_notify(code: int, payload: bytes) -> None:
    """Every registered BGP-LS TLV, held to the same rule as every other decoder.

    The TLV classes store their payload and unpack it in a property, so a TLV which
    reads past its payload does not fail in unpack_bgpls: it fails the first time the
    API writer calls json() or the logger calls repr().  Both are exercised here, and
    the JSON has to parse: TLV 1097 and 1157 let a peer choose a member of the API
    stream, which is GHSA-jcrv-p53f-v5w5 reached through attribute 29.
    """
    klass = Attribute.klass_by_id(Attribute.CODE.BGP_LS)
    assert klass is not None
    data = struct.pack('!HH', code, len(payload)) + payload
    try:
        decoded = klass.unpack_attribute(data, Negotiated.UNSET)
    except Notify:
        return
    representations(decoded)


@pytest.mark.fuzz
@pytest.mark.parametrize('code', LSID_CODES, ids=LSID_IDS)
@given(payload=st.text(min_size=0, max_size=30))
def test_bgpls_tlv_text_cannot_escape_its_json_string(code: int, payload: str) -> None:
    """Text a peer sends stays one JSON value, whatever quotes and braces it holds."""
    klass = Attribute.klass_by_id(Attribute.CODE.BGP_LS)
    assert klass is not None
    encoded = payload.encode('utf-8')
    data = struct.pack('!HH', code, len(encoded)) + encoded
    try:
        decoded = klass.unpack_attribute(data, Negotiated.UNSET)
    except Notify:
        return
    representations(decoded)
