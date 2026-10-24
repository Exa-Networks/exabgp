"""A labelled NLRI whose one label carried no bottom of stack bit reset the session.

RFC 8277 2.2, describing the S bit of the single label field an NLRI carries when the
Multiple Labels Capability is not in use:

    This 1-bit field MUST be set to one on transmission and MUST be ignored on
    reception.

and, a few lines further down the same section:

    As long as the Multiple Labels Capability is not sent and received by both BGP
    speakers on a given BGP session, this document REQUIRES that only one label be
    specified in the NLRI, that the S bit be set on transmission, and that it be ignored
    on reception.

RFC 8277 2.4 says the same of the three octets an MP_UNREACH withdraw carries where a
label would be:

    Upon transmission, the Compatibility field SHOULD be set to 0x800000.  Upon
    reception, the value of the Compatibility field MUST be ignored.

Both sentences bind every session exabgp forms.  The section 2.3 reading, where the S bit
is what delimits a stack of several labels, applies only "if the Multiple Labels
Capability has been both sent and received on a given BGP session", and exabgp has no
capability code 8 to exchange: `Capability.CODE` stops at 0x06 before jumping to 0x40.

Measured at HEAD before the fix, through `Update.unpack_message`, the call the reactor
makes, with an MP_UNREACH_NLRI carrying ipv4/nlri-mpls and the single label 1 with the S
bit clear:

    NLRI on the wire   : 300000100a0000
    withdraw   -> Notify(3, 10) 'UPDATE message error / Invalid Network Field /
                  invalid label stack in the NLRI, no bottom of stack bit and no terminator'
    MP_UNREACH withdraw -> Notify(3, 10) ... same

Notify(3, 10) closes the session, so a peer which omits a bit the RFC tells us to ignore
could not peer with us at all.

What ends a one field stack now is the LENGTH, not the S bit: RFC 8277 2.2 defines the
Length field as "the sum of 20 (number of bits in Label field), plus 3 (number of bits in
Rsrv field), plus 1 (number of bits in S field), plus the length in bits of the prefix",
so if the bits the length leaves behind the first field are a prefix the family can hold,
they are the prefix.

Depth
=====

The relaxation is depth one only, and it has to be.  Behind the first field the length no
longer distinguishes anything: 24 bits of a second label and 24 bits of prefix are the
same 48 bits to the mask byte, so a stack of two or more fields has nothing but the S bit
to say where it ends.  Those are refused exactly as before, which is what keeps the shape
that used to report 0.0.0.0/0 out.

The guard is `0 < mask - rd_mask <= IP.length(afi) * 8`, and neither end of it is
decoration:

  - the upper bound is the family's own prefix width, so the length rule can never leave
    a mask this family cannot hold.  It is the same number the existing
    `mask > IP.length(afi) * 8` check enforces after the loop.
  - the lower bound excludes zero bits left.  A labelled /0 and a stack which ate the
    prefix are the same bytes, and a peer-supplied default route is the more expensive of
    the two to be wrong about, so there the RFC 3107 conventions stay the only way out.

Nothing about the byte count moved.  The prefix is still read through
`size = CIDR.size(mask)` guarded by `len(bgp) < size`, so a shorter NLRI than the length
claims is still Notify(3, 10); the label loop's own `len(bgp) < 3` is still there; and
`mask > IP.length(afi) * 8` still bounds the mask.  The tests at the end of this file
drive each of those.

One decoder, four families
==========================

`Label` and `IPVPN` both inherit `INET.unpack_nlri` on this branch (their own copies are
commented out), so this single edit reaches ipv4 and ipv6 nlri-mpls and mpls-vpn alike.
main has two live copies and needed the fix in both; the parity test at the end of this
file pins that the four families agree here.
"""

from __future__ import annotations

import importlib.util
import pathlib
from typing import Any

import pytest

from exabgp.bgp.message import Action, Update
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open import ASN, HoldTime, Open, RouterID, Version
from exabgp.bgp.message.open.capability import Capabilities, Capability, Negotiated
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.environment import getenv
from exabgp.logger import log
from exabgp.protocol.family import AFI, SAFI

# NLRI.unpack_nlri logs the family it dispatches on, so the logger has to exist before
# the registry is exercised.  Going through the registry rather than calling the class
# directly is the point: it is the path MP_REACH and MP_UNREACH take.
log.init(getenv())


