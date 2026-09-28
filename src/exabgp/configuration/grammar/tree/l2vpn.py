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
from exabgp.bgp.message.update.attribute import AttributeCollection, NextHopSelf
from exabgp.bgp.message.update.nlri import VPLS
from exabgp.bgp.message.update.nlri.settings import VPLSSettings
from exabgp.configuration.grammar import shape
from exabgp.configuration.grammar.context import ReadContext
from exabgp.configuration.grammar.error import ConfigError
from exabgp.configuration.grammar.nodes import Block, Keep, Leaf
from exabgp.configuration.grammar.section import Collector, Kept, Pending, Store, Values
from exabgp.configuration.grammar.shape import Shape
from exabgp.configuration.grammar.tree.static import (
    ROUTE_VALUES,
    ROUTES,
    RouteValue,
    action,
    attribute_words,
    value_fields,
)
from exabgp.configuration.grammar.types.base import Type
from exabgp.configuration.grammar.types.route import RouteStatement
from exabgp.configuration.grammar.types.word import Number, Word
from exabgp.configuration.grammar.words import Words
from exabgp.protocol.family import AFI
from exabgp.protocol.ip import IP
from exabgp.rib.route import Route

VPLS_PARAM_MAX = 0xFFFF  # endpoint, size, offset and label base are sixteen bits


def _vpls_number(name: str) -> Number[int]:
    def convert(word: str) -> int:
        number = int(word)
        if not 0 <= number <= VPLS_PARAM_MAX:
            raise ValueError(f'invalid l2vpn vpls {name}')
        return number

    return Number(name, ((0, VPLS_PARAM_MAX),), convert=convert, examples=['0', '5', str(VPLS_PARAM_MAX)])


def _nexthop(word: str) -> NextHopSelf | IP:
    if word.lower() == 'self':
        return NextHopSelf(AFI.ipv4)
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
        'nlri',
        'nexthop',
        'the next-hop, or self for the IPv4 local address',
    ),
    'rd': RouteValue(ROUTE_VALUES['rd'].type, 'nlri', 'rd'),
    # RFC 4761 3.2.2
    'endpoint': RouteValue(_vpls_number('endpoint'), 'nlri', 'endpoint', 'the VE ID of the site'),
    'offset': RouteValue(_vpls_number('block-offset'), 'nlri', 'offset', 'the VE block offset'),
    'size': RouteValue(_vpls_number('block-size'), 'nlri', 'size', 'the VE block size'),
    'base': RouteValue(_vpls_number('label'), 'nlri', 'base', 'the label base'),
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
    **{keyword: RouteValue(ROUTE_VALUES[keyword].type, 'attribute') for keyword in VPLS_ATTRIBUTES},
}


def _apply(settings: VPLSSettings, attributes: AttributeCollection, spec: RouteValue, value: Any) -> None:
    if spec.target == 'nlri':
        settings.set(spec.field, value)
    else:
        attributes.add(value)


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

    def printed(self, route: Route) -> list[str]:
        return vpls_words(route)

    def hint(self) -> str:
        return 'endpoint <n> base <n> offset <n> size <n> rd <rd> next-hop <ip> [...]'

    def examples(self) -> list[str]:
        return ['endpoint 5 base 10702 offset 1 size 8 rd 1:1 next-hop 10.0.0.1']

    def shape(self) -> Shape:
        return shape.container(*value_fields(VPLS_VALUES))


def vpls_words(route: Route) -> list[str]:
    """What follows `vpls`: the text of the NLRI after its name, the next-hop, the attributes."""
    words = str(route.nlri).split()[1:]
    return words + attribute_words(route)


# --------------------------------------------------------------------------- the l2vpn section


class _Ignored(Type[str]):
    """The name of a vpls block: read, kept by nobody."""

    name = 'vpls name'

    def parse(self, words: Words) -> str:
        return words.word()

    def render(self, value: str) -> list[str]:
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


class LastRouteStore(Store):
    """legacy: an attribute given in the l2vpn section goes to the last route read, a static
    one included, and fails when there is none."""

    def keep(self, values: Values, value: Any, context: ReadContext) -> None:
        routes = context.routes
        if not routes:
            raise ValueError('there is no route for this attribute to be added to')
        routes[-1].attributes.add(value)


class _NoSetter(Type[Any]):
    """legacy: a VPLS value given in the l2vpn section is set on an NLRI which takes no change."""

    def __init__(self, name: str) -> None:
        self.name = name

    def parse(self, words: Words) -> Any:
        raise ConfigError(words.where(), f'{self.name} can not be changed on a route already made')

    def render(self, value: Any) -> list[str]:
        raise ValueError(f'{self.name} is never read, so never printed')

    def hint(self) -> str:
        return ''

    def examples(self) -> list[str]:
        return []

    def shape(self) -> Shape:
        return shape.REFUSED


class L2VPNSection(Kept):
    def build(self, name: Any, values: Values, context: ReadContext) -> Values:
        # legacy: the section takes every route not yet taken, those read before it included
        values.setdefault('routes', []).extend(context.take_routes())
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
        Leaf(keyword, spec.type, field=f'_{keyword}', store=Pending(spec), doc=spec.doc)
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
        *(Leaf(keyword, _NoSetter(keyword), field=f'_{keyword}') for keyword in VPLS_NLRI),
        *(
            Leaf(keyword, ROUTE_VALUES[keyword].type, field=f'_{keyword}', store=LastRouteStore())
            for keyword in VPLS_ATTRIBUTES
        ),
    ),
)
