#!/usr/bin/env python3
# encoding: utf-8

"""Property tests over every registered NLRI decoder

Peer supplied wire data, parametrised FROM the registry so an address family
added later is covered the day it is registered.

Three properties, per TIGER_STYLE section 1.1:
  1. malformed input raises Notify, never a Python exception
  2. a decoded object survives json(), str() and repr()
  3. the JSON it emits is one parseable value, with no member the peer chose
"""

import json

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI

FAMILIES = sorted(NLRI.registered_nlri)

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


def render(family, payload):
    """Decode one NLRI, then render it every way the API and the logger do

    Returns None when the decoder rejects the input by returning no NLRI,
    which several families use instead of raising.
    """
    afi_name, safi_name = family.split('/')
    klass = NLRI.registered_nlri[family]
    result = klass.unpack_nlri(AFI.value(afi_name), SAFI.value(safi_name), payload, Action.ANNOUNCE, False)
    nlri = result[0] if isinstance(result, tuple) else result
    if nlri is None:
        return None
    return nlri.json(), str(nlri), repr(nlri)


@pytest.mark.parametrize('family', FAMILIES)
@pytest.mark.parametrize('length', range(0, 32))
@pytest.mark.parametrize('filler', [b'A', b'\x00', b'\xff'], ids=['ascii', 'zero', 'ones'])
def test_short_nlri_raises_notify_or_renders(family, length, filler) -> None:
    """A truncated NLRI is a protocol error, never a Python exception

    The zero filler matters on its own: a flow NLRI of b'\\x00' announces a
    length of zero, decodes to a rule-less flow, and used to render '{, ...}'.
    """
    try:
        rendered = render(family, filler * length)
    except Notify:
        return
    if rendered is None:
        return
    json.loads('{"nlri": %s}' % rendered[0])


@pytest.mark.parametrize('family', FAMILIES)
def test_quote_payload_cannot_inject(family) -> None:
    """A peer must not be able to add a member of its own to the API stream"""
    try:
        rendered = render(family, INJECTION)
    except Notify:
        return
    if rendered is None:
        return
    parsed = json.loads('{"nlri": %s}' % rendered[0])
    assert 'injected' not in set(all_keys(parsed)), f'{family} let the peer inject a member'


@settings(max_examples=300, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(family=st.sampled_from(FAMILIES), payload=st.binary(min_size=0, max_size=64))
def test_arbitrary_bytes(family, payload) -> None:
    """Random bytes into any registered family: Notify, or a parseable render"""
    try:
        rendered = render(family, payload)
    except Notify:
        return
    if rendered is None:
        return
    json.loads('{"nlri": %s}' % rendered[0])


@settings(max_examples=300, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(family=st.sampled_from(FAMILIES), text=st.text(max_size=48))
def test_arbitrary_text(family, text) -> None:
    """Arbitrary text, which is where quotes and control characters come from"""
    try:
        rendered = render(family, text.encode('utf-8'))
    except Notify:
        return
    if rendered is None:
        return
    parsed = json.loads('{"nlri": %s}' % rendered[0])
    assert 'injected' not in set(all_keys(parsed))
