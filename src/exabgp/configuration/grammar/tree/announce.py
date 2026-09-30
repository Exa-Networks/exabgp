"""announce.py

    announce {
        ipv4 { unicast <prefix> next-hop <ip> [<attribute> <value> ...]; mpls-vpn ...; rtc ...; }
        ipv6 { unicast ...; nlri-mpls ...; mpls-vpn ...; }
    }
    static { rtc origin-as <asn> route-target <rt> | default next-hop <ip> [...]; }

The families of an `announce` block read their values with the rules the legacy parser gave
them, which are not quite those of `static`: `next-hop self` is IPv4 whatever the family,
`med` and `local-preference` are capped at 32 bits, and a list of keywords which static
routes take are refused, whatever their value (see REFUSED).

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute import MED, AttributeCollection, LocalPreference, NextHop, NextHopSelf
from exabgp.bgp.message.update.nlri import CIDR, INET, IPVPN, RTC, Label
from exabgp.bgp.message.update.nlri.settings import INETSettings, RTCSettings
from exabgp.configuration.grammar import shape
from exabgp.configuration.grammar.context import ReadContext
from exabgp.configuration.grammar.error import ConfigError
from exabgp.configuration.grammar.nodes import Block, Leaf
from exabgp.configuration.grammar.section import Kept, Store, Values
from exabgp.configuration.grammar.shape import Shape
from exabgp.configuration.grammar.tree.l2vpn import VPLSLine
from exabgp.configuration.grammar.tree.sr_policy import SRPolicyLine
from exabgp.configuration.grammar.tree.static import (
    ROUTE_VALUES,
    ROUTES,
    RouteValue,
    Unprintable,
    action,
    attribute_words,
    normalize,
    route_words,
    static_block,
    value_fields,
)
from exabgp.configuration.grammar.types import bgp
from exabgp.configuration.grammar.types.base import Type
from exabgp.configuration.grammar.types.network import ASN_WORD
from exabgp.configuration.grammar.types.route import RouteStatement, Target
from exabgp.configuration.grammar.types.word import Number, Word
from exabgp.configuration.grammar.words import Words
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP, IPSelf
from exabgp.rib.route import Route

VALUE_MAX = 0xFFFFFFFF  # med and local-preference, as the announce validators cap them
ANNOUNCED = '_announced'  # the routes of an address family block, until the block closes


class Refused(Type[Any]):
    """A keyword the legacy parser accepts and can never use: every value of it is refused.

    legacy: the announce families declare `name`, `split`, `atomic-aggregate`, ... with
    validators which return a string, a number or an address where an attribute is needed,
    and the route can not be built. `path-information` reads an address where a path id is
    needed. They are refused here up front, which is what the legacy parser ends up doing.
    """

    def __init__(self, name: str) -> None:
        self.name = name

    def parse(self, words: Words) -> Any:
        raise ConfigError(words.where(), f'{self.name} can not be used in an announce family')

    def render(self, value: Any) -> list[str]:
        raise ValueError(f'{self.name} is never read, so never printed')

    def hint(self) -> str:
        return ''

    def examples(self) -> list[str]:
        return []

    def shape(self) -> Shape:
        return shape.REFUSED


class AnnounceNextHop(Type[tuple[IP | IPSelf, NextHop | NextHopSelf]]):
    """An address, or `self`, which is the IPv4 local address whatever the family of the route."""

    name = 'next-hop'

    def parse(self, words: Words) -> tuple[IP | IPSelf, NextHop | NextHopSelf]:
        where = words.where()
        word = words.word()
        if word.lower() == 'self':
            return IPSelf(AFI.ipv4), NextHopSelf(AFI.ipv4)
        try:
            ip = IP.from_string(word)
            return ip, NextHop.from_string(ip.top())
        except (OSError, IndexError, ValueError):
            raise ConfigError(where, f"'{word}' is not a valid next-hop", expected=['<ip>', 'self']) from None

    def render(self, value: tuple[IP | IPSelf, NextHop | NextHopSelf]) -> list[str]:
        return ['self'] if isinstance(value[0], IPSelf) else [str(value[0])]

    def hint(self) -> str:
        return '<ip>|self'

    def examples(self) -> list[str]:
        return ['10.0.0.2', 'self']

    def shape(self) -> Shape:
        return shape.union(shape.IP_ADDRESS, shape.enumeration('self'))


def _capped(name: str, make: Any) -> Any:
    def convert(word: str) -> Any:
        if not word.isdigit():
            raise ValueError(f"'{word}' is not a valid {name}, it is a non-negative integer")
        if int(word) > VALUE_MAX:
            raise ValueError(f'{int(word)} exceeds maximum {name} value ({VALUE_MAX})')
        return make(int(word))

    return convert


REFUSED = (
    'atomic-aggregate',
    'originator-id',
    'cluster-list',
    'aigp',
    'attribute',
    'name',
    'split',
    'watchdog',
    'withdraw',
)

# the values of an IP route in an announce family, before the per family additions
IP_VALUES: dict[str, RouteValue] = {
    'next-hop': RouteValue(
        AnnounceNextHop(), Target.NEXTHOP_ATTRIBUTE, doc='the next-hop, or self for the IPv4 local address'
    ),
    'origin': ROUTE_VALUES['origin'],
    'otc': ROUTE_VALUES['otc'],
    'med': RouteValue(
        Number('med', ((0, MED.MAX),), convert=_capped('MED', MED.from_int), examples=['0', '100']),
        Target.ATTRIBUTE,
        doc=ROUTE_VALUES['med'].type.shape().description,
    ),
    'as-path': ROUTE_VALUES['as-path'],
    'local-preference': RouteValue(
        Number(
            'local-preference',
            ((0, LocalPreference.MAX),),
            convert=_capped('local-preference', LocalPreference.from_int),
            examples=['100'],
        ),
        Target.ATTRIBUTE,
        doc=ROUTE_VALUES['local-preference'].type.shape().description,
    ),
    'aggregator': ROUTE_VALUES['aggregator'],
    'community': ROUTE_VALUES['community'],
    'large-community': ROUTE_VALUES['large-community'],
    'extended-community': ROUTE_VALUES['extended-community'],
    **{keyword: RouteValue(Refused(keyword), Target.ATTRIBUTE) for keyword in REFUSED},
}
PATH_VALUES = {**IP_VALUES, 'path-information': RouteValue(Refused('path-information'), Target.NLRI, 'path_info')}
LABEL_VALUES = {**PATH_VALUES, 'label': ROUTE_VALUES['label']}
VPN_VALUES = {**LABEL_VALUES, 'rd': ROUTE_VALUES['rd']}


class _RTCNextHop(Type[Any]):
    """The next-hop of an RTC route: an address, or `self` for the IPv4 local address; no attribute."""

    name = 'next-hop'

    def parse(self, words: Words) -> Any:
        where = words.where()
        word = words.word()
        if word.lower() == 'self':
            return NextHopSelf(AFI.ipv4)
        try:
            return IP.from_string(word)
        except (OSError, IndexError, ValueError):
            raise ConfigError(where, f"'{word}' is not a valid next-hop", expected=['<ip>', 'self']) from None

    def render(self, value: Any) -> list[str]:
        return ['self'] if isinstance(value, NextHopSelf) else [str(value)]

    def hint(self) -> str:
        return '<ip>|self'

    def examples(self) -> list[str]:
        return ['10.0.0.2', 'self']

    def shape(self) -> Shape:
        return shape.union(shape.IP_ADDRESS, shape.enumeration('self'))


# a route target as exabgp prints it
ROUTE_TARGET = shape.string(pattern=r'target:[^:\s]+:\d+')


def _route_target(word: str) -> Any:
    from exabgp.bgp.message.update.attribute.community.extended.rt import RouteTarget

    kind, _, rest = word.partition(':')
    if kind != 'target' and rest.count(':'):
        raise ValueError(f"'{word}' is not a route target, it is <asn>:<number> or <ip>:<number>")
    community = bgp.extended_community(word if kind == 'target' else f'target:{word}')
    if not isinstance(community, RouteTarget):
        raise ValueError(f"'{word}' is not a route target, it is <asn>:<number> or <ip>:<number>")
    return community


class _Default(Type[bool]):
    """`default`: the zero-length route target, which takes no value."""

    name = 'default'

    def parse(self, words: Words) -> bool:
        return True

    def render(self, value: bool) -> list[str]:
        return []

    def hint(self) -> str:
        return ''

    def examples(self) -> list[str]:
        return ['']

    def shape(self) -> Shape:
        return shape.empty()


RTC_VALUES: dict[str, RouteValue] = {
    'next-hop': RouteValue(_RTCNextHop(), Target.NLRI, 'nexthop', 'the next-hop, or self for the IPv4 local address'),
    'origin-as': RouteValue(ASN_WORD, Target.NLRI, 'origin_as', 'the AS of the route target membership, RFC 4684'),
    'route-target': RouteValue(
        Word('route-target', '<asn>:<n>|<ip>:<n>', _route_target, ['65000:1'], shape=ROUTE_TARGET),
        Target.NLRI,
        'route_target',
        'the route target the membership is for',
    ),
    'default': RouteValue(
        _Default(), Target.NLRI, 'default', 'the default route target membership, every route target'
    ),
    **{keyword: value for keyword, value in IP_VALUES.items() if keyword not in ('split', 'aigp', 'otc', 'next-hop')},
}


@dataclass(frozen=True)
class AnnounceSafi:
    """What an announce family reads, and the NLRI it builds."""

    values: dict[str, RouteValue]
    nlri: Any  # the NLRI class, built with from_settings()
    prefix: bool = True  # the route starts with its prefix


ANNOUNCE_SAFIS: dict[str, AnnounceSafi] = {
    'unicast': AnnounceSafi(PATH_VALUES, INET),
    'multicast': AnnounceSafi(IP_VALUES, INET),
    'nlri-mpls': AnnounceSafi(LABEL_VALUES, Label),
    'mpls-vpn': AnnounceSafi(VPN_VALUES, IPVPN),
    'rtc': AnnounceSafi(RTC_VALUES, RTC, prefix=False),
}


class AnnounceLine(RouteStatement):
    """`[<prefix>] <keyword> <value> ...` of one family of one address family."""

    def __init__(self, afi: AFI, safi: SAFI, announce_safi: AnnounceSafi) -> None:
        self.afi = afi
        self.safi = safi
        self.announce_safi = announce_safi
        self.name = f'{afi.name()} {safi.name()} route'

    def parse(self, words: Words) -> list[Route]:
        settings: Any = RTCSettings() if self.announce_safi.nlri is RTC else INETSettings()
        settings.action = action(words)
        if self.announce_safi.prefix:
            # legacy: a prefix of the other address family is taken, the route is of the block's
            prefix = bgp.Prefix().parse(words)
            settings.cidr = CIDR.create_cidr(prefix.pack_ip(), prefix.mask.value)
            settings.afi, settings.safi = self.afi, self.safi
        attributes = AttributeCollection()
        for _, spec in self.keywords(words, self.announce_safi.values):
            _apply(settings, attributes, spec, spec.type.parse(words))
        try:
            nlri = self.announce_safi.nlri.from_settings(settings)
        except ValueError as exc:
            raise ConfigError(words.where(), str(exc)) from None
        return [Route(nlri, attributes, nexthop=settings.nexthop)]

    def printed(self, route: Route) -> list[str]:
        return announce_words(route)

    def hint(self) -> str:
        return '<prefix> next-hop <ip>|self [<attribute> <value> ...]' if self.announce_safi.prefix else '...'

    def examples(self) -> list[str]:
        return []

    def shape(self) -> Shape:
        fields = value_fields(self.announce_safi.values)
        return (
            shape.container(('prefix', bgp.Prefix().shape()), *fields)
            if self.announce_safi.prefix
            else shape.container(*fields)
        )


def _apply(settings: Any, attributes: AttributeCollection, spec: RouteValue, value: Any) -> None:
    if spec.target == Target.NLRI:
        settings.set(spec.field, value)
    elif spec.target == Target.NEXTHOP_ATTRIBUTE:
        ip, attribute = value
        if ip:
            settings.nexthop = ip
        if attribute:
            attributes.add(attribute)
    else:
        attributes.add(value)


class AnnouncedStore(Store):
    """The routes of an address family, kept by its block until it closes."""

    routes = True

    def keep(self, values: Values, value: list[Route], context: ReadContext) -> None:
        values.setdefault(ANNOUNCED, []).extend(value)


class AddressFamilySection(Kept):
    """legacy: the routes of an address family join the others when its block closes."""

    def build(self, name: Any, values: Values, context: ReadContext) -> Values:
        context.routes.extend(values.pop(ANNOUNCED, []))
        return values


ANNOUNCED_STORE = AnnouncedStore()
ADDRESS_FAMILY = AddressFamilySection()


def _refused_family(keyword: str) -> Leaf:
    """legacy: `labeled-unicast` is named as a family and refused as an unknown command."""
    return Leaf(keyword, Refused(keyword), field='_refused')


def _address_block(keyword: str, afi: AFI, safi_keywords: tuple[str, ...]) -> Block:
    from exabgp.configuration.grammar.tree.flow import AnnounceFlowLine
    from exabgp.configuration.grammar.tree.select import MUP_TYPES, MVPN_TYPES, SelectLine, mup_values

    return Block(
        keyword,
        field=keyword,
        section=ADDRESS_FAMILY,
        doc=f'the {keyword} routes, by subsequent address family',
        children=(
            *(
                Leaf(
                    safi_keyword,
                    AnnounceLine(afi, SAFI.from_string(safi_keyword), ANNOUNCE_SAFIS[safi_keyword]),
                    field=f'_{safi_keyword}',
                    store=ANNOUNCED_STORE,
                    multiple=True,
                    doc=f'a {keyword} {safi_keyword} route',
                )
                for safi_keyword in safi_keywords
            ),
            *(
                Leaf(
                    safi_keyword,
                    AnnounceFlowLine(afi, SAFI.from_string(safi_keyword)),
                    field=f'_{safi_keyword}',
                    store=ANNOUNCED_STORE,
                    multiple=True,
                    doc=f'a {keyword} {safi_keyword} rule, RFC 8955',
                )
                for safi_keyword in ('flow', 'flow-vpn')
            ),
            Leaf(
                'mup',
                SelectLine(afi, SAFI.mup, MUP_TYPES, mup_values()),
                field='_mup',
                store=ANNOUNCED_STORE,
                multiple=True,
                doc='a Mobile User Plane route, draft-mpmz-bess-mup-safi',
            ),
            Leaf(
                'mcast-vpn',
                SelectLine(afi, SAFI.mcast_vpn, MVPN_TYPES, IP_VALUES),
                field='_mcast-vpn',
                store=ANNOUNCED_STORE,
                multiple=True,
                doc='a multicast VPN route, RFC 6514',
            ),
            Leaf(
                'sr-policy',
                SRPolicyLine(afi),
                field='_sr-policy',
                store=ANNOUNCED_STORE,
                multiple=True,
                doc='an SR policy route, RFC 9830',
            ),
            _refused_family('labeled-unicast'),
        ),
    )


IPV4 = _address_block(
    'ipv4',
    AFI.ipv4,
    ('unicast', 'multicast', 'nlri-mpls', 'mpls-vpn', 'rtc'),
)
IPV6 = _address_block(
    'ipv6',
    AFI.ipv6,
    ('unicast', 'multicast', 'nlri-mpls', 'mpls-vpn'),
)
L2VPN = Block(
    'l2vpn',
    field='l2vpn',
    section=ADDRESS_FAMILY,
    doc='the l2vpn routes',
    children=(
        Leaf('vpls', VPLSLine(), field='_vpls', store=ANNOUNCED_STORE, multiple=True, doc='a VPLS route, RFC 4761'),
    ),
)

ANNOUNCE_BLOCK = Block('announce', field='announce', doc='routes by address family', children=(IPV4, IPV6, L2VPN))


def rtc_words(route: Route) -> list[str]:
    """`default|origin-as <asn> route-target <rt> next-hop <ip>|self <attributes>`."""
    nlri: Any = route.nlri
    words = ['default'] if nlri.rt is None else ['origin-as', str(nlri.origin), 'route-target', str(nlri.rt)]
    if route.nexthop is not IP.NoNextHop:
        words.extend(['next-hop', 'self' if route.nexthop.SELF else str(route.nexthop)])
    return words + attribute_words(route)


def announce_words(route: Route) -> list[str]:
    """What follows the family keyword of an announce family: the route line, or the RTC line."""
    if isinstance(route.nlri, RTC):
        return rtc_words(route)
    return route_words(route)


def announce_family(route: Route) -> tuple[str, str] | None:
    """(address family, family) of the announce block which prints a route no static line can.

    A static line picks the NLRI class from the rd and labels it has, and the address family and
    unicast or multicast from its prefix: a route built otherwise is printed where it came from.
    """
    nlri: Any = route.nlri
    if isinstance(nlri, RTC) or not isinstance(nlri, INET):
        return None
    try:
        prefix = nlri.cidr.prefix().split('/')[0]
    except Notify as exc:
        raise Unprintable(f'the route can not be shown: {exc}') from None
    if normalize(nlri) is nlri and nlri.afi == IP.toafi(prefix):
        if isinstance(nlri, Label) or nlri.safi == IP.tosafi(prefix):
            return None
    safi_keyword = (
        'mpls-vpn' if isinstance(nlri, IPVPN) else 'nlri-mpls' if isinstance(nlri, Label) else nlri.safi.name()
    )
    return nlri.afi.name(), safi_keyword


STATIC = static_block(
    (
        Leaf(
            'rtc',
            AnnounceLine(AFI.ipv4, SAFI.rtc, ANNOUNCE_SAFIS['rtc']),
            field='_rtc',
            store=ROUTES,
            multiple=True,
            doc='a route target membership route, RFC 4684',
        ),
        Leaf(
            'sr-policy',
            SRPolicyLine(None),
            field='_sr-policy',
            store=ROUTES,
            multiple=True,
            doc='an SR policy route',
        ),
    )
)
