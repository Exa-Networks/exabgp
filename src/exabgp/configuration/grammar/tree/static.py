"""static.py

    static {
        route <prefix> next-hop <ip>|self [<attribute> <value> ...];
        route <prefix> { next-hop <ip>; <attribute> <value>; ... }
        attributes <attribute> <value> ... nlri <prefix> ...;
    }

A route line is a prefix followed by keyword and value pairs in any order: the keywords and
their types are declared once, in ROUTE_VALUES, and read the same in a line and in a block.

The routes are kept, as the legacy parser kept them, in one list for the whole read, which
the next neighbor or template to close takes (resolve.py): `ReadContext.routes`.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.configuration.grammar.context import ReadContext
from dataclasses import dataclass
from typing import Any, Iterator, Mapping, cast

from exabgp.bgp.message import Action
from exabgp.bgp.message.update.attribute import Attribute, AttributeCollection
from exabgp.bgp.message.update.nlri import CIDR, INET, IPVPN, Label
from exabgp.bgp.message.update.nlri.empty import Empty
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier import PathInfo
from exabgp.bgp.message.update.nlri.settings import INETSettings
from exabgp.configuration.grammar import shape
from exabgp.configuration.grammar.error import ConfigError
from exabgp.configuration.grammar.shape import Shape
from exabgp.configuration.grammar.lexer import lex_command
from exabgp.configuration.grammar.nodes import Block, Keep, Leaf
from exabgp.configuration.grammar.types import bgp
from exabgp.configuration.grammar.types.base import Syntax, Type
from exabgp.configuration.grammar.words import Words
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP, IPRange
from exabgp.rib.route import Route

# a route line holds a handful of attributes, each given once or a few times
MAX_ROUTE_VALUES = 256


@dataclass(frozen=True)
class RouteValue:
    type: Type[Any]
    target: str  # 'attribute', 'nexthop' (an address and its attribute), or 'nlri'
    field: str = ''  # the INETSettings field, for an 'nlri' target
    doc: str = ''


ROUTE_VALUES: dict[str, RouteValue] = {
    'next-hop': RouteValue(bgp.NextHopType(), 'nexthop', doc='the next-hop, or self for the local address'),
    'path-information': RouteValue(bgp.PATH_INFORMATION, 'nlri', 'path_info', 'the ADD-PATH path identifier'),
    'rd': RouteValue(bgp.ROUTE_DISTINGUISHER, 'nlri', 'rd', 'the route distinguisher, making it a VPN route'),
    'route-distinguisher': RouteValue(bgp.ROUTE_DISTINGUISHER, 'nlri', 'rd'),
    'label': RouteValue(bgp.LabelsType(), 'nlri', 'labels', 'the MPLS label stack'),
    'bgp-prefix-sid': RouteValue(bgp.PrefixSidType(), 'attribute'),
    'bgp-prefix-sid-srv6': RouteValue(bgp.PrefixSidSrv6Type(), 'attribute'),
    'attribute': RouteValue(bgp.HexAttribute(), 'attribute', doc='any attribute, as its wire bytes'),
    'origin': RouteValue(bgp.ORIGIN, 'attribute'),
    'otc': RouteValue(bgp.OTC_VALUE, 'attribute', doc='RFC 9234 Only-to-Customer'),
    'med': RouteValue(bgp.MED_VALUE, 'attribute'),
    'as-path': RouteValue(bgp.ASPathType(), 'attribute'),
    'local-preference': RouteValue(bgp.LOCAL_PREFERENCE, 'attribute'),
    'atomic-aggregate': RouteValue(bgp.ATOMIC_AGGREGATE, 'attribute'),
    'aggregator': RouteValue(bgp.AggregatorType(), 'attribute'),
    'originator-id': RouteValue(bgp.ORIGINATOR_ID, 'attribute'),
    'cluster-list': RouteValue(bgp.ClusterListType(), 'attribute'),
    'community': RouteValue(bgp.COMMUNITIES, 'attribute'),
    'large-community': RouteValue(bgp.LARGE_COMMUNITIES, 'attribute'),
    'extended-community': RouteValue(bgp.ExtendedCommunitiesType(), 'attribute'),
    'aigp': RouteValue(bgp.AIGP_VALUE, 'attribute'),
    'name': RouteValue(bgp.NAME, 'attribute', doc='a name for the route, kept by exabgp'),
    'split': RouteValue(bgp.SPLIT, 'attribute', doc='announce the prefix as its more specifics of this length'),
    'watchdog': RouteValue(bgp.WATCHDOG, 'attribute', doc='the watchdog which announces and withdraws the route'),
    'withdraw': RouteValue(bgp.WITHDRAW, 'attribute', doc='start with the route withdrawn'),
}


class Collected:
    """What the values of one route set: the NLRI settings and the attributes, in their order."""

    def __init__(self, settings: INETSettings) -> None:
        self.settings = settings
        self.attributes = AttributeCollection()

    def apply(self, keyword: str, value: Any) -> None:
        spec = ROUTE_VALUES[keyword]
        if spec.target == 'nlri':
            self.settings.set(spec.field, value)
        elif spec.target == 'nexthop':
            ip, attribute = value
            self.settings.nexthop = ip
            self.attributes.add(attribute)
        else:
            self.attributes.add(value)


def read_values(words: Words, collected: Collected, stop: str = '') -> None:
    """The keyword and value pairs of a route line, applied as they are read; `stop` ends them."""
    for _ in range(MAX_ROUTE_VALUES):
        where = words.where()
        keyword = words.word()
        if not keyword or keyword == stop:
            return
        if keyword not in ROUTE_VALUES:
            raise ConfigError(where, f'unknown command "{keyword}"', expected=sorted(ROUTE_VALUES))
        collected.apply(keyword, ROUTE_VALUES[keyword].type.parse(words))
    raise ConfigError(words.where(), f'a route holds at most {MAX_ROUTE_VALUES} values')


def _mentions(words: Words, *keywords: str) -> bool:
    """legacy: whether a word of the statement is one of `keywords`, wherever it is, a value included."""
    return any(token.word in keywords for token in words.context.statement)


def _nlri_class(words: Words, settings: INETSettings, prefix: IPRange | None) -> type[INET]:
    if _mentions(words, 'rd', 'route-distinguisher'):
        settings.safi = SAFI.mpls_vpn
        return IPVPN
    if _mentions(words, 'label'):
        settings.safi = SAFI.nlri_mpls
        return Label
    settings.safi = IP.tosafi(prefix.top()) if prefix is not None else SAFI.unicast
    return INET


def action(words: Words) -> Action:
    """Whether the route read is announced or withdrawn, as the API command said."""
    return Action.ANNOUNCE if words.context.announce else Action.WITHDRAW


def value_fields(values: Mapping[str, Any]) -> tuple[tuple[str, Shape], ...]:
    """The members of a route, from the table of the values its statement reads."""
    fields = ((keyword, spec.type.shape().described(getattr(spec, 'doc', ''))) for keyword, spec in values.items())
    return tuple((keyword, value) for keyword, value in fields if value.kind != shape.Kind.REFUSED)


class RouteLine(Type[list[Route]]):
    """`<prefix> <keyword> <value> ...`: one route, or its more specifics when split."""

    name = 'route'

    def parse(self, words: Words) -> list[Route]:
        prefix = bgp.Prefix().parse(words)
        settings = INETSettings()
        settings.cidr = CIDR.create_cidr(prefix.pack_ip(), prefix.mask)
        settings.afi = IP.toafi(prefix.top())
        settings.action = action(words)
        klass = _nlri_class(words, settings, prefix)
        collected = Collected(settings)
        read_values(words, collected)
        route = Route(klass.from_settings(settings), collected.attributes, nexthop=settings.nexthop)
        return finish([route])

    def render(self, value: list[Route]) -> list[str]:
        return [word for route in value for word in route_words(route)]

    def hint(self) -> str:
        return '<prefix> next-hop <ip>|self [<attribute> <value> ...]'

    def examples(self) -> list[str]:
        return ['10.0.0.0/24 next-hop 10.0.0.1', '10.0.0.0/24 next-hop self']

    def shape(self) -> Shape:
        return shape.container(('prefix', bgp.Prefix().shape()), *value_fields(ROUTE_VALUES))


class AttributesLine(Type[list[Route]]):
    """`<attribute> <value> ... nlri <prefix> ...`: the same attributes for every prefix."""

    name = 'attributes'

    def parse(self, words: Words) -> list[Route]:
        statement = [token.word for token in words.context.statement]
        has_nlri = 'nlri' in statement
        found = _last_prefix(statement) if has_nlri else []
        prefix = found[0] if found else None
        words.context.afi = prefix.afi if prefix is not None else AFI.ipv4
        settings = INETSettings()
        settings.afi = IP.toafi(prefix.top()) if prefix is not None else AFI.ipv4
        settings.action = action(words)
        klass = _nlri_class(words, settings, prefix)
        collected = Collected(settings)
        read_values(words, collected, stop='nlri')
        routes = []
        for _ in range(bgp.MAX_LIST_ITEMS):
            if words.at_end():
                break
            each = bgp.Prefix().parse(words)
            settings_copy = INETSettings(**{name: getattr(settings, name) for name in settings.__dataclass_fields__})
            settings_copy.cidr = CIDR.create_cidr(each.pack_ip(), each.mask)
            settings_copy.action = Action.UNSET
            routes.append(Route(klass.from_settings(settings_copy), collected.attributes, nexthop=settings.nexthop))
        if not routes and collected.attributes:
            return [Route(Empty(AFI.ipv4, SAFI.unicast), collected.attributes)]
        return finish(routes)

    def render(self, value: list[Route]) -> list[str]:
        return [word for route in value for word in attribute_words(route)]

    def hint(self) -> str:
        return '<attribute> <value> ... nlri <prefix> ...'

    def examples(self) -> list[str]:
        return ['next-hop 10.0.0.1 nlri 10.0.0.0/24 10.0.1.0/24', 'origin igp']

    def shape(self) -> Shape:
        prefixes = shape.leaf_list(shape.IP_PREFIX).described('the prefixes the attributes are announced with')
        return shape.container(*value_fields(ROUTE_VALUES), ('nlri', prefixes))


def _last_prefix(statement: list[str]) -> list[IPRange]:
    """legacy: the family of `attributes ... nlri` is the one of its last word, when that is a prefix.

    The prefix, or no prefix when the last word is none: then the route has no address family.
    """
    last = statement[-1]
    ip, _, mask = last.partition('/')
    try:
        return [IPRange.make_range(ip, int(mask) if mask else (128 if ':' in ip else 32))]
    except (ValueError, KeyError, OSError):
        return []


# --------------------------------------------------------------------------- printing

# the keyword a route line gives each attribute, by attribute code
ATTRIBUTE_KEYWORDS: dict[int, str] = {
    Attribute.CODE.ORIGIN: 'origin',
    Attribute.CODE.AS_PATH: 'as-path',
    Attribute.CODE.MED: 'med',
    Attribute.CODE.LOCAL_PREF: 'local-preference',
    Attribute.CODE.ATOMIC_AGGREGATE: 'atomic-aggregate',
    Attribute.CODE.AGGREGATOR: 'aggregator',
    Attribute.CODE.COMMUNITY: 'community',
    Attribute.CODE.ORIGINATOR_ID: 'originator-id',
    Attribute.CODE.CLUSTER_LIST: 'cluster-list',
    Attribute.CODE.EXTENDED_COMMUNITY: 'extended-community',
    Attribute.CODE.AIGP: 'aigp',
    Attribute.CODE.LARGE_COMMUNITY: 'large-community',
    Attribute.CODE.OTC: 'otc',
    Attribute.CODE.BGP_PREFIX_SID: 'bgp-prefix-sid',
    Attribute.CODE.INTERNAL_NAME: 'name',
    Attribute.CODE.INTERNAL_WATCHDOG: 'watchdog',
}
_STRUCTURE = frozenset({'[', ']', '(', ')', ','})


class Unprintable(ValueError):
    """A route holding a value no statement writes back (an SRv6 prefix SID)."""


def _attribute_words(code: int, attribute: Any) -> list[str]:
    from exabgp.bgp.message.update.attribute import GenericAttribute

    if isinstance(attribute, GenericAttribute):
        return ['attribute', *bgp.HexAttribute().render(attribute)]
    if code == Attribute.CODE.INTERNAL_SPLIT:
        return ['split', f'/{int(attribute)}']
    if code == Attribute.CODE.INTERNAL_WITHDRAW:
        return ['withdraw']
    if code not in ATTRIBUTE_KEYWORDS:
        raise Unprintable(f'no statement writes the attribute {code} ({type(attribute).__name__})')
    if code == Attribute.CODE.BGP_PREFIX_SID and _srv6(attribute):
        return ['bgp-prefix-sid-srv6', *_srv6(attribute)]
    if code == Attribute.CODE.EXTENDED_COMMUNITY:
        # as their bytes: the text of an extended community depends on whether its class was
        # imported, and one of them (bandwidth) prints a word no parser reads
        hexes = ['0x' + bytes(each.community).hex() for each in attribute.communities]
        return ['extended-community', Syntax('['), *hexes, Syntax(']')]
    text = str(attribute)
    if not text and code != Attribute.CODE.ATOMIC_AGGREGATE:
        # an empty community list or as-path prints as nothing, and reads back from brackets
        text = '[ ]'
    return [ATTRIBUTE_KEYWORDS[code], *_words(text)]


def _words(text: str) -> list[str]:
    """The words the lexer makes of text an attribute prints: `300,` is two words."""
    statement = lex_command(f'{text};')[0]
    return [Syntax(token.word) if token.word in _STRUCTURE else token.word for token in statement.words]


def _srv6(attribute: Any) -> list[str]:
    """`( l3-service <sid> <behavior> [ <structure> ] )`, or nothing for a prefix SID without SRv6."""
    from exabgp.bgp.message.update.attribute.sr.srv6.l2service import Srv6L2Service
    from exabgp.bgp.message.update.attribute.sr.srv6.l3service import Srv6L3Service

    services = [each for each in attribute.sr_attrs if isinstance(each, (Srv6L2Service, Srv6L3Service))]
    if not services:
        return []
    if len(services) != 1 or len(services[0].subtlvs) != 1:
        raise Unprintable('only one SRv6 service with one SID is printed back')
    service = 'l3-service' if isinstance(services[0], Srv6L3Service) else 'l2-service'
    information = services[0].subtlvs[0]
    words = [Syntax('('), service, str(information.sid), f'0x{information.behavior:x}']
    for structure in information.subsubtlvs:
        fields = (
            structure.loc_block_len,
            structure.loc_node_len,
            structure.func_len,
            structure.arg_len,
            structure.tpose_len,
            structure.tpose_offset,
        )
        words.append(Syntax('['))
        for index, field in enumerate(fields):
            words.extend(([Syntax(',')] if index else []) + [str(field)])
        words.append(Syntax(']'))
    return words + [Syntax(')')]


def attribute_words(route: Route) -> list[str]:
    """The keyword and value pairs of a route's attributes, the next-hop first."""
    # legacy: the first next-hop given is the NEXT_HOP attribute (the first attribute of a code
    # wins), the last is the route's next-hop; two statements say it when the two differ
    words: list[str] = []
    attribute = route.attributes.get(Attribute.CODE.NEXT_HOP)
    first = None if attribute is None else str(attribute)
    last = None if route.nexthop is IP.NoNextHop else 'self' if route.nexthop.SELF else str(route.nexthop)
    for nexthop in dict.fromkeys(each for each in (first, last) if each is not None):
        words.extend(['next-hop', nexthop])
    for code, attribute in route.attributes.items():
        if code != Attribute.CODE.NEXT_HOP:
            words.extend(_attribute_words(code, attribute))
    return words


