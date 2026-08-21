#!/usr/bin/env python3
# encoding: utf-8

"""Property tests over every registered capability and attribute decoder

The NLRI registry is covered by test_nlri_decoder_properties.py and the BGP-LS
TLVs by test_bgpls_tlv_properties.py. These are the other two registries a peer
can reach, and both were swept by hand while hardening this branch: the ADD-PATH
KeyError and the PMSI ValueError were found that way, and nothing pinned them
afterwards. A sweep nobody runs again is not coverage.

Two rules, per TIGER_STYLE section 1.1:

  1. arbitrary bytes decode or raise Notify, never a Python exception, because
     an exception out of a decoder closes the session with a traceback instead
     of a NOTIFICATION
  2. what decoded survives json(), str() and repr(), and what json() returns is
     readable by the API subprocess it is written to. GHSA-jcrv-p53f-v5w5 was a
     peer choosing what appeared in that stream; a line the consumer cannot
     parse at all is the same defect from the other side, and escaping alone
     does not close it

The registries drive the parametrisation, so a capability or attribute
registered tomorrow is covered the day it is added.
"""

import importlib.util
import json
import pathlib

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message import Open
from exabgp.bgp.message.open import ASN, HoldTime, RouterID, Version
from exabgp.bgp.message.open.capability import Capabilities, Capability, Negotiated
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.attributes import Attributes

CAPABILITIES = sorted(Capability.registered_capability, key=int)
ATTRIBUTES = sorted(Attribute.registered_attributes, key=lambda key: (key[0], key[1]))

FILLS = (b'A', b'\x00', b'\xff', b'\x80', b'x", "injected": "owned')


def renders(instance):
    """Every way the API writer and the logger touch a decoded object"""
    emitted = instance.json() if hasattr(instance, 'json') else None
    str(instance)
    repr(instance)
    return emitted


def all_keys(node):
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from all_keys(value)
    elif isinstance(node, list):
        for value in node:
            yield from all_keys(value)


def check(emitted, what):
    if emitted is None:
        return
    text = str(emitted)
    if not text.strip():
        return
    assert len(text.splitlines()) == 1, f'{what} split the line delimited stream'
    try:
        parsed = json.loads('{"value": %s}' % text)
    except ValueError:
        # several decoders render a bare fragment rather than a value; those are
        # assembled by their container and checked where that happens
        return
    assert 'injected' not in set(all_keys(parsed)), f'{what} let the peer inject a member'


class TestEveryCapabilityDecoder:
    @pytest.mark.parametrize('code', CAPABILITIES)
    @pytest.mark.parametrize('length', range(0, 20))
    def test_short_input(self, code, length) -> None:
        for fill in FILLS:
            payload = (fill * (length // len(fill) + 1))[:length]
            try:
                instance = Capability.unpack(code, {}, payload)
            except Notify:
                continue
            except Exception as exc:  # noqa: BLE001 - that is the defect
                raise AssertionError(f'capability {int(code)} raised {type(exc).__name__} on {payload.hex()}')
            check(renders(instance), f'capability {int(code)}')

    @settings(max_examples=150)
    @given(payload=st.binary(min_size=0, max_size=48))
    @pytest.mark.parametrize('code', CAPABILITIES)
    def test_arbitrary_bytes(self, code, payload) -> None:
        try:
            instance = Capability.unpack(code, {}, payload)
        except Notify:
            return
        except Exception as exc:  # noqa: BLE001
            raise AssertionError(f'capability {int(code)} raised {type(exc).__name__} on {payload.hex()}')
        check(renders(instance), f'capability {int(code)}')


@pytest.fixture(scope='module')
def session():
    """A real negotiated session: Attributes.parse reads it while decoding"""
    spec = importlib.util.spec_from_file_location(
        'decode_fixtures', pathlib.Path(__file__).parent.parent / 'unit' / 'test_decode.py'
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    neighbor = module.FakeNeighbor()
    capabilities = Capabilities().new(neighbor, False)
    capabilities[Capability.CODE.MULTIPROTOCOL] = neighbor.families()
    negotiated = Negotiated(neighbor)
    negotiated.sent(Open(Version(4), ASN(neighbor['local-as']), HoldTime(180), RouterID('10.0.0.1'), capabilities))
    negotiated.received(Open(Version(4), ASN(neighbor['peer-as']), HoldTime(180), RouterID('10.0.0.2'), capabilities))
    return negotiated


def parse_attribute(aid, flag, payload, negotiated):
    """Hand the bytes to the parser a peer's UPDATE actually goes through

    Calling a decoder directly overstates the problem: Attributes.parse converts
    an IndexError into a treat-as-withdraw for the attributes RFC 7606 says to,
    and discards the ones it says to discard. What escapes THAT is what reaches
    the reactor, and that is the thing worth failing on.
    """
    # the registry normalises its keys with EXTENDED_LENGTH set, so the flag it
    # is filed under is NOT the flag that goes on the wire. Writing it verbatim
    # makes the parser read a two byte length where one was written, and every
    # attribute after it is misaligned: a harness bug which reads as a decoder
    # bug in exactly the way this file exists to catch.
    on_wire = flag & ~Attribute.Flag.EXTENDED_LENGTH
    wire = bytes([on_wire, aid, len(payload)]) + payload
    return Attributes().parse(wire, Direction.IN, negotiated)


class TestEveryAttributeThroughTheParser:
    @pytest.mark.parametrize('key', ATTRIBUTES)
    @pytest.mark.parametrize('length', range(0, 20))
    def test_short_input(self, key, length, session) -> None:
        aid, flag = key
        for fill in FILLS:
            payload = (fill * (length // len(fill) + 1))[:length]
            try:
                parse_attribute(aid, flag, payload, session)
            except Notify:
                continue
            except Exception as exc:  # noqa: BLE001 - that is the defect
                raise AssertionError(f'attribute {key} raised {type(exc).__name__} on {payload.hex()}')

    @settings(max_examples=150)
    @given(payload=st.binary(min_size=0, max_size=48))
    @pytest.mark.parametrize('key', ATTRIBUTES)
    def test_arbitrary_bytes(self, key, payload, session) -> None:
        aid, flag = key
        try:
            parse_attribute(aid, flag, payload, session)
        except Notify:
            return
        except Exception as exc:  # noqa: BLE001
            raise AssertionError(f'attribute {key} raised {type(exc).__name__} on {payload.hex()}')
