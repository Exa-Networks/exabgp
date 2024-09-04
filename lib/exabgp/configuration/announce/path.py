# encoding: utf-8
"""
announce/label.py

Created by Thomas Mangin on 2017-07-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.protocol.ip import NoNextHop

from exabgp.rib.change import Change

from exabgp.bgp.message import OUT

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.attribute import Attributes

from exabgp.configuration.announce import ParseAnnounce
from exabgp.configuration.announce.ip import AnnounceIP

from exabgp.configuration.static.parser import prefix
from exabgp.configuration.static.parser import path_information


class AnnouncePath(AnnounceIP):
    # put next-hop first as it is a requirement atm
    definition = ['label <15 bits number>',] + AnnounceIP.definition

    syntax = '<safi> <ip>/<netmask> { ' '\n   ' + ' ;\n   '.join(definition) + '\n}'

    known = dict(AnnounceIP.known, **{'path-information': path_information,})

    action = dict(AnnounceIP.action, **{'path-information': 'nlri-set',})

    assign = dict(AnnounceIP.assign, **{'path-information': 'path_info',})

    name = 'path'
    afi = None

    def __init__(self, tokeniser, scope, error, logger):
        AnnounceIP.__init__(self, tokeniser, scope, error, logger)

    def clear(self):
        return True

    @staticmethod
    def check(change, afi):
        if not AnnounceIP.check(change, afi):
            return False

        return True


def ip_unicast(tokeniser, afi, safi):
    action = OUT.ANNOUNCE if tokeniser.announce else OUT.WITHDRAW
    ipmask = prefix(tokeniser)

    nlri = INET(afi, safi, action)
    nlri.cidr = CIDR(ipmask.pack(), ipmask.mask)

    change = Change(nlri, Attributes())

    while True:
        command = tokeniser()

        if not command:
            break

        action = AnnouncePath.action.get(command, '')

        if action == 'attribute-add':
            change.attributes.add(AnnouncePath.known[command](tokeniser))
        elif action == 'nlri-set':
            change.nlri.assign(AnnouncePath.assign[command], AnnouncePath.known[command](tokeniser))
        elif action == 'nexthop-and-attribute':
            nexthop, attribute = AnnouncePath.known[command](tokeniser)
            change.nlri.nexthop = nexthop
            change.attributes.add(attribute)
        else:
            raise ValueError('unknown command "%s"' % command)

    if not AnnouncePath.check(change, afi):
        raise ValueError('invalid announcement (missing next-hop ?)')

    return [change]


@ParseAnnounce.register('unicast', 'extend-name', 'ipv4')
def unicast_v4(tokeniser):
    return ip_unicast(tokeniser, AFI.ipv4, SAFI.unicast)


@ParseAnnounce.register('unicast', 'extend-name', 'ipv6')
def unicast_v6(tokeniser):
    return ip_unicast(tokeniser, AFI.ipv6, SAFI.unicast)