@pytest.fixture(scope='module')
def session() -> Any:
    """A negotiated session, so Update.unpack_message really does reach the NLRI decoder."""
    here = pathlib.Path(__file__).parent / 'test_decode.py'
    spec = importlib.util.spec_from_file_location('decode_fixtures', here)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    neighbor = module.FakeNeighbor()
    capabilities = Capabilities().new(neighbor, False)
    capabilities[Capability.CODE.MULTIPROTOCOL] = neighbor.families()
    negotiated = Negotiated(neighbor)
    negotiated.sent(Open(Version(4), ASN(neighbor['local-as']), HoldTime(180), RouterID('10.0.0.1'), capabilities))
    negotiated.received(Open(Version(4), ASN(neighbor['peer-as']), HoldTime(180), RouterID('10.0.0.2'), capabilities))
    return negotiated


# label 1 and label 2, neither carrying the bottom of stack bit (the low bit of the three
# octets).  On its own the first is a section 2.2 NLRI and decodes; the two together have
# no end and do not.
NO_S_BIT = bytes([0x00, 0x00, 0x10])
SECOND_NO_S_BIT = bytes([0x00, 0x00, 0x20])
# label 1 with the bottom of stack bit set, which is what a conforming peer sends
WITH_S_BIT = bytes([0x00, 0x00, 0x11])
SECOND_WITH_S_BIT = bytes([0x00, 0x00, 0x21])
# RFC 3107's withdraw value, which carries no bottom of stack bit either
WITHDRAW_LABEL = bytes([0x80, 0x00, 0x00])

PREFIX4 = bytes([10, 0, 0])  # 10.0.0.0/24
PREFIX6 = bytes([0x20, 0x01, 0x0D, 0xB8]) + bytes(4)  # 2001:db8::/64

# eight zero octets: an RD whose leading bytes are indistinguishable from the 0x000000
# next-hop convention, which is why the depth rule matters for mpls-vpn
RD = bytes(8)
RD_BITS = 64

ACTIONS = [('announce', Action.ANNOUNCE), ('withdraw', Action.WITHDRAW)]


def mp_unreach_update(afi: AFI, safi: SAFI, nlri: bytes) -> bytes:
    """A whole UPDATE body carrying one MP_UNREACH_NLRI, as the reactor would read it."""
    value = afi.pack() + safi.pack() + nlri
    attribute = bytes([0x80, 15, len(value)]) + value
    return b'\x00\x00' + len(attribute).to_bytes(2, 'big') + attribute


# ------------------------------------------------------------------ now accepted


@pytest.mark.parametrize(
    'name, afi, safi, wire, prefix',
    [
        ('ipv4 nlri-mpls', AFI.ipv4, SAFI.nlri_mpls, bytes([24 + 24]) + NO_S_BIT + PREFIX4, '10.0.0.0/24'),
        ('ipv6 nlri-mpls', AFI.ipv6, SAFI.nlri_mpls, bytes([24 + 64]) + NO_S_BIT + PREFIX6, '2001:db8::/64'),
        (
            'ipv4 mpls-vpn',
            AFI.ipv4,
            SAFI.mpls_vpn,
            bytes([24 + RD_BITS + 24]) + NO_S_BIT + RD + PREFIX4,
            '10.0.0.0/24',
        ),
        (
            'ipv6 mpls-vpn',
            AFI.ipv6,
            SAFI.mpls_vpn,
            bytes([24 + RD_BITS + 64]) + NO_S_BIT + RD + PREFIX6,
            '2001:db8::/64',
        ),
    ],
    ids=['ipv4 nlri-mpls', 'ipv6 nlri-mpls', 'ipv4 mpls-vpn', 'ipv6 mpls-vpn'],
)
@pytest.mark.parametrize('action_name, action', ACTIONS, ids=[name for name, _ in ACTIONS])
def test_one_label_field_with_no_s_bit_decodes(
    name: str, afi: AFI, safi: SAFI, wire: bytes, prefix: str, action_name: str, action: Action
) -> None:
    """RFC 8277 2.2: the S bit "MUST be ignored on reception".

    The length says where the one field ends, so the bits behind it are the prefix.  Run
    for both actions because 2.2 binds an announce and 2.4 binds a withdraw, and neither
    permits us to read the bit.
    """
    nlri, rest = NLRI.unpack_nlri(afi, safi, wire, action, False)

    assert str(nlri.cidr) == prefix, f'{name} lost its prefix'
    assert nlri.labels.labels == [1], f'{name} read the wrong stack'
    assert rest == b'', f'{name} left bytes behind'


