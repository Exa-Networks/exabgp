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
# nlri-mpls used to be here for both families, and mpls-vpn was about to join it.
# Their only difference was the Rsrv and S bits of a label field, which RFC 8277
# 2.2 requires us to set on transmission and to ignore on reception, so in != out
# there is obedience and not disagreement. _ignoring_label_trailing_bits masks
# those four bits and all three families now round trip.
#
#   l2vpn/vpls                  differs for two reasons, and neither is a defect.
#                               Its decoder takes the length as a MINIMUM and reads
#                               the seventeen bytes it understands, so an NLRI
#                               framed at 18 is re-emitted at 17, which is what we
#                               hold. And pack_nlri sets the bottom-of-stack bit
#                               unconditionally, which test_vpls.py's
#                               test_pack_sets_bottom_of_stack argues for. Unlike
#                               the nlri-mpls families the difference is not
#                               confined to the four bits RFC 8277 2.2 makes
#                               unreadable, so masking cannot reach it. It stays
#                               here as a statement that the entry is understood,
#                               not as a defect waiting for a fix.
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
    # The VPN variant shares the plain family's re-encode limitation: pack_nlri
    # emits the descriptors and drops the type/length header and the route
    # distinguisher. It is added rather than removed, which a ratchet normally
    # forbids, because the decoder did not start accepting anything new: the
    # family simply had no corpus seed until now, so its existing limitation had
    # never been visible. Adding an entry for a NEW acceptance would be the
    # thing to refuse.
    'bgp-ls/bgp-ls-vpn',
    'ipv4/mup',
    'ipv4/rtc',
    'ipv6/mup',
    'l2vpn/vpls',
}

FAMILIES = sorted(NLRI.registered_nlri)


# RFC 8277 2.2 draws the third octet of a label field as |Label|Rsrv |S|, and says of both
# trailing fields that they are ours to set and not ours to read:
#   Rsrv  "This 3-bit field SHOULD be set to zero on transmission and MUST be ignored on
#          reception."
#   S     "This 1-bit field MUST be set to one on transmission and MUST be ignored on
#          reception."
# So the low nibble carries no information a receiver may act on, and all of it is masked.
LABEL_TRAILING_BITS = 0x0F


def _ignoring_label_trailing_bits(nlri, consumed, repacked):
    """Both byte strings with the Rsrv and S bits of every label field cleared.

    Both fields bind us the same way: we must set them on transmission and must ignore them on
    reception.  So a labelled NLRI which arrives with the S bit clear, or with reserved bits
    set, is accepted and re-encoded with S set and Rsrv zero, and in != out for ever.

    That is not the thing this file exists to catch.  Its reasoning is that a mismatch means
    "the NLRI held in the RIB disagrees with the bytes the peer sent", and by the RFC's own
    words these four bits carry nothing a receiver may act on, so there is no disagreement to
    find.  Masking them is what lets the ratchet keep meaning "accepts what it cannot re-emit"
    rather than growing an entry every time we obey a MUST.

    Only those four bits, and only inside the label stack, whose offset comes from the
    re-encode because the re-encode is the canonical form.  The twenty label bits, the stack
    length, the mask byte and everything else still count.
    """
    labels = getattr(nlri, 'labels', None)
    if labels is None or not labels.packed:
        return consumed, repacked

    start = repacked.find(labels.packed)
    if start < 0:
        return consumed, repacked
    end = start + len(labels.packed)
    if len(consumed) < end:
        return consumed, repacked

    def cleared(data):
        out = bytearray(data)
        for offset in range(start + 2, end, 3):
            out[offset] &= 0xFF ^ LABEL_TRAILING_BITS
        return bytes(out)

    return cleared(consumed), cleared(repacked)


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
        # the reported hex is the real wire, not the masked form: a message which shows bytes
        # nobody sent is worse than no message
        left, right = _ignoring_label_trailing_bits(nlri, consumed, repacked)
        if right != left:
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
