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

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Callable, Iterator, Mapping, cast

from exabgp.bgp.message import Action
from exabgp.bgp.message.update.attribute.internal import Split as InternalSplit
from exabgp.bgp.message.update.attribute import Attribute, AttributeCollection
from exabgp.bgp.message.update.attribute.community import Communities, ExtendedCommunities, LargeCommunities
from exabgp.bgp.message.update.nlri import CIDR, INET, IPVPN, Label
from exabgp.bgp.message.update.nlri.empty import Empty
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier import PathInfo
from exabgp.bgp.message.update.nlri.settings import INETSettings
from exabgp.configuration.grammar import shape
from exabgp.configuration.grammar.context import ReadContext
from exabgp.configuration.grammar.error import ROUTE_ERRORS
from exabgp.configuration.grammar.lexer import lex_command
from exabgp.configuration.grammar.nodes import Block, Keep, Leaf
from exabgp.configuration.grammar.section import Section, Store, Values
from exabgp.configuration.grammar.shape import Shape
from exabgp.configuration.grammar.types import bgp
from exabgp.configuration.grammar.types.base import Syntax, Type, WordOrSyntax
from exabgp.logger import lazymsg, log
from exabgp.configuration.grammar.types.route import RouteStatement, Target
from exabgp.configuration.grammar.words import Words
from exabgp.configuration.grammar.types.word import decimal
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP, IPRange
from exabgp.rib.route import Route

# a route line holds a handful of attributes, each given once or a few times


@dataclass(frozen=True)
class RouteValue:
    type: Type[Any]
    target: Target  # NLRI, NEXTHOP_ATTRIBUTE or ATTRIBUTE
    field: str = ''  # the INETSettings field, for an 'nlri' target
    doc: str = ''
    adds: bool = False  # given again, adds to the first (a list attribute, LIST_ATTRIBUTES)


ROUTE_VALUES: dict[str, RouteValue] = {
    'next-hop': RouteValue(
        bgp.NextHopType(), Target.NEXTHOP_ATTRIBUTE, doc='the next-hop, or self for the local address'
    ),
    'path-information': RouteValue(bgp.PATH_INFORMATION, Target.NLRI, 'path_info', 'the ADD-PATH path identifier'),
    'rd': RouteValue(bgp.ROUTE_DISTINGUISHER, Target.NLRI, 'rd', 'the route distinguisher, making it a VPN route'),
    'route-distinguisher': RouteValue(bgp.ROUTE_DISTINGUISHER, Target.NLRI, 'rd'),
    'label': RouteValue(bgp.LabelsType(), Target.NLRI, 'labels', 'the MPLS label stack'),
    'bgp-prefix-sid': RouteValue(bgp.PrefixSidType(), Target.ATTRIBUTE),
    'bgp-prefix-sid-srv6': RouteValue(bgp.PrefixSidSrv6Type(), Target.ATTRIBUTE),
    'attribute': RouteValue(
        bgp.HexAttribute(),
        Target.ATTRIBUTE,
        doc='any attribute, as its wire bytes, but 14, 15, 17 and 18, which exabgp makes',
    ),
    'origin': RouteValue(bgp.ORIGIN, Target.ATTRIBUTE),
    'otc': RouteValue(bgp.OTC_VALUE, Target.ATTRIBUTE, doc='RFC 9234 Only-to-Customer'),
    'med': RouteValue(bgp.MED_VALUE, Target.ATTRIBUTE),
    'as-path': RouteValue(bgp.ASPathType(), Target.ATTRIBUTE),
    'local-preference': RouteValue(bgp.LOCAL_PREFERENCE, Target.ATTRIBUTE),
    'atomic-aggregate': RouteValue(bgp.ATOMIC_AGGREGATE, Target.ATTRIBUTE),
    'aggregator': RouteValue(bgp.AggregatorType(), Target.ATTRIBUTE),
    'originator-id': RouteValue(bgp.ORIGINATOR_ID, Target.ATTRIBUTE),
    'cluster-list': RouteValue(bgp.ClusterListType(), Target.ATTRIBUTE),
    'community': RouteValue(bgp.COMMUNITIES, Target.ATTRIBUTE, adds=True),
    'large-community': RouteValue(bgp.LARGE_COMMUNITIES, Target.ATTRIBUTE, adds=True),
    'extended-community': RouteValue(bgp.ExtendedCommunitiesType(), Target.ATTRIBUTE, adds=True),
    'aigp': RouteValue(bgp.AIGP_VALUE, Target.ATTRIBUTE),
    'name': RouteValue(bgp.NAME, Target.ATTRIBUTE, doc='a name for the route, kept by exabgp'),
    'split': RouteValue(bgp.SPLIT, Target.ATTRIBUTE, doc='announce the prefix as its more specifics of this length'),
    'watchdog': RouteValue(bgp.WATCHDOG, Target.ATTRIBUTE, doc='the watchdog which announces and withdraws the route'),
    'withdraw': RouteValue(bgp.WITHDRAW, Target.ATTRIBUTE, doc='start with the route withdrawn'),
}


