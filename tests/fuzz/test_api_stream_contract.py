#!/usr/bin/env python3
# encoding: utf-8

"""The member names the JSON API promises are a contract, so pin them

GHSA-jcrv-p53f-v5w5 was about what a PEER can put into the API stream. This is
the other half of the same promise: what WE said would be in it. A controller
looks for "route-target"; if that member is renamed, it finds nothing, silently,
with no error for anyone to see.

Nothing held these names. Renaming "route-target" or "ethernet-tag" left all
6444 tests passing, which is how a rename reaches a consumer.

These are deliberately brittle. Adding a member, renaming one or dropping one
fails here and has to be argued rather than noticed by an operator. When a change
is intended, update the table and say why in the commit: that record is the point.
"""

import json

import pytest

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI

from .corpus import seeds_for

# every member name a family emits for a representative route, at any depth
MEMBERS = {
    'bgp-ls/bgp-ls': [
        'autonomous-system',
        'bgp-ls-identifier',
        'l3-routing-topology',
        'ls-nlri-type',
        'nexthop',
        'node-descriptors',
        'protocol-id',
        'router-id',
    ],
    # a plain prefix renders as a bare JSON string, not an object. That is a
    # contract too: turning it into an object would break every consumer which
    # reads it as a value.
    'ipv4/unicast': [],
    'ipv6/unicast': [],
    'ipv4/multicast': [],
    'ipv6/multicast': [],
    'ipv4/flow': ['destination-ipv4', 'port', 'protocol', 'string'],
    'ipv4/flow-vpn': ['protocol', 'rd', 'string'],
    'ipv4/mcast-vpn': ['code', 'group', 'name', 'parsed', 'raw', 'rd', 'source'],
    'ipv4/mpls-vpn': ['label', 'rd'],
    'ipv4/mup': ['arch', 'code', 'ip', 'name', 'raw', 'rd'],
    'ipv4/nlri-mpls': ['label'],
    'ipv4/rtc': ['origin', 'route-target'],
    'ipv6/flow': ['destination-ipv6', 'next-header', 'source-ipv6', 'string'],
    'ipv6/flow-vpn': ['next-header', 'rd', 'string'],
    'ipv6/mcast-vpn': ['code', 'group', 'name', 'parsed', 'raw', 'rd', 'source'],
    'ipv6/mpls-vpn': ['label', 'rd'],
    'ipv6/mup': ['arch', 'code', 'ip', 'name', 'raw', 'rd'],
    'ipv6/nlri-mpls': ['label'],
    'l2vpn/evpn': ['code', 'esi', 'ethernet-tag', 'label', 'name', 'parsed', 'raw', 'rd'],
    'l2vpn/vpls': ['base', 'endpoint', 'offset', 'rd', 'size'],
}


def member_names(node):
    """Every member name at any depth, because nesting hides a rename too"""
    if isinstance(node, dict):
        for name, value in node.items():
            yield name
            yield from member_names(value)
    elif isinstance(node, list):
        for value in node:
            yield from member_names(value)


def rendered_members(family):
    """Every member name this family emits across EVERY seed which decodes

    Not the first: a decoder can have branches which emit different members, and
    the first seed to render may take the branch nobody cares about. The RTC
    wildcard is exactly that, it emits a null route-target through a different
    line than a real one, so pinning only the first seed left "route-target"
    renameable with this very test passing.
    """
    afi_name, safi_name = family.split('/')
    afi, safi = AFI.value(afi_name), SAFI.value(safi_name)
    klass = NLRI.registered_nlri[family]
    names, decoded = set(), False
    for payload in seeds_for(family):
        try:
            result = klass.unpack_nlri(afi, safi, payload, Action.ANNOUNCE, False)
        except Exception:  # noqa: BLE001 - the decoder property tests judge this
            continue
        nlri = result[0] if isinstance(result, tuple) else result
        if nlri is None or 'unknown' in str(nlri):
            continue
        try:
            parsed = json.loads('{"nlri": %s}' % nlri.json())
        except ValueError:
            continue
        decoded = True
        names |= set(member_names(parsed)) - {'nlri'}
    return names if decoded else None


@pytest.mark.parametrize('family', sorted(MEMBERS))
def test_the_member_names_are_what_we_promised(family) -> None:
    found = rendered_members(family)
    assert found is not None, f'{family}: no seed rendered, this test proves nothing'
    names = sorted(found)
    assert names == MEMBERS[family], (
        f'{family} changed the members it puts in the API stream.\n'
        f'  was {MEMBERS[family]}\n'
        f'  now {names}\n'
        'A consumer looking for a renamed member finds nothing and says nothing. '
        'If the change is intended, update MEMBERS and say why in the commit.'
    )


def test_every_family_with_a_decoder_is_pinned() -> None:
    """A family added later must be given its members rather than skipped"""
    decodable = set()
    for family in NLRI.registered_nlri:
        if rendered_members(family) is not None:
            decodable.add(family)
    missing = sorted(decodable - set(MEMBERS))
    assert not missing, f'these families render JSON nobody has pinned: {missing}'