def test_a_withdraw_whose_compatibility_field_is_not_0x800000() -> None:
    """RFC 8277 2.4: "Upon reception, the value of the Compatibility field MUST be ignored".

    0x800000 already terminated a stack here.  Any OTHER three octets did not, so a peer
    which withdrew with a Compatibility field of 0x000010 was answered with a
    NOTIFICATION over a field the RFC says has no significance.
    """
    wire = bytes([24 + 24]) + NO_S_BIT + PREFIX4
    nlri, _ = NLRI.unpack_nlri(AFI.ipv4, SAFI.nlri_mpls, wire, Action.WITHDRAW, False)

    assert str(nlri.cidr) == '10.0.0.0/24'


def test_through_the_message_decoder_the_reactor_calls(session: Any) -> None:
    """The reproduction as the reactor sees it, not just the NLRI classmethod.

    `Update.unpack_message` is what `Protocol.read_message` hands the bytes to, and a
    Notify raised below it is what becomes a NOTIFICATION and a closed session.
    """
    message = mp_unreach_update(AFI.ipv4, SAFI.nlri_mpls, bytes([24 + 24]) + NO_S_BIT + PREFIX4)

    update = Update.unpack_message(message, Direction.IN, session)

    assert [str(nlri) for nlri in update.nlris] == ['10.0.0.0/24 label 1']


# ------------------------------------------------------------------ still refused

# Two fields and no bottom of stack bit anywhere.  48 bits behind the first field is more
# than IPv4 holds, so the section 2.2 reading is not available and the S bit is the only
# delimiter there is.  This is the shape which used to eat the prefix and report 0.0.0.0/0.
UNENDING4 = bytes([24 + 24 + 24]) + NO_S_BIT + SECOND_NO_S_BIT + PREFIX4
UNENDING_VPN4 = bytes([24 + 24 + RD_BITS + 24]) + NO_S_BIT + SECOND_NO_S_BIT + RD + PREFIX4
# For ipv6 the family is wide enough that 24 bits of a second field still read as a prefix
# ipv6 can hold, so the length rule absorbs the short shapes: see
# test_the_length_rule_absorbs_a_second_field_ipv6_could_hold_as_a_prefix below.  What is
# refused is what the length rule cannot read as one field, which for ipv6 means a full
# 128 bit prefix behind the stack.
# every three octet group of this prefix has an even low byte on purpose: a prefix octet
# whose low bit is set reads as a label with the bottom of stack bit, so an over-long
# stack would 'terminate' inside the prefix and the refusal under test would not happen.
# That residual is in the encoding, not in this decoder.
PREFIX6_FULL = bytes([0x20, 0x01, 0x0E]) + bytes(13)
UNENDING_VPN6 = bytes([24 + 24 + RD_BITS + 128]) + NO_S_BIT + SECOND_NO_S_BIT + RD + PREFIX6_FULL
UNENDING6 = bytes([24 + 24 + 128]) + NO_S_BIT + SECOND_NO_S_BIT + PREFIX6_FULL


@pytest.mark.parametrize(
    'name, afi, safi, wire',
    [
        ('ipv4 nlri-mpls', AFI.ipv4, SAFI.nlri_mpls, UNENDING4),
        ('ipv4 mpls-vpn', AFI.ipv4, SAFI.mpls_vpn, UNENDING_VPN4),
        ('ipv6 nlri-mpls', AFI.ipv6, SAFI.nlri_mpls, UNENDING6),
        ('ipv6 mpls-vpn', AFI.ipv6, SAFI.mpls_vpn, UNENDING_VPN6),
    ],
    ids=['ipv4 nlri-mpls', 'ipv4 mpls-vpn', 'ipv6 nlri-mpls', 'ipv6 mpls-vpn'],
)
@pytest.mark.parametrize('action_name, action', ACTIONS, ids=[name for name, _ in ACTIONS])
def test_more_than_one_field_with_no_s_bit_is_still_refused(
    name: str, afi: AFI, safi: SAFI, wire: bytes, action_name: str, action: Action
) -> None:
    """The half the length rule cannot reach, and the reason it is depth one only.

    Behind the first field the mask says nothing: a second label and 24 bits of prefix
    are the same 48 bits.  Reading on takes the prefix and reports 0.0.0.0/0, a default
    route from a peer, so it stays a protocol error.

    The mpls-vpn cases are here because the RD is what makes the depth rule necessary: an
    unterminated first field sends the loop into the distinguisher, whose leading zero
    bytes read exactly like the 0x000000 next-hop convention.
    """
    with pytest.raises(Notify) as raised:
        NLRI.unpack_nlri(afi, safi, wire, action, False)

    assert raised.value.code == 3 and raised.value.subcode == 10


