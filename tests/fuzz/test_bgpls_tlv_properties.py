#!/usr/bin/env python3
# encoding: utf-8

"""Property tests over every registered BGP-LS attribute TLV

The BGP-LS attribute is dispatched by attribute code with no address family
gate, so a peer can attach it to a plain IPv4 unicast UPDATE without BGP-LS
ever being negotiated.  Every TLV payload below is therefore untrusted input.

The tests are parametrised FROM the registry, so a TLV registered next year is
covered the day it is added rather than the day someone remembers to test it.

Three properties, per TIGER_STYLE section 1.1:
  1. malformed input raises Notify, never a Python exception
  2. a decoded object survives json(), str() and repr()
  3. the JSON it emits is one parseable object, with no member the peer chose
"""

import json
from struct import pack

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState

TLVS = sorted(LinkState.registered_lsids)

# an unregistered code, which must fall through to GenericLSID
UNKNOWN_TLV = 9999

INJECTION = b'x", "injected": "owned'


def all_keys(node):
    """Every member name in the decoded JSON, at any depth"""
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from all_keys(value)
    elif isinstance(node, list):
        for value in node:
            yield from all_keys(value)


def render(scode, payload):
    """Decode one TLV the way an UPDATE would, then render it every way the API does"""
    attribute = LinkState.unpack(pack('!HH', scode, len(payload)) + payload, None, None)
    return attribute.json(), str(attribute), repr(attribute)


@pytest.mark.parametrize('scode', TLVS + [UNKNOWN_TLV])
@pytest.mark.parametrize('length', range(0, 40))
def test_short_tlv_raises_notify_or_renders(scode, length) -> None:
    """A truncated TLV is a protocol error, never a Python exception"""
    try:
        emitted, _, _ = render(scode, b'A' * length)
    except Notify:
        return
    json.loads(emitted)


@pytest.mark.parametrize('scode', TLVS + [UNKNOWN_TLV])
def test_quote_payload_cannot_inject(scode) -> None:
    """A peer must not be able to add a member of its own to the API stream"""
    try:
        emitted, _, _ = render(scode, INJECTION)
    except Notify:
        return
    parsed = json.loads(emitted)
    assert 'injected' not in set(all_keys(parsed)), f'TLV {scode} let the peer inject a member'


@pytest.mark.parametrize('scode', TLVS + [UNKNOWN_TLV])
@pytest.mark.parametrize('payload', [b'\x00' * 8, b'\xff' * 8, b'\x00\x01\x02\x03\x04\x05\x06\x07'])
def test_non_text_payload_stays_one_json_line(scode, payload) -> None:
    """Control bytes and invalid UTF-8 must not break the line delimited stream"""
    try:
        emitted, _, _ = render(scode, payload)
    except Notify:
        return
    assert len(emitted.splitlines()) == 1, f'TLV {scode} split the line delimited stream'
    json.loads(emitted)


@settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(scode=st.sampled_from(TLVS + [UNKNOWN_TLV]), payload=st.binary(min_size=0, max_size=64))
def test_arbitrary_bytes(scode, payload) -> None:
    """Random bytes into any registered TLV: Notify, or a parseable single line"""
    try:
        emitted, _, _ = render(scode, payload)
    except Notify:
        return
    json.loads(emitted)


@settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(scode=st.sampled_from(TLVS + [UNKNOWN_TLV]), text=st.text(max_size=48))
def test_arbitrary_text(scode, text) -> None:
    """Arbitrary text, which is where quotes and control characters come from"""
    try:
        emitted, _, _ = render(scode, text.encode('utf-8'))
    except Notify:
        return
    parsed = json.loads(emitted)
    assert 'injected' not in set(all_keys(parsed))


class TestValidTlvRenders:
    """Real wire payloads, which the synthetic fillers above do not reach

    A TLV which decodes but cannot be rendered breaks the API writer and the
    logger, and after the decode boundary was tightened it also closed the
    session.  These came out of the decoding functional suite.
    """

    # SRv6 End.X (TLV 1106) as sent by a real router
    SRV6_ENDX = bytes.fromhex('003980000000FC0010000112E002000000000000000004E4000420101000')

    def test_srv6_endx_renders_every_way(self) -> None:
        # LinkState.__str__ renders each TLV, so this exercises Srv6EndX.__repr__,
        # which used attribute access on what is a dict and raised AttributeError
        emitted, as_str, _ = render(1106, self.SRV6_ENDX)
        json.loads(emitted)
        assert 'behavior' in as_str
        assert 'sid' in as_str

    def test_srv6_lan_endx_isis_renders_every_way(self) -> None:
        # same shape with a six byte IS-IS neighbour id in front of the SID
        payload = bytes.fromhex('0039800000000102030405060000000000000000000000000000000000')
        try:
            emitted, as_str, _ = render(1107, payload)
        except Notify:
            pytest.skip('payload rejected by the decoder, nothing to render')
        json.loads(emitted)
        assert 'neighbor-id' in as_str


class TestNoTlvRelyOnTheBoundary:
    """LinkState.unpack converts stray exceptions into Notify, which is a backstop
    and not a substitute for a decoder checking its own reads.

    A catch-all makes a fuzz sweep come back clean while the reads are still
    unchecked, and because it also converts AttributeError and TypeError, any
    render bug on VALID traffic becomes a session teardown.  That is not
    hypothetical: it is how Srv6EndX, Srv6LanEndXOSPF, Srv6EndpointBehavior and
    Srv6SidStructure were found, all four of them broken on well formed input.

    So the boundary must catch only what nobody anticipated.  If this test fails,
    the named TLV has a read nobody checked.
    """

    BOUNDARY = 'Invalid BGP-LS attribute TLV'

    @pytest.mark.parametrize('scode', TLVS)
    def test_tlv_checks_its_own_reads(self, scode) -> None:
        masked = []
        for length in range(0, 40):
            for filler in (b'A', b'\x00', b'\xff', b'\x80', b'\x01\x02\x03'):
                payload = (filler * (length // len(filler) + 1))[:length]
                try:
                    render(scode, payload)
                except Notify as exc:
                    if self.BOUNDARY in str(exc):
                        masked.append((length, str(exc)))
                except Exception:  # noqa: BLE001 - the property tests above cover these
                    pass
        assert not masked, f'TLV {scode} relies on the decode boundary: {masked[0][1]}'
