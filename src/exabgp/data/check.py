"""check.py

Created by Thomas Mangin on 2013-03-18.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any, Callable, ClassVar, Dict

from exabgp.protocol.ip import IPv4
from exabgp.protocol.ip import IPv6

# MD5 password maximum length (RFC 2385)
MD5_PASSWORD_MAX_LENGTH: int = 18  # Maximum length for MD5 authentication password

# Extended community format
EXTENDED_COMMUNITY_COLON_COUNT: int = 2  # Number of colons in extended community format (type:value:value)

# Route distinguisher format
ROUTE_DISTINGUISHER_PARTS: int = 2  # Number of parts in route distinguisher (asn:value or ip:value)

# Array size for aggregate data
AGGREGATOR_PARTS: int = 2  # Number of parts in aggregator (asn, ip)

# Array size for community data
COMMUNITY_PARTS: int = 2  # Number of parts in standard community (high:low)
LARGE_COMMUNITY_PARTS: int = 3  # Number of parts in large community (global:local1:local2)

# Flow numeric operator array size
FLOW_NUMERIC_PARTS: int = 2  # Number of parts in flow numeric operator (operator, value)

# Route distinguisher separator count
RD_SEPARATOR_COUNT: int = 1  # Number of colons in route distinguisher

# IPv4 range separator count
IPV4_RANGE_SEPARATOR_COUNT: int = 1  # Number of slashes in IPv4 range


class TYPE:
    NULL: ClassVar[int] = 0x01
    BOOLEAN: ClassVar[int] = 0x02
    INTEGER: ClassVar[int] = 0x04
    STRING: ClassVar[int] = 0x08
    ARRAY: ClassVar[int] = 0x10
    HASH: ClassVar[int] = 0x20


class PRESENCE:
    OPTIONAL: ClassVar[int] = 0x01
    MANDATORY: ClassVar[int] = 0x02


# TYPE CHECK


def null(data: Any) -> bool:
    return type(data) == type(None)  # noqa


def boolean(data: Any) -> bool:
    return type(data) == type(True)  # noqa


def integer(data: Any) -> bool:
    return type(data) == type(0)  # noqa


def string(data: Any) -> bool:
    return type(data) == type('') or type(data) == type('')  # noqa


def array(data: Any) -> bool:
    return type(data) == type([])  # noqa


def hashtable(data: Any) -> bool:
    return type(data) == type({})  # noqa


# XXX: Not very good to redefine the keyword object, but this class uses no OO ...

CHECK_TYPE: Dict[int, Callable[[Any], bool]] = {
    TYPE.NULL: null,
    TYPE.BOOLEAN: boolean,
    TYPE.INTEGER: integer,
    TYPE.STRING: string,
    TYPE.ARRAY: array,
    TYPE.HASH: hashtable,
}


def kind(kind: int, data: Any) -> bool:
    for t in CHECK_TYPE:
        if kind & t:
            if CHECK_TYPE[t](data):
                return True
    return False


# DATA CHECK


def nop(data: Any) -> bool:
    return True


def uint8(data: Any) -> bool:
    return bool(0 <= data < pow(2, 8))


def uint16(data: Any) -> bool:
    return bool(0 <= data < pow(2, 16))


def uint32(data: Any) -> bool:
    return bool(0 <= data < pow(2, 32))


def uint96(data: Any) -> bool:
    return bool(0 <= data < pow(2, 96))


def float(data: Any) -> bool:
    return bool(0 <= data < 3.4 * pow(10, 38))  # approximation of max from wikipedia


def ip(data: Any) -> bool:
    return ipv4(data) or ipv6(data)


def ipv4(data: Any) -> bool:  # XXX: improve
    return string(data) and data.count('.') == IPv4.DOT_COUNT


def ipv6(data: Any) -> bool:  # XXX: improve
    return string(data) and ':' in data


def range4(data: Any) -> bool:
    return bool(0 < data <= IPv4.BITS)


def range6(data: Any) -> bool:
    return bool(0 < data <= IPv6.BITS)


def ipv4_range(data: Any) -> bool:
    if not data.count('/') == IPV4_RANGE_SEPARATOR_COUNT:
        return False
    ip, r = data.split('/')
    if not ipv4(ip):
        return False
    if not r.isdigit():
        return False
    if not range4(int(r)):
        return False
    return True


def port(data: Any) -> bool:
    return bool(0 <= data < pow(2, 16))


def asn16(data: Any) -> bool:
    return bool(1 <= data < pow(2, 16))


def asn32(data: Any) -> bool:
    return bool(1 <= data < pow(2, 32))


asn = asn32


def md5(data: Any) -> bool:
    return len(data) <= MD5_PASSWORD_MAX_LENGTH


def localpreference(data: Any) -> bool:
    return uint32(data)


def med(data: Any) -> bool:
    return uint32(data)


def aigp(data: Any) -> bool:
    return uint32(data)


def originator(data: Any) -> bool:
    return ipv4(data)


def distinguisher(data: Any) -> bool:
    parts = data.split(':')
    if len(parts) != ROUTE_DISTINGUISHER_PARTS:
        return False
    _, __ = parts
    return (_.isdigit() and asn16(int(_)) and ipv4(__)) or (ipv4(_) and __.isdigit() and asn16(int(__)))


def pathinformation(data: Any) -> bool:
    if integer(data):
        return uint32(data)
    if string(data):
        return ipv4(data)
    return False


def watchdog(data: Any) -> bool:
    return ' ' not in data  # TODO: improve


def split(data: Any) -> bool:
    return range6(data)


# LIST DATA CHECK
# Those function need to perform type checks before using the data


def aspath(data: Any) -> bool:
    return integer(data) and data < pow(2, 32)


def assequence(data: Any) -> bool:
    return integer(data) and data < pow(2, 32)


def community(data: Any) -> bool:
    if integer(data):
        return uint32(data)
    if string(data) and data.lower() in (
        'no-export',
        'no-advertise',
        'no-export-subconfed',
        'nopeer',
        'no-peer',
        'blackhole',
    ):
        return True
    return (
        array(data)
        and len(data) == COMMUNITY_PARTS
        and integer(data[0])
        and integer(data[1])
        and asn16(data[0])
        and uint16(data[1])
    )


def largecommunity(data: Any) -> bool:
    if integer(data):
        return uint96(data)
    return (
        array(data)
        and len(data) == LARGE_COMMUNITY_PARTS
        and integer(data[0])
        and integer(data[1])
        and integer(data[2])
        and asn32(data[0])
        and uint32(data[1])
        and uint32(data[2])
    )


def extendedcommunity(data: Any) -> bool:  # TODO: improve, incomplete see https://tools.ietf.org/rfc/rfc4360.txt
    if integer(data):
        return True
    if string(data) and data.count(':') == EXTENDED_COMMUNITY_COLON_COUNT:
        _, __, ___ = data.split(':')
        if _.lower() not in ('origin', 'target'):
            return False
        return (__.isdigit() and asn16(__) and ipv4(___)) or (ipv4(__) and ___.isdigit() and asn16(___))
    return False


def label(data: Any) -> bool:
    return integer(data) and 0 <= data < pow(2, 20)  # XXX: SHOULD be taken from Label class


def clusterlist(data: Any) -> bool:
    return integer(data) and uint8(data)


def aggregator(data: Any) -> bool:
    if not array(data):
        return False
    if len(data) == 0:
        return True
    if len(data) == AGGREGATOR_PARTS:
        return integer(data[0]) and string(data[1]) and asn(data[0]) and ipv4(data[1])
    return False


def dscp(data: Any) -> bool:
    return integer(data) and uint8(data)


# FLOW DATA CHECK
#


def flow_ipv4_range(data: Any) -> bool:
    if array(data):
        for r in data:
            if not ipv4_range(r):
                return False
        return True
    if string(data):
        return ipv4_range(data)
    return False


def _flow_numeric(data: Any, check: Callable[[Any], bool]) -> bool:
    if not array(data):
        return False
    for et in data:
        if not (
            array(et)
            and len(et) == FLOW_NUMERIC_PARTS
            and et[0] in ('>', '<', '=', '>=', '<=')
            and integer(et[1])
            and check(et[1])
        ):
            return False
    return True


def flow_port(data: Any) -> bool:
    return _flow_numeric(data, port)


def _length(data: Any) -> bool:
    return uint16(data)


def flow_length(data: Any) -> bool:
    return _flow_numeric(data, _length)


def redirect(data: Any) -> bool:  # TODO: check that we are not too restrictive with our asn() calls
    parts = data.split(':')
    if len(parts) != ROUTE_DISTINGUISHER_PARTS:
        return False
    _, __ = parts
    if not __.isdigit() and asn16(int(__)):
        return False
    return ipv4(_) or (_.isdigit() and asn16(int(_)))