def route_words(route: Route) -> list[str]:
    """`<prefix> [rd ..] [label ..] [path-information ..] next-hop .. <attributes>`."""
    from exabgp.bgp.message.notification import Notify

    nlri: Any = route.nlri
    try:
        words = [nlri.cidr.prefix()]
    except Notify as exc:
        raise Unprintable(f'the route can not be shown: {exc}') from None
    if isinstance(nlri, IPVPN) and nlri._has_rd:
        words.extend(['rd', repr(nlri.rd).split()[-1]])
    if isinstance(nlri, Label) and nlri._has_labels:
        words.extend(['label', Syntax('['), *(str(label) for label in nlri.labels.labels), Syntax(']')])
    if nlri.path_info is not PathInfo.DISABLED:
        words.extend(['path-information', repr(nlri.path_info).split()[-1]])
    return words + attribute_words(route)


# --------------------------------------------------------------------------- split and NLRI type


def split(route: Route) -> Iterator[Route]:
    """The more specifics a route with `split /<len>` stands for, or the route itself."""
    if Attribute.CODE.INTERNAL_SPLIT not in route.attributes:
        yield route
        return
    nlri: Any = route.nlri
    cut = cast(int, route.attributes[Attribute.CODE.INTERNAL_SPLIT])
    if nlri.cidr.mask >= cut:
        yield route
        return
    afi, safi = nlri.afi, nlri.safi
    increment = pow(2, afi.mask() - cut)
    ip = int.from_bytes(bytes(nlri.cidr.packed_cidr()), 'big')
    kwargs: dict[str, object] = {}
    if safi.has_path():
        kwargs['path_info'] = nlri.path_info
    if isinstance(nlri, Label):
        kwargs['labels'] = nlri.labels
    if isinstance(nlri, IPVPN):
        kwargs['rd'] = nlri.rd
    klass = nlri.__class__
    for _ in range(pow(2, cut - nlri.cidr.mask)):
        packed = ip.to_bytes(IP.length(afi), 'big')
        yield Route(
            klass.from_cidr(CIDR.create_cidr(packed, cut), afi, safi, **kwargs), route.attributes, nexthop=route.nexthop
        )
        ip += increment


