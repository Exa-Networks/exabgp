# encoding: utf-8
"""
announce/ip.py

Created by Thomas Mangin on 2015-06-04.
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

from exabgp.configuration.static.parser import prefix

# from exabgp.configuration.static.parser import inet
from exabgp.configuration.static.parser import attribute
from exabgp.configuration.static.parser import next_hop
from exabgp.configuration.static.parser import origin
from exabgp.configuration.static.parser import med
from exabgp.configuration.static.parser import as_path
from exabgp.configuration.static.parser import local_preference
from exabgp.configuration.static.parser import atomic_aggregate
from exabgp.configuration.static.parser import aggregator
from exabgp.configuration.static.parser import originator_id
from exabgp.configuration.static.parser import cluster_list
from exabgp.configuration.static.parser import community
from exabgp.configuration.static.parser import large_community
from exabgp.configuration.static.parser import extended_community
from exabgp.configuration.static.parser import aigp
from exabgp.configuration.static.parser import name as named
from exabgp.configuration.static.parser import split
from exabgp.configuration.static.parser import watchdog
from exabgp.configuration.static.parser import withdraw


class AnnounceIP(ParseAnnounce):
    # put next-hop first as it is a requirement atm
    definition = [
        'next-hop <ip>',
        'origin IGP|EGP|INCOMPLETE',
        'as-path [ <asn>.. ]',
        'med <16 bits number>',
        'local-preference <16 bits number>',
        'atomic-aggregate',
        'community <16 bits number>',
        'large-community <96 bits number>',
        'extended-community target:<16 bits number>:<ipv4 formated number>',
        'originator-id <ipv4>',
        'cluster-list <ipv4>',
        'label <15 bits number>',
        'bgp-prefix-sid [ 32 bits number> ] | [ <32 bits number>, [ ( <24 bits number>,<24 bits number> ) ]]',
        'aggregator ( <asn16>:<ipv4> )',
        'aigp <40 bits number>',
        'attribute [ generic attribute format ]' 'name <mnemonic>',
        'split /<mask>',
        'watchdog <watchdog-name>',
        'withdraw',
    ]

    syntax = '<safi> <ip>/<netmask> { ' '\n   ' + ' ;\n   '.join(definition) + '\n}'

    known = {
        'attribute': attribute,
        'next-hop': next_hop,
        'origin': origin,
        'med': med,
        'as-path': as_path,
        'local-preference': local_preference,
        'atomic-aggregate': atomic_aggregate,
        'aggregator': aggregator,
        'originator-id': originator_id,
        'cluster-list': cluster_list,
        'community': community,
        'large-community': large_community,
        'extended-community': extended_community,
        'aigp': aigp,
        'name': named,
        'split': split,
        'watchdog': watchdog,
        'withdraw': withdraw,
    }

    action = {
        'attribute': 'attribute-add',
        'next-hop': 'nexthop-and-attribute',
        'origin': 'attribute-add',
        'med': 'attribute-add',
        'as-path': 'attribute-add',
        'local-preference': 'attribute-add',
        'atomic-aggregate': 'attribute-add',
        'aggregator': 'attribute-add',
        'originator-id': 'attribute-add',
        'cluster-list': 'attribute-add',
        'community': 'attribute-add',
        'large-community': 'attribute-add',
        'extended-community': 'attribute-add',
        'name': 'attribute-add',
        'split': 'attribute-add',
        'watchdog': 'attribute-add',
        'withdraw': 'attribute-add',
        'aigp': 'attribute-add',
    }

    assign = {}

    name = 'ip'

    def __init__(self, tokeniser, scope, error, logger):
        ParseAnnounce.__init__(self, tokeniser, scope, error, logger)

    def clear(self):
        return True

    def pre(self):
        return True

    def post(self):
        return ParseAnnounce.post() and self._check()

    @staticmethod
    def check(change, afi):
        if (
            change.nlri.action == OUT.ANNOUNCE
            and change.nlri.nexthop is NoNextHop
            and change.nlri.afi == afi
            and change.nlri.safi in (SAFI.unicast, SAFI.multicast)
        ):
            return False

        return True


def ip(tokeniser, afi, safi):
    action = OUT.ANNOUNCE if tokeniser.announce else OUT.WITHDRAW
    ipmask = prefix(tokeniser)

    nlri = INET(afi, safi, action)
    nlri.cidr = CIDR(ipmask.pack(), ipmask.mask)

    change = Change(nlri, Attributes())

    while True:
        command = tokeniser()

        if not command:
            break

        action = AnnounceIP.action.get(command, '')

        if action == 'attribute-add':
            change.attributes.add(AnnounceIP.known[command](tokeniser))
        elif action == 'nlri-set':
            change.nlri.assign(AnnounceIP.assign[command], AnnounceIP.known[command](tokeniser))
        elif action == 'nexthop-and-attribute':
            nexthop, attribute = AnnounceIP.known[command](tokeniser)
            change.nlri.nexthop = nexthop
            change.attributes.add(attribute)
        else:
            raise ValueError('unknown command "%s"' % command)

    if not AnnounceIP.check(change, afi):
        raise ValueError('invalid announcement (missing next-hop ?)')

    return [change]


def ip_multicast(tokeniser, afi, safi):
    action = OUT.ANNOUNCE if tokeniser.announce else OUT.WITHDRAW
    ipmask = prefix(tokeniser)

    nlri = INET(afi, safi, action)
    nlri.cidr = CIDR(ipmask.pack(), ipmask.mask)

    change = Change(nlri, Attributes())

    while True:
        command = tokeniser()

        if not command:
            break

        action = AnnounceIP.action.get(command, '')

        if action == 'attribute-add':
            change.attributes.add(AnnounceIP.known[command](tokeniser))
        elif action == 'nlri-set':
            change.nlri.assign(AnnounceIP.assign[command], AnnounceIP.known[command](tokeniser))
        elif action == 'nexthop-and-attribute':
            nexthop, attribute = AnnounceIP.known[command](tokeniser)
            change.nlri.nexthop = nexthop
            change.attributes.add(attribute)
        else:
            raise ValueError('unknown command "%s"' % command)

    return [change]


@ParseAnnounce.register('multicast', 'extend-name', 'ipv4')
def multicast_v4(tokeniser):
    return ip_multicast(tokeniser, AFI.ipv4, SAFI.multicast)


@ParseAnnounce.register('multicast', 'extend-name', 'ipv6')
def multicast_v6(tokeniser):
    return ip_multicast(tokeniser, AFI.ipv6, SAFI.multicast)