class Collected:
    """What the values of one route set: the NLRI settings and the attributes, in their order."""

    def __init__(self, settings: INETSettings) -> None:
        self.settings = settings
        self.attributes = AttributeCollection()

    def apply(self, spec: RouteValue, value: Any) -> None:
        if spec.target == Target.NLRI:
            self.settings.set(spec.field, value)
        elif spec.target == Target.NEXTHOP_ATTRIBUTE:
            ip, attribute = value
            # given twice, the first is the route's, address and attribute alike
            if first_next_hop(self.attributes, attribute):
                self.settings.nexthop = ip
        else:
            add_attribute(self.attributes, value)


# the attributes which are lists, by code, with what makes one of a list: given twice, the
# second adds to the first
LIST_ATTRIBUTES: dict[int, Callable[[list[Any]], Attribute]] = {
    Attribute.CODE.COMMUNITY: Communities.make_communities,
    Attribute.CODE.LARGE_COMMUNITY: LargeCommunities.make_large_communities,
    Attribute.CODE.EXTENDED_COMMUNITY: ExtendedCommunities.make_extended_communities,
}


# set while an API command is read (read.read_command): a helper written for 4.2 or 5.0 may
# repeat an attribute, and those releases kept the first, so a command warns where a file refuses
READING_COMMAND: ContextVar[bool] = ContextVar('reading_command', default=False)


def add_attribute(attributes: AttributeCollection, attribute: Attribute) -> None:
    """Add a configured attribute: a list one given twice is merged, any other is refused.

    The second of a repeated attribute was dropped without a word, `med 10 med 20` sent 10,
    `community 1:1 community 2:2` sent only 1:1. An API command still keeps the first, as
    4.2 and 5.0 did, but says which value it dropped.
    """
    existing = attributes.get(attribute.ID)
    if existing is None:
        attributes.add(attribute)
        return
    if attribute.ID not in LIST_ATTRIBUTES or attribute.GENERIC or existing.GENERIC:
        name = ATTRIBUTE_KEYWORDS.get(attribute.ID) or INTERNAL_KEYWORDS.get(
            attribute.ID, f'attribute 0x{attribute.ID:02x}'
        )
        if not READING_COMMAND.get():
            raise ValueError(f'{name} is given twice, it can be given once')
        log.warning(
            lazymsg(
                'api.attribute.repeated name={name} kept="{kept}" dropped="{dropped}"',
                name=name,
                kept=existing,
                dropped=attribute,
            ),
            'configuration',
        )
        return
    # a new attribute rather than the first changed: the first may be shared with other routes
    lists: Any = (existing, attribute)
    merged = LIST_ATTRIBUTES[attribute.ID](lists[0].communities + lists[1].communities)
    # rebuilt through add(), which keeps the order and clears what the collection cached
    rebuilt = [merged if code == attribute.ID else each for code, each in attributes.items()]
    for code in list(attributes):
        del attributes[code]
    for each in rebuilt:
        attributes.add(each)


def first_next_hop(attributes: AttributeCollection, attribute: Attribute) -> bool:
    """Keep the NEXT_HOP attribute unless one was given before, and say whether it was kept.

    The attribute kept the first `next-hop` and the address the last, so `next-hop self
    next-hop 1.2.3.4` made a route which said self and could not be packed. The first wins
    for both: 5.0 sent the first for IPv4 unicast, and a repeated attribute keeps the first.
    """
    if attribute.ID in attributes:
        return False
    attributes.add(attribute)
    return True


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


class RouteLine(RouteStatement):
    """`<prefix> <keyword> <value> ...`: one route, or its more specifics when split."""

    name = 'route'
    unknown = 'unknown command "{keyword}"'

    def parse(self, words: Words) -> list[Route]:
        prefix = bgp.Prefix().parse(words)
        settings = INETSettings()
        settings.cidr = CIDR.create_cidr(prefix.pack_ip(), prefix.mask.value)
        settings.afi = IP.toafi(prefix.top())
        settings.action = action(words)
        klass = _nlri_class(words, settings, prefix)
        collected = Collected(settings)
        for _, spec in self.keywords(words, ROUTE_VALUES):
            collected.apply(spec, spec.type.parse(words))
        route = Route(klass.from_settings(settings), collected.attributes, nexthop=settings.nexthop)
        return finish([route])

    def printed(self, route: Route) -> list[WordOrSyntax]:
        return route_words(route)

    def hint(self) -> str:
        return '<prefix> next-hop <ip>|self [<attribute> <value> ...]'

    def examples(self) -> list[str]:
        return ['10.0.0.0/24 next-hop 10.0.0.1', '10.0.0.0/24 next-hop self']

    def shape(self) -> Shape:
        return shape.container(('prefix', bgp.Prefix().shape()), *value_fields(ROUTE_VALUES))