def normalize(nlri: NLRI) -> NLRI:
    """The smallest NLRI class holding what the NLRI has: IPVPN with an RD, Label with labels, else INET."""
    if not isinstance(nlri, INET):
        return nlri
    has_rd = isinstance(nlri, IPVPN) and nlri._has_rd
    has_label = isinstance(nlri, Label) and nlri._has_labels
    target: type[INET]
    if has_rd:
        target, safi = IPVPN, SAFI.mpls_vpn
        if isinstance(nlri, IPVPN) and nlri.safi == safi:
            return nlri
    elif has_label:
        target, safi = Label, SAFI.nlri_mpls
        if isinstance(nlri, Label) and not isinstance(nlri, IPVPN) and nlri.safi == safi:
            return nlri
    else:
        target, safi = INET, IP.tosafi(nlri.cidr.prefix().split('/')[0])
        if type(nlri) is INET:  # noqa: E721 - the exact class, a subclass is to be rebuilt
            return nlri
    kwargs: dict[str, Any] = {}
    if has_label:
        kwargs['labels'] = cast(Label, nlri).labels
    if has_rd:
        kwargs['rd'] = cast(IPVPN, nlri).rd
    return target.from_cidr(nlri.cidr, nlri.afi, safi, nlri.path_info, **kwargs)