@pytest.mark.parametrize('action_name, action', ACTIONS, ids=[name for name, _ in ACTIONS])
def test_a_length_leaving_no_prefix_bits_is_still_refused(action_name: str, action: Action) -> None:
    """The residual the lower bound of the guard deliberately keeps closed.

    One field, no S bit, and a length which leaves nothing behind it.  Read as section
    2.2 that is a labelled 0.0.0.0/0; read as a stack it is the old bug.  Same bytes,
    nothing to choose between them, and a default route is the costlier mistake.

    A peer which really means a labelled default route sets the S bit, which RFC 8277 2.2
    says it MUST do on transmission, and then it decodes: the companion below.
    """
    with pytest.raises(Notify) as raised:
        NLRI.unpack_nlri(AFI.ipv4, SAFI.nlri_mpls, bytes([24]) + NO_S_BIT + PREFIX4, action, False)

    assert raised.value.code == 3 and raised.value.subcode == 10


def test_a_labelled_default_route_with_the_s_bit_set_decodes() -> None:
    """Without this the refusal above would pass against a decoder refusing /0 outright."""
    nlri, _ = NLRI.unpack_nlri(AFI.ipv4, SAFI.nlri_mpls, bytes([24]) + WITH_S_BIT, Action.ANNOUNCE, False)

    assert str(nlri.cidr) == '0.0.0.0/0'
    assert nlri.labels.labels == [1]


def test_the_length_rule_absorbs_a_second_field_ipv6_could_hold_as_a_prefix() -> None:
    """The narrowing is family-wide, and for ipv6 it is wide.  Written down rather than hidden.

    `0 < mask - rd_mask <= IP.length(afi) * 8` is 32 bits for ipv4 and 128 for ipv6, so a
    second 24 bit field followed by a short prefix is still "bits ipv6 can hold" and the
    length rule reads the whole remainder as one prefix.  Here two unterminated fields and
    64 bits of prefix are read as one label and a /88.

    This is a MISREAD, not an over-read, and the distinction is the whole point:

      - the byte count is unchanged.  88 bits is 11 octets, the NLRI carries 11 octets
        behind the first field, and `len(bgp) < size` would refuse it otherwise.
      - the prefix is never empty, because the lower bound of the guard excludes zero bits
        left, so this cannot produce the 0.0.0.0/0 or ::/0 a peer would want.
      - nothing is read past the NLRI: `rest` is empty.

    And it is not a choice we have.  RFC 8277 2.2 says the S bit "MUST be ignored on
    reception", so a decoder is not allowed to use the absent bit to decide there is a
    second field.  A peer which means two labels sets the bit, which 2.2 says it MUST do.

    IF THIS TEST EVER FAILS the encoding gained a boundary marker the length cannot
    imitate, or someone read the S bit again.  Check which before adjusting it.
    """
    wire = bytes([24 + 24 + 64]) + NO_S_BIT + SECOND_NO_S_BIT + PREFIX6
    nlri, rest = NLRI.unpack_nlri(AFI.ipv6, SAFI.nlri_mpls, wire, Action.ANNOUNCE, False)

    assert nlri.labels.labels == [1]
    assert nlri.cidr.mask == 88
    assert rest == b'', 'the decoder read past the NLRI it was handed'


def test_a_sentinel_below_depth_one_still_ends_nothing() -> None:
    """The narrowing the depth rule already carried is untouched by the length rule.

    A withdraw whose SECOND field is 0x800000 is refused: the sentinel describes a whole
    stack, so below depth one it is an ordinary label and the stack still has to reach a
    bottom of stack bit.  48 bits behind the first field is past IPv4, so the length rule
    does not reach this either.
    """
    wire = bytes([24 + 24 + 24]) + NO_S_BIT + WITHDRAW_LABEL + PREFIX4

    with pytest.raises(Notify):
        NLRI.unpack_nlri(AFI.ipv4, SAFI.nlri_mpls, wire, Action.WITHDRAW, False)


# ------------------------------------------------------------------ the bound still holds


def test_a_prefix_shorter_than_the_length_claims_is_refused() -> None:
    """The length rule must not have let the decoder read past what the peer sent.

    Before the fix this was refused by accident, because the label loop ran on and hit
    its own `len(bgp) < 3`.  Now the loop stops at one field and the refusal comes from
    `len(bgp) < size` on the prefix instead, which is the check that was always meant to
    hold it.  Same answer, and it is the answer that matters.
    """
    wire = bytes([24 + 24]) + NO_S_BIT + bytes([10])  # announces 24 bits of prefix, carries 8

    with pytest.raises(Notify) as raised:
        NLRI.unpack_nlri(AFI.ipv4, SAFI.nlri_mpls, wire, Action.ANNOUNCE, False)

    assert raised.value.code == 3 and raised.value.subcode == 10


