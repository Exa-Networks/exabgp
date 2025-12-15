"""inet/__init__.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any

from exabgp.bgp.message import Action
from exabgp.bgp.message.update.attribute import AttributeCollection
from exabgp.bgp.message.update.nlri import CIDR, INET, IPVPN, Label
from exabgp.bgp.message.update.nlri.settings import INETSettings
from exabgp.configuration.schema import Container, ActionTarget, ActionOperation
from exabgp.configuration.static.mpls import label, route_distinguisher
from exabgp.configuration.static.parser import path_information, prefix
from exabgp.configuration.static.route import ParseStaticRoute as ParseStaticRoute  # Re-export
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP
from exabgp.rib.route import Route


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


@ParseStatic.register_command('route', ActionTarget.ROUTE, ActionOperation.EXTEND)
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
    if has_rd:
        nlri_class = IPVPN
        settings.safi = SAFI.mpls_vpn
    elif has_label:
        nlri_class = Label
        settings.safi = SAFI.nlri_mpls
    else:
        nlri_class = INET
        settings.safi = IP.tosafi(ipmask.top())

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

        # Get action from schema
        action_enums = ParseStatic._action_enums_from_schema(command)
        if action_enums is None:
            raise ValueError('unknown command "{}"'.format(command))

        target, operation, key, field_name = action_enums

        if target == ActionTarget.ATTRIBUTE:
            attributes.add(ParseStatic.known[command](tokeniser))
        elif target == ActionTarget.NLRI:
            settings.set(ParseStatic.assign[command], ParseStatic.known[command](tokeniser))
        elif target == ActionTarget.NEXTHOP_ATTRIBUTE:
            nexthop, attribute = ParseStatic.known[command](tokeniser)
            settings.nexthop = nexthop
            attributes.add(attribute)
        else:
            raise ValueError('unknown command "{}"'.format(command))

    # Create immutable NLRI from settings
    # Note: Validation (nexthop, labels, RD) happens at wire format generation time
    nlri = nlri_class.from_settings(settings)
    static_route = Route(nlri, attributes, nexthop=settings.nexthop)

    return list(ParseStatic.split(static_route))


@ParseStatic.register_command('attributes', ActionTarget.ROUTE, ActionOperation.EXTEND)
def attributes(tokeniser: Any) -> list[Route]:
    """Parse attributes with optional NLRIs using deferred construction (Settings pattern).

    Collects shared settings first, then creates immutable NLRIs for each prefix.
    If no 'nlri' keyword or no prefixes, returns an attributes-only Route
    that generates an UPDATE with just path attributes and no NLRI.
    """
    from copy import copy

    from exabgp.bgp.message.update.nlri.empty import Empty

    nlri_action = Action.ANNOUNCE if tokeniser.announce else Action.WITHDRAW

    # Check if there are any IP prefixes in the tokens (look-ahead for nlri keyword)
    has_nlri_keyword = 'nlri' in tokeniser.tokens

    # Try to parse the last token as a prefix to determine AFI
    # If it fails, this is an attributes-only command
    has_prefix = False
    ipmask = None
    if has_nlri_keyword:
        try:
            ipmask = prefix(lambda: tokeniser.tokens[-1])
            has_prefix = True
        except (ValueError, KeyError):
            pass

    if has_prefix and ipmask is not None:
        tokeniser.afi = ipmask.afi
    else:
        tokeniser.afi = AFI.ipv4  # Default for attributes-only

    # Create template settings with initial values
    template_settings = INETSettings()
    if has_prefix and ipmask is not None:
        template_settings.afi = IP.toafi(ipmask.top())
    else:
        template_settings.afi = AFI.ipv4
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
    elif has_prefix and ipmask is not None:
        nlri_class = INET
        template_settings.safi = IP.tosafi(ipmask.top())
    else:
        nlri_class = INET
        template_settings.safi = SAFI.unicast

    # Parse shared attributes - collect into template settings
    while True:
        command = tokeniser()

        if not command:
            # No more tokens - check if we have NLRIs or just attributes
            if not has_nlri_keyword:
                # Attributes-only: return Route with Empty NLRI
                if attr:
                    empty_nlri = Empty(AFI.ipv4, SAFI.unicast)
                    return [Route(empty_nlri, attr)]
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

        # Get action from schema
        action_enums = ParseStatic._action_enums_from_schema(command)
        if action_enums is None:
            raise ValueError(f"The command '{command}' is not known or valid where used")

        target, operation, key, field_name = action_enums

        if target == ActionTarget.ATTRIBUTE:
            attr.add(ParseStatic.known[command](tokeniser))
        elif target == ActionTarget.NLRI:
            template_settings.set(ParseStatic.assign[command], ParseStatic.known[command](tokeniser))
        elif target == ActionTarget.NEXTHOP_ATTRIBUTE:
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
        routes.append(Route(new_nlri, attr, nexthop=settings.nexthop))

    # If 'nlri' keyword was present but no prefixes followed, return attributes-only
    if not routes and attr:
        empty_nlri = Empty(AFI.ipv4, SAFI.unicast)
        return [Route(empty_nlri, attr)]

    return routes
