"""announce/vpn.py

Created by Thomas Mangin on 2017-07-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import cast

from exabgp.rib.change import Change

from exabgp.bgp.message import Action

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message.update.nlri import IPVPN
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.attribute import Attributes

from exabgp.configuration.announce import ParseAnnounce
from exabgp.configuration.announce.label import AnnounceLabel
from exabgp.configuration.core import Parser
from exabgp.configuration.core import Tokeniser
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Error

from exabgp.configuration.static.parser import prefix
from exabgp.configuration.static.mpls import route_distinguisher


class AnnounceVPN(ParseAnnounce):
    # put next-hop first as it is a requirement atm
    definition = [
        '  (optional) rd 255.255.255.255:65535|65535:65536|65536:65535;\n',
    ] + AnnounceLabel.definition

    syntax = '<safi> <ip>/<netmask> { \n   ' + ' ;\n   '.join(definition) + '\n}'

    known = {**AnnounceLabel.known, 'rd': route_distinguisher}
    action = {**AnnounceLabel.action, 'rd': 'nlri-set'}
    assign = {**AnnounceLabel.assign, 'rd': 'rd'}

    name = 'vpn'
    afi: AFI | None = None

    def __init__(self, parser: Parser, scope: Scope, error: Error) -> None:
        ParseAnnounce.__init__(self, parser, scope, error)

    def clear(self) -> None:
        pass

    @staticmethod
    def check(change: Change, afi: AFI | None) -> bool:
        if not AnnounceLabel.check(change, afi):
            return False

        # has_rd() confirms the NLRI type has an rd attribute
        if change.nlri.action == Action.ANNOUNCE and change.nlri.has_rd():
            if cast(IPVPN, change.nlri).rd is RouteDistinguisher.NORD:
                return False

        return True


def ip_vpn(tokeniser: Tokeniser, afi: AFI, safi: SAFI) -> list[Change]:
    nlri_action = Action.ANNOUNCE if tokeniser.announce else Action.WITHDRAW
    ipmask = prefix(tokeniser)

    nlri = IPVPN(afi, safi, nlri_action)
    nlri.cidr = CIDR(ipmask.pack_ip(), ipmask.mask)

    change = Change(nlri, Attributes())

    while True:
        command = tokeniser()

        if not command:
            break

        command_action = AnnounceVPN.action.get(command, '')

        if command_action == 'attribute-add':
            change.attributes.add(AnnounceVPN.known[command](tokeniser))
        elif command_action == 'nlri-set':
            change.nlri.assign(AnnounceVPN.assign[command], AnnounceVPN.known[command](tokeniser))
        elif command_action == 'nexthop-and-attribute':
            nexthop, attribute = AnnounceVPN.known[command](tokeniser)
            change.nlri.nexthop = nexthop
            change.attributes.add(attribute)
        else:
            raise ValueError('unknown command "{}"'.format(command))

    if not AnnounceVPN.check(change, afi):
        raise ValueError('invalid announcement (missing next-hop, label or rd ?)')

    return [change]


@ParseAnnounce.register('mpls-vpn', 'extend-name', 'ipv4')
def mpls_vpn_v4(tokeniser: Tokeniser) -> list[Change]:
    return ip_vpn(tokeniser, AFI.ipv4, SAFI.unicast)


@ParseAnnounce.register('mpls-vpn', 'extend-name', 'ipv6')
def mpls_vpn_v6(tokeniser: Tokeniser) -> list[Change]:
    return ip_vpn(tokeniser, AFI.ipv6, SAFI.unicast)
