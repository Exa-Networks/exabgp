# encoding: utf-8
"""
inet/__init__.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.configuration.static.route import ParseStaticRoute
from exabgp.configuration.static.parser import prefix

from exabgp.configuration.announce.path import AnnouncePath
from exabgp.configuration.announce.label import AnnounceLabel
from exabgp.configuration.announce.vpn import AnnounceVPN

from exabgp.protocol.ip import IP
from exabgp.protocol.family import SAFI

from exabgp.bgp.message import OUT
from exabgp.bgp.message.update.nlri import CIDR
from exabgp.bgp.message.update.nlri import INET
from exabgp.bgp.message.update.nlri import Label
from exabgp.bgp.message.update.nlri import IPVPN

from exabgp.bgp.message.update.attribute import Attributes

from exabgp.rib.change import Change

from exabgp.configuration.static.mpls import label
from exabgp.configuration.static.mpls import route_distinguisher


class ParseStatic(ParseStaticRoute):
    syntax = 'route <ip>/<netmask> %s;' % ' '.join(ParseStaticRoute.definition)

    action = dict(ParseStaticRoute.action)

    name = 'static'

    def __init__(self, tokeniser, scope, error, logger):
        ParseStaticRoute.__init__(self, tokeniser, scope, error, logger)

    def clear(self):
        return True

    def pre(self):
        return True

    def post(self):
        return True


@ParseStatic.register('route', 'append-route')
def route(tokeniser):
    action = OUT.ANNOUNCE if tokeniser.announce else OUT.WITHDRAW
    ipmask = prefix(tokeniser)
    check = lambda change, afi: True

    if 'rd' in tokeniser.tokens or 'route-distinguisher' in tokeniser.tokens:
        nlri = IPVPN(IP.toafi(ipmask.top()), SAFI.mpls_vpn, action)
        check = AnnounceVPN.check
    elif 'label' in tokeniser.tokens:
        nlri = Label(IP.toafi(ipmask.top()), SAFI.nlri_mpls, action)
        check = AnnounceLabel.check
    else:
        nlri = INET(IP.toafi(ipmask.top()), IP.tosafi(ipmask.top()), action)
        check = AnnouncePath.check

    nlri.cidr = CIDR(ipmask.pack(), ipmask.mask)

    change = Change(nlri, Attributes())

    while True:
        command = tokeniser()

        if not command:
            break

        if command == 'label':
            nlri.labels = label(tokeniser)
            continue

        if command == 'rd' or command == 'route-distinguisher':
            nlri.rd = route_distinguisher(tokeniser)
            continue

        action = ParseStatic.action.get(command, '')

        if action == 'attribute-add':
            change.attributes.add(ParseStatic.known[command](tokeniser))
        elif action == 'nlri-set':
            change.nlri.assign(ParseStatic.assign[command], ParseStatic.known[command](tokeniser))
        elif action == 'nexthop-and-attribute':
            nexthop, attribute = ParseStatic.known[command](tokeniser)
            change.nlri.nexthop = nexthop
            change.attributes.add(attribute)
        else:
            raise ValueError('unknown command "%s"' % command)

    if not check(change, nlri.afi):
        raise ValueError('invalid route (missing next-hop, label or rd ?)')

    return list(ParseStatic.split(change))


@ParseStatic.register('attributes', 'append-route')
def attributes(tokeniser):
    action = OUT.ANNOUNCE if tokeniser.announce else OUT.WITHDRAW
    ipmask = prefix(lambda: tokeniser.tokens[-1])
    tokeniser.afi = ipmask.afi

    if 'rd' in tokeniser.tokens or 'route-distinguisher' in tokeniser.tokens:
        nlri = IPVPN(IP.toafi(ipmask.top()), SAFI.mpls_vpn, action)
    elif 'label' in tokeniser.tokens:
        nlri = Label(IP.toafi(ipmask.top()), SAFI.nlri_mpls, action)
    else:
        nlri = INET(IP.toafi(ipmask.top()), IP.tosafi(ipmask.top()), action)

    nlri.cidr = CIDR(ipmask.pack(), ipmask.mask)
    attr = Attributes()

    labels = None
    rd = None

    while True:
        command = tokeniser()

        if not command:
            return []

        if command == 'nlri':
            break

        if command == 'label':
            labels = label(tokeniser)
            continue

        if command == 'rd' or command == 'route-distinguisher':
            rd = route_distinguisher(tokeniser)
            continue

        action = ParseStatic.action[command]

        if action == 'attribute-add':
            attr.add(ParseStatic.known[command](tokeniser))
        elif action == 'nlri-set':
            nlri.assign(ParseStatic.assign[command], ParseStatic.known[command](tokeniser))
        elif action == 'nexthop-and-attribute':
            nexthop, attribute = ParseStatic.known[command](tokeniser)
            nlri.nexthop = nexthop
            attr.add(attribute)
        else:
            raise ValueError('unknown command "%s"' % command)

    changes = []
    while True:
        peeked_nlri = tokeniser.peek()
        if not peeked_nlri:
            break

        ipmask = prefix(tokeniser)
        new = Change(nlri.__class__(nlri.afi, nlri.safi, OUT.UNSET), attr)
        new.nlri.cidr = CIDR(ipmask.pack(), ipmask.mask)
        if labels:
            new.nlri.labels = labels
        if rd:
            new.nlri.rd = rd
        new.nlri.nexthop = nlri.nexthop
        changes.append(new)

    return changes
