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

from exabgp.bgp.message.update.nlri.label import Label
from exabgp.bgp.message.update.nlri.qualifier import Labels
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.attribute import Attributes

from exabgp.configuration.announce import ParseAnnounce
from exabgp.configuration.announce.path import AnnouncePath

from exabgp.configuration.static.parser import prefix
from exabgp.configuration.static.mpls import label


class AnnounceLabel(AnnouncePath):
    # put next-hop first as it is a requirement atm
    definition = ['label <15 bits number>',] + AnnouncePath.definition

    syntax = '<safi> <ip>/<netmask> { ' '\n   ' + ' ;\n   '.join(definition) + '\n}'

    known = dict(AnnouncePath.known, **{'label': label,})

    action = dict(AnnouncePath.action, **{'label': 'nlri-set',})

    assign = dict(AnnouncePath.assign, **{'label': 'labels',})

    name = 'vpn'
    afi = None

    def __init__(self, tokeniser, scope, error, logger):
        AnnouncePath.__init__(self, tokeniser, scope, error, logger)

    def clear(self):
        return True

    @staticmethod
    def check(change, afi):
        if not AnnouncePath.check(change, afi):
            return False

        if change.nlri.action == OUT.ANNOUNCE and change.nlri.has_label() and change.nlri.labels is Labels.NOLABEL:
            return False

        return True


def ip_label(tokeniser, afi, safi):
    action = OUT.ANNOUNCE if tokeniser.announce else OUT.WITHDRAW
    ipmask = prefix(tokeniser)

    nlri = Label(afi, safi, action)
    nlri.cidr = CIDR(ipmask.pack(), ipmask.mask)

    change = Change(nlri, Attributes())

    while True:
        command = tokeniser()

        if not command:
            break

        action = AnnounceLabel.action.get(command, '')

        if action == 'attribute-add':
            change.attributes.add(AnnounceLabel.known[command](tokeniser))
        elif action == 'nlri-set':
            change.nlri.assign(AnnounceLabel.assign[command], AnnounceLabel.known[command](tokeniser))
        elif action == 'nexthop-and-attribute':
            nexthop, attribute = AnnounceLabel.known[command](tokeniser)
            change.nlri.nexthop = nexthop
            change.attributes.add(attribute)
        else:
            raise ValueError('unknown command "%s"' % command)

    if not AnnounceLabel.check(change, afi):
        raise ValueError('invalid announcement (missing next-hop or label ?)')

    return [change]


@ParseAnnounce.register('nlri-mpls', 'extend-name', 'ipv4')
def nlri_mpls_v4(tokeniser):
    return ip_label(tokeniser, AFI.ipv4, SAFI.nlri_mpls)


@ParseAnnounce.register('nlri-mpls', 'extend-name', 'ipv6')
def nlri_mpls_v6(tokeniser):
    return ip_label(tokeniser, AFI.ipv6, SAFI.nlri_mpls)
