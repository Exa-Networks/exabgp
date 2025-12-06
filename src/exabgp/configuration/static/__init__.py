"""inet/__init__.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any, Callable

from exabgp.bgp.message import Action
from exabgp.bgp.message.update.attribute import AttributeCollection
from exabgp.bgp.message.update.nlri import CIDR, INET, IPVPN, Label
from exabgp.configuration.announce.label import AnnounceLabel
from exabgp.configuration.announce.path import AnnouncePath
from exabgp.configuration.announce.vpn import AnnounceVPN
from exabgp.configuration.schema import Container
from exabgp.configuration.static.mpls import label, route_distinguisher
from exabgp.configuration.static.parser import path_information, prefix
from exabgp.configuration.static.route import ParseStaticRoute as ParseStaticRoute  # Re-export
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP
from exabgp.rib.route import Route


def _check_true(route: Route, afi: AFI) -> bool:
    return True


class ParseStatic(ParseStaticRoute):
    syntax: str = 'route <ip>/<netmask> {};'.format(' '.join(ParseStaticRoute.definition))

    # Schema: inherit parent schema children and add route subsection
    schema = Container(
        description='Static route configuration',
        children={
            **ParseStaticRoute.schema.children,
            'route': Container(description='Static route definition'),
        },
    )

    action: dict[str | tuple[Any, ...], str] = dict(ParseStaticRoute.action)

    name: str = 'static'

    def __init__(self, parser: Any, scope: Any, error: Any) -> None:
        ParseStaticRoute.__init__(self, parser, scope, error)

    def clear(self) -> None:
        pass

    def pre(self) -> bool:
        return True

    def post(self) -> bool:
        return ParseStaticRoute.post(self)


@ParseStatic.register('route', 'append-route')
def route(tokeniser: Any) -> list[Route]:
    nlri_action = Action.ANNOUNCE if tokeniser.announce else Action.WITHDRAW
    ipmask = prefix(tokeniser)
    check: Callable[[Route, AFI], bool] = _check_true

    # Create CIDR first (packed-bytes-first pattern)
    cidr = CIDR.make_cidr(ipmask.pack_ip(), ipmask.mask)

    nlri: INET
    if 'rd' in tokeniser.tokens or 'route-distinguisher' in tokeniser.tokens:
        nlri = IPVPN.from_cidr(cidr, IP.toafi(ipmask.top()), SAFI.mpls_vpn, nlri_action)
        check = AnnounceVPN.check
    elif 'label' in tokeniser.tokens:
        nlri = Label.from_cidr(cidr, IP.toafi(ipmask.top()), SAFI.nlri_mpls, nlri_action)
        check = AnnounceLabel.check
    else:
        nlri = INET.from_cidr(cidr, IP.toafi(ipmask.top()), IP.tosafi(ipmask.top()), nlri_action)
        check = AnnouncePath.check

    static_route = Route(nlri, AttributeCollection())

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

        if command == 'path-information':
            nlri.path_info = path_information(tokeniser)
            continue

        cmd_action = ParseStatic.action.get(command, '')

        if cmd_action == 'attribute-add':
            static_route.attributes.add(ParseStatic.known[command](tokeniser))
        elif cmd_action == 'nlri-set':
            static_route.nlri.assign(ParseStatic.assign[command], ParseStatic.known[command](tokeniser))
        elif cmd_action == 'nexthop-and-attribute':
            nexthop, attribute = ParseStatic.known[command](tokeniser)
            static_route.nlri.nexthop = nexthop
            static_route.attributes.add(attribute)
        else:
            raise ValueError('unknown command "{}"'.format(command))

    if not check(static_route, nlri.afi):
        raise ValueError('invalid route (missing next-hop, label or rd ?)')

    return list(ParseStatic.split(static_route))


@ParseStatic.register('attributes', 'append-route')
def attributes(tokeniser: Any) -> list[Route]:
    nlri_action = Action.ANNOUNCE if tokeniser.announce else Action.WITHDRAW
    ipmask = prefix(lambda: tokeniser.tokens[-1])  # type: ignore[arg-type]
    tokeniser.afi = ipmask.afi

    # Create CIDR first (packed-bytes-first pattern)
    cidr = CIDR.make_cidr(ipmask.pack_ip(), ipmask.mask)

    nlri: INET
    if 'rd' in tokeniser.tokens or 'route-distinguisher' in tokeniser.tokens:
        nlri = IPVPN.from_cidr(cidr, IP.toafi(ipmask.top()), SAFI.mpls_vpn, nlri_action)
    elif 'label' in tokeniser.tokens:
        nlri = Label.from_cidr(cidr, IP.toafi(ipmask.top()), SAFI.nlri_mpls, nlri_action)
    else:
        nlri = INET.from_cidr(cidr, IP.toafi(ipmask.top()), IP.tosafi(ipmask.top()), nlri_action)
    attr = AttributeCollection()

    labels: Any = None
    rd: Any = None
    path_info: Any = None

    while True:
        command = tokeniser()

        if not command:
            return []

        if command == 'nlri':
            break

        if command == 'label':
            labels = label(tokeniser)
            continue

        if command == 'path-information':
            path_info = path_information(tokeniser)
            continue

        if command == 'rd' or command == 'route-distinguisher':
            rd = route_distinguisher(tokeniser)
            continue

        cmd_action = ParseStatic.action.get(command, '')
        if cmd_action == '':
            raise ValueError(f"The command '{command}' is not known or valid where used")

        if cmd_action == 'attribute-add':
            attr.add(ParseStatic.known[command](tokeniser))
        elif cmd_action == 'nlri-set':
            nlri.assign(ParseStatic.assign[command], ParseStatic.known[command](tokeniser))
        elif cmd_action == 'nexthop-and-attribute':
            nexthop, attribute = ParseStatic.known[command](tokeniser)
            nlri.nexthop = nexthop
            attr.add(attribute)
        else:
            raise ValueError('unknown command "{}"'.format(command))

    routes = []

    while True:
        peeked_nlri = tokeniser.peek()
        if not peeked_nlri:
            break

        ipmask = prefix(tokeniser)
        # Create new NLRI of same type (nlri is typed as INET, all subclasses share same interface)
        new_cidr = CIDR.make_cidr(ipmask.pack_ip(), ipmask.mask)
        new_nlri: INET = nlri.__class__.from_cidr(new_cidr, nlri.afi, nlri.safi, Action.UNSET)
        if labels:
            new_nlri.labels = labels
        if rd:
            new_nlri.rd = rd
        if path_info:
            new_nlri.path_info = path_info
        new_nlri.nexthop = nlri.nexthop
        routes.append(Route(new_nlri, attr))

    return routes
