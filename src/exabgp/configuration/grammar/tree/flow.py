"""flow.py

    flow {
        route [<name>] {
            rd <rd>; path-information <id>; next-hop <ip>;
            match { source <prefix>; destination-port >1024; ... }
            then { discard; rate-limit <n>; redirect <target>; community ...; ... }
            scope { interface-set <set>; }
        }
        route <match and action> ...;
    }
    announce { ipv4|ipv6 { flow <match and action> ...; flow-vpn ...; } }

What a flow route matches and does is declared once, in FLOW_VALUES, and read the same in
the block, the one-line route and the announce families, with the target each gives it.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence
from typing import Any, cast

from exabgp.bgp.message.update.attribute import AttributeCollection
from exabgp.bgp.message.update.nlri import Flow
from exabgp.bgp.message.update.nlri.flow import (
    FlowAnyPort,
    FlowDestinationPort,
    FlowDSCP,
    FlowFlowLabel,
    FlowFragment,
    FlowICMPCode,
    FlowICMPType,
    FlowIPProtocol,
    FlowNextHeader,
    FlowPacketLength,
    FlowSourcePort,
    FlowTCPFlag,
    FlowTrafficClass,
)
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.nlri.settings import FlowSettings
from exabgp.configuration.grammar import shape
from exabgp.configuration.grammar.context import PrintContext, ReadContext
from exabgp.configuration.grammar.error import ConfigError
from exabgp.configuration.grammar.nodes import Block, Keep, Leaf
from exabgp.configuration.grammar.section import Collector, Pending, Values
from exabgp.configuration.grammar.shape import Shape
from exabgp.configuration.grammar.tree.static import (
    ROUTE_VALUES,
    ROUTES,
    action,
    add_attribute,
    community_word,
    read_back,
    text_words,
    value_fields,
)
from exabgp.configuration.grammar.types import flow as types
from exabgp.configuration.grammar.types.base import Printed, Type, WordOrSyntax
from exabgp.configuration.grammar.types.route import RouteStatement, Target
from exabgp.configuration.grammar.words import Words
from exabgp.logger import lazymsg, log
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP
from exabgp.rib.route import Route


@dataclass(frozen=True)
class FlowValue:
    type: Type[Any]
    target: Target
    field: str = ''
    doc: str = ''
    adds: bool = False  # given again, adds to the first: a rule or an attribute made of a list


MATCH: dict[str, FlowValue] = {
    'source': FlowValue(types.SOURCE, Target.RULE, doc='the source prefix, RFC 8955 type 2'),
    'source-ipv4': FlowValue(types.SOURCE, Target.RULE, doc='the source prefix, as source'),
    'source-ipv6': FlowValue(types.SOURCE, Target.RULE, doc='the source prefix, as source'),
    'destination': FlowValue(types.DESTINATION, Target.RULE, doc='the destination prefix, RFC 8955 type 1'),
    'destination-ipv4': FlowValue(types.DESTINATION, Target.RULE, doc='the destination prefix, as destination'),
    'destination-ipv6': FlowValue(types.DESTINATION, Target.RULE, doc='the destination prefix, as destination'),
    'protocol': FlowValue(
        types.condition('protocol', FlowIPProtocol, ['tcp', '[ udp tcp ]', '=6']),
        Target.RULE,
        adds=True,
        doc='the IP protocol, RFC 8955 type 3',
    ),
    'next-header': FlowValue(
        types.condition('next-header', FlowNextHeader, ['tcp']),
        Target.RULE,
        adds=True,
        doc='the IPv6 next header, RFC 8956 type 3',
    ),
    'port': FlowValue(
        types.condition('port', FlowAnyPort, ['25', '[ =80 >8080&<8088 ]']),
        Target.RULE,
        adds=True,
        doc='the source or destination port, RFC 8955 type 4',
    ),
    'destination-port': FlowValue(
        types.condition('destination-port', FlowDestinationPort, ['=80']),
        Target.RULE,
        adds=True,
        doc='the destination port, RFC 8955 type 5',
    ),
    'source-port': FlowValue(
        types.condition('source-port', FlowSourcePort, ['>1024']),
        Target.RULE,
        adds=True,
        doc='the source port, RFC 8955 type 6',
    ),
    'icmp-type': FlowValue(
        types.condition('icmp-type', FlowICMPType, ['8']), Target.RULE, adds=True, doc='the ICMP type, RFC 8955 type 7'
    ),
    'icmp-code': FlowValue(
        types.condition('icmp-code', FlowICMPCode, ['0']), Target.RULE, adds=True, doc='the ICMP code, RFC 8955 type 8'
    ),
    'tcp-flags': FlowValue(
        types.condition('tcp-flags', FlowTCPFlag, ['syn', '[ syn ack ]']),
        Target.RULE,
        adds=True,
        doc='the TCP flags, RFC 8955 type 9',
    ),
    'packet-length': FlowValue(
        types.condition('packet-length', FlowPacketLength, ['>200&<300']),
        Target.RULE,
        adds=True,
        doc='the packet length, RFC 8955 type 10',
    ),
    'dscp': FlowValue(
        types.condition('dscp', FlowDSCP, ['10']), Target.RULE, adds=True, doc='the DSCP, RFC 8955 type 11'
    ),
    'traffic-class': FlowValue(
        types.condition('traffic-class', FlowTrafficClass, ['10']),
        Target.RULE,
        adds=True,
        doc='the IPv6 traffic class, RFC 8956 type 11',
    ),
    'fragment': FlowValue(
        types.condition('fragment', FlowFragment, ['is-fragment']),
        Target.RULE,
        adds=True,
        doc='the fragment flags, RFC 8955 type 12',
    ),
    'flow-label': FlowValue(
        types.condition('flow-label', FlowFlowLabel, ['>100&<2000']),
        Target.RULE,
        adds=True,
        doc='the IPv6 flow label, RFC 8956 type 13',
    ),
}

THEN: dict[str, FlowValue] = {
    'accept': FlowValue(types.ACCEPT, Target.NOTHING, doc='no action: the traffic is accepted'),
    'discard': FlowValue(types.DISCARD, Target.ATTRIBUTE, doc='drop the traffic, a traffic-rate of 0'),
    'rate-limit': FlowValue(
        types.RATE_LIMIT, Target.ATTRIBUTE, adds=True, doc='traffic-rate, RFC 8955 7.3: bytes or packets per second'
    ),
    'redirect': FlowValue(
        types.REDIRECT,
        Target.NEXTHOP_ATTRIBUTE,
        adds=True,
        doc='redirect to the VRF of a route target, or to an address',
    ),
    'redirect-to-nexthop': FlowValue(
        types.REDIRECT_TO_NEXTHOP,
        Target.ATTRIBUTE,
        adds=True,
        doc='redirect to the next-hop of the route, or to the address given',
    ),
    'redirect-to-nexthop-ietf': FlowValue(
        types.REDIRECT_TO_NEXTHOP_IETF, Target.ATTRIBUTE, doc='redirect to an address, the IETF community'
    ),
    'redirect-to-nexthop-simpson': FlowValue(
        types.REDIRECT_TO_NEXTHOP_SIMPSON,
        Target.ATTRIBUTE,
        doc='redirect to the next-hop of the UPDATE, the older form',
    ),
    'copy': FlowValue(types.COPY, Target.NEXTHOP_ATTRIBUTE, doc='copy the traffic to an address, the IETF community'),
    'copy-simpson': FlowValue(
        types.COPY_SIMPSON, Target.NEXTHOP_ATTRIBUTE, doc='copy the traffic to an address, the older form'
    ),
    'redirect-simpson': FlowValue(
        types.REDIRECT_SIMPSON, Target.NEXTHOP_ATTRIBUTE, doc='redirect to an address, the older form'
    ),
    'mark': FlowValue(types.MARK, Target.ATTRIBUTE, adds=True, doc='traffic-marking, RFC 8955 7.5: the DSCP to set'),
    'action': FlowValue(
        types.ACTION,
        Target.ATTRIBUTE,
        adds=True,
        doc='traffic-action, RFC 8955 7.6: sample the traffic, stop at this rule, or both',
    ),
    'community': FlowValue(ROUTE_VALUES['community'].type, Target.ATTRIBUTE, adds=True),
    'large-community': FlowValue(ROUTE_VALUES['large-community'].type, Target.ATTRIBUTE, adds=True),
    'extended-community': FlowValue(ROUTE_VALUES['extended-community'].type, Target.ATTRIBUTE, adds=True),
}

SCOPE: dict[str, FlowValue] = {
    'interface-set': FlowValue(
        types.INTERFACE_SET,
        Target.ATTRIBUTE,
        doc='the interfaces the rule applies to, draft-ietf-idr-flowspec-interfaceset',
    )
}

ROUTE: dict[str, FlowValue] = {
    'rd': FlowValue(ROUTE_VALUES['rd'].type, Target.NLRI, 'rd'),
    'route-distinguisher': FlowValue(ROUTE_VALUES['rd'].type, Target.NLRI, 'rd'),
    'path-information': FlowValue(ROUTE_VALUES['path-information'].type, Target.NLRI, 'addpath'),
    'next-hop': FlowValue(types.FLOW_NEXTHOP, Target.NEXTHOP, doc='the next-hop of the flow route, or self'),
}

# a one-line route reads no next-hop; its `route-distinguisher` is the rd, as in a route block
# (it set a field of that name, which no flow route has, and the route was refused)
LINE = {
    **MATCH,
    **THEN,
    **SCOPE,
    **ROUTE,
}
del LINE['next-hop']


class FlowRoute:
    """A flow route being built: the legacy parser changed the NLRI in place, so this does too."""

    def __init__(self) -> None:
        self.nlri = Flow.make_flow()
        self.attributes = AttributeCollection()
        self.nexthop: IP = IP.NoNextHop

    def apply(self, spec: FlowValue, value: Any, line: bool) -> None:
        if spec.target == Target.RULE:
            for rule in value:
                if not self.nlri.add(rule):
                    raise ValueError(self.nlri.rule_conflict(rule))
        elif spec.target == Target.NLRI:
            setattr(self.nlri, spec.field, value)
        elif spec.target == Target.NEXTHOP:
            if value:
                self.nexthop = value
        elif spec.target == Target.NEXTHOP_ATTRIBUTE:
            ip, attribute = value
            # legacy: a one-line route takes the address even when there is none
            if ip or line:
                self.nexthop = ip
            add_attribute(self.attributes, attribute)
        elif spec.target == Target.ATTRIBUTE:
            add_attribute(self.attributes, value)

    def route(self) -> Route:
        nlri = self.nlri
        if nlri.rd is not RouteDistinguisher.NORD and nlri.safi != SAFI.flow_vpn:
            vpn = Flow.make_flow(nlri.afi, SAFI.flow_vpn)
            vpn._rd_override = nlri._rd_override
            vpn._rules_cache = nlri._rules_cache
            vpn._packed_stale = True
            vpn.addpath = nlri.addpath
            nlri = vpn
        return Route(nlri, self.attributes, nexthop=self.nexthop)


def propagated(route: Route) -> list[Route]:
    """The route, or nothing when no packet can match it (RFC 8955 4.2 SHOULD NOT propagate).

    Dropped with a warning rather than refused: a configuration which loaded before still
    loads, and the operator is told which route is not announced and why.
    """
    reason = cast(Flow, route.nlri).unmatchable()
    if not reason:
        return [route]
    log.warning(
        lazymsg('flow.unmatchable action=drop route="{route}" reason="{reason}"', route=route.nlri, reason=reason),
        'configuration',
    )
    return []


# a flow route with no match component matches every packet: 4.2 and 5.0 sent one, and a
# `discard` or `rate-limit` on it applied to all the traffic the peer forwards
NO_MATCH = 'a flow route needs at least one match, or it matches every packet'


class FlowLine(RouteStatement):
    """`<keyword> <value> ...`: a flow route on one line."""

    name = 'flow route'
    unknown = 'flow route: unknown command "{keyword}"'
    too_many = 'a flow route holds at most {count} values'

    def parse(self, words: Words) -> list[Route]:
        words.context.afi = AFI.undefined  # the route's own family, from what it matches
        start = words.where()
        built = FlowRoute()
        for where, spec in self.keywords(words, LINE):
            value = spec.type.parse(words)
            try:
                built.apply(spec, value, line=True)
            except ValueError as exc:
                raise ConfigError(where, str(exc)) from None
        if not built.nlri.rules:
            raise ConfigError(start, NO_MATCH)
        return propagated(built.route())

    def printed(self, route: Route) -> list[WordOrSyntax]:
        # a one-line route has no next-hop, and matches what it is given: nothing is possible
        return announce_flow_words(route)

    def hint(self) -> str:
        return '<match> <value> ... <action> <value> ...'

    def examples(self) -> list[str]:
        return []

    def shape(self) -> Shape:
        return shape.container(*value_fields(LINE))


# --------------------------------------------------------------------------- printing

MAX_PRINTED_WORDS = 4096  # the text of one flow NLRI, far past a real one
IPV6_PREFIXES = ('source-ipv6', 'destination-ipv6')


def rule_pairs(nlri: Any) -> list[tuple[str, list[str]]]:
    """The keyword and value words of the text of a flow NLRI, which reads back as the same rules."""
    from exabgp.configuration.grammar.lexer import lex_command

    words = [token.word for token in lex_command(f'{nlri};')[0].words][1:]
    assert len(words) < MAX_PRINTED_WORDS, 'the text of a flow NLRI is short'
    pairs: list[tuple[str, list[str]]] = []
    index = 0
    while index < len(words):
        keyword = words[index]
        if words[index + 1] == '[':
            end = words.index(']', index + 1)
            pairs.append((keyword, words[index + 1 : end + 1]))
            index = end + 1
        else:
            pairs.append((keyword, [words[index + 1]]))
            index += 2
    return pairs


# the statements of a flow route which are written as their own keyword, not as a community
_COMMUNITY_KEYWORDS = ('community', 'large-community', 'extended-community')


def _spellings(text: str) -> list[list[str]]:
    """How the text of a traffic community may be written as a statement: `rate-limit:0` is
    `rate-limit 0`, `rate-limit:9600:packets` is `rate-limit 9600 packets`, `redirect:1:2` is
    `redirect 1:2`, `mark 10` is itself; the text of an interface-set leaves out whether it is
    transitive, which the statement says.
    """
    if ' ' in text or ':' not in text:
        return [text.split()]
    keyword, rest = text.split(':', 1)
    return [[keyword, *rest.split(':')], [keyword, rest], *([keyword, f'{kind}:{rest}'] for kind in INTERFACE_KINDS)]


INTERFACE_KINDS = ('transitive', 'non-transitive')


def traffic_action(community: Any) -> tuple[str, list[WordOrSyntax]] | None:
    """The action statement a flow extended community is, when one reads back to its bytes."""
    packed = bytes(community.community)
    for words in _spellings(str(community)):
        spec = THEN.get(words[0]) or SCOPE.get(words[0])
        if spec is None or words[0] in _COMMUNITY_KEYWORDS:
            continue
        value = read_back(spec.type, ' '.join(words[1:]))
        if spec.target == Target.NEXTHOP_ATTRIBUTE and value is not None:
            nexthop, value = value
            if nexthop is not IP.NoNextHop:
                continue  # a redirect to an address also sets the next-hop of the route
        communities = getattr(value, 'communities', None)
        if communities is not None and [bytes(each.community) for each in communities] == [packed]:
            return words[0], list(words[1:])
    return None


def action_pairs(route: Route) -> list[tuple[str, list[WordOrSyntax]]]:
    """The actions of a flow route, as keyword and words; ValueError when one has no statement."""
    from exabgp.bgp.message.update.attribute import Attribute, GenericAttribute
    from exabgp.bgp.message.update.attribute.community.extended import TrafficNextHopIPv6IETF, TrafficRedirectIPv6
    from exabgp.configuration.grammar.types.base import Syntax
    from exabgp.configuration.grammar.types.bgp import HexAttribute

    actions: list[tuple[str, list[WordOrSyntax]]] = []
    attribute: Any
    for code, attribute in route.attributes.items():
        if isinstance(attribute, GenericAttribute):
            actions.append(('attribute', HexAttribute().render(attribute)))
        elif code == Attribute.CODE.EXTENDED_COMMUNITY:
            others: list[WordOrSyntax] = []
            for each in attribute.communities:
                found = traffic_action(each)
                if found is None:
                    others.append(community_word(each))
                else:
                    actions.append(found)
            if others:
                actions.append(('extended-community', [Syntax('['), *others, Syntax(']')]))
        elif code in (Attribute.CODE.COMMUNITY, Attribute.CODE.LARGE_COMMUNITY):
            keyword = 'community' if code == Attribute.CODE.COMMUNITY else 'large-community'
            # the brackets of a list are syntax: as words, they were printed quoted, `"["`
            actions.append((keyword, text_words(str(attribute)) or [Syntax('['), Syntax(']')]))
        elif code == Attribute.CODE.IPV6_EXTENDED_COMMUNITY:
            for each in attribute.communities:
                if isinstance(each, TrafficRedirectIPv6):
                    address, number = str(each).split()[-1][1:].split(']:')
                    actions.append(('redirect', [Syntax('['), address, Syntax(']'), f':{number}']))
                elif isinstance(each, TrafficNextHopIPv6IETF):
                    name, address = str(each).split()[:2]
                    actions.append(('copy' if name.startswith('copy') else 'redirect-to-nexthop-ietf', [address]))
                else:
                    raise ValueError(f'no statement writes the IPv6 extended community {each}')
        else:
            raise ValueError(f'no flow statement writes the attribute {code}')
    return actions


def _printed(words: Sequence[WordOrSyntax]) -> list[Any]:
    return [Printed(list(words))]


def route_values(route: Route) -> tuple[Any, dict[str, Any]]:
    """The statements of the route block which reads back as `route`."""
    nlri: Any = route.nlri
    match: dict[str, Any] = {}
    values: dict[str, Any] = {'match': match, 'then': {}}
    for keyword, words in rule_pairs(nlri):
        if keyword in ('rd', 'path-information'):
            values[f'_{keyword}'] = _printed(words)
        else:
            match.setdefault(f'_{keyword}', []).extend(_printed(words))
    for keyword, then in action_pairs(route):
        # an interface-set is where the route applies, said in its scope block
        block = values.setdefault('scope', {}) if keyword in SCOPE else values['then']
        block.setdefault(f'_{keyword}', []).extend(_printed(then))
    if route.nexthop is not IP.NoNextHop:
        values['_next-hop'] = _printed(['self' if route.nexthop.SELF else str(route.nexthop)])
    return '', values


def block_printable(route: Route) -> bool:
    """Whether a route block reads back as the route: its family follows from its prefixes and rd."""
    nlri: Any = route.nlri
    pairs = [keyword for keyword, _ in rule_pairs(nlri)]
    if nlri.safi == SAFI.flow_vpn and 'rd' not in pairs:
        return False
    if any(keyword == 'attribute' for keyword, _ in action_pairs(route)):
        return False
    has_ipv6_prefix = any(keyword in IPV6_PREFIXES for keyword in pairs)
    return bool(nlri.afi == AFI.ipv6) == has_ipv6_prefix


def announce_flow_words(route: Route) -> list[WordOrSyntax]:
    """The words after `flow` or `flow-vpn` in an announce family which read back as `route`."""
    if route.nexthop is not IP.NoNextHop:
        raise ValueError('an announce flow route has no next-hop statement')
    words: list[WordOrSyntax] = []
    for keyword, value in rule_pairs(route.nlri) + action_pairs(route):
        words.extend([keyword, *value])
    return words


# --------------------------------------------------------------------------- the route block


def _leaves(values: dict[str, FlowValue]) -> tuple[Leaf, ...]:
    return tuple(
        Leaf(keyword, spec.type, field=f'_{keyword}', store=Pending(spec), doc=spec.doc, adds=spec.adds)
        for keyword, spec in values.items()
    )


class _Ignored(Type[str]):
    """The name of a flow route block: read and kept by nobody."""

    name = 'route name'

    def parse(self, words: Words) -> str:
        return words.word()

    def render(self, value: str) -> list[WordOrSyntax]:
        return [value] if value else []

    def hint(self) -> str:
        return '[<name>]'

    def examples(self) -> list[str]:
        return ['', 'name']


class FlowRouteSection(Collector[list[Route]]):
    """`route [<name>] { match { } then { } scope { } }`: one flow route."""

    def opened(self, context: ReadContext) -> None:
        super().opened(context)
        # the family is the route's own, from what it matches: not that of the last prefix read
        context.afi = AFI.undefined

    def collected(self, name: Any, values: Values, entries: list[tuple[Any, Any]], context: ReadContext) -> list[Route]:
        built = FlowRoute()
        for spec, value in entries:
            built.apply(spec, value, line=False)
        if not built.nlri.rules:
            raise ValueError(NO_MATCH)
        routes = propagated(built.route())
        context.routes.extend(routes)
        return routes

    def unbuild(self, name: Any, built: Route, context: PrintContext) -> tuple[Any, Values]:
        return route_values(built)


ROUTE_BLOCK = Block(
    'route',
    field='_routes',
    section=FlowRouteSection(),
    keep=Keep.EXTEND,
    name=_Ignored(),
    key='label',  # the name is read and ignored
    doc='a flow route, what it matches and what it does',
    # the blocks first: printed in this order, a redirect in `then` is read before `next-hop`
    children=(
        Block('match', field='match', children=_leaves(MATCH), doc='what the route matches'),
        Block('then', field='then', children=_leaves(THEN), doc='what is done with what matches'),
        Block('scope', field='scope', children=_leaves(SCOPE), doc='where the route applies'),
        *_leaves(ROUTE),
    ),
)

# the routes of the block reach the neighbor with the others not yet taken
# (ReadContext.take_routes): the block keeps none, or each would be the neighbor's twice
FLOW = Block(
    'flow',
    field='flow',
    doc='FlowSpec routes (RFC 8955, RFC 8956)',
    children=(Leaf('route', FlowLine(), field='_line', store=ROUTES, multiple=True), ROUTE_BLOCK),
)

# --------------------------------------------------------------------------- announce families

ANNOUNCE_FLOW: dict[str, FlowValue] = {
    'rd': FlowValue(ROUTE_VALUES['rd'].type, Target.NLRI, 'rd'),
    'route-distinguisher': FlowValue(ROUTE_VALUES['rd'].type, Target.NLRI, 'rd'),
    'path-information': FlowValue(ROUTE_VALUES['path-information'].type, Target.NLRI, 'path_info'),
    **MATCH,
    **THEN,
    **SCOPE,
    'attribute': FlowValue(ROUTE_VALUES['attribute'].type, Target.ATTRIBUTE),
}


class AnnounceFlowLine(RouteStatement):
    """`flow|flow-vpn <keyword> <value> ...` of an announce address family."""

    too_many = 'a flow route holds at most {count} values'

    def __init__(self, afi: AFI, safi: SAFI) -> None:
        self.afi = afi
        self.safi = safi
        self.name = f'{afi.name()} {safi.name()} route'

    def parse(self, words: Words) -> list[Route]:
        words.context.afi = self.afi  # the family of the announce block
        start = words.where()
        settings = FlowSettings()
        settings.action = action(words)
        settings.afi, settings.safi = self.afi, self.safi
        attributes = AttributeCollection()
        for where, spec in self.keywords(words, ANNOUNCE_FLOW):
            try:
                self._apply(settings, attributes, spec, spec.type.parse(words))
            except ValueError as exc:
                raise ConfigError(where, str(exc)) from None
        if not settings.rules:
            raise ConfigError(start, NO_MATCH)
        # it made a flow route carrying an rd, which no statement prints back as it was read
        if settings.rd is not None and self.safi == SAFI.flow_ip:
            raise ConfigError(
                start, f'a flow route with a route distinguisher is announced as {self.afi.name()} flow-vpn'
            )
        return [Route(Flow.from_settings(settings), attributes, nexthop=settings.nexthop)]

    @staticmethod
    def _apply(settings: FlowSettings, attributes: AttributeCollection, spec: FlowValue, value: Any) -> None:
        if spec.target == Target.RULE:
            for rule in value:
                settings.add_rule(rule)
        elif spec.target == Target.NLRI:
            settings.set(spec.field, value)
        elif spec.target == Target.NEXTHOP_ATTRIBUTE:
            ip, attribute = value
            if ip:
                settings.nexthop = ip
            if attribute:
                add_attribute(attributes, attribute)
        elif spec.target == Target.ATTRIBUTE:
            add_attribute(attributes, value)

    def printed(self, route: Route) -> list[WordOrSyntax]:
        return announce_flow_words(route)

    def hint(self) -> str:
        return '<match> <value> ... <action> <value> ...'

    def examples(self) -> list[str]:
        return []

    def shape(self) -> Shape:
        return shape.container(*value_fields(ANNOUNCE_FLOW))
