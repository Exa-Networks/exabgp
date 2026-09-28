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
from exabgp.configuration.grammar.shape import Shape
from exabgp.configuration.grammar.error import ConfigError
from exabgp.configuration.grammar.nodes import Block, Keep, Leaf
from exabgp.configuration.grammar.tree.static import (
    MAX_ROUTE_VALUES,
    ROUTE_VALUES,
    ROUTES,
    RouteValue,
    action,
    attribute_words,
    store_routes,
    value_fields,
)
from exabgp.configuration.grammar.types.base import Type
from exabgp.configuration.grammar.types.word import Number, Word
from exabgp.configuration.grammar.words import Words
from exabgp.protocol.family import AFI
from exabgp.protocol.ip import IP
from exabgp.rib.route import Route

VPLS_PARAM_MAX = 0xFFFF  # endpoint, size, offset and label base are sixteen bits
OPS = 'vpls-ops'  # the values of the vpls block being read


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


class VPLSLine(Type[list[Route]]):
    """`<keyword> <value> ...`: a VPLS route on one line."""

    name = 'vpls route'

    def parse(self, words: Words) -> list[Route]:
        settings = VPLSSettings()
        settings.action = action(words)
        attributes = AttributeCollection()
        for _ in range(MAX_ROUTE_VALUES):
            where = words.where()
            keyword = words.word()
            if not keyword:
                return [_vpls_route(settings, attributes, where)]
            spec = VPLS_VALUES.get(keyword)
            if spec is None:
                raise ConfigError(where, f"Unknown command '{keyword}'", expected=sorted(VPLS_VALUES))
            _apply(settings, attributes, spec, spec.type.parse(words))
        raise ConfigError(words.where(), f'a vpls route holds at most {MAX_ROUTE_VALUES} values')

    def render(self, value: list[Route]) -> list[str]:
        return [word for route in value for word in vpls_words(route)]

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


def _opened(context: dict[str, Any]) -> None:
    context[OPS] = []


def _store_op(spec: RouteValue) -> Any:
    def store(values: dict[str, Any], value: Any, context: dict[str, Any]) -> None:
        context.setdefault(OPS, []).append((spec, value))

    return store


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


def _vpls(name: Any, values: dict[str, Any], context: dict[str, Any]) -> list[Route]:
    settings = VPLSSettings()
    settings.action = Action.ANNOUNCE
    attributes = AttributeCollection()
    for spec, value in context.pop(OPS, []):
        _apply(settings, attributes, spec, value)
    route = _vpls_route(settings, attributes, '')
    context.setdefault(ROUTES, []).append(route)
    return [route]


def _store_on_last_route(values: dict[str, Any], value: Any, context: dict[str, Any]) -> None:
    # legacy: an attribute given in the l2vpn section goes to the last route read, a static
    # one included, and fails when there is none
    routes = context.get(ROUTES, [])
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


def _l2vpn(name: Any, values: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    # legacy: the section takes every route not yet taken, those read before it included
    values.setdefault('routes', []).extend(context.pop(ROUTES, []))
    return values


VPLS_BLOCK = Block(
    'vpls',
    field='_blocks',
    build=_vpls,
    keep=Keep.EXTEND,
    name=_Ignored(),
    key='label',  # the name is read and ignored
    opened=_opened,
    doc='a VPLS route, its values one per statement',
    children=tuple(
        Leaf(keyword, spec.type, field=f'_{keyword}', store=_store_op(spec), doc=spec.doc)
        for keyword, spec in VPLS_VALUES.items()
    ),
)

L2VPN_SECTION = Block(
    'l2vpn',
    field='l2vpn',
    build=_l2vpn,
    doc='VPLS routes',
    children=(
        Leaf('vpls', VPLSLine(), field='_line', store=store_routes, doc='a VPLS route, on one line', multiple=True),
        VPLS_BLOCK,
        *(Leaf(keyword, _NoSetter(keyword), field=f'_{keyword}') for keyword in VPLS_NLRI),
        *(
            Leaf(keyword, ROUTE_VALUES[keyword].type, field=f'_{keyword}', store=_store_on_last_route)
            for keyword in VPLS_ATTRIBUTES
        ),
    ),
)
