"""family.py

The families a neighbor negotiates, the ADD-PATH ones, and the next-hop encodings.

    family { ipv4 unicast [prefix-limit <n>]; ... all; }
    add-path { ipv4 unicast [limit <n>]; ... all; }
    nexthop { ipv4 unicast ipv6; ipv6 unicast ipv4; ... }

These blocks keep their values as the legacy parser did, one list per AFI keyword, and the
neighbor resolves them. The per-block state (what was already seen, `all`) lives in
keys starting with `_`, which `finish` removes.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any

from exabgp.bgp.message.update.nlri import NLRI
from exabgp.configuration.grammar import shape
from exabgp.configuration.grammar.context import ReadContext
from exabgp.configuration.grammar.error import ConfigError
from exabgp.configuration.grammar.nodes import Block, Leaf
from exabgp.configuration.grammar.section import Kept, Store, Values
from exabgp.configuration.grammar.shape import Shape
from exabgp.configuration.grammar.types.base import Type, WordOrSyntax
from exabgp.configuration.grammar.words import Words
from exabgp.configuration.grammar.types.word import is_decimal
from exabgp.protocol.family import AFI, SAFI, FamilyTuple

PREFIX_LIMIT_MAX = 0xFFFFFFFF
PATHS_LIMIT_MAX = 65535

SAFIS: dict[str, dict[str, FamilyTuple]] = {
    'ipv4': {
        'unicast': (AFI.ipv4, SAFI.unicast),
        'multicast': (AFI.ipv4, SAFI.multicast),
        'nlri-mpls': (AFI.ipv4, SAFI.nlri_mpls),
        'labeled-unicast': (AFI.ipv4, SAFI.nlri_mpls),
        'mpls-vpn': (AFI.ipv4, SAFI.mpls_vpn),
        'mcast-vpn': (AFI.ipv4, SAFI.mcast_vpn),
        'flow': (AFI.ipv4, SAFI.flow_ip),
        'flow-vpn': (AFI.ipv4, SAFI.flow_vpn),
        'mup': (AFI.ipv4, SAFI.mup),
        'sr-policy': (AFI.ipv4, SAFI.sr_policy),
        'rtc': (AFI.ipv4, SAFI.rtc),
    },
    'ipv6': {
        'unicast': (AFI.ipv6, SAFI.unicast),
        # `all` negotiates it, so it can be asked for alone, and the printed `all` reads back
        'multicast': (AFI.ipv6, SAFI.multicast),
        'nlri-mpls': (AFI.ipv6, SAFI.nlri_mpls),
        'labeled-unicast': (AFI.ipv6, SAFI.nlri_mpls),
        'mpls-vpn': (AFI.ipv6, SAFI.mpls_vpn),
        'mcast-vpn': (AFI.ipv6, SAFI.mcast_vpn),
        'mup': (AFI.ipv6, SAFI.mup),
        'sr-policy': (AFI.ipv6, SAFI.sr_policy),
        'flow': (AFI.ipv6, SAFI.flow_ip),
        'flow-vpn': (AFI.ipv6, SAFI.flow_vpn),
    },
    'l2vpn': {
        'vpls': (AFI.l2vpn, SAFI.vpls),
        'evpn': (AFI.l2vpn, SAFI.evpn),
    },
    'bgp-ls': {
        'bgp-ls': (AFI.bgpls, SAFI.bgp_ls),
        'bgp-ls-vpn': (AFI.bgpls, SAFI.bgp_ls_vpn),
    },
}

NEXTHOP_SAFIS = ['unicast', 'multicast', 'nlri-mpls', 'labeled-unicast', 'mpls-vpn']
NEXTHOP_AFIS = {'ipv4': ['ipv6'], 'ipv6': ['ipv4']}

# families which are only negotiated when asked for: a neighbor with no family block has the others
LISTED_ONLY = frozenset({(AFI.ipv4, SAFI.rtc)})


def family_name(family: FamilyTuple) -> str:
    return f'{family[0].name()} {family[1].name()}'


def default_families() -> list[FamilyTuple]:
    return [family for family in NLRI.known_families() if family not in LISTED_ONLY]


class FamilyLine(Type[tuple[FamilyTuple, int]]):
    """`<safi> [prefix-limit <n>]` after an AFI keyword; the SAFI in any case."""

    def __init__(self, afi_keyword: str) -> None:
        self.afi_keyword = afi_keyword
        self.name = f'{afi_keyword} family'

    def parse(self, words: Words) -> tuple[FamilyTuple, int]:
        where = words.where()
        word = words.word()
        family = SAFIS[self.afi_keyword].get(word.lower())
        if family is None:
            raise ConfigError(
                where, f"'{word}' is not valid for {self.afi_keyword}", expected=sorted(SAFIS[self.afi_keyword])
            )
        return family, self._limit(words, family)

    def _limit(self, words: Words, family: FamilyTuple) -> int:
        where = words.where()
        keyword = words.word()
        if not keyword:
            return 0
        if keyword != 'prefix-limit':
            raise ConfigError(
                where, f'unexpected token after {family_name(family)}: {keyword}', expected=['prefix-limit']
            )
        where = words.where()
        value = words.word()
        if not value:
            raise ConfigError(where, 'prefix-limit requires a number', expected=['<number>'])
        if not is_decimal(value):
            raise ConfigError(where, f'prefix-limit must be a number, got: {value}', expected=['<number>'])
        limit = int(value)
        if not 1 <= limit <= PREFIX_LIMIT_MAX:
            raise ConfigError(where, f'prefix-limit must be 1-{PREFIX_LIMIT_MAX}, got {limit}')
        if not words.at_end():
            where = words.where()
            raise ConfigError(
                where, f'unexpected token after the prefix-limit of {family_name(family)}: {words.word()}'
            )
        return limit

    def render(self, value: tuple[FamilyTuple, int]) -> list[WordOrSyntax]:
        family, limit = value
        safi: list[WordOrSyntax] = [family[1].name()]
        return safi + (['prefix-limit', str(limit)] if limit else [])

    def hint(self) -> str:
        return f'{"|".join(SAFIS[self.afi_keyword])} [prefix-limit <n>]'

    def examples(self) -> list[str]:
        return list(SAFIS[self.afi_keyword]) + [f'{next(iter(SAFIS[self.afi_keyword]))} prefix-limit 10']

    def shape(self) -> Shape:
        return shape.container(
            ('safi', shape.enumeration(*SAFIS[self.afi_keyword]).described('the subsequent address family')),
            (
                'prefix-limit',
                shape.integer(1, PREFIX_LIMIT_MAX).described('RFC 4486, the most prefixes the peer may send'),
            ),
        )

    def choices(self, partial: str) -> list[str]:
        return [safi for safi in SAFIS[self.afi_keyword] if safi.startswith(partial.lower())]


class AddPathLine(Type[tuple[FamilyTuple, int]]):
    """`<safi> [limit <n>]` after an AFI keyword; the SAFI as written, case matters."""

    def __init__(self, afi_keyword: str) -> None:
        self.afi_keyword = afi_keyword
        self.name = f'{afi_keyword} add-path family'

    def parse(self, words: Words) -> tuple[FamilyTuple, int]:
        where = words.where()
        word = words.word()
        if not word:
            raise ConfigError(
                where, f'add-path {self.afi_keyword} requires a SAFI', expected=sorted(SAFIS[self.afi_keyword])
            )
        family = SAFIS[self.afi_keyword].get(word)
        if family is None:
            raise ConfigError(
                where, f'unknown SAFI for {self.afi_keyword}: {word}', expected=sorted(SAFIS[self.afi_keyword])
            )
        return family, self._limit(words, word)

    def _limit(self, words: Words, safi: str) -> int:
        where = words.where()
        keyword = words.word()
        if not keyword:
            return 0
        if keyword != 'limit':
            raise ConfigError(where, f'unexpected token after {self.afi_keyword} {safi}: {keyword}', expected=['limit'])
        where = words.where()
        value = words.word()
        if not value:
            raise ConfigError(where, f'add-path {self.afi_keyword} {safi} limit requires a value')
        try:
            limit = int(value)
        except ValueError:
            raise ConfigError(where, f'paths-limit must be a number, got: {value}') from None
        if not 1 <= limit <= PATHS_LIMIT_MAX:
            raise ConfigError(where, f'paths-limit must be 1-{PATHS_LIMIT_MAX}, got {limit}')
        if not words.at_end():
            where = words.where()
            raise ConfigError(where, f'unexpected token after paths-limit value: {words.word()}')
        return limit

    def render(self, value: tuple[FamilyTuple, int]) -> list[WordOrSyntax]:
        family, limit = value
        words: list[WordOrSyntax] = [family[1].name()]
        return words + (['limit', str(limit)] if limit else [])

    def hint(self) -> str:
        return f'{"|".join(SAFIS[self.afi_keyword])} [limit <n>]'

    def examples(self) -> list[str]:
        return list(SAFIS[self.afi_keyword]) + [f'{next(iter(SAFIS[self.afi_keyword]))} limit 10']

    def shape(self) -> Shape:
        return shape.container(
            ('safi', shape.enumeration(*SAFIS[self.afi_keyword]).described('the subsequent address family')),
            ('limit', shape.integer(1, PATHS_LIMIT_MAX).described('the most paths per prefix')),
        )


class NextHopLine(Type[tuple[AFI, SAFI, AFI]]):
    """`<safi> <next-hop afi>` after an AFI keyword, in any case."""

    def __init__(self, afi_keyword: str) -> None:
        self.afi_keyword = afi_keyword
        self.name = f'{afi_keyword} next-hop'

    def parse(self, words: Words) -> tuple[AFI, SAFI, AFI]:
        where = words.where()
        safi = words.word().lower()
        if safi not in NEXTHOP_SAFIS:
            raise ConfigError(where, f"'{safi}' is not a valid SAFI for {self.afi_keyword}", expected=NEXTHOP_SAFIS)
        where = words.where()
        nexthop_afi = words.word().lower()
        if nexthop_afi not in NEXTHOP_AFIS[self.afi_keyword]:
            raise ConfigError(
                where, f"'{nexthop_afi}' is not a valid next-hop AFI", expected=NEXTHOP_AFIS[self.afi_keyword]
            )
        return AFI.from_string(self.afi_keyword), SAFI.from_string(safi), AFI.from_string(nexthop_afi)

    def render(self, value: tuple[AFI, SAFI, AFI]) -> list[WordOrSyntax]:
        return [value[1].name(), value[2].name()]

    def hint(self) -> str:
        return f'{"|".join(NEXTHOP_SAFIS)} {"|".join(NEXTHOP_AFIS[self.afi_keyword])}'

    def examples(self) -> list[str]:
        return [f'{safi} {NEXTHOP_AFIS[self.afi_keyword][0]}' for safi in NEXTHOP_SAFIS] + [
            f'UNICAST {NEXTHOP_AFIS[self.afi_keyword][0].upper()}'
        ]

    def shape(self) -> Shape:
        return shape.container(
            ('safi', shape.enumeration(*NEXTHOP_SAFIS).described('the subsequent address family')),
            (
                'nexthop-afi',
                shape.enumeration(*NEXTHOP_AFIS[self.afi_keyword]).described('the address family of the next-hop'),
            ),
        )


class Nothing(Type[None]):
    """A keyword with no value: what follows it is ignored."""

    name = 'nothing'

    def parse(self, words: Words) -> None:
        return None

    def render(self, value: None) -> list[WordOrSyntax]:
        return []

    def hint(self) -> str:
        return ''

    def examples(self) -> list[str]:
        return ['']

    def shape(self) -> Shape:
        return shape.empty()


def _seen(values: dict[str, Any]) -> set[Any]:
    seen: set[Any] = values.setdefault('_seen', set())
    return seen


class FamilyStore(Store):
    """A family to negotiate, once, and not after `all`."""

    def __init__(self, afi_keyword: str) -> None:
        self.afi_keyword = afi_keyword

    def keep(self, values: Values, value: tuple[FamilyTuple, int], context: ReadContext) -> None:
        if values.get('_all'):
            raise ValueError('cannot add any family once family all is set')
        family, limit = value
        if family in _seen(values):
            raise ValueError(f'Duplicate entry: {family}')
        _seen(values).add(family)
        values.setdefault(self.afi_keyword, []).append(family)
        if limit:
            values.setdefault('_limits', {})[family] = limit


class AddPathStore(Store):
    """A family to negotiate ADD-PATH for, once, and not after `all`."""

    def __init__(self, afi_keyword: str) -> None:
        self.afi_keyword = afi_keyword

    def keep(self, values: Values, value: tuple[FamilyTuple, int], context: ReadContext) -> None:
        if values.get('_all'):
            raise ValueError('cannot add specific families after "all"')
        family, _ = value
        if family in _seen(values):
            raise ValueError(f'duplicate add-path entry for {family_name(family)}')
        _seen(values).add(family)
        values.setdefault(self.afi_keyword, []).append(value)


class AllStore(Store):
    """`all`: every family known."""

    def keep(self, values: Values, value: None, context: ReadContext) -> None:
        # legacy: `all` after a family is reported but not refused, and still asks for every family
        if not (values.get('_all') or _seen(values)):
            values['_all'] = True
            _seen(values).update(NLRI.known_families())
        values.setdefault('all', []).append(None)


class NextHopStore(Store):
    """A family whose next-hop may be of the other address family, once."""

    def __init__(self, afi_keyword: str) -> None:
        self.afi_keyword = afi_keyword

    def keep(self, values: Values, value: tuple[AFI, SAFI, AFI], context: ReadContext) -> None:
        if value in _seen(values):
            raise ValueError(f'Duplicate entry: {value}')
        _seen(values).add(value)
        values.setdefault(self.afi_keyword, []).append(value)


class FamiliesSection(Kept):
    """A list of families: what was seen is per block, a second `family { }` may name a family again."""

    def finish(self, values: Values) -> None:
        limits = values.pop('_limits', {})
        if limits:
            # legacy: the limits of the last block giving any replace those of the blocks before
            values['prefix-limit'] = list(limits.items())
        values.pop('_seen', None)
        values.pop('_all', None)


FAMILIES = FamiliesSection()
ALL = AllStore()


FAMILY = Block(
    'family',
    field='family',
    doc='the address families to negotiate',
    section=FAMILIES,
    children=(
        *(
            Leaf(
                afi_keyword,
                FamilyLine(afi_keyword),
                field=afi_keyword,
                store=FamilyStore(afi_keyword),
                multiple=True,
                doc=f'an {afi_keyword} family to negotiate',
            )
            for afi_keyword in SAFIS
        ),
        Leaf('all', Nothing(), field='all', store=ALL, doc='every family exabgp knows'),
    ),
)

ADD_PATH = Block(
    'add-path',
    field='add-path',
    doc='the families ADD-PATH is negotiated for, with an optional PATHS-LIMIT',
    section=FAMILIES,
    children=(
        *(
            Leaf(
                afi_keyword,
                AddPathLine(afi_keyword),
                field=afi_keyword,
                store=AddPathStore(afi_keyword),
                multiple=True,
                doc=f'an {afi_keyword} family to negotiate ADD-PATH for',
            )
            for afi_keyword in SAFIS
        ),
        Leaf('all', Nothing(), field='all', store=ALL, doc='no family, ADD-PATH is negotiated for none'),
    ),
)

NEXTHOP = Block(
    'nexthop',
    field='nexthop',
    doc='the families whose next-hop may be of the other address family (RFC 8950)',
    section=FAMILIES,
    children=tuple(
        Leaf(
            afi_keyword,
            NextHopLine(afi_keyword),
            field=afi_keyword,
            store=NextHopStore(afi_keyword),
            multiple=True,
            doc=f'an {afi_keyword} family whose next-hop may be of the other address family',
        )
        for afi_keyword in NEXTHOP_AFIS
    ),
)
