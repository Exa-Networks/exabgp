"""Every family ExaBGP offers ADD-PATH for must be able to carry a path identifier.

RFC 7911 section 3: once ADD-PATH is negotiated for an AFI/SAFI, every NLRI in that family
carries a four octet Path Identifier ahead of it. Offering the capability for a family whose
encoder does not write one is not a missing feature, it is a malformed UPDATE: the peer reads
the first four octets of the NLRI as a path id and mis-frames everything after it.

MUP was in `Capabilities._ADD_PATH` while `MUP.pack_nlri` carried a TODO and wrote no path
id, so `add-path { ipv4 mup; }` put `AddPath(send/receive ipv4 mup)` on the wire and then
sent MUP NLRI without one. This test is written against the capability list rather than
against MUP, so a family added to that list without an encoder to match fails here rather
than at a peer.
"""

import pytest

from exabgp.bgp.message.open.capability.capabilities import Capabilities
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.ipvpn import IPVPN
from exabgp.bgp.message.update.nlri.label import Label
from exabgp.bgp.message.update.nlri.mup.nlri import MUP
from exabgp.bgp.message.update.nlri.qualifier.labels import Labels
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.bgp.message.update.nlri.qualifier.rd import RouteDistinguisher
from exabgp.protocol.family import AFI, SAFI, FamilyTuple
from exabgp.protocol.ip import IP
from exabgp.bgp.message.update.nlri.nlri import NLRI


PATH_ID_SIZE = 4

ADDRESS = {AFI.ipv4: ('192.0.2.0', 24), AFI.ipv6: ('2001:db8::', 32)}


def build_nlri(family: FamilyTuple) -> NLRI:
    """One NLRI of this family, built without a path identifier."""
    afi, safi = family
    address, mask = ADDRESS[afi]
    cidr = CIDR.create_cidr(IP.pton(address), mask)

    if safi == SAFI.unicast:
        return INET.from_cidr(cidr, afi, safi, PathInfo.DISABLED)
    if safi == SAFI.nlri_mpls:
        return Label.from_cidr(cidr, afi, safi, PathInfo.DISABLED, Labels.make_labels([800]))
    if safi == SAFI.mpls_vpn:
        return IPVPN.from_cidr(
            cidr, afi, safi, PathInfo.DISABLED, Labels.make_labels([800]), RouteDistinguisher(bytes(8))
        )
    if safi == SAFI.mup:
        return MUP(afi)
    raise AssertionError(f'no NLRI builder for {afi}/{safi}; add one rather than skipping the family')


def negotiated_for(family: FamilyTuple, addpath: bool) -> Negotiated:
    # A fresh instance each time: Negotiated.UNSET is one process-wide object and setting an
    # addpath direction on it would leak into every other caller in this interpreter.
    negotiated = Negotiated._create_unset()
    if addpath:
        negotiated.addpath._send[family] = True
        negotiated.addpath._receive[family] = True
    return negotiated


@pytest.mark.parametrize('family', Capabilities._ADD_PATH, ids=lambda f: f'{f[0]}-{f[1]}')
def test_offered_addpath_family_encodes_a_path_identifier(family: FamilyTuple) -> None:
    nlri = build_nlri(family)

    plain = len(nlri.pack_nlri(negotiated_for(family, addpath=False)))
    with_path = len(nlri.pack_nlri(negotiated_for(family, addpath=True)))

    assert with_path == plain + PATH_ID_SIZE, (
        f'{family[0]}/{family[1]} is offered in the ADD-PATH capability, but its NLRI packs '
        f'{with_path - plain} extra octets once ADD-PATH is negotiated instead of {PATH_ID_SIZE}. '
        f'Either the encoder writes the path identifier, or the family comes out of '
        f'Capabilities._ADD_PATH until it does.'
    )
