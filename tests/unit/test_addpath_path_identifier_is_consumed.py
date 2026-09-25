"""Seven NLRI families never took the ADD-PATH path identifier off the wire.

RFC 7911 section 3: when ADD-PATH has been negotiated for a family, every NLRI of that
family is preceded by a four byte Path Identifier. The decoder has to consume it before
reading the NLRI, and `inet.py` does exactly that.

EVPN, BGP-LS, MVPN, MUP, FlowSpec, VPLS and RTC did not. Each of them read its first
field straight from `bgp[0]`, which with ADD-PATH on is the first byte of the path
identifier rather than the route type. The damage is not limited to one route: because
the identifier is never consumed, the NLRI length is read from the wrong offset too, so
the reader ends up at the wrong place in the buffer and every NLRI after it in the same
UPDATE is garbage. An EVPN type 1 route preceded by a path identifier decoded as a
GenericEVPN of an unknown type, consuming 2 bytes of 31, and VPLS answered a perfectly
legal NLRI with a NOTIFICATION because its length no longer matched what was left.

What let it survive is a name collision. The `unpack_nlri` parameter named `addpath` is
the question "has ADD-PATH been negotiated", a boolean. The NLRI attribute named
`addpath` is the identifier itself. Five families assigned the first into the second and
the other two ignored it altogether.

A live session does not reach this: `Capabilities._ADD_PATH` only offers the capability
for unicast, labelled unicast and VPN, and `Negotiated` only turns ADD-PATH on for a
family our own OPEN carried. What does reach it is `configuration/check.py`, which builds
the capability from the configured families unfiltered and backs the offline tools. The
decoders are right now for the day one of these families joins `_ADD_PATH`, which needs
the encoder half first.
"""

from struct import pack
from typing import Any

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.bgpls.nlri import BGPLS
from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN
from exabgp.bgp.message.update.nlri.flow import Flow
from exabgp.bgp.message.update.nlri.mup.nlri import MUP
from exabgp.bgp.message.update.nlri.mvpn.nlri import MVPN
from exabgp.bgp.message.update.nlri.qualifier import PathInfo
from exabgp.bgp.message.update.nlri.rtc import RTC
from exabgp.bgp.message.update.nlri.vpls import VPLS
from exabgp.protocol.family import AFI, SAFI

PATH_ID = bytes([0, 0, 0, 7])

# One well formed NLRI per family, without any path identifier in front of it.
EVPN_NLRI = bytes([1, 25]) + bytes(25)  # ethernet auto-discovery, 25 bytes of payload
MVPN_NLRI = bytes([1, 12]) + bytes(12)  # intra-AS I-PMSI, 12 bytes of payload
# Deliberately unregistered type codes for MUP and BGP-LS. This file is about the four
# bytes in front of the NLRI, not about each family's payload rules, and a registered
# type would have its contents validated and reject a block of zeros for its own
# reasons. Both decode to their Generic form, which is enough to see where the reader
# ended up.
MUP_NLRI = bytes([99, 0, 99, 12]) + bytes(12)  # unregistered arch/type, 12 byte payload
BGPLS_NLRI = pack('!HH', 999, 12) + bytes(12)  # unregistered NLRI type, 12 byte payload
FLOW_NLRI = bytes([3, 1, 8, 10])  # RFC 8955: one component, destination 10.0.0.0/8
VPLS_NLRI = bytes([0, 17]) + bytes(17)  # RFC 4761: two byte length, 17 byte payload
RTC_NLRI = bytes([96]) + bytes(12)  # RFC 4684: origin AS and a full route target

FAMILIES = [
    ('evpn', EVPN, AFI.l2vpn, SAFI.evpn, EVPN_NLRI),
    ('mvpn', MVPN, AFI.ipv4, SAFI.mcast_vpn, MVPN_NLRI),
    ('mup', MUP, AFI.ipv4, SAFI.mup, MUP_NLRI),
    ('bgpls', BGPLS, AFI.bgpls, SAFI.bgp_ls, BGPLS_NLRI),
    ('flow', Flow, AFI.ipv4, SAFI.flow_ip, FLOW_NLRI),
    ('vpls', VPLS, AFI.l2vpn, SAFI.vpls, VPLS_NLRI),
    ('rtc', RTC, AFI.ipv4, SAFI.rtc, RTC_NLRI),
]
IDS = [name for name, _, _, _, _ in FAMILIES]


