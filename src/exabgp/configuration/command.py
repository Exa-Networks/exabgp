"""command.py

The API commands which send what a BGP UPDATE carries: `exabgp decode --command`.

The UPDATE is decoded into its routes, and each route is printed by the statement of the API
section which reads it back, with the grammar's own printer: what is printed is what the API
reads. It used to go through the JSON of the UPDATE, turned into text by hand, and wrote
commands the API refuses (`extended-community [rate-limit:0]`).

The attributes every UPDATE is sent with when a route gives none (origin igp, the AS_PATH of
an originated route, LOCAL_PREF 100 inside the AS) are left out: the command sends them anyway.

Created by Thomas Mangin on 2024-12-10.
Copyright (c) 2024 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from exabgp.bgp.neighbor import Neighbor

from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute import AttributeCollection
from exabgp.bgp.message.update.nlri import RTC, VPLS, Flow
from exabgp.bgp.message.update.nlri.sr_policy import SRPolicyNLRI
from exabgp.configuration.check import _hexa, _make_update, _negotiated
from exabgp.configuration.grammar.nodes import Block
from exabgp.configuration.grammar.render import one_line, quote
from exabgp.configuration.grammar.tree.announce import IPV4, IPV6, L2VPN, STATIC, announce_family
from exabgp.configuration.grammar.tree.flow import ROUTE_BLOCK, block_printable
from exabgp.configuration.grammar.tree.static import attribute_words, route_words
from exabgp.protocol.family import SAFI
from exabgp.protocol.ip import IP
from exabgp.rib.route import Route

# the API section an address family names: `announce ipv4 <safi> ...`
FAMILY_SECTIONS: dict[str, Block] = {'ipv4': IPV4, 'ipv6': IPV6}


def _place(route: Route) -> tuple[str, Block, str]:
    """Where the API reads a route: the family it names, its section and the statement.

    The choice is the one the configuration printer makes (grammar/tree/unresolve.routes).
    """
    nlri: Any = route.nlri
    afi = nlri.afi.name()
    if isinstance(nlri, Flow):
        return afi, FAMILY_SECTIONS[afi], 'flow-vpn' if nlri.safi == SAFI.flow_vpn else 'flow'
    if nlri.safi in (SAFI.mup, SAFI.mcast_vpn):
        return afi, FAMILY_SECTIONS[afi], nlri.safi.name()
    if isinstance(nlri, VPLS):
        return '', L2VPN, 'vpls'
    if isinstance(nlri, RTC):
        return afi, FAMILY_SECTIONS[afi], 'rtc'
    if isinstance(nlri, SRPolicyNLRI):
        return afi, FAMILY_SECTIONS[afi], 'sr-policy'
    family = announce_family(route)
    if family is not None:
        return family[0], FAMILY_SECTIONS[family[0]], family[1]
    return '', STATIC, 'route'


def _command(action: str, route: Route) -> str:
    """`<action> [<afi>] <statement> <words>`, the API command for one route."""
    if isinstance(route.nlri, Flow) and route.nexthop is not IP.NoNextHop and block_printable(route):
        # the flow line of an address family has no next-hop, the route block of `flow` has
        return f'{action} flow {one_line(ROUTE_BLOCK, route)}'
    family, section, keyword = _place(route)
    leaf = section.leaf(keyword)
    assert leaf is not None, f'the {section.keyword} section has no {keyword} statement'
    words = [quote(word) for word in leaf.type.render([route])]
    return ' '.join([action, *([family] if family else []), keyword, *words])


def _sent_anyway(attributes: AttributeCollection, negotiated: Negotiated) -> AttributeCollection:
    """The attributes less those a route is sent with when it gives none of its own."""
    defaults = AttributeCollection._default_attributes(negotiated)
    kept = AttributeCollection()
    for code, attribute in attributes.items():
        default = defaults[code]() if code in defaults else None
        if getattr(default, 'ID', None) == code and str(default) == str(attribute):
            continue
        kept.add(attribute)
    return kept


def _shared(routes: list[Route]) -> str | None:
    """`announce attributes <values> nlri <prefix> ...`: routes which differ by their prefix only."""
    first = routes[0]
    prefixes: list[str] = []
    for route in routes:
        if _place(route)[2] != 'route' or route.nexthop != first.nexthop:
            return None
        words = route_words(route)
        if len(words) != 1 + len(attribute_words(route)):
            return None  # an rd, a label or a path-information: not said by `nlri`
        prefixes.append(str(words[0]))
    values = [quote(word) for word in attribute_words(first)]
    return ' '.join(['announce', 'attributes', *values, 'nlri', *prefixes])


def decode_to_api_command(payload_hex: str, neighbor: 'Neighbor') -> list[str]:
    """The API commands which send the UPDATE in `payload_hex` (the message after its header).

    One command for one route, or for routes which differ by their prefix only; a `group` of
    commands otherwise, which the API sends as one UPDATE where the reactor packs several
    routes in one, announcements of ipv4 unicast and mcast-vpn (rib/outgoing._select_updates),
    and as several UPDATEs of the same routes otherwise; `announce eor <afi> <safi>` for
    an End-of-RIB marker. An empty list for a message
    which is no UPDATE, or an UPDATE with no route. A route no statement prints raises
    Unprintable (a ValueError), as a payload which is not hexadecimal raises ValueError.
    """
    update = _make_update(neighbor, _hexa(payload_hex))
    if not update:
        return []
    if update.IS_EOR:
        marker: Any = update.nlris[0]
        return [f'announce eor {marker.afi} {marker.safi}']
    _, negotiated = _negotiated(neighbor)
    attributes = _sent_anyway(update.attributes, negotiated)
    announced = [Route(routed.nlri, attributes, routed.nexthop) for routed in update.announces]
    withdrawn = [Route(nlri, attributes, IP.NoNextHop) for nlri in update.withdraws]

    if len(announced) > 1 and not withdrawn:
        shared = _shared(announced)
        if shared is not None:
            return [shared]
    commands = [_command('announce', route) for route in announced]
    commands.extend(_command('withdraw', route) for route in withdrawn)
    if len(commands) > 1:
        return ['group ' + ' ; '.join(commands)]
    return commands
