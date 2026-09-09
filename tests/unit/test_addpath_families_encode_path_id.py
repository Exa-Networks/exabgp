"""Every family ExaBGP offers ADD-PATH for must be able to carry a path identifier.

RFC 7911 section 3: once ADD-PATH is negotiated for an AFI/SAFI, every NLRI in that family
carries a four octet Path Identifier ahead of it. Offering the capability for a family whose
encoder does not write one is not a missing feature, it is a malformed UPDATE: the peer reads
the first four octets of the NLRI as a path id and mis-frames everything after it.

MUP was in `Capabilities._ADD_PATH` while `MUP.pack_nlri` wrote no path id, so
`add-path { ipv4 mup; }` put `AddPath(send/receive ipv4 mup)` on the wire and then sent MUP
NLRI without one. This test is written against the capability list rather than against MUP,
so a family added to that list without an encoder to match fails here rather than at a peer.
"""

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.open.capability.capabilities import Capabilities
from exabgp.bgp.message.open.capability.negotiated import RequirePath
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.ipvpn import IPVPN
from exabgp.bgp.message.update.nlri.label import Label
from exabgp.bgp.message.update.nlri.mup.nlri import MUP
from exabgp.bgp.message.update.nlri.qualifier import Labels
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.protocol.family import SAFI
from exabgp.protocol.ip import IP


PATH_ID_SIZE = 4

ADDRESS = {'ipv4': ('192.0.2.0', 24), 'ipv6': ('2001:db8::', 32)}


class Session:
    """The only thing an NLRI encoder reads from a Negotiated is addpath.send()."""

    def __init__(self, addpath):
        self.addpath = addpath


def build_nlri(family):
    """One NLRI of this family, built without a path identifier."""
    afi, safi = family
    address, mask = ADDRESS[str(afi)]
    cidr = CIDR(IP.pton(address), mask)

    if safi == SAFI.unicast:
        nlri = INET(afi, safi, Action.ANNOUNCE)
        nlri.cidr = cidr
        return nlri
    if safi == SAFI.nlri_mpls:
        nlri = Label(afi, safi, Action.ANNOUNCE)
        nlri.cidr = cidr
        nlri.labels = Labels([800])
        return nlri
    if safi == SAFI.mpls_vpn:
        nlri = IPVPN(afi, safi, Action.ANNOUNCE)
        nlri.cidr = cidr
        nlri.labels = Labels([800])
        nlri.rd = RouteDistinguisher(bytes(8))
        return nlri
    if safi == SAFI.mup:
        return MUP(afi)
    raise AssertionError('no NLRI builder for {}/{}; add one rather than skipping the family'.format(afi, safi))


def negotiated_for(family, addpath):
    # A fresh instance each time, so setting a direction here cannot leak into another test.
    require = RequirePath()
    if addpath:
        require._send[family] = True
        require._receive[family] = True
    return Session(require)


@pytest.mark.parametrize('family', Capabilities._ADD_PATH, ids=lambda f: '{}-{}'.format(f[0], f[1]))
def test_offered_addpath_family_encodes_a_path_identifier(family):
    nlri = build_nlri(family)

    plain = len(nlri.pack(negotiated_for(family, addpath=False)))
    with_path = len(nlri.pack(negotiated_for(family, addpath=True)))

    assert with_path == plain + PATH_ID_SIZE, (
        '{}/{} is offered in the ADD-PATH capability, but its NLRI packs {} extra octets once '
        'ADD-PATH is negotiated instead of {}. Either the encoder writes the path identifier, '
        'or the family comes out of Capabilities._ADD_PATH until it does.'.format(
            family[0], family[1], with_path - plain, PATH_ID_SIZE
        )
    )
