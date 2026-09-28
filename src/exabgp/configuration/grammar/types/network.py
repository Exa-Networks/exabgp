"""network.py

Addresses, ports and AS numbers, as the configuration writes them.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.holdtime import HoldTime
from exabgp.bgp.message.open.routerid import RouterID
from exabgp.configuration.grammar import shape
from exabgp.configuration.grammar.types.word import Number, Word
from exabgp.protocol.ip import IP, IPRange

PORT_MAX = 65535
TTL_MAX = 255
IPV4_MASK = 32
IPV6_MASK = 128
HOLD_TIME_MIN_NONZERO = 3  # RFC 4271: 0 disables the hold timer, otherwise at least 3 seconds


def _ip(word: str) -> IP:
    try:
        return IP.from_string(word)
    except (OSError, IndexError, ValueError):
        raise ValueError(f"'{word}' is not a valid IP address") from None


def _ip_or_auto(word: str) -> IP | None:
    if word == 'auto':
        return None
    return _ip(word)


def _ip_range(word: str) -> IPRange:
    """An address, or an address and a mask: the peers a neighbor accepts."""
    try:
        if '/' in word:
            address, mask = word.split('/', 1)
            return IPRange.make_range(address, int(mask))
        return IPRange.make_range(word, IPV6_MASK if ':' in word else IPV4_MASK)
    except (OSError, IndexError, ValueError):
        raise ValueError(f"'{word}' is not a valid IP address or range") from None


def _asn(word: str) -> ASN:
    return ASN.from_string(word)


def _asn_or_auto(word: str) -> ASN | None:
    # case matters: `AUTO` is not `auto`, it is refused as an AS number
    if word == 'auto':
        return None
    return ASN.from_string(word)


def _router_id(word: str) -> RouterID:
    try:
        return RouterID(word)
    except (ValueError, OSError):
        raise ValueError(f"'{word}' is not a valid router-id") from None


def _hold_time(word: str) -> HoldTime:
    try:
        hold_time = HoldTime(int(word))
    except ValueError:
        raise ValueError(f"'{word}' is not a valid hold-time") from None
    if hold_time < HOLD_TIME_MIN_NONZERO and hold_time != 0:
        raise ValueError(f'hold-time {hold_time} is invalid, it is 0 or at least {HOLD_TIME_MIN_NONZERO} seconds')
    if hold_time > HoldTime.MAX:
        raise ValueError(f'hold-time {hold_time} is invalid, the most is {HoldTime.MAX} seconds')
    return hold_time


def _port(word: str) -> int:
    try:
        port = int(word)
    except ValueError:
        raise ValueError(f"'{word}' is not a valid port") from None
    if not 1 <= port <= PORT_MAX:
        raise ValueError(f'port {port} is invalid, it is 1-{PORT_MAX}')
    return port


def _ttl(word: str) -> int | None:
    try:
        ttl = int(word)
    except ValueError:
        if word in ('false', 'disable', 'disabled'):
            return None
        raise ValueError(f"'{word}' is not a valid TTL") from None
    if not 0 <= ttl <= TTL_MAX:
        raise ValueError(f'TTL {ttl} is invalid, it is 0-{TTL_MAX}')
    return ttl


IP_ADDRESS = Word('ip-address', '<ip>', _ip, ['192.0.2.1', '2001:db8::1'], shape=shape.IP_ADDRESS)
IP_OR_AUTO = Word(
    'ip-address',
    '<ip>|auto',
    _ip_or_auto,
    ['192.0.2.1', '2001:db8::1', 'auto'],
    render=lambda value: ['auto' if value is None else str(value)],
    shape=shape.union(shape.IP_ADDRESS, shape.enumeration('auto')),
)
IP_RANGE = Word(
    'ip-range',
    '<ip>[/<mask>]',
    _ip_range,
    ['127.0.0.1', '127.0.0.0/8', '::1', '2001:db8::/64'],
    render=lambda value: [repr(value)],
    shape=shape.union(shape.IP_ADDRESS, shape.IP_PREFIX),
)
ASN_OR_AUTO = Word(
    'as-number',
    '<asn>|auto',
    _asn_or_auto,
    ['65000', '4200000000', '1.1', 'auto'],
    render=lambda value: ['auto' if value is None else str(value)],
    shape=shape.union(shape.AS_NUMBER, shape.enumeration('auto')),
)
ASN_WORD: Number[ASN] = Number(
    'as-number',
    ((0, shape.UINT32_MAX),),
    convert=_asn,
    examples=['65000', '4200000000', '1.1'],
    hint='<asn>',
    typedef='inet:as-number',
)
ROUTER_ID = Word('router-id', '<ipv4>', _router_id, ['192.0.2.1'], shape=shape.IPV4_ADDRESS)
HOLD_TIME: Number[HoldTime] = Number(
    'hold-time',
    ((0, 0), (HOLD_TIME_MIN_NONZERO, HoldTime.MAX)),
    convert=_hold_time,
    examples=['0', '3', '180', '65535'],
)
PORT: Number[int] = Number('port', ((1, PORT_MAX),), convert=_port, examples=['1', '179', '65535'])
TTL = Word(
    'ttl',
    '<0-255>|disable',
    _ttl,
    ['0', '1', '255', 'false', 'disable', 'disabled'],
    render=lambda value: ['disable' if value is None else str(value)],
    shape=shape.union(shape.integer(0, TTL_MAX), shape.enumeration('disable')),
)