@pytest.mark.parametrize('name,klass,afi,safi,nlri_bytes', FAMILIES, ids=IDS)
def test_the_path_identifier_is_consumed(name: str, klass: Any, afi: AFI, safi: SAFI, nlri_bytes: bytes) -> None:
    """With ADD-PATH on, the four identifier bytes must be gone from what is left.

    This is the assertion which catches the desynchronisation: whatever the decoder makes
    of this NLRI, it must leave the reader positioned after it, not four bytes short.
    """
    wire = PATH_ID + nlri_bytes

    _, left = klass.unpack_nlri(afi, safi, wire, Action.ANNOUNCE, True)

    assert len(left) == 0, (
        '{} left {} bytes of {}: the path identifier was not consumed, so every NLRI '
        'after this one in the UPDATE is read from the wrong offset'.format(name, len(left), len(wire))
    )


@pytest.mark.parametrize('name,klass,afi,safi,nlri_bytes', FAMILIES, ids=IDS)
def test_the_nlri_parses_the_same_with_and_without_a_path_identifier(
    name: str, klass: Any, afi: AFI, safi: SAFI, nlri_bytes: bytes
) -> None:
    """The identifier is a prefix, not part of the NLRI, so it must not change the parse.

    Consuming the right number of bytes is not enough on its own: a decoder which skipped
    four bytes and then read the NLRI from the wrong place would satisfy the test above.
    """
    with_path, _ = klass.unpack_nlri(afi, safi, PATH_ID + nlri_bytes, Action.ANNOUNCE, True)
    without_path, _ = klass.unpack_nlri(afi, safi, nlri_bytes, Action.ANNOUNCE, False)

    assert type(with_path) is type(without_path), '{} decoded to {} with a path identifier and {} without one'.format(
        name, type(with_path).__name__, type(without_path).__name__
    )


@pytest.mark.parametrize('name,klass,afi,safi,nlri_bytes', FAMILIES, ids=IDS)
def test_the_identifier_is_kept_as_path_information(
    name: str, klass: Any, afi: AFI, safi: SAFI, nlri_bytes: bytes
) -> None:
    """`nlri.addpath` holds a PathInfo. It used to hold the boolean parameter.

    RFC 7911 makes the identifier part of what distinguishes one path from another, so
    storing True there loses the only thing which tells two paths apart.
    """
    nlri, _ = klass.unpack_nlri(afi, safi, PATH_ID + nlri_bytes, Action.ANNOUNCE, True)

    assert isinstance(nlri.addpath, PathInfo), '{} stored {!r} where the path identifier belongs'.format(
        name, nlri.addpath
    )
    assert bytes(nlri.addpath.pack()) == PATH_ID, '{} kept the wrong path identifier'.format(name)


@pytest.mark.parametrize('name,klass,afi,safi,nlri_bytes', FAMILIES, ids=IDS)
def test_without_addpath_nothing_is_consumed(name: str, klass: Any, afi: AFI, safi: SAFI, nlri_bytes: bytes) -> None:
    """The far commoner case must not have gained a four byte skip."""
    nlri, left = klass.unpack_nlri(afi, safi, nlri_bytes, Action.ANNOUNCE, False)

    assert len(left) == 0, '{} did not consume its own NLRI'.format(name)
    assert nlri.addpath is PathInfo.NOPATH, '{} invented path information nobody sent'.format(name)


@pytest.mark.parametrize('name,klass,afi,safi,nlri_bytes', FAMILIES, ids=IDS)
def test_a_truncated_path_identifier_is_refused(name: str, klass: Any, afi: AFI, safi: SAFI, nlri_bytes: bytes) -> None:
    """Three bytes where four are required is the peer's error, so it gets a Notify.

    TIGER STYLE 1.1: check the length before reading, so malformed peer input raises
    Notify rather than coming back from a short slice as though it were complete.
    """
    with pytest.raises(Notify):
        klass.unpack_nlri(afi, safi, PATH_ID[:3], Action.ANNOUNCE, True)
