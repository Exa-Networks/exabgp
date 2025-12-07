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
from exabgp.bgp.message.update.nlri.settings import INETSettings
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
    """Parse static route using deferred NLRI construction (Settings pattern).

    Collects all values during parsing, then creates immutable NLRI at the end.
    """
    nlri_action = Action.ANNOUNCE if tokeniser.announce else Action.WITHDRAW
    ipmask = prefix(tokeniser)

    # Create settings and populate initial values
    settings = INETSettings()
    settings.cidr = CIDR.make_cidr(ipmask.pack_ip(), ipmask.mask)
    settings.afi = IP.toafi(ipmask.top())
    settings.action = nlri_action
    attributes = AttributeCollection()

    # Determine NLRI class from tokens (look-ahead)
    has_rd = 'rd' in tokeniser.tokens or 'route-distinguisher' in tokeniser.tokens
    has_label = 'label' in tokeniser.tokens

    nlri_class: type[INET]
    check: Callable[[Route, AFI], bool]
    if has_rd:
        nlri_class = IPVPN
        settings.safi = SAFI.mpls_vpn
        check = AnnounceVPN.check
    elif has_label:
        nlri_class = Label
        settings.safi = SAFI.nlri_mpls
        check = AnnounceLabel.check
    else:
        nlri_class = INET
        settings.safi = IP.tosafi(ipmask.top())
        check = AnnouncePath.check

    # Parse all tokens - collect into settings
    while True:
        command = tokeniser()

        if not command:
            break

        if command == 'label':
            settings.labels = label(tokeniser)
            continue

        if command == 'rd' or command == 'route-distinguisher':
            settings.rd = route_distinguisher(tokeniser)
            continue

        if command == 'path-information':
            settings.path_info = path_information(tokeniser)
            continue

        cmd_action = ParseStatic.action.get(command, '')

        if cmd_action == 'attribute-add':
            attributes.add(ParseStatic.known[command](tokeniser))
        elif cmd_action == 'nlri-set':
            settings.set(ParseStatic.assign[command], ParseStatic.known[command](tokeniser))
        elif cmd_action == 'nexthop-and-attribute':
            nexthop, attribute = ParseStatic.known[command](tokeniser)
            settings.nexthop = nexthop
            attributes.add(attribute)
        else:
            raise ValueError('unknown command "{}"'.format(command))

    # Create immutable NLRI from validated settings
    nlri = nlri_class.from_settings(settings)
    static_route = Route(nlri, attributes)

    if not check(static_route, nlri.afi):
        raise ValueError('invalid route (missing next-hop, label or rd ?)')

    return list(ParseStatic.split(static_route))


@ParseStatic.register('attributes', 'append-route')
def attributes(tokeniser: Any) -> list[Route]:
    """Parse attributes with multiple NLRIs using deferred construction (Settings pattern).

    Collects shared settings first, then creates immutable NLRIs for each prefix.
    """
    from copy import copy

    nlri_action = Action.ANNOUNCE if tokeniser.announce else Action.WITHDRAW
    ipmask = prefix(lambda: tokeniser.tokens[-1])
    tokeniser.afi = ipmask.afi

    # Create template settings with initial values
    template_settings = INETSettings()
    template_settings.afi = IP.toafi(ipmask.top())
    template_settings.action = nlri_action
    attr = AttributeCollection()

    # Determine NLRI class from tokens (look-ahead)
    has_rd = 'rd' in tokeniser.tokens or 'route-distinguisher' in tokeniser.tokens
    has_label = 'label' in tokeniser.tokens

    nlri_class: type[INET]
    if has_rd:
        nlri_class = IPVPN
        template_settings.safi = SAFI.mpls_vpn
    elif has_label:
        nlri_class = Label
        template_settings.safi = SAFI.nlri_mpls
    else:
        nlri_class = INET
        template_settings.safi = IP.tosafi(ipmask.top())

    # Parse shared attributes - collect into template settings
    while True:
        command = tokeniser()

        if not command:
            return []

        if command == 'nlri':
            break

        if command == 'label':
            template_settings.labels = label(tokeniser)
            continue

        if command == 'path-information':
            template_settings.path_info = path_information(tokeniser)
            continue

        if command == 'rd' or command == 'route-distinguisher':
            template_settings.rd = route_distinguisher(tokeniser)
            continue

        cmd_action = ParseStatic.action.get(command, '')
        if cmd_action == '':
            raise ValueError(f"The command '{command}' is not known or valid where used")

        if cmd_action == 'attribute-add':
            attr.add(ParseStatic.known[command](tokeniser))
        elif cmd_action == 'nlri-set':
            template_settings.set(ParseStatic.assign[command], ParseStatic.known[command](tokeniser))
        elif cmd_action == 'nexthop-and-attribute':
            nexthop, attribute = ParseStatic.known[command](tokeniser)
            template_settings.nexthop = nexthop
            attr.add(attribute)
        else:
            raise ValueError('unknown command "{}"'.format(command))

    # Create routes for each NLRI prefix using template settings
    routes = []

    while True:
        peeked_nlri = tokeniser.peek()
        if not peeked_nlri:
            break

        ipmask = prefix(tokeniser)
        # Copy template settings and update with new CIDR
        settings = copy(template_settings)
        settings.cidr = CIDR.make_cidr(ipmask.pack_ip(), ipmask.mask)
        settings.action = Action.UNSET

        # Create immutable NLRI from settings
        new_nlri = nlri_class.from_settings(settings)
        routes.append(Route(new_nlri, attr))

    return routes