def finish(routes: list[Route]) -> list[Route]:
    """Split, then give each NLRI its class, as a static section does when it closes."""
    finished = []
    for route in routes:
        for each in split(route):
            each.nlri = normalize(each.nlri)
            finished.append(each)
    return finished


# --------------------------------------------------------------------------- the blocks


def store_routes(values: dict[str, Any], routes: list[Route], context: ReadContext) -> None:
    context.routes.extend(routes)


def _store_value(keyword: str) -> Any:
    def store(values: dict[str, Any], value: Any, context: ReadContext) -> None:
        values.setdefault('_values', []).append((keyword, value))

    return store


class NestedPrefix(Type[IPRange]):
    name = 'prefix'

    def parse(self, words: Words) -> IPRange:
        return bgp.Prefix().parse(words)

    def render(self, value: IPRange) -> list[str]:
        return bgp.Prefix().render(value)

    def hint(self) -> str:
        return '<prefix>'

    def examples(self) -> list[str]:
        return ['10.0.0.0/24']

    def shape(self) -> Shape:
        return shape.IP_PREFIX


def _nested(prefix: IPRange, values: dict[str, Any], context: ReadContext) -> list[Route]:
    settings = INETSettings()
    settings.cidr = CIDR.create_cidr(prefix.pack_ip(), prefix.mask)
    settings.afi = IP.toafi(prefix.top())
    settings.safi = SAFI.mpls_vpn
    settings.action = Action.ANNOUNCE
    collected = Collected(settings)
    for keyword, value in values.get('_values', []):
        collected.apply(keyword, value)
    klass: type[INET]
    if settings.rd is not None:
        klass, settings.safi = IPVPN, SAFI.mpls_vpn
    elif settings.labels is not None:
        klass, settings.safi = Label, SAFI.nlri_mpls
    else:
        klass, settings.safi = INET, IP.tosafi(settings.cidr.prefix().split('/')[0])
    routes = finish([Route(klass.from_settings(settings), collected.attributes, nexthop=settings.nexthop)])
    context.routes.extend(routes)
    return routes


