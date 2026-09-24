"""The label stack scanner answered wrongly, and nothing ever called it.

_label_end_offset had two ways to find where a label stack ends: the size the decoder
recorded, and a fallback which scanned forward for the bottom of stack bit.  The fallback
cannot be made correct, and its own comment said so:

    a label stack does not always end with the bottom of stack bit: RFC 3107 withdraws
    use 0x800000, which does not set it, and scanning would then swallow the rd and the
    prefix

BOS is the low bit, and 0x800000 does not set it, so the scan ran past the stack and read
the prefix as more labels.  Measured on the loop this replaced, one withdraw label and a
10.0.0.0/24 prefix:

    labels   label [ 524288 (8388608) 40960 (655360) ]   two labels, from one
    cidr     0.0.0.0/0                                   the prefix, gone

A default route, reported confidently.  The comment described the bug rather than
preventing it.

It was never reached: the suite calls _label_end_offset 6479 times and took that branch
zero times, and every factory in src records the size.  So it was a landmine rather than a
fallback, waiting for a factory which forgot, and the failure it was covering for is a bug
in construction rather than anything a peer sends.  It raises now.

EXA_STYLE.md 4 cites this function as its example of an invariant written where the code
checks it.  The invariant is now the whole of it.

Where the boundary moved
========================

The first version of this file made the bottom of stack bit the ONLY thing which ends a
stack, at every depth, and refused everything else.  That was too wide, and it cost a
session over input the RFC declares legal.  RFC 8277 2.4, on the three octets an
MP_UNREACH withdraw carries where a label would be:

    Upon reception, the value of the Compatibility field MUST be ignored.

and again at the end of the same section, "it is REQUIRED that it be ignored upon
reception".  RFC 8277 2.2 says the same of a label's S bit: "This 1-bit field MUST be set
to one on transmission and MUST be ignored on reception."  Both sentences bind every
session exabgp forms, because the section 2.3 reading where the S bit delimits the stack
applies only once the Multiple Labels Capability has been exchanged, and exabgp has no
capability code 8 to exchange.  A peer withdrawing with a Compatibility field of 0x000010,
which the RFC permits because the field "is of no significance", was answered with a
NOTIFICATION.

So the LENGTH ends a one field stack now, not the S bit: if the bits the length leaves
behind the first field are a prefix the family can hold, they are the prefix.  Beyond the
first field nothing changed, because there section 2.3 is the only reading available and
the S bit really is the only delimiter.

What that does NOT relax, and what the tests below still pin:

  - a stack of more than one field with no bottom of stack bit anywhere, which is the
    shape that ate the prefix and reported 0.0.0.0/0
  - a length which leaves no prefix bits behind the first field, where a /0 and a stack
    which ate the prefix are the same bytes and the length cannot choose between them
  - a sentinel below depth one, which is an ordinary label and does not end anything

The RFC 8277 requirements this proved are in tests/unit/rfc/test_rfc8277_labelled_unicast.py;
what is here is the boundary itself.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.ipvpn import IPVPN
from exabgp.bgp.message.update.nlri.label import Label
from exabgp.bgp.message.update.nlri.qualifier.labels import Labels
from exabgp.bgp.message.update.nlri.qualifier.rd import RouteDistinguisher
from exabgp.protocol.family import AFI, SAFI

# RFC 3107: a withdraw carries this label value, and it does NOT set the bottom of stack
# bit, which is the low bit of the three octets
WITHDRAW_LABEL = bytes([0x80, 0x00, 0x00])
LABEL_17 = bytes([0x00, 0x00, 0x11])
PREFIX = bytes([10, 0, 0])

# Label 1 and label 2, neither carrying the bottom of stack bit.  One of them on its own
# is a section 2.2 NLRI and decodes; the two together have no end and do not.
UNTERMINATED = bytes([0x00, 0x00, 0x10])
SECOND_UNTERMINATED = bytes([0x00, 0x00, 0x20])

# An 8 byte route distinguisher of zeroes, which is what makes the VPN cases interesting:
# its leading bytes are indistinguishable from the 0x000000 next-hop convention.
RD = bytes(8)


def labelled(label: bytes) -> bytes:
    """One labelled IPv4 route: mask covering label and prefix, then both."""
    return bytes([24 + 24]) + label + PREFIX


def test_a_route_built_without_its_label_size_is_refused() -> None:
    """The construction bug is named rather than guessed around.

    __init__ leaves the size unset and every factory fills it in.  An object which reaches
    the accessor without one was built by something which forgot, and the old fallback
    answered it with a default route instead of saying so.
    """
    built = Label(labelled(LABEL_17), AFI.ipv4, has_labels=True)

    with pytest.raises(ValueError, match='without recording its label size'):
        built.cidr


def test_the_withdraw_label_no_longer_eats_the_prefix() -> None:
    """The case the old comment described and the old code did.

    Asserting the refusal rather than a corrected scan, because there is no correct scan:
    the wire does not say where the stack ends when BOS is absent, which is exactly why
    the decoder records the size.
    """
    built = Label(labelled(WITHDRAW_LABEL), AFI.ipv4, has_labels=True)

    with pytest.raises(ValueError):
        built.cidr


@pytest.mark.parametrize(
    'name, afi, safi, wire',
    [
        ('labelled ipv4', AFI.ipv4, SAFI.nlri_mpls, bytes([48, 0, 0, 0x11, 10, 0, 0])),
        ('labelled vpn', AFI.ipv4, SAFI.mpls_vpn, bytes([112, 0, 0, 0x11]) + bytes(8) + bytes([10, 0, 0])),
    ],
    ids=['labelled ipv4', 'labelled vpn'],
)
def test_a_route_off_the_wire_still_reads_its_prefix(name: str, afi: AFI, safi: SAFI, wire: bytes) -> None:
    """Removing the fallback must not have removed the path which works.

    Every test above is satisfied by an accessor which refuses everything, so one of them
    has to decode a real route and read what it says.
    """
    nlri, _ = NLRI.unpack_nlri(afi, safi, wire, Action.ANNOUNCE, None, None)

    assert str(nlri.cidr) == '10.0.0.0/24', f'{name} lost its prefix'
    # the wire carries the label shifted left by four with the flags below it, so
    # 0x000011 is label 1 with the bottom of stack bit set
    assert nlri.labels.labels == [1], f'{name} lost its label'


def test_a_route_built_by_a_factory_still_reads_its_prefix() -> None:
    """The other construction path, which is what the raise tells people to use."""
    made = Label.from_cidr(CIDR.create_cidr(bytes([10, 0, 0, 0]), 24), AFI.ipv4, labels=Labels.make_labels([17], True))
    assert str(made.cidr) == '10.0.0.0/24'

    vpn = IPVPN.make_vpn_route(
        AFI.ipv4,
        SAFI.mpls_vpn,
        bytes([10, 0, 0, 0]),
        24,
        Labels.make_labels([17], True),
        RouteDistinguisher.make_from_elements('10.0.0.1', 7),
    )
    assert str(vpn.cidr) == '10.0.0.0/24'


def test_a_withdraw_label_keeps_its_prefix_on_a_withdraw() -> None:
    """0x800000 ends a stack only on a withdraw, which is what RFC 3107 defines it for."""
    nlri, _ = NLRI.unpack_nlri(
        AFI.ipv4, SAFI.nlri_mpls, bytes([48]) + WITHDRAW_LABEL + PREFIX, Action.WITHDRAW, None, None
    )

    assert str(nlri.cidr) == '10.0.0.0/24', 'a withdraw label ate the prefix off the wire'


# ---------------------------------------------------------------- what is refused still

# Two fields and no bottom of stack bit anywhere.  The length cannot read this as one
# field followed by a prefix, because 48 bits of prefix is more than IPv4 has, so the
# decoder is in the section 2.3 case where the S bit is the only delimiter and there is
# none.  Reading on takes the prefix, and the route arrives as 0.0.0.0/0.
UNENDING_LABELLED = bytes([72]) + UNTERMINATED + SECOND_UNTERMINATED + PREFIX


@pytest.mark.parametrize(
    'name, action',
    [
        ('announce', Action.ANNOUNCE),
        ('withdraw', Action.WITHDRAW),
    ],
    ids=['announce', 'withdraw'],
)
def test_a_stack_which_never_ends_is_refused(name: str, action: Action) -> None:
    """This decoded to 0.0.0.0/0, so a peer could hand us a default route.

    RFC 3107 3 and RFC 8277 2.3 put the bottom of stack bit on the last label, and beyond
    the first field it is the only thing on the wire which says where the stack ends.
    Without it the decoder read every remaining byte as a label, the prefix included, and
    reported what was left: nothing.

    The action makes no difference, which is the point of running both: a withdraw's
    Compatibility field is one field, never a stack, so two unterminated fields are as
    malformed on a withdraw as on an announce.
    """
    with pytest.raises(Notify, match='never ends'):
        NLRI.unpack_nlri(AFI.ipv4, SAFI.nlri_mpls, UNENDING_LABELLED, action, None, None)


@pytest.mark.parametrize(
    'name, action',
    [
        ('announce', Action.ANNOUNCE),
        ('withdraw', Action.WITHDRAW),
    ],
    ids=['announce', 'withdraw'],
)
def test_a_length_which_leaves_no_prefix_bits_is_refused(name: str, action: Action) -> None:
    """The residual the length rule deliberately does not close.

    One field with no bottom of stack bit, and a length which leaves nothing behind it.
    Read as section 2.2 that is a labelled 0.0.0.0/0, and read as a stack it is the old
    bug: the same bytes, and nothing on the wire to choose between them.  A default route
    is the more expensive of the two to be wrong about, so it is refused.

    A peer which really means a labelled default route sets the S bit, which RFC 8277 2.2
    says it MUST do on transmission, and then it decodes.
    """
    with pytest.raises(Notify, match='never ends'):
        NLRI.unpack_nlri(AFI.ipv4, SAFI.nlri_mpls, bytes([24]) + UNTERMINATED + PREFIX, action, None, None)


def test_a_label_stack_of_one_field_with_no_bottom_of_stack_bit_decodes() -> None:
    """The other side of the two tests above, and the reason they are narrow.

    RFC 8277 2.2: the S bit "MUST be ignored on reception".  One field, 24 bits of prefix
    behind it, and the length says which is which.  Without this the two refusals above
    would pass equally against a decoder which had gone back to refusing everything.
    """
    nlri, rest = NLRI.unpack_nlri(
        AFI.ipv4, SAFI.nlri_mpls, bytes([48]) + UNTERMINATED + PREFIX, Action.ANNOUNCE, None, None
    )

    assert str(nlri.cidr) == '10.0.0.0/24'
    assert nlri.labels.labels == [1]
    assert rest == b''


# The route distinguisher is why mpls-vpn needs its own cases.  IPVPN has its OWN
# unpack_nlri, a second copy of the label loop, so a fix to inet.py leaves it untouched:
# the pair rule, on two decoders rather than two accessors.
#
# And the RD is what makes the depth rule necessary.  Below depth one the loop is reading
# the distinguisher, whose leading bytes are zero for most encodings, and 0x000000 is the
# next-hop convention.  So an unterminated stack 'ended' the stack on the peer's own RD, a
# check which only counted whether the loop terminated was satisfied, and the prefix
# vanished anyway.  Session 5.0 found that half after I had fixed the other.
#
# The lengths below are what it takes to get past the first field now: 24 for the field,
# 64 for the RD, and more prefix bits than the family has, so that the section 2.2 reading
# is not available and the loop has to carry on into the RD.
UNENDING_VPN4 = bytes([24 + 24 + 64 + 24]) + UNTERMINATED + SECOND_UNTERMINATED + RD + PREFIX
UNENDING_VPN6 = (
    bytes([24 + 24 + 64 + 128]) + UNTERMINATED + SECOND_UNTERMINATED + RD + bytes([0x20, 0x01, 0x0D]) + bytes(13)
)


@pytest.mark.parametrize(
    'name, afi, wire',
    [
        ('ipv4 vpn', AFI.ipv4, UNENDING_VPN4),
        ('ipv6 vpn', AFI.ipv6, UNENDING_VPN6),
    ],
    ids=['ipv4 vpn', 'ipv6 vpn'],
)
def test_a_vpn_stack_which_never_ends_is_refused(name: str, afi: AFI, wire: bytes) -> None:
    """The half a fix to inet.py does not reach, because IPVPN decodes for itself."""
    with pytest.raises(Notify, match='never ends'):
        NLRI.unpack_nlri(afi, SAFI.mpls_vpn, wire, Action.ANNOUNCE, None, None)


def test_a_second_label_may_carry_a_sentinel_value() -> None:
    """The reorder the depth rule needs, and the reason the sentinels are tested last.

    0x000000 is the next-hop convention for a whole stack.  As the second label of a real
    stack it is just a label, and a decoder which tests the sentinels before the bottom of
    stack bit refuses a route which is perfectly well formed.
    """
    wire = bytes([72]) + bytes([0x00, 0x00, 0x10]) + bytes([0x00, 0x00, 0x21]) + bytes([10, 0, 0])
    nlri, _ = NLRI.unpack_nlri(AFI.ipv4, SAFI.nlri_mpls, wire, Action.ANNOUNCE, None, None)

    assert str(nlri.cidr) == '10.0.0.0/24'
    assert nlri.labels.labels == [1, 2], (
        'a two label stack lost a label, or the sentinel test ran before the bottom of stack test'
    )


def test_a_well_formed_vpn_route_still_decodes() -> None:
    """The refusals must not have closed the path they guard."""
    wire = bytes([112]) + bytes([0x00, 0x00, 0x11]) + RD + bytes([10, 0, 0])
    nlri, _ = NLRI.unpack_nlri(AFI.ipv4, SAFI.mpls_vpn, wire, Action.ANNOUNCE, None, None)

    assert str(nlri.cidr) == '10.0.0.0/24'
    assert nlri.labels.labels == [1]


def test_what_this_still_cannot_tell_apart_is_written_down() -> None:
    """A stack which terminates on the WRONG byte cannot be detected, only one which never does.

    Prefix bytes whose low bit is set read as a label with the bottom of stack bit, so a
    stack running one label too long into a prefix like 192.168.1.0 terminates and looks
    well formed.  The ambiguity is in the encoding, not in this decoder: the mask covers
    labels, RD and prefix together and nothing else marks the boundary.

    The length rule took the one field case away from this, so the shape needs two fields
    now where it needed one before.  The incompleteness was narrowed, not removed, and
    that is the whole reason this test was rewritten rather than deleted: its predecessor
    used a single field, failed the day the length rule landed, and carried an instruction
    to delete it if it ever did.

    IF THIS TEST EVER FAILS, DELETE IT.  It asserts an incompleteness, so a failure means
    the incompleteness is gone and the right response is to remove the test, not to adjust
    it until it passes again.  A comment saying "this is incomplete" ages into a comment
    nobody believes; a test asserting the incompleteness fails the day somebody fixes it.
    That framing is 5.0's and it is better than the comment it replaced.
    """
    # 0xc0a801: the last byte is odd, so it reads as a bottom of stack label
    wire = bytes([72]) + UNTERMINATED + SECOND_UNTERMINATED + bytes([0xC0, 0xA8, 0x01])
    nlri, _ = NLRI.unpack_nlri(AFI.ipv4, SAFI.nlri_mpls, wire, Action.ANNOUNCE, None, None)

    assert str(nlri.cidr) == '0.0.0.0/0', (
        'the prefix now survives an over-long stack: the encoding gained a boundary marker, or this decoder learned something it could not know'
    )


def test_the_same_prefix_one_bit_different_is_refused() -> None:
    """The twin of the case above, and the two together say where the boundary is.

    0xc0a801 ends in an odd byte and reads as a bottom of stack label, so the over-long
    stack looks terminated.  0xc0a800 does not, so the same shape is refused.  One bit of
    peer data decides which, and neither the decoder nor the encoding can do better.
    """
    wire = bytes([72]) + UNTERMINATED + SECOND_UNTERMINATED + bytes([0xC0, 0xA8, 0x00])

    with pytest.raises(Notify, match='never ends'):
        NLRI.unpack_nlri(AFI.ipv4, SAFI.nlri_mpls, wire, Action.ANNOUNCE, None, None)


def test_the_two_label_decoders_agree() -> None:
    """main has TWO live copies of the label loop and a fix can land in one.

    INET.unpack_nlri decodes nlri-mpls; IPVPN.unpack_nlri is a second copy which decodes
    mpls-vpn.  The first version of this fix went into inet.py alone and changed nothing
    for mpls-vpn, which stayed at 0.0.0.0/0, and every nlri-mpls test passed.  Session 5.0
    found it by measuring rather than by reading, and their branch does not have the hazard
    at all: their second copy is commented out, so their single edit reached both families.

    This asserts the two agree about what terminates a stack, so the next fix to one is a
    failure rather than a silence.  The third pair is the RFC 8277 2.2 reading, added when
    the length rule landed, because that is the newest place the two could drift apart.
    """
    terminated = bytes([0x00, 0x00, 0x11])

    def outcome(afi: AFI, safi: SAFI, wire: bytes) -> str:
        try:
            nlri, _ = NLRI.unpack_nlri(afi, safi, wire, Action.ANNOUNCE, None, None)
        except Notify:
            return 'refused'
        return str(nlri.cidr)

    plain_bad = outcome(AFI.ipv4, SAFI.nlri_mpls, UNENDING_LABELLED)
    vpn_bad = outcome(AFI.ipv4, SAFI.mpls_vpn, UNENDING_VPN4)
    assert plain_bad == vpn_bad == 'refused', (
        f'the two decoders disagree about an unterminated stack: nlri-mpls {plain_bad}, mpls-vpn {vpn_bad}'
    )

    plain_good = outcome(AFI.ipv4, SAFI.nlri_mpls, bytes([48]) + terminated + PREFIX)
    vpn_good = outcome(AFI.ipv4, SAFI.mpls_vpn, bytes([112]) + terminated + RD + PREFIX)
    assert plain_good == vpn_good == '10.0.0.0/24', (
        f'the two decoders disagree about a good stack: nlri-mpls {plain_good}, mpls-vpn {vpn_good}'
    )

    plain_one = outcome(AFI.ipv4, SAFI.nlri_mpls, bytes([48]) + UNTERMINATED + PREFIX)
    vpn_one = outcome(AFI.ipv4, SAFI.mpls_vpn, bytes([112]) + UNTERMINATED + RD + PREFIX)
    assert plain_one == vpn_one == '10.0.0.0/24', (
        f'the two decoders disagree about one field with no bottom of stack bit: '
        f'nlri-mpls {plain_one}, mpls-vpn {vpn_one}'
    )


def test_a_sentinel_below_depth_one_no_longer_ends_a_stack() -> None:
    """A narrowing the depth rule brings which is wider than "unterminated stacks".

    A withdraw whose SECOND label is 0x800000 used to terminate there and be accepted with
    two labels.  It is refused now: the sentinel describes a whole stack, so below depth
    one it is an ordinary label and the stack still has to reach a bottom of stack bit.

    RFC 3107 has the withdraw value replace the stack rather than sit inside one, so there
    is no defined encoding for what this used to accept.  compat_gate cannot see the change
    because the corpus does not produce this shape, which is why it is asserted here.
    """
    wire = bytes([72]) + bytes([0x00, 0x00, 0x10]) + WITHDRAW_LABEL + PREFIX

    with pytest.raises(Notify, match='never ends'):
        NLRI.unpack_nlri(AFI.ipv4, SAFI.nlri_mpls, wire, Action.WITHDRAW, None, None)


def test_a_sentinel_below_depth_one_is_still_a_usable_label() -> None:
    """The other half: it is refused for not terminating, not for containing the value.

    The same stack with a third label carrying the bottom of stack bit is accepted, and
    0x800000 sits in the middle of it as an ordinary label.  Without this, the test above
    would pass equally if the decoder had started refusing the VALUE anywhere it appeared.
    """
    wire = bytes([96]) + bytes([0x00, 0x00, 0x10]) + WITHDRAW_LABEL + bytes([0x00, 0x00, 0x21]) + PREFIX
    nlri, _ = NLRI.unpack_nlri(AFI.ipv4, SAFI.nlri_mpls, wire, Action.WITHDRAW, None, None)

    assert str(nlri.cidr) == '10.0.0.0/24'
    assert nlri.labels.labels == [1, 0x800000 >> 4, 2]
