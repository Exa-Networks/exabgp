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
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.update.attribute import LocalPreference, MED, NextHop, NextHopSelf
from exabgp.bgp.message.update.attribute import AttributeCollection
from exabgp.bgp.message.update.nlri import CIDR, INET, IPVPN, RTC, Label
from exabgp.bgp.message.update.nlri.settings import INETSettings, RTCSettings
from exabgp.configuration.grammar.error import ConfigError
from exabgp.configuration.grammar.nodes import Block, Leaf
from exabgp.configuration.grammar.tree.l2vpn import VPLSLine
from exabgp.configuration.grammar.tree.sr_policy import SRPolicyLine
from exabgp.configuration.grammar.tree.static import (
    MAX_ROUTE_VALUES,
    ROUTES,
    ROUTE_VALUES,
    RouteValue,
    Unprintable,
    action,
    attribute_words,
    normalize,
    route_words,
    static_block,
    store_routes,
)
from exabgp.configuration.grammar.types import bgp
from exabgp.configuration.grammar.types.base import Type
from exabgp.configuration.grammar.types.word import Word
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
    'next-hop': RouteValue(AnnounceNextHop(), 'nexthop'),
    'origin': ROUTE_VALUES['origin'],
    'otc': ROUTE_VALUES['otc'],
    'med': RouteValue(Word('med', '<number>', _capped('MED', MED.from_int), ['0', '100']), 'attribute'),
    'as-path': ROUTE_VALUES['as-path'],
    'local-preference': RouteValue(
        Word('local-preference', '<number>', _capped('local-preference', LocalPreference.from_int), ['100']),
        'attribute',
    ),
    'aggregator': ROUTE_VALUES['aggregator'],
    'community': ROUTE_VALUES['community'],
    'large-community': ROUTE_VALUES['large-community'],
    'extended-community': ROUTE_VALUES['extended-community'],
    **{keyword: RouteValue(Refused(keyword), 'attribute') for keyword in REFUSED},
}
PATH_VALUES = {**IP_VALUES, 'path-information': RouteValue(Refused('path-information'), 'nlri', 'path_info')}
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


RTC_VALUES: dict[str, RouteValue] = {
    'next-hop': RouteValue(_RTCNextHop(), 'nlri', 'nexthop'),
    'origin-as': RouteValue(Word('as-number', '<asn>', ASN.from_string, ['65000', '1.1']), 'nlri', 'origin_as'),
    'route-target': RouteValue(
        Word('route-target', '<asn>:<n>|<ip>:<n>', _route_target, ['65000:1']), 'nlri', 'route_target'
    ),
    'default': RouteValue(_Default(), 'nlri', 'default'),
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


class AnnounceLine(Type[list[Route]]):
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
            settings.cidr = CIDR.create_cidr(prefix.pack_ip(), prefix.mask)
            settings.afi, settings.safi = self.afi, self.safi
        attributes = AttributeCollection()
        for _ in range(MAX_ROUTE_VALUES):
            where = words.where()
            keyword = words.word()
            if not keyword:
                break
            spec = self.announce_safi.values.get(keyword)
            if spec is None:
                raise ConfigError(where, f"Unknown command '{keyword}'", expected=sorted(self.announce_safi.values))
            _apply(settings, attributes, spec, spec.type.parse(words))
        try:
            nlri = self.announce_safi.nlri.from_settings(settings)
        except ValueError as exc:
            raise ConfigError(words.where(), str(exc)) from None
        return [Route(nlri, attributes, nexthop=settings.nexthop)]

    def render(self, value: list[Route]) -> list[str]:
        return [word for route in value for word in announce_words(route)]

    def hint(self) -> str:
        return '<prefix> next-hop <ip>|self [<attribute> <value> ...]' if self.announce_safi.prefix else '...'

    def examples(self) -> list[str]:
        return []


def _apply(settings: Any, attributes: AttributeCollection, spec: RouteValue, value: Any) -> None:
    if spec.target == 'nlri':
        settings.set(spec.field, value)
    elif spec.target == 'nexthop':
        ip, attribute = value
        if ip:
            settings.nexthop = ip
        if attribute:
            attributes.add(attribute)
    else:
        attributes.add(value)


def _store_announced(values: dict[str, Any], routes: list[Route], context: dict[str, Any]) -> None:
    values.setdefault(ANNOUNCED, []).extend(routes)


def _address_family(name: Any, values: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    # legacy: the routes of an address family join the others when its block closes
    context.setdefault(ROUTES, []).extend(values.pop(ANNOUNCED, []))
    return values


def _refused_family(keyword: str) -> Leaf:
    """legacy: `labeled-unicast` is named as a family and refused as an unknown command."""
    return Leaf(keyword, Refused(keyword), field='_refused')


def _address_block(keyword: str, afi: AFI, safi_keywords: tuple[str, ...]) -> Block:
    from exabgp.configuration.grammar.tree.flow import AnnounceFlowLine
    from exabgp.configuration.grammar.tree.select import MUP_TYPES, MVPN_TYPES, SelectLine, mup_values

    return Block(
        keyword,
        field=keyword,
        build=_address_family,
        children=(
            *(
                Leaf(
                    safi_keyword,
                    AnnounceLine(afi, SAFI.from_string(safi_keyword), ANNOUNCE_SAFIS[safi_keyword]),
                    field=f'_{safi_keyword}',
                    store=_store_announced,
                )
                for safi_keyword in safi_keywords
            ),
            *(
                Leaf(
                    safi_keyword,
                    AnnounceFlowLine(afi, SAFI.from_string(safi_keyword)),
                    field=f'_{safi_keyword}',
                    store=_store_announced,
                )
                for safi_keyword in ('flow', 'flow-vpn')
            ),
            Leaf('mup', SelectLine(afi, SAFI.mup, MUP_TYPES, mup_values()), field='_mup', store=_store_announced),
            Leaf(
                'mcast-vpn',
                SelectLine(afi, SAFI.mcast_vpn, MVPN_TYPES, IP_VALUES),
                field='_mcast-vpn',
                store=_store_announced,
            ),
            Leaf('sr-policy', SRPolicyLine(afi), field='_sr-policy', store=_store_announced),
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
    build=_address_family,
    children=(Leaf('vpls', VPLSLine(), field='_vpls', store=_store_announced),),
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
        Leaf('rtc', AnnounceLine(AFI.ipv4, SAFI.rtc, ANNOUNCE_SAFIS['rtc']), field='_rtc', store=store_routes),
        Leaf('sr-policy', SRPolicyLine(None), field='_sr-policy', store=store_routes, doc='an SR policy route'),
    )
)
