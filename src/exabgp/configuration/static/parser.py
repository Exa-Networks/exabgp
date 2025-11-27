"""inet/parser.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import List, Optional, Tuple, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.configuration.core.parser import Tokeniser

from struct import pack

from exabgp.protocol.family import AFI

from exabgp.protocol.ip import IP
from exabgp.protocol.ip import IPSelf
from exabgp.protocol.ip import IPRange
from exabgp.protocol.ip import IPv4

from exabgp.bgp.message import Action
from exabgp.bgp.message.update.nlri import CIDR
from exabgp.bgp.message.update.nlri import INET
from exabgp.bgp.message.update.nlri import IPVPN

from exabgp.bgp.message.open import ASN
from exabgp.bgp.message.open import RouterID
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute import Attributes
from exabgp.bgp.message.update.attribute import NextHop
from exabgp.bgp.message.update.attribute import NextHopSelf
from exabgp.bgp.message.update.attribute import Origin
from exabgp.bgp.message.update.attribute import MED
from exabgp.bgp.message.update.attribute import ASPath
from exabgp.bgp.message.update.attribute import SET
from exabgp.bgp.message.update.attribute import SEQUENCE
from exabgp.bgp.message.update.attribute import CONFED_SET
from exabgp.bgp.message.update.attribute import CONFED_SEQUENCE
from exabgp.bgp.message.update.attribute import LocalPreference
from exabgp.bgp.message.update.attribute import AtomicAggregate
from exabgp.bgp.message.update.attribute import Aggregator
from exabgp.bgp.message.update.attribute import Aggregator4  # noqa: F401,E261
from exabgp.bgp.message.update.attribute import OriginatorID
from exabgp.bgp.message.update.attribute import ClusterID
from exabgp.bgp.message.update.attribute import ClusterList
from exabgp.bgp.message.update.attribute import AIGP
from exabgp.bgp.message.update.attribute import GenericAttribute

from exabgp.bgp.message.update.attribute.community import Community
from exabgp.bgp.message.update.attribute.community import Communities
from exabgp.bgp.message.update.attribute.community import LargeCommunity
from exabgp.bgp.message.update.attribute.community import LargeCommunities
from exabgp.bgp.message.update.attribute.community import ExtendedCommunity
from exabgp.bgp.message.update.attribute.community import ExtendedCommunities

from exabgp.bgp.message.update.nlri.qualifier import PathInfo

from exabgp.rib.change import Change

# IP address validation constants
EXTENDED_COMMUNITY_TARGET_PARTS = 2  # Target extended community has 2 parts (ASN:value)


def prefix(tokeniser: 'Tokeniser') -> IPRange:
    # XXX: could raise
    ip = tokeniser()
    try:
        ip, mask = ip.split('/')
    except ValueError:
        mask = '32'
        if ':' in ip:
            mask = '128'

    tokeniser.afi = IP.toafi(ip)
    iprange = IPRange.create(ip, mask)

    if iprange.address() & iprange.mask.hostmask() != 0:
        raise ValueError(
            f"'{ip}/{mask}' is not a valid network\n  The host bits must be zero for the given prefix length"
        )

    return iprange


def path_information(tokeniser: 'Tokeniser') -> PathInfo:
    pi = tokeniser()
    if pi.isdigit():
        return PathInfo(integer=int(pi))
    return PathInfo(ip=pi)


def next_hop(
    tokeniser: 'Tokeniser', afi: Optional[AFI] = None
) -> Tuple[Union[IP, IPSelf], Union[NextHop, NextHopSelf]]:
    value = tokeniser()
    if value.lower() == 'self':
        return IPSelf(tokeniser.afi), NextHopSelf(tokeniser.afi)
    ip = IP.create(value)
    if ip.afi == AFI.ipv4 and afi == AFI.ipv6:
        ip = IP.create('::ffff:{}'.format(ip))
    return ip, NextHop(ip.top())


# XXX: using Action.UNSET should we use the following ?
# action = Action.ANNOUNCE if tokeniser.announce else Action.WITHDRAW


def inet(tokeniser: 'Tokeniser') -> Change:
    ipmask = prefix(tokeniser)
    inet = INET(afi=IP.toafi(ipmask.top()), safi=IP.tosafi(ipmask.top()), action=Action.UNSET)
    inet.cidr = CIDR(ipmask.ton(), ipmask.mask)

    return Change(inet, Attributes())


# XXX: using Action.ANNOUNCE should we use the following ?
# action = Action.ANNOUNCE if tokeniser.announce else Action.WITHDRAW


def mpls(tokeniser: 'Tokeniser') -> Change:
    ipmask = prefix(tokeniser)
    mpls = IPVPN(afi=IP.toafi(ipmask.top()), safi=IP.tosafi(ipmask.top()), action=Action.ANNOUNCE)
    mpls.cidr = CIDR(ipmask.ton(), ipmask.mask)

    return Change(mpls, Attributes())


def attribute(tokeniser: 'Tokeniser') -> GenericAttribute:
    start = tokeniser()
    if start != '[':
        raise ValueError('invalid attribute format\n  Format: [ 0xCODE 0xFLAG 0xDATA ]')

    code = tokeniser().lower()
    if not code.startswith('0x'):
        raise ValueError(f"'{code}' is not a valid attribute code\n  Must be hexadecimal (e.g., 0x01)")
    try:
        code_int: int = int(code, 16)
    except ValueError:
        raise ValueError(f"'{code}' is not a valid attribute code\n  Must be hexadecimal (e.g., 0x01)") from None

    flag = tokeniser().lower()
    if not flag.startswith('0x'):
        raise ValueError(f"'{flag}' is not a valid attribute flag\n  Must be hexadecimal (e.g., 0x40)")
    try:
        flag_int: int = int(flag, 16)
    except ValueError:
        raise ValueError(f"'{flag}' is not a valid attribute flag\n  Must be hexadecimal (e.g., 0x40)") from None

    data = tokeniser().lower()
    if not data.startswith('0x'):
        raise ValueError(f"'{data}' is not valid attribute data\n  Must be hexadecimal (e.g., 0x0102)")
    if len(data) % 2:
        raise ValueError(f"'{data}' has invalid length\n  Hexadecimal data must have even number of digits")
    data_bytes: bytes = b''.join(bytes([int(data[_ : _ + 2], 16)]) for _ in range(2, len(data), 2))

    end = tokeniser()
    if end != ']':
        raise ValueError("invalid attribute format - missing closing ']'\n  Format: [ 0xCODE 0xFLAG 0xDATA ]")

    return GenericAttribute(code_int, flag_int, data_bytes)

    # for ((ID,flag),klass) in Attribute.registered_attributes.items():
    # 	length = len(data)
    # 	if code == ID and flag | Attribute.Flag.EXTENDED_LENGTH == klass.FLAG | Attribute.Flag.EXTENDED_LENGTH:
    # 		# if length > 0xFF or flag & Attribute.Flag.EXTENDED_LENGTH:
    # 		# 	raw = pack('!BBH',flag,code,length & (0xFF-Attribute.Flag.EXTENDED_LENGTH)) + data
    # 		# else:
    # 		# 	raw = pack('!BBB',flag,code,length) + data
    # 		return klass.unpack(data,None)


def aigp(tokeniser: 'Tokeniser') -> AIGP:
    if not tokeniser.tokens:
        raise ValueError('aigp requires a value\n  Format: <number> or 0x<hex> (e.g., 100 or 0x64)')
    value = tokeniser()
    base = 16 if value.lower().startswith('0x') else 10
    try:
        number = int(value, base)
    except ValueError:
        raise ValueError(
            f"'{value}' is not a valid AIGP value\n  Format: <number> or 0x<hex> (e.g., 100 or 0x64)"
        ) from None

    return AIGP(b'\x01\x00\x0b' + pack('!Q', number))


def origin(tokeniser: 'Tokeniser') -> Origin:
    value = tokeniser().lower()
    if value == 'igp':
        return Origin(Origin.IGP)
    if value == 'egp':
        return Origin(Origin.EGP)
    if value == 'incomplete':
        return Origin(Origin.INCOMPLETE)
    raise ValueError(f"'{value}' is not a valid origin\n  Valid options: igp, egp, incomplete")


def med(tokeniser: 'Tokeniser') -> MED:
    value = tokeniser()
    if not value.isdigit():
        raise ValueError(f"'{value}' is not a valid MED\n  Must be a non-negative integer (e.g., 100)")
    return MED(int(value))


def as_path(tokeniser: 'Tokeniser') -> ASPath:
    as_path: List[Union[SEQUENCE, CONFED_SEQUENCE, SET, CONFED_SET, ASN]] = []
    insert: Optional[Union[SEQUENCE, CONFED_SEQUENCE, SET, CONFED_SET]] = None

    while True:
        value = tokeniser()

        if value == '[':
            value = tokeniser.peek()

            if value != '{':
                insert = SEQUENCE()
            else:
                insert = CONFED_SEQUENCE()

        elif value == '(':
            value = tokeniser.peek()

            if value != '{':
                insert = SET()
            else:
                insert = CONFED_SET()

        elif len(as_path) == 0:
            try:
                return ASPath(ASN.from_string(value))  # type: ignore[arg-type]
            except ValueError:
                raise ValueError('could not parse as-path') from None
        else:
            raise ValueError('could not parse as-path')

        while True:
            value = tokeniser()

            # could be too nice eating a trailing and ignore a erroneous },,
            # but simpler that way
            if value in (',', '}'):
                continue

            if value in (')', ']'):
                as_path.append(insert)

                value = tokeniser.peek()
                if value in ('[', '('):
                    break

                return ASPath(as_path)  # type: ignore[arg-type]

            try:
                insert.append(ASN.from_string(value))
                continue
            except ValueError:
                raise ValueError('could not parse as-path') from None


def local_preference(tokeniser: 'Tokeniser') -> LocalPreference:
    value = tokeniser()
    if not value.isdigit():
        raise ValueError(f"'{value}' is not a valid local-preference\n  Must be a non-negative integer (e.g., 100)")
    return LocalPreference(int(value))


def atomic_aggregate(tokeniser: 'Tokeniser') -> AtomicAggregate:
    return AtomicAggregate()


def aggregator(tokeniser: 'Tokeniser') -> Aggregator:
    agg = tokeniser()
    eat = agg == '('

    if eat:
        agg = tokeniser()
        if agg.endswith(')'):
            eat = False
            agg = agg[:-1]
    elif agg.startswith('('):
        if agg.endswith(')'):
            eat = False
            agg = agg[1:-1]
        else:
            eat = True
            agg = agg[1:]

    try:
        as_number, address = agg.split(':')
        local_as = ASN.from_string(as_number)
        local_address = RouterID(address)
    except (ValueError, IndexError):
        raise ValueError(
            f"'{agg}' is not a valid aggregator\n"
            f'  Format: <ASN>:<router-id> or (<ASN>:<router-id>) (e.g., 65001:192.0.2.1)'
        ) from None

    if eat:
        if tokeniser() != ')':
            raise ValueError("invalid aggregator - missing closing ')'\n  Format: (<ASN>:<router-id>)")

    return Aggregator(local_as, local_address)


def originator_id(tokeniser: 'Tokeniser') -> OriginatorID:
    value = tokeniser()
    if value.count('.') != IPv4.DOT_COUNT:
        raise ValueError(f"'{value}' is not a valid originator-id\n  Format: IPv4 address (e.g., 192.0.2.1)")
    if not all(_.isdigit() for _ in value.split('.')):
        raise ValueError(f"'{value}' is not a valid originator-id\n  Format: IPv4 address (e.g., 192.0.2.1)")
    return OriginatorID(value)


def cluster_list(tokeniser: 'Tokeniser') -> ClusterList:
    clusterids: List[ClusterID] = []
    value = tokeniser()
    try:
        if value == '[':
            while True:
                value = tokeniser()
                if value == ']':
                    break
                clusterids.append(ClusterID(value))
        else:
            clusterids.append(ClusterID(value))
        if not clusterids:
            raise ValueError('cluster-list is empty\n  Format: <cluster-id> or [ <cluster-id1>, <cluster-id2>, ... ]')
        return ClusterList(clusterids)  # type: ignore[arg-type]
    except ValueError:
        raise ValueError(
            f"'{value}' is not a valid cluster-list\n  Format: <cluster-id> or [ <cluster-id1>, <cluster-id2>, ... ]"
        ) from None


# XXX: Community does does not cache anymore .. we SHOULD really do it !


def _community(value: str) -> Community:
    separator = value.find(':')
    if separator > 0:
        prefix = value[:separator]
        suffix = value[separator + 1 :]

        if not prefix.isdigit() or not suffix.isdigit():
            raise ValueError('invalid community {}'.format(value))

        prefix_int, suffix_int = int(prefix), int(suffix)

        if prefix_int > Community.MAX:
            raise ValueError('invalid community {} (prefix too large)'.format(value))

        if suffix_int > Community.MAX:
            raise ValueError('invalid community {} (suffix too large)'.format(value))

        return Community(pack('!L', (prefix_int << 16) + suffix_int))

    if value[:2].lower() == '0x':
        number = int(value, 16)
        if number > Community.MAX:
            raise ValueError('invalid community {} (too large)'.format(value))
        return Community(pack('!L', number))

    low = value.lower()
    if low == 'no-export' or low == 'no_export':
        return Community(Community.NO_EXPORT)
    if low == 'no-advertise' or low == 'no_advertise':
        return Community(Community.NO_ADVERTISE)
    if low == 'no-export-subconfed':
        return Community(Community.NO_EXPORT_SUBCONFED)
    # no-peer is not a correct syntax but I am sure someone will make the mistake :)
    if low == 'nopeer' or low == 'no-peer':
        return Community(Community.NO_PEER)
    if low == 'blackhole':
        return Community(Community.BLACKHOLE)
    if value.isdigit():
        number = int(value)
        if number > Community.MAX:
            raise ValueError('invalid community {} (too large)'.format(value))
        return Community(pack('!L', number))
    raise ValueError('invalid community name {}'.format(value))


def community(tokeniser: 'Tokeniser') -> Communities:
    communities = Communities()

    value = tokeniser()
    if value == '[':
        while True:
            value = tokeniser()
            if value == ']':
                break
            communities.add(_community(value))
    else:
        communities.add(_community(value))

    return communities


def _large_community(value: str) -> LargeCommunity:
    separator = value.find(':')
    if separator > 0:
        prefix, affix, suffix = value.split(':')

        if not any(map(lambda c: c.isdigit(), [prefix, affix, suffix])):
            raise ValueError('invalid community {}'.format(value))

        prefix_int, affix_int, suffix_int = map(int, [prefix, affix, suffix])

        for i in [prefix_int, affix_int, suffix_int]:
            if i > LargeCommunity.MAX:
                raise ValueError('invalid community %i in %s too large' % (i, value))

        return LargeCommunity(pack('!LLL', prefix_int, affix_int, suffix_int))

    if value[:2].lower() == '0x':
        number = int(value)
        if number > LargeCommunity.MAX:
            raise ValueError('invalid large community {} (too large)'.format(value))
        return LargeCommunity(pack('!LLL', number >> 64, (number >> 32) & 0xFFFFFFFF, number & 0xFFFFFFFF))

    value = value.lower()
    if value.isdigit():
        number = int(value)
        if number > LargeCommunity.MAX:
            raise ValueError('invalid large community {} (too large)'.format(value))
        return LargeCommunity(pack('!LLL', number >> 64, (number >> 32) & 0xFFFFFFFF, number & 0xFFFFFFFF))
    raise ValueError('invalid large community name {}'.format(value))


def large_community(tokeniser: 'Tokeniser') -> LargeCommunities:
    large_communities = LargeCommunities()

    value = tokeniser()
    if value == '[':
        while True:
            value = tokeniser()
            if value == ']':
                break
            lc = _large_community(value)
            if lc in large_communities.communities:
                continue
            large_communities.add(lc)  # type: ignore[arg-type]
    else:
        large_communities.add(_large_community(value))  # type: ignore[arg-type]

    return large_communities


# fmt: off
_HEADER = {
    # header and subheader
    'target':   bytes([0x00, 0x02]),
    'target4':  bytes([0x01, 0x02]),
    # TODO: OriginASN4Number (2,2)
    'origin':   bytes([0x00, 0x03]),
    'origin4':  bytes([0x01, 0x03]),
    # TODO: RouteTargetASN4Number (2,3)
    'redirect': bytes([0x80, 0x08]),
    'l2info':   bytes([0x80, 0x0A]),
    'redirect-to-nexthop': bytes([0x08, 0x00]),
    'bandwidth': bytes([0x40, 0x04]),
    'mup': bytes([0x0C, 0x00]),
}

# fmt: off
_ENCODE = {
    'target':   'HL',
    'target4':  'LH',
    'origin':   'HL',
    'origin4':  'LH',
    'redirect': 'HL',
    'l2info':   'BBHH',
    'bandwidth': 'Hf',
    'mup': 'HL',
}
# fmt: on

_SIZE_B = 0xFF
_SIZE_H = 0xFFFF
_SIZE_L = 0xFFFFFFFF


def _digit(string: str) -> bool:
    if string.endswith('L'):
        string = string[:-1]
    return string.isdigit()


# backward compatibility hack
def _integer(string: str) -> int:
    base = 10
    if string.startswith('0x'):
        string = string[2:]
        base = 16
    if string[-1] == 'L':
        return int(string[:-1])
    return int(string, base)


def _ip(string: str, error: str) -> int:
    if '.' not in string:
        raise ValueError('invalid extended community: {}'.format(error))
    v = [int(_) for _ in string.split('.')]
    # could use b''.join() - for speed?
    return (v[0] << 24) + (v[1] << 16) + (v[2] << 8) + v[3]


def _encode(command: str, components: List[int], parts: List[str]) -> Tuple[bytes, str]:
    if command not in _HEADER:
        raise ValueError('invalid extended community type {}'.format(command))

    if command in ('origin', 'target'):
        if components[0] > _SIZE_H or '.' in parts[0] or parts[0][-1] == 'L':
            command += '4'

    encoding = _ENCODE[command]

    if len(components) != len(encoding):
        raise ValueError('invalid extended community %s, expecting %d fields' % (command, len(components)))

    for size, value in zip(encoding, components):
        if size == 'B' and value > _SIZE_B:
            raise ValueError('invalid extended community, value is too large %d' % value)
        if size == 'H' and value > _SIZE_H:
            raise ValueError('invalid extended community, value is too large %d' % value)
        if size in ('L', 'f') and value > _SIZE_L:
            raise ValueError('invalid extended community, value is too large %d' % value)

    return _HEADER[command], '!' + _ENCODE[command]


def _extended_community_hex(value: str) -> ExtendedCommunity:
    # we could raise if the length is not 8 bytes (16 chars)
    if len(value) % 2:
        raise ValueError('invalid extended community {}'.format(value))
    raw = b''.join(bytes([int(value[_ : _ + 2], 16)]) for _ in range(2, len(value), 2))
    return ExtendedCommunity.unpack_attribute(raw, None)


def _extended_community(value: str) -> ExtendedCommunity:
    if not value.count(':'):
        if value[:2].lower() == '0x':
            return _extended_community_hex(value)

        if value == 'redirect-to-nexthop':
            header = _HEADER[value]
            return ExtendedCommunity.unpack_attribute(header + pack('!HL', 0, 0), None)  # type: ignore[return-value]

        raise ValueError('invalid extended community {} - lc+gc'.format(value))

    parts = value.split(':')
    command = 'target' if len(parts) == EXTENDED_COMMUNITY_TARGET_PARTS else parts.pop(0)
    components = [_integer(_) if _digit(_) else _ip(_, value) for _ in parts]
    header, packed = _encode(command, components, parts)

    return ExtendedCommunity.unpack_attribute(header + pack(packed, *components), None)


def extended_community(tokeniser: 'Tokeniser') -> ExtendedCommunities:
    communities = ExtendedCommunities()

    value = tokeniser()
    if value == '[':
        while True:
            value = tokeniser()
            if value == ']':
                break
            communities.add(_extended_community(value))
    else:
        communities.add(_extended_community(value))

    return communities


# Duck class, faking part of the Attribute interface
# We add this to routes when when need o split a route in smaller route
# The value stored is the longer netmask we want to use
# As this is not a real BGP attribute this stays in the configuration file


def name(tokeniser: 'Tokeniser') -> str:
    class Name(str):
        ID = Attribute.CODE.INTERNAL_NAME

    return Name(tokeniser())


def split(tokeniser: 'Tokeniser') -> int:
    class Split(int):
        ID = Attribute.CODE.INTERNAL_SPLIT

    cidr = tokeniser()

    if not cidr or cidr[0] != '/':
        raise ValueError(f"'{cidr}' is not a valid split value\n  Format: /<prefix-length> (e.g., /24)")

    size = cidr[1:]

    if not size.isdigit():
        raise ValueError(f"'{cidr}' is not a valid split value\n  Format: /<prefix-length> (e.g., /24)")

    return Split(int(size))


def watchdog(tokeniser: 'Tokeniser') -> str:
    class Watchdog(str):
        ID = Attribute.CODE.INTERNAL_WATCHDOG

    command = tokeniser()
    if command.lower() in ['announce', 'withdraw']:
        raise ValueError(
            f"'{command}' is a reserved word and cannot be used as a watchdog name\n  Choose a different name"
        )
    return Watchdog(command)


def withdraw(tokeniser: Optional['Tokeniser'] = None) -> object:
    class Withdrawn:
        ID = Attribute.CODE.INTERNAL_WITHDRAW

    return Withdrawn()