NESTED_ROUTE = Block(
    'route',
    field='_nested',
    build=_nested,
    keep=Keep.EXTEND,
    name=NestedPrefix(),
    key='prefix',
    doc='a route, its values one per statement',
    children=tuple(
        Leaf(keyword, spec.type, field=keyword, store=_store_value(keyword), doc=spec.doc)
        for keyword, spec in ROUTE_VALUES.items()
    ),
)


def static_block(extra: tuple[Leaf, ...]) -> Block:
    """The static section, with the statements declared elsewhere (`rtc`, in announce.py)."""
    return Block(
        'static',
        field='static',
        doc='routes to announce',
        children=STATIC_CHILDREN + extra,
    )


STATIC_CHILDREN = (
    Leaf('route', RouteLine(), field='_routes', store=store_routes, doc='a route, on one line', multiple=True),
    Leaf(
        'attributes',
        AttributesLine(),
        field='_attributes',
        store=store_routes,
        multiple=True,
        doc='the same attributes for several prefixes',
    ),
    # legacy: 3.4 wrote `attribute`, still read as `attributes`
    Leaf(
        'attribute',
        AttributesLine(),
        field='_attribute',
        store=store_routes,
        multiple=True,
        doc='the same attributes for several prefixes, as attributes',
    ),
    NESTED_ROUTE,
)
