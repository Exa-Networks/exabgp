# encoding: utf-8
"""
announce/vpn.py

Created by Thomas Mangin on 2017-07-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.protocol.ip import NoNextHop

from exabgp.rib.change import Change

from exabgp.bgp.message import OUT

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message.update.nlri import IPVPN
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.attribute import Attributes

from exabgp.configuration.announce import ParseAnnounce
from exabgp.configuration.announce.label import AnnounceLabel

from exabgp.configuration.static.parser import prefix
from exabgp.configuration.static.mpls import route_distinguisher


class AnnounceVPN(ParseAnnounce):
    # put next-hop first as it is a requirement atm
    definition = ['  (optional) rd 255.255.255.255:65535|65535:65536|65536:65535;\n',] + AnnounceLabel.definition

    syntax = '<safi> <ip>/<netmask> { ' '\n   ' + ' ;\n   '.join(definition) + '\n}'

    known = dict(AnnounceLabel.known, **{'rd': route_distinguisher,})

    action = dict(AnnounceLabel.action, **{'rd': 'nlri-set',})

    assign = dict(AnnounceLabel.assign, **{'rd': 'rd',})

    name = 'vpn'
    afi = None

    def __init__(self, tokeniser, scope, error, logger):
        ParseAnnounce.__init__(self, tokeniser, scope, error, logger)

    def clear(self):
        return True

    @staticmethod
    def check(change, afi):
        if not AnnounceLabel.check(change, afi):
            return False

        if change.nlri.action == OUT.ANNOUNCE and change.nlri.has_rd() and change.nlri.rd is RouteDistinguisher.NORD:
            return False

        return True


def ip_vpn(tokeniser, afi, safi):
    action = OUT.ANNOUNCE if tokeniser.announce else OUT.WITHDRAW
    ipmask = prefix(tokeniser)

    nlri = IPVPN(afi, safi, action)
    nlri.cidr = CIDR(ipmask.pack(), ipmask.mask)

    change = Change(nlri, Attributes())

    while True:
        command = tokeniser()

        if not command:
            break

        action = AnnounceVPN.action.get(command, '')

        if action == 'attribute-add':
            change.attributes.add(AnnounceVPN.known[command](tokeniser))
        elif action == 'nlri-set':
            change.nlri.assign(AnnounceVPN.assign[command], AnnounceVPN.known[command](tokeniser))
        elif action == 'nexthop-and-attribute':
            nexthop, attribute = AnnounceVPN.known[command](tokeniser)
            change.nlri.nexthop = nexthop
            change.attributes.add(attribute)
        else:
            raise ValueError('unknown command "%s"' % command)

    if not AnnounceVPN.check(change, afi):
        raise ValueError('invalid announcement (missing next-hop, label or rd ?)')

    return [change]


@ParseAnnounce.register('mpls-vpn', 'extend-name', 'ipv4')
def mpls_vpn_v4(tokeniser):
    return ip_vpn(tokeniser, AFI.ipv4, SAFI.unicast)


@ParseAnnounce.register('mpls-vpn', 'extend-name', 'ipv6')
def mpls_vpn_v6(tokeniser):
    return ip_vpn(tokeniser, AFI.ipv6, SAFI.unicast)
