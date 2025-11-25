"""generic/parser.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Optional

from exabgp.bgp.message.open.asn import ASN
from exabgp.protocol.ip import IP
from exabgp.protocol.ip import IPRange


def string(tokeniser: object) -> str:
    return tokeniser()  # type: ignore[no-any-return,operator]


def boolean(tokeniser: object, default: bool) -> bool:
    status = tokeniser().lower()  # type: ignore[operator]
    if not status:
        return default
    if status in ('true', 'enable', 'enabled'):
        return True
    if status in ('false', 'disable', 'disabled'):
        return False
    raise ValueError(
        f"'{status}' is not a valid boolean\n  Valid options: true, enable, enabled, false, disable, disabled"
    )


def auto_boolean(tokeniser: object, default: bool) -> Optional[bool]:
    status = tokeniser().lower()  # type: ignore[operator]
    if not status:
        return default
    if status in ('true', 'enable', 'enabled'):
        return True
    if status in ('false', 'disable', 'disabled'):
        return False
    if status in ('auto',):
        return None
    raise ValueError(f"'{status}' is not a valid boolean\n  Valid options: true, false, enable, disable, auto")


def port(tokeniser: object) -> int:
    if not tokeniser.tokens:
        raise ValueError('a port number is required (1-65535)')

    value = tokeniser()  # type: ignore[operator]
    try:
        port_num = int(value)
    except ValueError:
        raise ValueError(f"'{value}' is not a valid port number (must be 1-65535)") from None
    if port_num < 1:
        raise ValueError(f'port {port_num} is invalid (must be 1-65535)')
    if port_num > 65535:
        raise ValueError(f'port {port_num} is invalid (must be 1-65535)')
    return port_num


def auto_asn(tokeniser: object, value: Optional[str] = None) -> Optional[ASN]:
    if value is None:
        if not tokeniser.tokens:
            raise ValueError("an ASN or 'auto' is required (e.g., 65001, 1.1, auto)")

    if tokeniser.peek() == 'auto':
        tokeniser()  # type: ignore[operator]
        return None

    return asn(tokeniser)


def asn(tokeniser: object, value: Optional[str] = None) -> ASN:
    if value is None:
        if not tokeniser.tokens:
            raise ValueError('an ASN is required (e.g., 65001 or 1.1)')

    value = tokeniser()  # type: ignore[operator]
    try:
        if value.count('.'):
            high, low = value.split('.', 1)
            as_number = (int(high) << 16) + int(low)
        else:
            as_number = int(value)
        return ASN(as_number)
    except ValueError:
        raise ValueError(
            f"'{value}' is not a valid ASN\n  Format: <number> or <high>.<low> (e.g., 65001 or 1.1)"
        ) from None


def peer_ip(tokeniser: object) -> IPRange:
    if not tokeniser.tokens:
        raise ValueError('an IP address is required (e.g., 192.0.2.1 or 192.0.2.0/24)')

    value = tokeniser()  # type: ignore[operator]
    if '/' in value:
        value, mask = value.split('/', 1)
    else:
        # XXX: This only works as no port are allowed, improve
        mask = '128' if ':' in value else '32'

    try:
        return IPRange.create(value, mask)
    except (OSError, IndexError, ValueError):
        raise ValueError(
            f"'{value}' is not a valid IP address\n  Format: <ip> or <ip>/<prefix> (e.g., 192.0.2.1 or 2001:db8::1/64)"
        ) from None


def ip(tokeniser: object) -> IP:
    if not tokeniser.tokens:
        raise ValueError('an IP address is required (e.g., 192.0.2.1 or 2001:db8::1)')

    value = tokeniser()  # type: ignore[operator]
    try:
        return IP.create(value)
    except (OSError, IndexError, ValueError):
        raise ValueError(f"'{value}' is not a valid IP address (e.g., 192.0.2.1 or 2001:db8::1)") from None
