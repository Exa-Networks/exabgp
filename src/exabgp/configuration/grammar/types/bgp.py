"""bgp.py

The values of a route: its prefix and path attributes.

Each type reads what the legacy value function read (configuration/static/parser.py and
mpls.py), and builds the same attribute object; the forms and differential tests hold the
two to it. A route line keeps what one value tells the next in `words.context`: the address
family of the prefix decides what `next-hop self` means.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack
from typing import Any, cast

from exabgp.bgp.message.open import ASN, RouterID
from exabgp.bgp.message.open.capability.role import RoleValue
from exabgp.bgp.message.update.attribute import (
    AIGP,
    CONFED_SEQUENCE,
    CONFED_SET,
    MED,
    SEQUENCE,
    SET,
    Aggregator,
    AS2Path,
    AtomicAggregate,
    ClusterID,
    ClusterList,
    GenericAttribute,
    LocalPreference,
    NextHop,
    NextHopSelf,
    Origin,
    OriginatorID,
)
from exabgp.bgp.message.update.attribute.community import (
    Communities,
    Community,
    ExtendedCommunities,
    ExtendedCommunity,
    LargeCommunities,
    LargeCommunity,
)
from exabgp.bgp.message.update.attribute.internal import InternalNumber, InternalText
from exabgp.bgp.message.update.attribute.internal import Name as InternalName
from exabgp.bgp.message.update.attribute.internal import Split as InternalSplit
from exabgp.bgp.message.update.attribute.internal import Watchdog as InternalWatchdog
from exabgp.bgp.message.update.attribute.internal import Withdrawn as InternalWithdraw
from exabgp.bgp.message.update.attribute.otc import OTC, OTCSelf
from exabgp.bgp.message.update.nlri.qualifier import Labels, PathInfo, RouteDistinguisher
from exabgp.configuration.grammar import shape
from exabgp.configuration.grammar.error import ConfigError
from exabgp.configuration.grammar.shape import Shape
from exabgp.configuration.grammar.types.base import Syntax, Type, WordOrSyntax
from exabgp.configuration.grammar.types.word import (
    Number,
    Word,
    decimal,
    decimal_or_hexadecimal,
    hexadecimal,
    is_decimal,
    is_hexadecimal,
)
from exabgp.configuration.grammar.words import Words
from exabgp.protocol.ip import IP, IPRange, IPSelf, IPv4, IPv6

AIGP_MAX = 0xFFFFFFFFFFFFFFFF  # RFC 7311: a 64 bit metric
MAX_SEGMENT_ASNS = 255  # RFC 4271 4.3: a path segment counts its AS numbers in one octet
MAX_LIST_ITEMS = 1024  # a list of values is written by hand
COMMUNITY_HALF_MAX = 0xFFFF  # RFC 1997: an AS number and a value of two octets each
LARGE_COMMUNITY_FIELD_MAX = 0xFFFFFFFF  # RFC 8092: three four-octet fields
IPV6_MASK = 128
HEX_DATA = shape.string(pattern=r'0x([0-9a-fA-F]{2})*')
# an extended community as exabgp prints it: <kind>:<value>..., or eight octets in hexadecimal
EXTENDED_COMMUNITY = shape.string(pattern=r'0x[0-9a-fA-F]{16}|[a-z0-9-]+(:[^:\s]+)+')
IPV4_OCTETS = 4
RD_TYPE_1_OCTETS = 4


class Prefix(Type[IPRange]):
    """`<ip>/<mask>`, or an address alone for its host route; the host bits must be zero."""

    name = 'prefix'

    def parse(self, words: Words) -> IPRange:
        where = words.where()
        word = words.word()
        # legacy: a word with no mask, several slashes, or a mask which is no number is taken
        # as a host route of what precedes the first slash, or of the whole word
        parts = word.split('/')
        ip = parts[0] if len(parts) == 2 else word
        try:
            mask = decimal(parts[1]) if len(parts) == 2 else (128 if ':' in ip else 32)
        except ValueError:
            mask = 128 if ':' in ip else 32
        try:
            words.context.afi = IP.toafi(ip)
            iprange = IPRange.make_range(ip, mask)
        except (OSError, ValueError):
            raise ConfigError(where, f"'{ip}/{mask}' is not a valid prefix", expected=['<ip>/<mask>']) from None
        if iprange.address() & iprange.mask.hostmask() != 0:
            raise ConfigError(where, f"'{ip}/{mask}' is not a valid network, the host bits are not zero")
        return iprange

    def render(self, value: IPRange) -> list[WordOrSyntax]:
        return [f'{value.top()}/{int(value.mask)}']

    def hint(self) -> str:
        return '<ip>/<mask>'

    def examples(self) -> list[str]:
        return ['10.0.0.0/24', '10.0.0.1', '2001:db8::/32', '2001:db8::1']

    def shape(self) -> Shape:
        return shape.IP_PREFIX.described('an IP prefix, <address>/<length>')


def _path_information(word: str) -> PathInfo:
    if is_decimal(word):
        return PathInfo.make_from_integer(int(word))
    return PathInfo.make_from_ip(word)


PATH_INFORMATION: Number[PathInfo] = Number(
    'path-information',
    ((0, PathInfo.MAX),),
    convert=_path_information,
    examples=['1', '0.0.0.1'],
    hint='<number>|<ipv4>',
    doc='the ADD-PATH path identifier, RFC 7911, a number or a dotted quad',
)


class NextHopType(Type[tuple[IP | IPSelf, NextHop | NextHopSelf]]):
    """An address, or `self` for the local address of the session, in the family of the prefix."""

    name = 'next-hop'

    def parse(self, words: Words) -> tuple[IP | IPSelf, NextHop | NextHopSelf]:
        where = words.where()
        word = words.word()
        afi = words.context.afi
        if word.lower() == 'self':
            return IPSelf(afi), NextHopSelf(afi)
        try:
            ip = IP.from_string(word)
        except (OSError, IndexError, ValueError):
            raise ConfigError(where, f"'{word}' is not a valid next-hop", expected=['<ip>', 'self']) from None
        return ip, NextHop.from_string(ip.top())

    def render(self, value: tuple[IP | IPSelf, NextHop | NextHopSelf]) -> list[WordOrSyntax]:
        ip = value[0]
        return ['self'] if isinstance(ip, IPSelf) else [str(ip)]

    def hint(self) -> str:
        return '<ip>|self'

    def examples(self) -> list[str]:
        return ['10.0.0.1', 'self', 'SELF']

    def shape(self) -> Shape:
        return shape.union(shape.IP_ADDRESS, shape.enumeration('self')).described(
            'the next-hop address, or self for the local address of the session'
        )


class HexAttribute(Type[GenericAttribute]):
    """`[ 0x<code> 0x<flag> 0x<data> ]`: an attribute given as its wire bytes."""

    name = 'attribute'

    def parse(self, words: Words) -> GenericAttribute:
        where = words.where()
        if words.word() != '[':
            raise ConfigError(where, 'invalid attribute format', expected=[self.hint()])
        code = self._hex(words, 'attribute code')
        flag = self._hex(words, 'attribute flag')
        where = words.where()
        data = words.word().lower()
        if not data.startswith('0x'):
            raise ConfigError(where, f"'{data}' is not valid attribute data, it is hexadecimal")
        if len(data) % 2:
            raise ConfigError(where, f"'{data}' has an odd number of hexadecimal digits")
        if data != '0x' and not is_hexadecimal(data):
            raise ConfigError(where, f"'{data}' is not valid attribute data, it is hexadecimal")
        raw = bytes.fromhex(data[2:])
        if words.word() != ']':
            raise ConfigError(where, "invalid attribute format - missing closing ']'")
        return GenericAttribute.make_generic(code, flag, raw)

    @staticmethod
    def _hex(words: Words, what: str) -> int:
        where = words.where()
        word = words.word().lower()
        if not word.startswith('0x'):
            raise ConfigError(where, f"'{word}' is not a valid {what}, it is hexadecimal")
        try:
            return hexadecimal(word)
        except ValueError:
            raise ConfigError(where, f"'{word}' is not a valid {what}, it is hexadecimal") from None

    def render(self, value: GenericAttribute) -> list[WordOrSyntax]:
        return [Syntax('['), f'0x{value.ID:02x}', f'0x{value.FLAG:02x}', '0x' + bytes(value.data).hex(), Syntax(']')]

    def hint(self) -> str:
        return '[ 0x<code> 0x<flag> 0x<data> ]'

    def examples(self) -> list[str]:
        return ['[ 0x20 0xc0 0x00000001 ]']

    def shape(self) -> Shape:
        return shape.container(
            ('code', shape.UINT8.described('the attribute type code')),
            ('flag', shape.UINT8.described('the attribute flags')),
            ('data', HEX_DATA.described('the attribute value, 0x and its bytes')),
        ).described('an attribute given as its wire bytes, for one exabgp does not know')


def _aigp(word: str) -> AIGP:
    try:
        number = decimal_or_hexadecimal(word)
    except ValueError:
        raise ValueError(f"'{word}' is not a valid AIGP value") from None
    if not 0 <= number <= AIGP_MAX:
        raise ValueError(f'AIGP value {number} out of range, it is 0 to {AIGP_MAX}')
    return AIGP.from_int(number)


AIGP_VALUE: Number[AIGP] = Number(
    'aigp',
    ((0, AIGP_MAX),),
    convert=_aigp,
    examples=['100', '0x64', '0'],
    hint='<number>|0x<hex>',
    doc='AIGP, RFC 7311: the accumulated IGP metric',
)

_ORIGINS = {'igp': Origin.IGP, 'egp': Origin.EGP, 'incomplete': Origin.INCOMPLETE}


def _origin(word: str) -> Origin:
    value = word.lower()
    if value not in _ORIGINS:
        raise ValueError(f"'{value}' is not a valid origin")
    return Origin.from_int(_ORIGINS[value])


ORIGIN = Word(
    'origin',
    'igp|egp|incomplete',
    _origin,
    ['igp', 'egp', 'incomplete', 'IGP'],
    render=lambda value: [{Origin.IGP: 'igp', Origin.EGP: 'egp', Origin.INCOMPLETE: 'incomplete'}[int(value.origin)]],
    choices=list(_ORIGINS),
    shape=shape.enumeration(*_ORIGINS),
    doc='ORIGIN, RFC 4271 5.1.1',
)

OTC_NONE_REMOVED = (
    "'otc none' was removed in 6.0.0: RFC 9234 section 5 says the operator MUST NOT have the "
    'ability to modify the Only-to-Customer procedures.'
)


def _otc(word: str) -> OTC | OTCSelf:
    if word == 'none':
        raise ValueError(OTC_NONE_REMOVED)
    if word == 'self':
        return OTCSelf()
    try:
        role = RoleValue.from_string(word)
    except ValueError:
        try:
            return OTC.make_otc(ASN.from_string(word))
        except ValueError:
            raise ValueError(f"'{word}' is not a valid OTC: expected an ASN, self, or a BGP role name") from None
    return OTCSelf(role)


OTC_VALUE = Word(
    'otc',
    '<asn>|self|<role>',
    _otc,
    ['65000', 'self', 'provider', 'customer'],
    shape=shape.union(shape.AS_NUMBER, shape.enumeration('self', *(str(role) for role in RoleValue.assigned()))),
    doc='Only-to-Customer, RFC 9234: an AS number, self for our AS, or the role which gives it',
)


def _digits(name: str, make: Any) -> Any:
    def convert(word: str) -> Any:
        if not is_decimal(word):
            raise ValueError(f"'{word}' is not a valid {name}, it is a non-negative integer")
        return make(int(word))

    return convert


# the range is the attribute's own, from its width on the wire
MED_VALUE: Number[MED] = Number(
    'med',
    ((0, MED.MAX),),
    convert=_digits('MED', MED.from_int),
    examples=['0', '100'],
    doc='MULTI_EXIT_DISC, RFC 4271 5.1.4: the lower is preferred',
)
LOCAL_PREFERENCE: Number[LocalPreference] = Number(
    'local-preference',
    ((0, LocalPreference.MAX),),
    convert=_digits('local-preference', LocalPreference.from_int),
    examples=['0', '100'],
    doc='LOCAL_PREF, RFC 4271 5.1.5: the higher is preferred',
)


class Flag(Type[Any]):
    """A keyword with no value, what follows ignored: `atomic-aggregate;`."""

    def __init__(self, name: str, make: Any, doc: str) -> None:
        self.name = name
        self._make = make
        self._doc = doc

    def parse(self, words: Words) -> Any:
        return self._make()

    def render(self, value: Any) -> list[WordOrSyntax]:
        return []

    def hint(self) -> str:
        return ''

    def examples(self) -> list[str]:
        return ['']

    def shape(self) -> Shape:
        return shape.empty().described(self._doc)


ATOMIC_AGGREGATE = Flag(
    'atomic-aggregate',
    AtomicAggregate.make_atomic_aggregate,
    'ATOMIC_AGGREGATE, RFC 4271 5.1.6: a less specific route was selected',
)


class AggregatorType(Type[Aggregator]):
    """`<asn>:<router-id>`, in brackets or not: `( 65000:10.0.0.1 )`, `(65000:10.0.0.1)`."""

    name = 'aggregator'

    def parse(self, words: Words) -> Aggregator:
        where = words.where()
        word = words.word()
        eat = word == '('
        if eat:
            word = words.word()
            if word.endswith(')'):
                eat, word = False, word[:-1]
        elif word.startswith('('):
            eat, word = not word.endswith(')'), word[1:-1] if word.endswith(')') else word[1:]
        try:
            as_number, address = word.split(':')
            aggregator = Aggregator.make_aggregator(ASN.from_string(as_number), RouterID(address))
        except (ValueError, IndexError, OSError):
            raise ConfigError(where, f"'{word}' is not a valid aggregator", expected=[self.hint()]) from None
        if eat and words.word() != ')':
            raise ConfigError(where, "invalid aggregator - missing closing ')'")
        return aggregator

    def render(self, value: Aggregator) -> list[WordOrSyntax]:
        return [Syntax('('), f'{value.asn}:{value.speaker}', Syntax(')')]

    def hint(self) -> str:
        return '( <asn>:<router-id> )'

    def examples(self) -> list[str]:
        return ['( 65000:10.0.0.1 )', '(65000:10.0.0.1)', '65000:10.0.0.1', '( 65000:10.0.0.1)']

    def shape(self) -> Shape:
        return shape.container(
            ('as-number', shape.AS_NUMBER.described('the AS of the speaker which aggregated')),
            ('address', shape.IPV4_ADDRESS.described('its BGP identifier')),
        ).described('AGGREGATOR, RFC 4271 5.1.7')


def _originator_id(word: str) -> OriginatorID:
    if word.count('.') != IPv4.DOT_COUNT or not all(is_decimal(part) for part in word.split('.')):
        raise ValueError(f"'{word}' is not a valid originator-id, it is an IPv4 address")
    return OriginatorID.from_string(word)


ORIGINATOR_ID = Word(
    'originator-id',
    '<ipv4>',
    _originator_id,
    ['10.0.0.1'],
    shape=shape.IPV4_ADDRESS,
    doc='ORIGINATOR_ID, RFC 4456: the router-id of the client of the route reflector which originated the route',
)


class ClusterListType(Type[ClusterList]):
    """A cluster id, or several in brackets; a comma is read as a cluster id, and refused."""

    name = 'cluster-list'

    def parse(self, words: Words) -> ClusterList:
        where = words.where()
        word = words.word()
        ids: list[ClusterID] = []
        try:
            if word != '[':
                ids.append(ClusterID.from_string(word))
            else:
                for _ in range(MAX_LIST_ITEMS):
                    word = words.word()
                    if word == ']':
                        break
                    ids.append(ClusterID.from_string(word))
                else:
                    raise ValueError(f'a cluster-list holds at most {MAX_LIST_ITEMS} ids')
            if not ids:
                raise ValueError('cluster-list is empty')
            return ClusterList.make_clusterlist(ids)
        except (ValueError, OSError):
            raise ConfigError(where, f"'{word}' is not a valid cluster-list", expected=[self.hint()]) from None

    def render(self, value: ClusterList) -> list[WordOrSyntax]:
        return [Syntax('['), *(str(each) for each in value.clusters), Syntax(']')]

    def hint(self) -> str:
        return '<ipv4>|[ <ipv4> ... ]'

    def examples(self) -> list[str]:
        return ['10.0.0.1', '[ 10.0.0.1 ]', '[ 10.0.0.1 10.0.0.2 ]']

    def shape(self) -> Shape:
        return shape.leaf_list(shape.IPV4_ADDRESS).described(
            'CLUSTER_LIST, RFC 4456: the clusters the route was reflected through'
        )


# --------------------------------------------------------------------------- as-path

_SEGMENT_OPEN: dict[str, tuple[type[SEQUENCE | CONFED_SEQUENCE | SET | CONFED_SET], str]] = {
    '[': (SEQUENCE, ']'),
    '(': (SET, ')'),
}
_SEGMENT_KEYWORD: dict[str, type[CONFED_SEQUENCE | CONFED_SET]] = {
    'confed-sequence': CONFED_SEQUENCE,
    'confed-set': CONFED_SET,
}


def _as_path(segments: list[SEQUENCE | CONFED_SEQUENCE | SET | CONFED_SET]) -> AS2Path:
    """The path, held with four octet ASNs when one of them needs it.

    Two octets were used for every path, and an ASN above 65535 raised struct.error. Paths
    without one keep the two octet form they always had; ASPath.pack converts either.
    """
    asn4 = any(asn.asn4() for segment in segments for asn in segment)
    return AS2Path.make_aspath(segments, asn4=asn4)


class ASPathType(Type[AS2Path]):
    """`as-path [ 1 2 ] ( 3 4 ) confed-sequence [ 5 ] confed-set [ 6 7 ];`, or one AS alone."""

    name = 'as-path'

    def parse(self, words: Words) -> AS2Path:
        where = words.where()
        word = words.word()
        try:
            if word not in _SEGMENT_OPEN and word not in _SEGMENT_KEYWORD:
                try:
                    return _as_path([SEQUENCE([ASN.from_string(word)])])
                except ValueError:
                    raise ValueError('could not parse as-path') from None
            # `as-path [ ]` alone is the empty path, which is not an empty segment
            if word == '[' and words.peek() == ']':
                words.take()
                return _as_path([])
            segments = [self._segment(words, word)]
            for _ in range(MAX_LIST_ITEMS):
                if words.peek() not in _SEGMENT_OPEN and words.peek() not in _SEGMENT_KEYWORD:
                    break
                segments.append(self._segment(words, words.word()))
            return _as_path(segments)
        except ValueError as exc:
            raise ConfigError(where, str(exc), expected=[self.hint()]) from None

    @staticmethod
    def _segment(words: Words, opener: str) -> SEQUENCE | CONFED_SEQUENCE | SET | CONFED_SET:
        kind: type[SEQUENCE | CONFED_SEQUENCE | SET | CONFED_SET]
        if opener in _SEGMENT_KEYWORD:
            kind = _SEGMENT_KEYWORD[opener]
            bracket = words.word()
            if bracket not in _SEGMENT_OPEN:
                raise ValueError(f"'{opener}' must be followed by '[' or '(', not '{bracket}'")
            close = _SEGMENT_OPEN[bracket][1]
        else:
            kind, close = _SEGMENT_OPEN[opener]
        segment = kind()
        for _ in range(MAX_SEGMENT_ASNS + 2):
            value = words.word()
            if value == close:
                break
            if value == ',':
                continue
            if value in ('', ';', ']', ')'):
                raise ValueError(f"as-path segment opened with '{opener}' is not closed with '{close}'")
            if len(segment) == MAX_SEGMENT_ASNS:
                raise ValueError(f'an as-path segment holds at most {MAX_SEGMENT_ASNS} AS numbers')
            try:
                segment.append(ASN.from_string(value))
            except ValueError:
                raise ValueError(f"'{value}' is not an AS number in the as-path") from None
        if not segment:
            raise ValueError('an as-path segment can not be empty')
        return segment

    def render(self, value: AS2Path) -> list[WordOrSyntax]:
        # the text of an as-path reads back as the same path
        return [Syntax(word) if word in ('[', ']', '(', ')') else word for word in str(value).split()] or [
            Syntax('['),
            Syntax(']'),
        ]

    def hint(self) -> str:
        return '<asn>|[ <asn> ... ] ( <asn> ... ) confed-sequence [ ... ] confed-set [ ... ]'

    def examples(self) -> list[str]:
        return ['65001', '[ 1 2 ]', '( 3 4 )', '[ 1 , 2 ]', '[ ]', 'confed-sequence [ 5 ] [ 1 ]', 'confed-set ( 7 8 )']

    def shape(self) -> Shape:
        kinds = shape.enumeration('sequence', 'set', 'confed-sequence', 'confed-set')
        segment = shape.container(
            ('type', kinds.described('an AS_SEQUENCE or AS_SET, or their confederation forms, RFC 5065')),
            ('as-numbers', shape.leaf_list(shape.AS_NUMBER, max_items=MAX_SEGMENT_ASNS).described('its AS numbers')),
        )
        return shape.leaf_list(segment).described('AS_PATH, RFC 4271 5.1.2: its segments in order')


# --------------------------------------------------------------------------- communities


def community(word: str) -> Community:
    separator = word.find(':')
    if separator > 0:
        high, low = word[:separator], word[separator + 1 :]
        if not is_decimal(high) or not is_decimal(low):
            raise ValueError(f'invalid community {word}')
        if int(high) > COMMUNITY_HALF_MAX:
            raise ValueError(f'invalid community {word} (AS number must be 0-{COMMUNITY_HALF_MAX})')
        if int(low) > COMMUNITY_HALF_MAX:
            raise ValueError(f'invalid community {word} (value must be 0-{COMMUNITY_HALF_MAX})')
        return Community(pack('!L', (int(high) << 16) + int(low)))
    if word[:2].lower() == '0x':
        number = hexadecimal(word)
        if number > Community.MAX:
            raise ValueError(f'invalid community {word} (too large)')
        return Community(pack('!L', number))
    named = _WELL_KNOWN.get(word.lower())
    if named is not None:
        return Community(named)
    if is_decimal(word):
        number = int(word)
        if number > Community.MAX:
            raise ValueError(f'invalid community {word} (too large)')
        return Community(pack('!L', number))
    raise ValueError(f'invalid community name {word}')


_WELL_KNOWN = {
    'no-export': Community.NO_EXPORT,
    'no_export': Community.NO_EXPORT,
    'no-advertise': Community.NO_ADVERTISE,
    'no_advertise': Community.NO_ADVERTISE,
    'no-export-subconfed': Community.NO_EXPORT_SUBCONFED,
    'nopeer': Community.NO_PEER,
    'no-peer': Community.NO_PEER,
    'blackhole': Community.BLACKHOLE,
}


def large_community(word: str) -> LargeCommunity:
    if word.find(':') > 0:
        high, middle, low = word.split(':')
        if not all(is_decimal(part) for part in (high, middle, low)):
            raise ValueError(f'invalid community {word}')
        fields = [int(part) for part in (high, middle, low)]
        if any(field > LARGE_COMMUNITY_FIELD_MAX for field in fields):
            raise ValueError(f'invalid large community {word}: every field must be 0-{LARGE_COMMUNITY_FIELD_MAX}')
        return LargeCommunity(pack('!LLL', *fields))
    if word[:2].lower() == '0x':
        number = hexadecimal(word)
    elif is_decimal(word):
        number = int(word)
    else:
        raise ValueError(f'invalid large community name {word.lower()}')
    if number > LargeCommunity.MAX:
        raise ValueError(f'invalid large community {word} (too large)')
    return LargeCommunity(pack('!LLL', number >> 64, (number >> 32) & 0xFFFFFFFF, number & 0xFFFFFFFF))


class CommunitiesType(Type[Any]):
    """One community, or several in brackets; a comma is read as a community, and refused."""

    def __init__(
        self,
        name: str,
        make: Any,
        container: Any,
        unique: bool,
        hint: str,
        examples: list[str],
        item: Shape,
        doc: str,
    ) -> None:
        self.name = name
        self._shape = item
        self._doc = doc
        self._make = make
        self._container = container
        self._unique = unique  # a large community given twice is kept once
        self._hint = hint
        self._examples = examples

    def parse(self, words: Words) -> Any:
        where = words.where()
        found = self._container()
        word = words.word()
        try:
            if word != '[':
                found.add(self._make(word))
                return found
            for _ in range(MAX_LIST_ITEMS):
                where = words.where()
                word = words.word()
                if word == ']':
                    return found
                value = self._make(word)
                if self._unique and value in found.communities:
                    continue
                found.add(value)
        except ValueError as exc:
            raise ConfigError(where, str(exc), expected=[self._hint]) from None
        raise ConfigError(where, f'a {self.name} list holds at most {MAX_LIST_ITEMS} values')

    def render(self, value: Any) -> list[WordOrSyntax]:
        return [Syntax('['), *(str(each) for each in value.communities), Syntax(']')]

    def hint(self) -> str:
        return f'{self._hint}|[ {self._hint} ... ]'

    def examples(self) -> list[str]:
        return self._examples

    def shape(self) -> Shape:
        return shape.leaf_list(self._shape).described(self._doc)


COMMUNITIES = CommunitiesType(
    'community',
    community,
    Communities,
    False,
    '<asn>:<value>',
    ['1:1', '[ 1:1 2:2 ]', 'no-export', '[ no-advertise nopeer blackhole ]', '0x10001', '65537', '[ ]'],
    shape.union(
        shape.string(pattern=r'\d+:\d+'),
        shape.enumeration('no-export', 'no-advertise', 'no-export-subconfed', 'no-peer', 'blackhole'),
    ),
    'COMMUNITIES, RFC 1997: <asn>:<value>, or a well-known name',
)
LARGE_COMMUNITIES = CommunitiesType(
    'large-community',
    large_community,
    LargeCommunities,
    True,
    '<asn>:<value>:<value>',
    ['1:2:3', '[ 1:2:3 4:5:6 ]', '[ 1:2:3 1:2:3 ]', '0x1', '1'],
    shape.string(pattern=r'\d+:\d+:\d+'),
    'LARGE_COMMUNITY, RFC 8092: <asn>:<value>:<value>',
)

# --------------------------------------------------------------------------- extended communities

# RFC 4360: two octet AS (0x00) and IPv4 address (0x01); RFC 5668: four octet AS (0x02)
_HEADER = {
    'target': bytes([0x00, 0x02]),
    'target4': bytes([0x01, 0x02]),
    'target-as4': bytes([0x02, 0x02]),
    'origin': bytes([0x00, 0x03]),
    'origin4': bytes([0x01, 0x03]),
    'origin-as4': bytes([0x02, 0x03]),
    'redirect': bytes([0x80, 0x08]),
    'l2info': bytes([0x80, 0x0A]),
    'redirect-to-nexthop': bytes([0x08, 0x00]),
    'bandwidth': bytes([0x40, 0x04]),
    'mup': bytes([0x0C, 0x00]),
}
_ENCODE = {
    'target': 'HL',
    'target4': 'LH',
    'target-as4': 'LH',
    'origin': 'HL',
    'origin4': 'LH',
    'origin-as4': 'LH',
    'redirect': 'HL',
    'l2info': 'BBHH',
    'bandwidth': 'Hf',
    'mup': 'HL',
}
_SIZE = {'B': 0xFF, 'H': 0xFFFF, 'L': 0xFFFFFFFF, 'f': 0xFFFFFFFF}
# draft-ietf-idr-flowspec-redirect-ip: a name and an address, the only two word communities
TAKES_AN_ADDRESS = ('redirect-to-nexthop-ietf', 'copy-to-nexthop-ietf')


def _digit(word: str) -> bool:
    return is_decimal(word[:-1] if word.endswith('L') else word)


def _integer(word: str) -> int:
    # backward compatibility: a trailing L asks for a four octet AS
    if word[-1] == 'L':
        return decimal(word[:-1])
    return decimal_or_hexadecimal(word)


def _ipv4(text: str, value: str) -> int:
    parts = text.split('.')
    if len(parts) != IPV4_OCTETS:
        raise ValueError(f'invalid extended community: {value}, expecting {IPV4_OCTETS} dotted decimal parts')
    number = 0
    for part in parts:
        if not is_decimal(part) or int(part) > _SIZE['B']:
            raise ValueError(f'invalid extended community: {value}, "{part}" is not a decimal number 0-255')
        number = (number << 8) + int(part)
    return number


def _encode(command: str, components: list[int], parts: list[str]) -> tuple[bytes, str]:
    if command not in _HEADER:
        raise ValueError(f'invalid extended community type {command}')
    if command in ('origin', 'target'):
        if '.' in parts[0]:
            command += '4'
        elif components[0] > _SIZE['H'] or parts[0][-1] == 'L':
            command += '-as4'
    encoding = _ENCODE[command]
    if len(components) != len(encoding):
        raise ValueError(f'invalid extended community {command}, expecting {len(components)} fields')
    for size, value in zip(encoding, components):
        if value > _SIZE[size]:
            raise ValueError(f'invalid extended community, value is too large {value}')
    return _HEADER[command], '!' + encoding


def extended_community(word: str) -> ExtendedCommunity:
    name, _, address = word.partition(' ')
    if name in TAKES_AN_ADDRESS:
        from exabgp.bgp.message.update.attribute.community.extended import (
            TrafficNextHopIPv4IETF,
            TrafficNextHopIPv6IETF,
        )

        ip = IP.from_string(address)
        copy = name.startswith('copy')
        if ip.ipv4():
            return TrafficNextHopIPv4IETF.make_traffic_nexthop_ipv4(cast(IPv4, ip), copy)
        return cast(ExtendedCommunity, TrafficNextHopIPv6IETF.make_traffic_nexthop_ipv6(cast(IPv6, ip), copy))
    if not word.count(':'):
        if word[:2].lower() == '0x':
            if len(word) % 2 or not is_hexadecimal(word):
                raise ValueError(f'invalid extended community {word}')
            raw = bytes.fromhex(word[2:])
            return cast(ExtendedCommunity, ExtendedCommunity.unpack_attribute(raw, None))
        if word == 'redirect-to-nexthop':
            return cast(ExtendedCommunity, ExtendedCommunity.unpack_attribute(_HEADER[word] + pack('!HL', 0, 0), None))
        raise ValueError(f'invalid extended community {word} - lc+gc')
    parts = word.split(':')
    command = 'target' if len(parts) == 2 else parts.pop(0)
    components = [_integer(part) if _digit(part) else _ipv4(part, word) for part in parts]
    header, encoding = _encode(command, components, parts)
    return cast(ExtendedCommunity, ExtendedCommunity.unpack_attribute(header + pack(encoding, *components), None))


class ExtendedCommunitiesType(Type[ExtendedCommunities]):
    """One extended community, or several in brackets; the redirect-to-IP ones take an address."""

    name = 'extended-community'

    def parse(self, words: Words) -> ExtendedCommunities:
        where = words.where()
        found = ExtendedCommunities()
        word = words.word()
        try:
            if word != '[':
                found.add(self._one(words, word))
                return found
            for _ in range(MAX_LIST_ITEMS):
                where = words.where()
                word = words.word()
                if word == ']':
                    return found
                found.add(self._one(words, word))
        except (ValueError, IndexError, OSError) as exc:
            raise ConfigError(where, str(exc) or f"'{word}' is not a valid extended community") from None
        raise ConfigError(where, f'an extended-community list holds at most {MAX_LIST_ITEMS} values')

    @staticmethod
    def _one(words: Words, word: str) -> ExtendedCommunity:
        if word in TAKES_AN_ADDRESS:
            address = words.word()
            if not address or address == ']':
                raise ValueError(f'invalid extended community: {word} needs an IP address')
            return extended_community(f'{word} {address}')
        return extended_community(word)

    def render(self, value: ExtendedCommunities) -> list[WordOrSyntax]:
        return [Syntax('['), *(word for each in value.communities for word in str(each).split()), Syntax(']')]

    def hint(self) -> str:
        return '<type>:<value>|[ <type>:<value> ... ]'

    def examples(self) -> list[str]:
        return [
            'target:65000:1',
            '65000:1',
            'origin:10.0.0.1:1',
            'target:4200000000:1',
            '[ target:1:1 origin:2:2 ]',
            'redirect:65000:1',
            'l2info:19:0:1500:111',
            'bandwidth:1:1000',
            '0x0002fde800000001',
            'redirect-to-nexthop',
            'redirect-to-nexthop-ietf 10.0.0.1',
            'copy-to-nexthop-ietf 2001:db8::1',
            '[ redirect-to-nexthop-ietf 10.0.0.1 target:1:1 ]',
        ]

    def shape(self) -> Shape:
        return shape.leaf_list(EXTENDED_COMMUNITY).described(
            'EXTENDED_COMMUNITIES, RFC 4360: route targets, route origins, flow actions and others'
        )


# --------------------------------------------------------------------------- MPLS


class LabelsType(Type[Labels]):
    """One MPLS label, or a stack of them in brackets."""

    name = 'label'

    def parse(self, words: Words) -> Labels:
        where = words.where()
        labels: list[int] = []
        word = words.word()
        try:
            if word != '[':
                labels.append(self._label(word))
            else:
                for _ in range(MAX_LIST_ITEMS):
                    where = words.where()
                    word = words.word()
                    if word == ']':
                        break
                    labels.append(self._label(word))
        except ValueError as exc:
            raise ConfigError(where, str(exc) or f"'{word}' is not a valid label", expected=[self.hint()]) from None
        return Labels.make_labels(labels)

    @staticmethod
    def _label(word: str) -> int:
        label = decimal(word)
        if not 0 <= label <= Labels.MAX:
            raise ValueError(f'MPLS label {label} out of range, it is 0 to {Labels.MAX}')
        return label

    def render(self, value: Labels) -> list[WordOrSyntax]:
        return [Syntax('['), *(str(label) for label in value.labels), Syntax(']')]

    def hint(self) -> str:
        return '<label>|[ <label> ... ]'

    def examples(self) -> list[str]:
        return ['100', '[ 100 ]', '[ 100 200 ]', '1048575']

    def shape(self) -> Shape:
        return shape.leaf_list(shape.integer(0, Labels.MAX), min_items=1).described('the MPLS label stack, RFC 8277')


def _route_distinguisher(word: str) -> RouteDistinguisher:
    separator = word.find(':')
    if separator <= 0:
        raise ValueError(f"'{word}' is not a valid route-distinguisher, it is <asn>:<n> or <ipv4>:<n>")
    administrator = word[:separator]
    try:
        suffix = decimal(word[separator + 1 :])
    except ValueError:
        raise ValueError(f"'{word}' is not a valid route-distinguisher, the suffix is a number") from None
    if '.' in administrator:
        if not 0 <= suffix < pow(2, 16):
            raise ValueError(f"'{word}' is not a valid route-distinguisher (suffix must be 0-65535)")
        octets = administrator.split('.')
        if len(octets) != RD_TYPE_1_OCTETS:
            raise ValueError(f"'{word}' is not a valid route-distinguisher, an IPv4 administrator is 4 octets")
        try:
            raw = bytes([0, 1]) + bytes(decimal(octet) for octet in octets) + bytes([suffix >> 8, suffix & 0xFF])
        except ValueError:
            raise ValueError(f"'{word}' is not a valid route-distinguisher (invalid IPv4 address)") from None
        return RouteDistinguisher(raw)
    try:
        number = decimal(administrator)
    except ValueError:
        raise ValueError(f"'{word}' is not a valid route-distinguisher (prefix must be ASN or IPv4)") from None
    if 0 <= number < pow(2, 16) and 0 <= suffix < pow(2, 32):
        return RouteDistinguisher(bytes([0, 0]) + pack('!H', number) + pack('!L', suffix))
    if 0 <= number < pow(2, 32) and 0 <= suffix < pow(2, 16):
        return RouteDistinguisher(bytes([0, 2]) + pack('!L', number) + pack('!H', suffix))
    raise ValueError(f'invalid route-distinguisher {word}')


ROUTE_DISTINGUISHER = Word(
    'route-distinguisher',
    '<asn>:<n>|<ipv4>:<n>',
    _route_distinguisher,
    ['65000:1', '10.0.0.1:1', '4200000000:1'],
    shape=shape.string(pattern=r'(\d+|(\d{1,3}\.){3}\d{1,3}):\d+'),
    doc='the route distinguisher, RFC 4364: <asn>:<number> or <ipv4>:<number>',
)

# --------------------------------------------------------------------------- configuration only


class Internal(Type[Any]):
    """A value exabgp keeps with the route and never sends: name, split, watchdog, withdraw.

    They travel in the attribute collection under a private code, as an InternalAttribute
    holding the value (bgp/message/update/attribute/internal.py).
    """

    def __init__(
        self,
        name: str,
        klass: type[InternalText] | type[InternalNumber],
        convert: Any,
        hint: str,
        examples: list[str],
        doc: str,
        value: Shape = shape.TEXT,
    ) -> None:
        self.name = name
        self._shape = value.described(doc)
        self._class = klass
        self._convert = convert
        self._hint = hint
        self._examples = examples

    def parse(self, words: Words) -> Any:
        where = words.where()
        try:
            return self._class(self._convert(words.word()))
        except ValueError as exc:
            raise ConfigError(where, str(exc), expected=[self._hint]) from None

    def render(self, value: Any) -> list[WordOrSyntax]:
        return [f'/{int(value)}'] if isinstance(value, InternalNumber) else [str(value)]

    def hint(self) -> str:
        return self._hint

    def examples(self) -> list[str]:
        return self._examples

    def shape(self) -> Shape:
        return self._shape


def _split(word: str) -> int:
    if not word or word[0] != '/' or not is_decimal(word[1:]):
        raise ValueError(f"'{word}' is not a valid split value, it is /<length>")
    return int(word[1:])


def _watchdog(word: str) -> str:
    if word.lower() in ('announce', 'withdraw'):
        raise ValueError(f"'{word}' is a reserved word and cannot be used as a watchdog name")
    return word


NAME = Internal(
    'name',
    InternalName,
    str,
    '<name>',
    ['route-name', ''],
    'a name for the route, kept by exabgp and never sent',
)
# the length of the more specifics to announce, written /<length>
SPLIT = Internal(
    'split',
    InternalSplit,
    _split,
    '/<length>',
    ['/24', '/32'],
    'announce the prefix as its more specifics of this length',
    value=shape.integer(0, IPV6_MASK),
)
WATCHDOG = Internal(
    'watchdog',
    InternalWatchdog,
    _watchdog,
    '<name>',
    ['dog', ''],
    'the watchdog whose API commands announce and withdraw the route',
)


WITHDRAW = Flag('withdraw', InternalWithdraw, 'start with the route withdrawn')


# --------------------------------------------------------------------------- segment routing

SRGB_MAX = pow(2, 24)  # an SRGB base and range are three octets each
LABEL_INDEX_MAX = pow(2, 32)
SRV6_STRUCTURE_FIELDS = 6  # LBL, LNL, FL, AL, transposition length and offset
# the legacy parser looped until it met a closing bracket, forever when there was none
MAX_PREFIX_SID_WORDS = 1024


def _srgb_number(word: str) -> int:
    """The number the word writes in ASCII digits; SRGB_MAX, which is refused, when none."""
    try:
        return decimal(word)
    except ValueError:
        return SRGB_MAX


class PrefixSidType(Type[Any]):
    """`[ <label-index> ]` or `[ <label-index>, [ ( <base>,<range> ) ... ] ]` (RFC 8669).

    legacy: words the format does not expect are skipped, and a word after the closing
    bracket is swallowed when an inner `[` was seen. Where the legacy parser looped forever
    on a list which was never closed, this one stops and refuses it.
    """

    name = 'bgp-prefix-sid'

    def parse(self, words: Words) -> Any:
        from exabgp.bgp.message.update.attribute.sr.labelindex import SrLabelIndex
        from exabgp.bgp.message.update.attribute.sr.prefixsid import PrefixSid
        from exabgp.bgp.message.update.attribute.sr.srgb import SrGb

        where = words.where()
        if words.word() != '[':
            raise ConfigError(where, 'invalid bgp-prefix-sid', expected=[self.hint()])
        label_sid = words.word()
        ranges = self._ranges(words, where)
        try:
            index = decimal(label_sid)
        except ValueError:
            raise ConfigError(where, f"'{label_sid}' is not a valid label index") from None
        attributes: list[Any] = [SrLabelIndex.make_labelindex(index)] if index < LABEL_INDEX_MAX else []
        srgbs: list[tuple[int, int]] = []
        for base, size in ranges:
            numbers = (_srgb_number(base), _srgb_number(size))
            if not all(number < SRGB_MAX for number in numbers):
                raise ConfigError(where, 'could not parse SRGB tupple')
            srgbs.append(numbers)
        if srgbs:
            attributes.append(SrGb.make_srgb(srgbs))
        return PrefixSid(attributes)

    @staticmethod
    def _ranges(words: Words, where: str) -> list[tuple[str, str]]:
        ranges: list[tuple[str, str]] = []
        extra = False
        base = size = None
        for _ in range(MAX_PREFIX_SID_WORDS):
            if words.at_end():
                raise ConfigError(where, "could not parse BGP PrefixSid attribute: missing ']'")
            word = words.word()
            if word == '[':
                extra = True
            elif word == '(':
                base, size = PrefixSidType._range(words, where)
            elif word == ')':
                if base is None or size is None:
                    raise ConfigError(where, 'could not parse BGP PrefixSid attribute: a range without its values')
                ranges.append((base, size))
            elif word == ']':
                if extra:
                    words.take()
                return ranges
        raise ConfigError(where, f'a bgp-prefix-sid holds at most {MAX_PREFIX_SID_WORDS} words')

    @staticmethod
    def _range(words: Words, where: str) -> tuple[str | None, str | None]:
        base = size = None
        after_comma = False
        for _ in range(MAX_PREFIX_SID_WORDS):
            if words.at_end():
                raise ConfigError(where, "could not parse BGP PrefixSid attribute: missing ')'")
            word = words.peek()
            if word == ')':
                return base, size
            words.take()
            if word == ',':
                after_comma = True
            elif after_comma:
                size, after_comma = word, False
            else:
                base = word
        raise ConfigError(where, f'a bgp-prefix-sid holds at most {MAX_PREFIX_SID_WORDS} words')

    def render(self, value: Any) -> list[WordOrSyntax]:
        return list(str(value).split())

    def hint(self) -> str:
        return '[ <label-index> ] | [ <label-index>, [ ( <base>,<range> ) ... ] ]'

    def examples(self) -> list[str]:
        return ['[ 300 ]', '[ 300, [ ( 800000,100 ) ] ]', '[ 300, [ ( 800000,100 ), ( 1000000,5000 ) ] ]']

    def shape(self) -> Shape:
        srgb = shape.container(
            ('base', shape.integer(0, SRGB_MAX - 1).described('the first label of the range')),
            ('range', shape.integer(0, SRGB_MAX - 1).described('the number of labels')),
        )
        return shape.container(
            ('label-index', shape.integer(0, LABEL_INDEX_MAX - 1).described('the label index')),
            ('srgb', shape.leaf_list(srgb).described('the SRGB of the originator')),
        ).described('BGP Prefix-SID, RFC 8669')


class PrefixSidSrv6Type(Type[Any]):
    """`( l3-service|l2-service <sid> [<behavior> [ [ <LBL>,<LNL>,<FL>,<AL>,<Tpose-len>,<Tpose-offset> ] ]] )`."""

    name = 'bgp-prefix-sid-srv6'

    def parse(self, words: Words) -> Any:
        from exabgp.bgp.message.update.attribute.sr.prefixsid import PrefixSid
        from exabgp.bgp.message.update.attribute.sr.srv6.l2service import Srv6L2Service
        from exabgp.bgp.message.update.attribute.sr.srv6.l3service import Srv6L3Service
        from exabgp.bgp.message.update.attribute.sr.srv6.sidinformation import Srv6SidInformation

        where = words.where()
        try:
            words.expect('(')
            service = words.word()
            if service not in ('l3-service', 'l2-service'):
                raise ValueError(f"expect 'l3-service' or 'l2-service', but received '{service}'")
            sid = IPv6.from_string(words.word())
            behavior, structures = self._behavior(words)
            information = [Srv6SidInformation(sid=sid, behavior=behavior, subsubtlvs=structures)]
        except (ValueError, OSError, IndexError) as exc:
            raise ConfigError(where, str(exc) or 'invalid bgp-prefix-sid-srv6', expected=[self.hint()]) from None
        if service == 'l3-service':
            return PrefixSid([Srv6L3Service(subtlvs=information)])
        return PrefixSid([Srv6L2Service(subtlvs=information)])

    @staticmethod
    def _number(word: str) -> int:
        return decimal_or_hexadecimal(word)

    def _behavior(self, words: Words) -> tuple[int, list[Any]]:
        from exabgp.bgp.message.update.attribute.sr.srv6.sidstructure import Srv6SidStructure

        word = words.word()
        if word == ')':
            return 0xFFFF, []
        behavior = self._number(word)
        word = words.word()
        structures: list[Any] = []
        if word == '[':
            fields = []
            for index in range(SRV6_STRUCTURE_FIELDS):
                if index:
                    words.expect(',')
                fields.append(self._number(words.word()))
            words.expect(']')
            structures.append(Srv6SidStructure.make_sid_structure(*fields))
            word = words.word()
        if word != ')':
            raise ValueError(f"expect ')', but received '{word}'")
        return behavior, structures

    def render(self, value: Any) -> list[WordOrSyntax]:
        return list(str(value).split())

    def hint(self) -> str:
        return '( l3-service|l2-service <ipv6> [<behavior> [ [ <LBL>, <LNL>, <FL>, <AL>, <len>, <offset> ] ]] )'

    def examples(self) -> list[str]:
        return [
            '( l3-service 2001:db8::1 )',
            '( l3-service 2001:db8::1 0x48 )',
            '( l2-service 2001:db8::1 0x48 )',
            '( l3-service 2001:db8::1 0x48 [ 64, 24, 16, 0, 16, 64 ] )',
        ]

    def shape(self) -> Shape:
        # RFC 9252 3.2.1, each a length in bits
        fields = (
            ('locator-block', 'the length of the locator block'),
            ('locator-node', 'the length of the locator node'),
            ('function', 'the length of the function'),
            ('argument', 'the length of the argument'),
            ('transposition-length', 'the number of bits transposed into the label'),
            ('transposition-offset', 'the position of the first bit transposed'),
        )
        structure = shape.container(*((name, shape.UINT8.described(doc)) for name, doc in fields))
        return shape.container(
            ('service', shape.enumeration('l3-service', 'l2-service').described('an L3 or an L2 service')),
            ('sid', shape.IPV6_ADDRESS.described('the SRv6 SID')),
            ('behavior', shape.UINT16.described('the endpoint behaviour, RFC 8986')),
            ('structure', structure.described('the SID structure, in bits')),
        ).described('SRv6 services, RFC 9252')