class AttributesLine(RouteStatement):
    """`<attribute> <value> ... nlri <prefix> ...`: the same attributes for every prefix."""

    name = 'attributes'
    unknown = 'unknown command "{keyword}"'

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
        for _, spec in self.keywords(words, ROUTE_VALUES, stop='nlri'):
            collected.apply(spec, spec.type.parse(words))
        routes = []
        for _ in range(bgp.MAX_LIST_ITEMS):
            if words.at_end():
                break
            each = bgp.Prefix().parse(words)
            settings_copy = INETSettings(**{name: getattr(settings, name) for name in settings.__dataclass_fields__})
            settings_copy.cidr = CIDR.create_cidr(each.pack_ip(), each.mask.value)
            settings_copy.action = Action.UNSET
            routes.append(Route(klass.from_settings(settings_copy), collected.attributes, nexthop=settings.nexthop))
        if not routes and collected.attributes:
            # the next-hop is kept: a group shares it with routes which give none of their own
            return [Route(Empty(AFI.ipv4, SAFI.unicast), collected.attributes, nexthop=settings.nexthop)]
        return finish(routes)

    def printed(self, route: Route) -> list[WordOrSyntax]:
        return attribute_words(route)

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
        return [IPRange.make_range(ip, decimal(mask) if mask else (128 if ':' in ip else 32))]
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
# the keyword of an internal attribute printed its own way (one_attribute_words), for messages:
# without it, `split` given twice was said to be `attribute 0xfffd`
INTERNAL_KEYWORDS: dict[int, str] = {
    Attribute.CODE.INTERNAL_SPLIT: 'split',
    Attribute.CODE.INTERNAL_WITHDRAW: 'withdraw',
}
_STRUCTURE = frozenset({'[', ']', '(', ')', ','})


class Unprintable(ValueError):
    """A route holding a value no statement writes back (an SRv6 prefix SID)."""


def one_attribute_words(code: int, attribute: Any) -> list[WordOrSyntax]:
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
        return [
            'extended-community',
            Syntax('['),
            *(community_word(each) for each in attribute.communities),
            Syntax(']'),
        ]
    text = str(attribute)
    if not text and code != Attribute.CODE.ATOMIC_AGGREGATE:
        # an empty community list or as-path prints as nothing, and reads back from brackets
        text = '[ ]'
    return [ATTRIBUTE_KEYWORDS[code], *text_words(text)]


def read_back(value_type: Type[Any], text: str) -> Any:
    """`text` read as one value of the type, None when it is not exactly one such value."""
    statement = lex_command(f'value {text};')[0]
    words = Words(statement.words[1:], statement.tokens[-1], ReadContext())
    value: Any = None
    try:
        value = value_type.parse(words)
    except ROUTE_ERRORS as exc:  # a ConfigError is a ValueError
        # the answer asked for: the text is not such a value, and the caller prints another
        log.debug(lazymsg('grammar.read_back refused={text} reason={exc}', text=text, exc=exc), 'configuration')
    return value if value is not None and not words.left() else None


def community_word(community: Any) -> str:
    """An extended community as its text where the text reads back to it, as its bytes otherwise.

    The text depends on whether the class of the community was imported, and some texts are
    no word a parser reads (a traffic rate, `rate-limit:0`), so it is read back to be kept.
    """
    packed = bytes(community.community)
    text = str(community)
    if not text or any(char.isspace() for char in text):
        return '0x' + packed.hex()  # printed, it would be quoted as one word: not what was read
    read = read_back(ROUTE_VALUES['extended-community'].type, f'[ {text} ]')
    if read is not None and [bytes(each.community) for each in read.communities] == [packed]:
        return text
    return '0x' + packed.hex()


def text_words(text: str) -> list[WordOrSyntax]:
    """The words the lexer makes of text an attribute prints: `300,` is two words."""
    statement = lex_command(f'{text};')[0]
    return [Syntax(token.word) if token.word in _STRUCTURE else token.word for token in statement.words]


def _srv6(attribute: Any) -> list[WordOrSyntax]:
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
    words: list[WordOrSyntax] = [Syntax('('), service, str(information.sid), f'0x{information.behavior:x}']
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


