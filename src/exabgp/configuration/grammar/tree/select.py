"""select.py

The routes whose first word selects their type, which reads its own fields:

    announce { ipv4|ipv6 {
        mup mup-isd <prefix> rd <rd> | mup-dsd <ip> rd <rd> | mup-t1st ... | mup-t2st ... [...];
        mcast-vpn source-ad source <ip> group <ip> rd <rd> | source-join ... | shared-join ... [...];
    } }

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from ipaddress import IPv4Address, IPv6Address, ip_address
from typing import Any, Callable

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.update.attribute import AttributeCollection, NextHop, NextHopSelf
from exabgp.bgp.message.update.nlri.mup import (
    DirectSegmentDiscoveryRoute,
    InterworkSegmentDiscoveryRoute,
    Type1SessionTransformedRoute,
    Type2SessionTransformedRoute,
)
from exabgp.bgp.message.update.nlri.mvpn import SharedJoin, SourceAD, SourceJoin
from exabgp.bgp.message.update.nlri.mvpn.sourcead import is_ssm_group
from exabgp.configuration.grammar import shape
from exabgp.configuration.grammar.error import ROUTE_ERRORS, ConfigError
from exabgp.configuration.grammar.shape import Shape
from exabgp.configuration.grammar.tree.static import (
    ROUTE_VALUES,
    RouteValue,
    action,
    attribute_words,
    value_fields,
)
from exabgp.configuration.grammar.types.base import Type, WordOrSyntax
from exabgp.configuration.grammar.types.route import RouteStatement, Target
from exabgp.configuration.grammar.words import Words
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP, IPSelf, IPv4, IPv6
from exabgp.rib.route import Route

ASN_MAX = 4294967295
TEID_MAX = 0xFFFFFFFF  # 3GPP TS 29.281: a 32 bit tunnel endpoint identifier
TEID_MAX_BITS = 32
QFI_MAX = 63  # 3GPP TS 24.501: a six bit QoS flow identifier


def _address(words: Words, afi: AFI) -> IPv4 | IPv6:
    if afi == AFI.ipv4:
        return IPv4.from_string(words.word())
    if afi == AFI.ipv6:
        return IPv6.from_string(words.word())
    raise ValueError(f'unexpected afi: {afi}')


def _rd(words: Words) -> Any:
    rd: Any = ROUTE_VALUES['rd'].type.parse(words)
    return rd


def _prefix(word: str) -> tuple[IPv4 | IPv6, int]:
    address, length = word.split('/')
    if not length.isdigit():
        raise ValueError(f"unexpect prefix format '{word}'")
    found = ip_address(address)
    if isinstance(found, IPv4Address):
        return IPv4.from_string(address), int(length)
    if isinstance(found, IPv6Address):
        return IPv6.from_string(address), int(length)
    raise ValueError(f"unexpect ipaddress format '{address}'")


def _number(words: Words, name: str, maximum: int) -> int:
    word = words.word()
    if not word.isdigit() or int(word) > maximum:
        raise ValueError(f"{name} is a number 0-{maximum}, received '{word}'")
    return int(word)


def mup_isd(words: Words, afi: AFI) -> Any:
    prefix, length = _prefix(words.word())
    words.expect('rd')
    return InterworkSegmentDiscoveryRoute.make_isd(rd=_rd(words), prefix_ip_len=length, prefix_ip=prefix, afi=afi)


def mup_dsd(words: Words, afi: AFI) -> Any:
    ip = _address(words, afi)
    words.expect('rd')
    return DirectSegmentDiscoveryRoute.make_dsd(rd=_rd(words), ip=ip, afi=afi)


def mup_t1st(words: Words, afi: AFI) -> Any:
    prefix, length = _prefix(words.word())
    words.expect('rd')
    rd = _rd(words)
    words.expect('teid')
    teid = _number(words, 'teid', TEID_MAX)
    words.expect('qfi')
    qfi = _number(words, 'qfi', QFI_MAX)
    words.expect('endpoint')
    endpoint = _address(words, afi)
    source: bytes | IPv4 | IPv6 = b''
    source_len = 0
    if words.peek() == 'source':
        words.take()
        source = _address(words, afi)
        source_len = 32 if afi == AFI.ipv4 else 128
    return Type1SessionTransformedRoute.make_t1st(
        rd=rd,
        prefix_ip_len=length,
        prefix_ip=prefix,
        teid=teid,
        qfi=qfi,
        endpoint_ip_len=endpoint.bits,
        endpoint_ip=endpoint,
        source_ip_len=source_len,
        source_ip=source,
        afi=afi,
    )


def mup_t2st(words: Words, afi: AFI) -> Any:
    endpoint = _address(words, afi)
    words.expect('rd')
    rd = _rd(words)
    words.expect('teid')
    teids = words.word().split('/')
    if len(teids) != 2:
        raise ValueError(f'invalid teid format, it is <teid>/<length> (length 0-{TEID_MAX_BITS})')
    teid, teid_len = int(teids[0]), int(teids[1])
    if not 0 <= teid <= TEID_MAX:
        raise ValueError(f'TEID {teid} out of range, it is 0 to {TEID_MAX}')
    if not 0 <= teid_len <= TEID_MAX_BITS:
        raise ValueError(f'teid length {teid_len} out of range, it is 0 to {TEID_MAX_BITS}')
    if teid >= pow(2, teid_len):
        raise ValueError(f'TEID {teid} cannot be stored in {teid_len} bits')
    return Type2SessionTransformedRoute.make_t2st(
        rd=rd, endpoint_len=endpoint.bits + teid_len, endpoint_ip=endpoint, teid=teid, afi=afi
    )


def _join(words: Words, afi: AFI, first: str) -> tuple[Any, Any, Any]:
    words.expect(first)
    source = _address(words, afi)
    words.expect('group')
    group = _address(words, afi)
    words.expect('rd')
    return source, group, _rd(words)


def _source_as(words: Words) -> int:
    words.expect('source-as')
    return _number(words, 'source-as', ASN_MAX)


def mvpn_shared_join(words: Words, afi: AFI) -> Any:
    source, group, rd = _join(words, afi, 'rp')
    return SharedJoin.make_sharedjoin(rd=rd, afi=afi, source=source, group=group, source_as=_source_as(words))


def mvpn_source_join(words: Words, afi: AFI) -> Any:
    source, group, rd = _join(words, afi, 'source')
    return SourceJoin.make_sourcejoin(rd=rd, afi=afi, source=source, group=group, source_as=_source_as(words))


def mvpn_source_ad(words: Words, afi: AFI) -> Any:
    source, group, rd = _join(words, afi, 'source')
    # RFC 6514 4.5: a Source Active A-D route for a group in the SSM range MUST NOT be
    # advertised. A withdrawal is still accepted, it can only remove such a route.
    if action(words) == Action.ANNOUNCE and is_ssm_group(group):
        raise ValueError(
            f'source-ad group {group} is in the Source Specific Multicast range, '
            f'which RFC 6514 4.5 forbids advertising in a Source Active A-D route'
        )
    return SourceAD.make_sourcead(rd=rd, afi=afi, source=source, group=group)


MUP_TYPES: dict[str, Callable[[Words, AFI], Any]] = {
    'mup-isd': mup_isd,
    'mup-dsd': mup_dsd,
    'mup-t1st': mup_t1st,
    'mup-t2st': mup_t2st,
}
MVPN_TYPES: dict[str, Callable[[Words, AFI], Any]] = {
    'source-ad': mvpn_source_ad,
    'source-join': mvpn_source_join,
    'shared-join': mvpn_shared_join,
}

_RD = ('rd', ROUTE_VALUES['rd'].type.shape())
_TEID = ('teid', shape.integer(0, TEID_MAX).described('the GTP tunnel endpoint identifier, 3GPP TS 29.281'))
_PREFIX = ('prefix', shape.IP_PREFIX.described('the prefix of the user equipment'))
_ENDPOINT = ('endpoint', shape.IP_ADDRESS.described('the tunnel endpoint'))
_GROUP = ('group', shape.IP_ADDRESS.described('the multicast group'))
_SOURCE_AS = ('source-as', shape.AS_NUMBER.described('the AS of the source'))
# the fields each route type reads, in their order, for the data model
TYPE_FIELDS: dict[str, tuple[tuple[str, Shape], ...]] = {
    'mup-isd': (_PREFIX, _RD),
    'mup-dsd': (('address', shape.IP_ADDRESS.described('the address of the direct segment')), _RD),
    'mup-t1st': (
        _PREFIX,
        _RD,
        _TEID,
        ('qfi', shape.integer(0, QFI_MAX).described('the QoS flow identifier, 3GPP TS 24.501')),
        _ENDPOINT,
        ('source', shape.IP_ADDRESS.described('the source of the tunnel')),
    ),
    'mup-t2st': (
        _ENDPOINT,
        _RD,
        ('teid', shape.string(pattern=r'\d+/\d+').described('the TEID and its length in bits')),
    ),
    'source-ad': (('source', shape.IP_ADDRESS.described('the multicast source')), _GROUP, _RD),
    'source-join': (('source', shape.IP_ADDRESS.described('the multicast source')), _GROUP, _RD, _SOURCE_AS),
    'shared-join': (('rp', shape.IP_ADDRESS.described('the rendezvous point')), _GROUP, _RD, _SOURCE_AS),
}
TYPE_DOCS = {
    'mup-isd': 'Interwork Segment Discovery route',
    'mup-dsd': 'Direct Segment Discovery route',
    'mup-t1st': 'Type 1 Session Transformed route',
    'mup-t2st': 'Type 2 Session Transformed route',
    'source-ad': 'Source Active A-D route, RFC 6514 type 5',
    'source-join': 'Source Tree Join C-multicast route, RFC 6514 type 7',
    'shared-join': 'Shared Tree Join C-multicast route, RFC 6514 type 6',
}


class MupNextHop(Type[tuple[Any, Any]]):
    """The next-hop of a MUP route: an IPv4 address is mapped into IPv6 for an IPv6 route.

    legacy: `self` is of the family of the last prefix read, not the route's.
    """

    name = 'next-hop'

    def parse(self, words: Words) -> tuple[Any, Any]:
        where = words.where()
        word = words.word()
        afi = words.context.afi
        if word.lower() == 'self':
            return IPSelf(afi), NextHopSelf(afi)
        try:
            ip = IP.from_string(word)
            if ip.afi == AFI.ipv4 and words.context.mup_afi == AFI.ipv6:
                ip = IP.from_string(f'::ffff:{ip}')
            return ip, NextHop.from_string(ip.top())
        except ROUTE_ERRORS:
            raise ConfigError(where, f"'{word}' is not a valid next-hop", expected=['<ip>', 'self']) from None

    def render(self, value: tuple[Any, Any]) -> list[WordOrSyntax]:
        return ['self'] if isinstance(value[0], IPSelf) else [str(value[0])]

    def hint(self) -> str:
        return '<ip>|self'

    def examples(self) -> list[str]:
        return ['10.0.0.1', '2001:db8::1', 'self']

    def shape(self) -> Shape:
        return shape.union(shape.IP_ADDRESS, shape.enumeration('self'))


def mup_values() -> dict[str, RouteValue]:
    return {
        'next-hop': RouteValue(
            MupNextHop(), Target.NEXTHOP_ATTRIBUTE, doc='the next-hop, IPv4 mapped into IPv6 for an IPv6 route'
        ),
        'bgp-prefix-sid-srv6': ROUTE_VALUES['bgp-prefix-sid-srv6'],
        'extended-community': ROUTE_VALUES['extended-community'],
    }


class SelectLine(RouteStatement):
    """`<type> <fields of the type> [<keyword> <value> ...]`."""

    def __init__(
        self, afi: AFI, safi: SAFI, types: dict[str, Callable[[Words, AFI], Any]], values: dict[str, RouteValue]
    ) -> None:
        self.afi = afi
        self.safi = safi
        self.types = types
        self.values = values
        self.name = f'{afi.name()} {safi.name()} route'

    def parse(self, words: Words) -> list[Route]:
        where = words.where()
        kind = words.word()
        factory = self.types.get(kind)
        if factory is None:
            raise ConfigError(where, f"Unknown route type '{kind}'", expected=sorted(self.types))
        words.context.mup_afi = self.afi
        try:
            nlri = factory(words, self.afi)
        except ConfigError:
            raise  # a value of the route (its rd) says where it is itself
        except ROUTE_ERRORS as exc:
            raise ConfigError(where, str(exc) or f'invalid {kind} route') from None
        route = Route(nlri, AttributeCollection(), nexthop=IP.NoNextHop)
        for _, spec in self.keywords(words, self.values):
            route = self._apply(route, spec, spec.type.parse(words))
        return [route]

    def _apply(self, route: Route, spec: RouteValue, value: Any) -> Route:
        if spec.target != Target.NEXTHOP_ATTRIBUTE:
            route.attributes.add(value)
            return route
        ip, attribute = value
        if ip:
            route = route.with_nexthop(ip)
        # legacy: the MUP next-hop of an IPv6 route is in MP_REACH_NLRI only, with no attribute
        if attribute and not (isinstance(spec.type, MupNextHop) and self.afi == AFI.ipv6):
            route.attributes.add(attribute)
        return route

    def printed(self, route: Route) -> list[WordOrSyntax]:
        return select_words(route.nlri) + attribute_words(route)

    def hint(self) -> str:
        return '|'.join(self.types) + ' ...'

    def examples(self) -> list[str]:
        return []

    def shape(self) -> Shape:
        values = value_fields(self.values)
        cases = ((kind, shape.container(*TYPE_FIELDS[kind], *values).described(TYPE_DOCS[kind])) for kind in self.types)
        return shape.choice(*cases)


def select_words(nlri: Any) -> list[str]:
    """The route type and its fields, as the type reads them back."""
    rd = repr(nlri.rd).split()[-1]
    if isinstance(nlri, InterworkSegmentDiscoveryRoute):
        return ['mup-isd', f'{nlri.prefix_ip}/{nlri.prefix_ip_len}', 'rd', rd]
    if isinstance(nlri, DirectSegmentDiscoveryRoute):
        return ['mup-dsd', str(nlri.ip), 'rd', rd]
    if isinstance(nlri, Type1SessionTransformedRoute):
        words = ['mup-t1st', f'{nlri.prefix_ip}/{nlri.prefix_ip_len}', 'rd', rd, 'teid', str(nlri.teid)]
        words += ['qfi', str(nlri.qfi), 'endpoint', str(nlri.endpoint_ip)]
        return words + (['source', str(nlri.source_ip)] if nlri.source_ip_len else [])
    if isinstance(nlri, Type2SessionTransformedRoute):
        teid_len = nlri.endpoint_len - (32 if nlri.endpoint_ip.afi == AFI.ipv4 else 128)
        return ['mup-t2st', str(nlri.endpoint_ip), 'rd', rd, 'teid', f'{nlri.teid}/{teid_len}']
    if isinstance(nlri, SourceAD):
        return ['source-ad', 'source', str(nlri.source), 'group', str(nlri.group), 'rd', rd]
    if isinstance(nlri, SourceJoin):
        words = ['source-join', 'source', str(nlri.source), 'group', str(nlri.group), 'rd', rd]
        return words + ['source-as', str(nlri.source_as)]
    if isinstance(nlri, SharedJoin):
        words = ['shared-join', 'rp', str(nlri.source), 'group', str(nlri.group), 'rd', rd]
        return words + ['source-as', str(nlri.source_as)]
    raise ValueError(f'no route type prints {type(nlri).__name__}')
