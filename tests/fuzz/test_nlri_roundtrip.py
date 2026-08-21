#!/usr/bin/env python3
# encoding: utf-8

"""What a decoder accepts, it must be able to re-encode

TIGER_STYLE 1.1. If pack(unpack(x)) is not x, the NLRI held in the RIB
disagrees with the bytes the peer sent, and a route reflector re-advertises
something nobody announced. That mismatch surfaces later, in JSON output or in
someone else's routing table, where nobody can trace it back.

This class had no coverage at all, and it is where BGPLS.pack_nlri writing a
one byte header for a wire format with a two byte one had been hiding.

Note pack(), not pack_nlri(): several classes override pack() and that is what
the send path calls. A round trip test against the wrong entry point reports
failures which are not real, which is how the first version of this test went.

KNOWN carries the families which do not round trip yet. It is a ratchet: it may
shrink, never grow. A new entry means a decoder started accepting something it
cannot re-emit.
"""

import pytest

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI

from .corpus import seeds_for

# families whose decoder accepts a shape it re-encodes differently. All of these
# predate the hardening work; none was introduced by it.
#
#   nlri-mpls, mpls-vpn, vpls   a label stack whose last label does not have the
#                               bottom-of-stack bit set is accepted, and the
#                               encoder sets it. The route stored and the route
#                               re-advertised differ by that bit.
#   ipv4/rtc                    a length below 96 is accepted and re-encoded as
#                               96. RTC prefix length decides what the route
#                               target matches, so a reflector changes the
#                               meaning of the route it passes on.
#   mup                         an unknown architecture type re-encodes as a
#                               known one.
#   bgp-ls                      the four byte NLRI header is dropped entirely on
#                               re-encode, because the registered subclasses
#                               never populate _packed. Harmless today: there is
#                               no announce/bgpls.py, so BGP-LS is receive only
#                               and nothing re-advertises it.
KNOWN = {
    'bgp-ls/bgp-ls',
    'ipv4/mup',
    'ipv4/nlri-mpls',
    'ipv4/rtc',
    'ipv6/mup',
    'ipv6/nlri-mpls',
    'l2vpn/vpls',
}

FAMILIES = sorted(NLRI.registered_nlri)


def mismatches(family):
    afi_name, safi_name = family.split('/')
    afi, safi = AFI.value(afi_name), SAFI.value(safi_name)
    klass = NLRI.registered_nlri[family]
    found, decoded = [], 0
    for payload in seeds_for(family):
        try:
            result = klass.unpack_nlri(afi, safi, payload, Action.ANNOUNCE, False)
        except (Notify, Exception):  # noqa: BLE001 - the property tests judge the outcome
            continue
        nlri, rest = result if isinstance(result, tuple) else (result, b'')
        if nlri is None:
            continue
        consumed = bytes(payload[: len(payload) - len(rest)])
        try:
            repacked = bytes(nlri.pack(None))
        except Exception:  # noqa: BLE001 - a decoder which cannot re-encode at all
            found.append((consumed.hex(), 'raised'))
            continue
        decoded += 1
        if repacked != consumed:
            found.append((consumed.hex(), repacked.hex()))
    return decoded, found


@pytest.mark.parametrize('family', FAMILIES)
def test_round_trip(family) -> None:
    decoded, found = mismatches(family)
    assert decoded, f'{family}: nothing decoded, this test proves nothing'
    if family in KNOWN:
        pytest.xfail(f'{family} is a known re-encode mismatch, see KNOWN')
    assert not found, f'{family} accepts what it cannot re-encode: in {found[0][0]} out {found[0][1]}'


def test_the_ratchet_only_shrinks() -> None:
    """A family which starts round tripping must be taken out of KNOWN"""
    still_broken = {family for family in KNOWN if mismatches(family)[1]}
    fixed = KNOWN - still_broken
    assert not fixed, f'these now round trip and must be removed from KNOWN: {sorted(fixed)}'


# Ratchet on the registry this file parametrises over. A short registry does not
# fail these tests, it collects fewer of them, and a smaller green number reads
# exactly like a larger one. Marked so qa/bin/check_sweep_floors can ask for the
# floor BY NAME: a file whose seeds break under thinning goes red with or without
# a floor, so "something failed" cannot stand in for "the floor fired".
NLRI_FAMILY_FLOOR = 18


@pytest.mark.registry_floor
def test_the_registry_this_file_sweeps_is_populated() -> None:
    assert len(FAMILIES) >= NLRI_FAMILY_FLOOR, sorted(FAMILIES)
