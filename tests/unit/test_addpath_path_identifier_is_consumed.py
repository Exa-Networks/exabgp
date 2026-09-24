"""Five NLRI families never took the ADD-PATH path identifier off the wire.

RFC 7911 section 3: when ADD-PATH has been negotiated for a family, every NLRI of that
family is preceded by a four byte Path Identifier. The decoder has to consume it before
reading the NLRI, and `inet.py` does exactly that.

EVPN, BGP-LS, MVPN, MUP and SR-Policy did not. Each of them read its first field straight
from `data[0]`, which with ADD-PATH on is the first byte of the path identifier rather
than the route type. The damage is not limited to one route: because the identifier is
never consumed, the NLRI length is read from the wrong offset too, so the reader ends up
at the wrong place in the buffer and every NLRI after it in the same UPDATE is garbage.

For EVPN the effect was visible in one line: a type 1 route preceded by a path identifier
decoded as a GenericEVPN of an unknown type, consuming 2 bytes of 31.

What let it survive was a name collision the type system could not see. The `unpack_nlri`
parameter named `addpath` is a bool, "has ADD-PATH been negotiated". The NLRI attribute
named `addpath` is a `PathInfo`, the identifier itself. All five assigned the first to the
second, and the parameter was annotated `Any`, so `nlri.addpath = addpath` type-checked.
Typing the parameter `bool` is what surfaced it.

`add-path` in the configuration accepts any AFI/SAFI, so this is reachable: it needs only
`add-path { l2vpn evpn; }` and a peer which agrees.
"""

from __future__ import annotations

from struct import pack
from typing import Any
from unittest.mock import Mock

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.update.nlri.bgpls.nlri import BGPLS
from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN
from exabgp.bgp.message.update.nlri.mup.nlri import MUP
from exabgp.bgp.message.update.nlri.mvpn.nlri import MVPN
from exabgp.bgp.message.update.nlri.qualifier import PathInfo
from exabgp.bgp.message.update.nlri.sr_policy import SRPolicyNLRI
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
SR_POLICY_NLRI = bytes([96]) + bytes(12)  # RFC 9830: 96 bits for IPv4

FAMILIES = [
    ('evpn', EVPN, AFI.l2vpn, SAFI.evpn, EVPN_NLRI),
    ('mvpn', MVPN, AFI.ipv4, SAFI.mcast_vpn, MVPN_NLRI),
    ('mup', MUP, AFI.ipv4, SAFI.mup, MUP_NLRI),
    ('bgpls', BGPLS, AFI.bgpls, SAFI.bgp_ls, BGPLS_NLRI),
    ('sr-policy', SRPolicyNLRI, AFI.ipv4, SAFI.sr_policy, SR_POLICY_NLRI),
]
IDS = [name for name, _, _, _, _ in FAMILIES]


def negotiated() -> Any:
    session = Mock()
    session.asn4 = False
    session.families = []
    session.nexthop = []
    return session


@pytest.mark.parametrize('name,klass,afi,safi,nlri_bytes', FAMILIES, ids=IDS)
def test_the_path_identifier_is_consumed(name: str, klass: Any, afi: AFI, safi: SAFI, nlri_bytes: bytes) -> None:
    """With ADD-PATH on, the four identifier bytes must be gone from what is left.

    This is the assertion which catches the desynchronisation: whatever the decoder makes
    of this NLRI, it must leave the reader positioned after it, not four bytes short.
    """
    wire = PATH_ID + nlri_bytes

    _, left = klass.unpack_nlri(afi, safi, wire, Action.ANNOUNCE, True, negotiated())

    assert len(left) == 0, (
        f'{name} left {len(left)} bytes of {len(wire)}: the path identifier was not consumed, '
        f'so every NLRI after this one in the UPDATE is read from the wrong offset'
    )


@pytest.mark.parametrize('name,klass,afi,safi,nlri_bytes', FAMILIES, ids=IDS)
def test_the_nlri_parses_the_same_with_and_without_a_path_identifier(
    name: str, klass: Any, afi: AFI, safi: SAFI, nlri_bytes: bytes
) -> None:
    """The identifier is a prefix, not part of the NLRI, so it must not change the parse.

    Consuming the right number of bytes is not enough on its own: a decoder which skipped
    four bytes and then read the NLRI from the wrong place would satisfy the test above.
    """
    with_path, _ = klass.unpack_nlri(afi, safi, PATH_ID + nlri_bytes, Action.ANNOUNCE, True, negotiated())
    without_path, _ = klass.unpack_nlri(afi, safi, nlri_bytes, Action.ANNOUNCE, False, negotiated())

    assert type(with_path) is type(without_path), (
        f'{name} decoded to {type(with_path).__name__} with a path identifier and '
        f'{type(without_path).__name__} without one'
    )


@pytest.mark.parametrize('name,klass,afi,safi,nlri_bytes', FAMILIES, ids=IDS)
def test_the_identifier_is_kept_as_path_information(
    name: str, klass: Any, afi: AFI, safi: SAFI, nlri_bytes: bytes
) -> None:
    """`nlri.addpath` holds a PathInfo. It used to hold the boolean parameter.

    RFC 7911 makes the identifier part of what distinguishes one path from another, so
    storing True there loses the only thing which tells two paths apart.
    """
    nlri, _ = klass.unpack_nlri(afi, safi, PATH_ID + nlri_bytes, Action.ANNOUNCE, True, negotiated())

    assert isinstance(nlri.addpath, PathInfo), f'{name} stored {nlri.addpath!r} where the path identifier belongs'
    assert bytes(nlri.addpath.pack_path()) == PATH_ID, f'{name} kept the wrong path identifier'


@pytest.mark.parametrize('name,klass,afi,safi,nlri_bytes', FAMILIES, ids=IDS)
def test_without_addpath_nothing_is_consumed(name: str, klass: Any, afi: AFI, safi: SAFI, nlri_bytes: bytes) -> None:
    """The far commoner case must not have gained a four byte skip."""
    nlri, left = klass.unpack_nlri(afi, safi, nlri_bytes, Action.ANNOUNCE, False, negotiated())

    assert len(left) == 0, f'{name} did not consume its own NLRI'
    assert nlri.addpath is PathInfo.DISABLED, f'{name} invented path information nobody sent'


@pytest.mark.parametrize('name,klass,afi,safi,nlri_bytes', FAMILIES, ids=IDS)
def test_a_truncated_path_identifier_is_refused(name: str, klass: Any, afi: AFI, safi: SAFI, nlri_bytes: bytes) -> None:
    """Three bytes where four are required is the peer's error, so it gets a Notify.

    EXA_STYLE 1.1: check the length before reading, and malformed peer input raises Notify
    rather than an IndexError out of a slice.
    """
    from exabgp.bgp.message.notification import Notify

    with pytest.raises(Notify):
        klass.unpack_nlri(afi, safi, PATH_ID[:3], Action.ANNOUNCE, True, negotiated())
