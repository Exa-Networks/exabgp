"""l2vpn.py

    l2vpn {
        vpls endpoint <n> base <n> offset <n> size <n> rd <rd> next-hop <ip> [<attribute> <value> ...];
        vpls [<name>] { endpoint <n>; base <n>; ...; }
    }
    announce { l2vpn { vpls ...; } }

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any

from exabgp.bgp.message import Action
from exabgp.bgp.message.update.attribute import AttributeCollection
from exabgp.bgp.message.update.nlri import VPLS
from exabgp.bgp.message.update.nlri.settings import VPLSSettings
from exabgp.configuration.grammar import shape
from exabgp.configuration.grammar.context import ReadContext
from exabgp.configuration.grammar.error import ConfigError
from exabgp.configuration.grammar.nodes import Block, Keep, Leaf
from exabgp.configuration.grammar.section import Collector, Kept, Pending, Values
from exabgp.configuration.grammar.shape import Shape
from exabgp.configuration.grammar.tree.static import (
    ROUTE_VALUES,
    ROUTES,
    RouteValue,
    action,
    add_attribute,
    attribute_words,
    value_fields,
)
from exabgp.configuration.grammar.types.base import Type, WordOrSyntax
from exabgp.configuration.grammar.types.route import RouteStatement, Target
from exabgp.configuration.grammar.types.word import Number, Word, decimal
from exabgp.configuration.grammar.words import Words
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP, IPSelf
from exabgp.rib.route import Route

VPLS_PARAM_MAX = 0xFFFF  # RFC 4761 3.2.2: VE ID, VE block offset and VE block size are two octets
VPLS_LABEL_MAX = 0xFFFFF  # RFC 4761 3.2.2: the label base is a twenty bit label


def _vpls_number(name: str, maximum: int = VPLS_PARAM_MAX) -> Number[int]:
    def convert(word: str) -> int:
        number = decimal(word)
        if not 0 <= number <= maximum:
            raise ValueError(f'invalid l2vpn vpls {name}')
        return number

    return Number(name, ((0, maximum),), convert=convert, examples=['0', '5', str(maximum)])


def _nexthop(word: str) -> IP:
    if word.lower() == 'self':
        # the route's next-hop, an IP: IPSelf, as the other families use, not the attribute
        return IPSelf(AFI.ipv4)
    return IP.from_string(word)


VPLS_NLRI: dict[str, RouteValue] = {
    'next-hop': RouteValue(
        Word(
            'next-hop',
            '<ip>|self',
            _nexthop,
            ['10.0.0.1', 'self'],
            shape=shape.union(shape.IP_ADDRESS, shape.enumeration('self')),
        ),
        Target.NLRI,
        'nexthop',
        'the next-hop, or self for the IPv4 local address',
    ),
    'rd': RouteValue(ROUTE_VALUES['rd'].type, Target.NLRI, 'rd'),
    # RFC 4761 3.2.2
    'endpoint': RouteValue(_vpls_number('endpoint'), Target.NLRI, 'endpoint', 'the VE ID of the site'),
    'offset': RouteValue(_vpls_number('block-offset'), Target.NLRI, 'offset', 'the VE block offset'),
    'size': RouteValue(_vpls_number('block-size'), Target.NLRI, 'size', 'the VE block size'),
    'base': RouteValue(_vpls_number('label', VPLS_LABEL_MAX), Target.NLRI, 'base', 'the label base'),
}
VPLS_ATTRIBUTES = (
    'attribute',
    'origin',
    'med',
    'as-path',
    'local-preference',
    'atomic-aggregate',
    'aggregator',
    'originator-id',
    'cluster-list',
    'community',
    'extended-community',
    'name',
    'split',
    'watchdog',
    'withdraw',
)
VPLS_VALUES: dict[str, RouteValue] = {
    **VPLS_NLRI,
    **{
        keyword: RouteValue(ROUTE_VALUES[keyword].type, Target.ATTRIBUTE, adds=ROUTE_VALUES[keyword].adds)
        for keyword in VPLS_ATTRIBUTES
    },
}


def _apply(settings: VPLSSettings, attributes: AttributeCollection, spec: RouteValue, value: Any) -> None:
    if spec.target == Target.NLRI:
        settings.set(spec.field, value)
    else:
        add_attribute(attributes, value)


def _vpls_route(settings: VPLSSettings, attributes: AttributeCollection, where: str) -> Route:
    try:
        nlri = VPLS.from_settings(settings)
    except ValueError as exc:
        raise ConfigError(where, str(exc)) from None
    return Route(nlri, attributes, nexthop=settings.nexthop)


class VPLSLine(RouteStatement):
    """`<keyword> <value> ...`: a VPLS route on one line."""

    name = 'vpls route'
    too_many = 'a vpls route holds at most {count} values'

    def parse(self, words: Words) -> list[Route]:
        settings = VPLSSettings()
        settings.action = action(words)
        attributes = AttributeCollection()
        for _, spec in self.keywords(words, VPLS_VALUES):
            _apply(settings, attributes, spec, spec.type.parse(words))
        return [_vpls_route(settings, attributes, words.where())]

    def printed(self, route: Route) -> list[WordOrSyntax]:
        return vpls_words(route)

    def hint(self) -> str:
        return 'endpoint <n> base <n> offset <n> size <n> rd <rd> next-hop <ip> [...]'

    def examples(self) -> list[str]:
        return ['endpoint 5 base 10702 offset 1 size 8 rd 1:1 next-hop 10.0.0.1']

    def shape(self) -> Shape:
        return shape.container(*value_fields(VPLS_VALUES))


def vpls_words(route: Route) -> list[WordOrSyntax]:
    """What follows `vpls`: the text of the NLRI after its name, the next-hop, the attributes."""
    words = str(route.nlri).split()[1:]
    return words + attribute_words(route)


# --------------------------------------------------------------------------- the l2vpn section


class _Ignored(Type[str]):
    """The name of a vpls block: read, kept by nobody."""

    name = 'vpls name'

    def parse(self, words: Words) -> str:
        return words.word()

    def render(self, value: str) -> list[WordOrSyntax]:
        return []

    def hint(self) -> str:
        return '[<name>]'

    def examples(self) -> list[str]:
        return ['', 'site']


class VPLSSection(Collector[list[Route]]):
    """`vpls [<name>] { ... }`: one VPLS route, its values one per statement."""

    def collected(self, name: Any, values: Values, entries: list[tuple[Any, Any]], context: ReadContext) -> list[Route]:
        settings = VPLSSettings()
        settings.action = Action.ANNOUNCE
        attributes = AttributeCollection()
        for spec, value in entries:
            _apply(settings, attributes, spec, value)
        route = _vpls_route(settings, attributes, '')
        context.routes.append(route)
        return [route]


class _InVpls(Type[Any]):
    """A value of a VPLS route given in the l2vpn section, outside any route: refused.

    An attribute went to the last route read, a static one included, and a VPLS field was
    refused as a change to a route already made.
    """

    def __init__(self, name: str) -> None:
        self.name = name

    def parse(self, words: Words) -> Any:
        raise ConfigError(words.where(), f'{self.name} is given in a vpls route, not in the l2vpn section')

    def render(self, value: Any) -> list[WordOrSyntax]:
        raise ValueError(f'{self.name} is never read, so never printed')

    def hint(self) -> str:
        return ''

    def examples(self) -> list[str]:
        return []

    def shape(self) -> Shape:
        return shape.REFUSED


VPLS_FAMILY = (AFI.l2vpn, SAFI.vpls)


class L2VPNSection(Kept):
    def build(self, name: Any, values: Values, context: ReadContext) -> Values:
        # its own routes: it took every route not yet taken, a static route read before it included
        taken = context.take_routes()
        values.setdefault('routes', []).extend(
            route for route in taken if route.nlri.family().afi_safi() == VPLS_FAMILY
        )
        context.routes.extend(route for route in taken if route.nlri.family().afi_safi() != VPLS_FAMILY)
        return values


VPLS_BLOCK = Block(
    'vpls',
    field='_blocks',
    section=VPLSSection(),
    keep=Keep.EXTEND,
    name=_Ignored(),
    key='label',  # the name is read and ignored
    doc='a VPLS route, its values one per statement',
    children=tuple(
        Leaf(keyword, spec.type, field=f'_{keyword}', store=Pending(spec), doc=spec.doc, adds=spec.adds)
        for keyword, spec in VPLS_VALUES.items()
    ),
)

L2VPN_SECTION = Block(
    'l2vpn',
    field='l2vpn',
    section=L2VPNSection(),
    doc='VPLS routes',
    children=(
        Leaf('vpls', VPLSLine(), field='_line', store=ROUTES, doc='a VPLS route, on one line', multiple=True),
        VPLS_BLOCK,
        *(Leaf(keyword, _InVpls(keyword), field=f'_{keyword}') for keyword in (*VPLS_NLRI, *VPLS_ATTRIBUTES)),
    ),
)