def attribute_words(route: Route) -> list[WordOrSyntax]:
    """The keyword and value pairs of a route's attributes, the next-hop first."""
    # legacy: the first next-hop given is the NEXT_HOP attribute (the first attribute of a code
    # wins), the last is the route's next-hop; two statements say it when the two differ
    words: list[WordOrSyntax] = []
    attribute = route.attributes.get(Attribute.CODE.NEXT_HOP)
    first = None if attribute is None else str(attribute)
    last = None if route.nexthop is IP.NoNextHop else 'self' if route.nexthop.SELF else str(route.nexthop)
    for nexthop in dict.fromkeys(each for each in (first, last) if each is not None):
        words.extend(['next-hop', nexthop])
    for code, attribute in route.attributes.items():
        if code != Attribute.CODE.NEXT_HOP:
            words.extend(one_attribute_words(code, attribute))
    return words


def route_words(route: Route) -> list[WordOrSyntax]:
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


# the more specifics one `split` may make: an IPv4 /16 into /32, where an IPv6 /32 into
# /128 would be 2**96 routes, more than any memory holds
MAX_SPLIT_ROUTES = pow(2, 16)


def _check_split(mask: int, cut: int, longest: int) -> None:
    """Refuse a split making no more specific of the prefix, or more than MAX_SPLIT_ROUTES of them."""
    if cut < mask:
        raise ValueError(f'split /{cut} is shorter than the prefix /{mask}, it makes no more specific of it')
    if cut > longest:
        raise ValueError(f'split /{cut} is longer than an address of the family, /{longest}')
    if pow(2, cut - mask) > MAX_SPLIT_ROUTES:
        raise ValueError(f'split /{cut} of a /{mask} makes more than {MAX_SPLIT_ROUTES} routes')


def split(route: Route) -> Iterator[Route]:
    """The more specifics a route with `split /<len>` stands for, or the route itself."""
    if Attribute.CODE.INTERNAL_SPLIT not in route.attributes:
        yield route
        return
    nlri: Any = route.nlri
    # the code is the class: only InternalSplit is stored under INTERNAL_SPLIT
    cut = cast(InternalSplit, route.attributes[Attribute.CODE.INTERNAL_SPLIT]).value
    if cut < nlri.cidr.mask and READING_COMMAND.get():
        # 4.2 and 5.0 sent the prefix itself, and a helper written for them may rely on it
        log.warning(lazymsg('api.split.ignored route={route} split=/{cut}', route=nlri, cut=cut), 'configuration')
        yield route
        return
    _check_split(nlri.cidr.mask, cut, nlri.afi.mask())
    if nlri.cidr.mask == cut:
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


class RoutesStore(Store):
    """The routes of a statement join those not yet taken by a neighbor."""

    routes = True

    def keep(self, values: Values, value: list[Route], context: ReadContext) -> None:
        context.routes.extend(value)


ROUTES = RoutesStore()


class RouteValueStore(Store):
    """A value of a route block, kept in order with its keyword: they apply one after the other."""

    def __init__(self, keyword: str) -> None:
        self.keyword = keyword

    def keep(self, values: Values, value: Any, context: ReadContext) -> None:
        values.setdefault('_values', []).append((self.keyword, value))


class NestedPrefix(Type[IPRange]):
    name = 'prefix'

    def parse(self, words: Words) -> IPRange:
        return bgp.Prefix().parse(words)

    def render(self, value: IPRange) -> list[WordOrSyntax]:
        return bgp.Prefix().render(value)

    def hint(self) -> str:
        return '<prefix>'

    def examples(self) -> list[str]:
        return ['10.0.0.0/24']

    def shape(self) -> Shape:
        return shape.IP_PREFIX


class NestedRouteSection(Section[list[Route]]):
    """`route <prefix> { ... }`: one route, its values one per statement."""

    def build(self, name: IPRange, values: Values, context: ReadContext) -> list[Route]:
        settings = INETSettings()
        settings.cidr = CIDR.create_cidr(name.pack_ip(), name.mask.value)
        settings.afi = IP.toafi(name.top())
        settings.safi = SAFI.mpls_vpn
        settings.action = Action.ANNOUNCE
        collected = Collected(settings)
        for keyword, value in values.get('_values', []):
            collected.apply(ROUTE_VALUES[keyword], value)
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
    section=NestedRouteSection(),
    keep=Keep.EXTEND,
    name=NestedPrefix(),
    key='prefix',
    doc='a route, its values one per statement',
    children=tuple(
        Leaf(keyword, spec.type, field=keyword, store=RouteValueStore(keyword), doc=spec.doc, adds=spec.adds)
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
    Leaf('route', RouteLine(), field='_routes', store=ROUTES, doc='a route, on one line', multiple=True),
    Leaf(
        'attributes',
        AttributesLine(),
        field='_attributes',
        store=ROUTES,
        multiple=True,
        doc='the same attributes for several prefixes',
    ),
    # legacy: 3.4 wrote `attribute`, still read as `attributes`
    Leaf(
        'attribute',
        AttributesLine(),
        field='_attribute',
        store=ROUTES,
        multiple=True,
        doc='the same attributes for several prefixes, as attributes',
    ),
    NESTED_ROUTE,
)