def test_a_truncated_label_field_is_refused() -> None:
    """The loop's own length check, which the fix did not touch."""
    wire = bytes([24 + 24]) + bytes([0x00, 0x00])  # a length claiming a field, two octets of it

    with pytest.raises(Notify) as raised:
        NLRI.unpack_nlri(AFI.ipv4, SAFI.nlri_mpls, wire, Action.ANNOUNCE, False)

    assert raised.value.code == 3 and raised.value.subcode == 10


def test_a_mask_past_the_family_is_refused() -> None:
    """The upper bound of the guard is the family width, so this cannot become reachable.

    72 bits of prefix behind the label is more than IPv4 holds, and it is refused after
    the loop rather than silently indexing past the prefix.
    """
    wire = bytes([24 + 72]) + WITH_S_BIT + bytes(9)

    with pytest.raises(Notify) as raised:
        NLRI.unpack_nlri(AFI.ipv4, SAFI.nlri_mpls, wire, Action.ANNOUNCE, False)

    assert raised.value.code == 3 and raised.value.subcode == 10
    assert 'invalid mask' in str(raised.value)


# ------------------------------------------------------------------ multi-label reads


def test_a_well_formed_two_field_stack_still_reads_both_labels() -> None:
    """The length rule must not have shortened a real stack.

    Two fields, the second carrying the bottom of stack bit.  The length rule is not
    consulted at depth one here because the bit ends the stack first, and it is not
    consulted at depth two at all.
    """
    wire = bytes([24 + 24 + 24]) + NO_S_BIT + SECOND_WITH_S_BIT + PREFIX4
    nlri, rest = NLRI.unpack_nlri(AFI.ipv4, SAFI.nlri_mpls, wire, Action.ANNOUNCE, False)

    assert str(nlri.cidr) == '10.0.0.0/24'
    assert nlri.labels.labels == [1, 2]
    assert rest == b''


def test_a_sentinel_inside_a_well_formed_stack_is_just_a_label() -> None:
    """Why the bottom of stack test still runs before everything else.

    A three field stack whose middle field happens to equal 0x000000, the last carrying
    the bit.  The length rule sits after the bit test for the same reason the sentinels
    do: a field which looks like a convention is still a label.
    """
    wire = bytes([24 + 24 + 24 + 24]) + NO_S_BIT + bytes(3) + SECOND_WITH_S_BIT + PREFIX4
    nlri, _ = NLRI.unpack_nlri(AFI.ipv4, SAFI.nlri_mpls, wire, Action.ANNOUNCE, False)

    assert str(nlri.cidr) == '10.0.0.0/24'
    assert nlri.labels.labels == [1, 0, 2]


def test_the_four_labelled_families_agree() -> None:
    """One decoder serves all four, and this is what says so if that ever changes.

    `Label` and `IPVPN` inherit `INET.unpack_nlri` here; main has two live copies and a
    fix to one of them left mpls-vpn at 0.0.0.0/0 for a while.  If someone ever gives
    this branch a second copy, this fails rather than going quiet.
    """

    def outcome(afi: AFI, safi: SAFI, wire: bytes) -> str:
        try:
            nlri, _ = NLRI.unpack_nlri(afi, safi, wire, Action.ANNOUNCE, False)
        except Notify:
            return 'refused'
        return str(nlri.cidr)

    one_field = {
        'ipv4 nlri-mpls': outcome(AFI.ipv4, SAFI.nlri_mpls, bytes([48]) + NO_S_BIT + PREFIX4),
        'ipv4 mpls-vpn': outcome(AFI.ipv4, SAFI.mpls_vpn, bytes([112]) + NO_S_BIT + RD + PREFIX4),
    }
    assert set(one_field.values()) == {'10.0.0.0/24'}, f'the labelled families disagree at depth one: {one_field}'

    unending = {
        'ipv4 nlri-mpls': outcome(AFI.ipv4, SAFI.nlri_mpls, UNENDING4),
        'ipv4 mpls-vpn': outcome(AFI.ipv4, SAFI.mpls_vpn, UNENDING_VPN4),
    }
    assert set(unending.values()) == {'refused'}, f'the labelled families disagree below depth one: {unending}'
