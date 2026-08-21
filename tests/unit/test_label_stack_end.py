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

TIGER_STYLE.md 4 cites this function as its example of an invariant written where the code
checks it.  The invariant is now the whole of it.
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


@pytest.mark.parametrize(
    'name, action, label',
    [
        ('announce carrying the withdraw label', Action.ANNOUNCE, WITHDRAW_LABEL),
        ('announce with no bottom of stack', Action.ANNOUNCE, bytes([0x00, 0x00, 0x10])),
        ('withdraw with no bottom of stack', Action.WITHDRAW, bytes([0x00, 0x00, 0x10])),
    ],
    ids=['announce with withdraw label', 'announce without bos', 'withdraw without bos'],
)
def test_a_stack_which_never_ends_is_refused(name: str, action: Action, label: bytes) -> None:
    """Each of these decoded to 0.0.0.0/0, so a peer could hand us a default route.

    RFC 3107 3 puts the bottom of stack bit on the last label, and it is the only thing on
    the wire which says where the stack ends.  Without it the decoder read every remaining
    byte as a label, the prefix included, and reported what was left: nothing.
    """
    with pytest.raises(Notify, match='never ends'):
        NLRI.unpack_nlri(AFI.ipv4, SAFI.nlri_mpls, bytes([48]) + label + PREFIX, action, None, None)
