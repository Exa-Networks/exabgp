"""neighbor/parser.py

Created by Thomas Mangin on 2014-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import re
from string import ascii_letters
from string import digits
from typing import List
from typing import Optional

from exabgp.bgp.message.open.routerid import RouterID
from exabgp.bgp.message.open.holdtime import HoldTime
from exabgp.configuration.parser import string
from exabgp.protocol.ip import IP

# Configuration parsing constants
INHERIT_SINGLE_TOKEN_COUNT = 2  # Number of tokens for single inheritance
INHERIT_MIN_LIST_TOKEN_COUNT = 4  # Minimum tokens for inherit list ([...])
HOSTNAME_MAX_LENGTH = 255  # Maximum hostname length (RFC 1123)

# Hold time constraint (RFC 4271)
MIN_NONZERO_HOLDTIME = 3  # Minimum hold time in seconds (must be 0 or >= 3)


def inherit(tokeniser) -> List[str]:
    if len(tokeniser.tokens) == INHERIT_SINGLE_TOKEN_COUNT:
        return [tokeniser()]
    if (
        len(tokeniser.tokens) < INHERIT_MIN_LIST_TOKEN_COUNT
        or tokeniser.tokens[1] != '['
        or tokeniser.tokens[-1] != ']'
    ):
        raise ValueError('invalid inherit list')
    return tokeniser.tokens[2:-1]  # type: ignore[no-any-return]


def hostname(tokeniser) -> str:
    value = string(tokeniser)
    if not value[0].isalnum():
        raise ValueError('bad host-name (alphanumeric)')
    if not value[-1].isalnum() or value[-1].isdigit():
        raise ValueError('bad host-name (alphanumeric)')
    if '..' in value:
        raise ValueError('bad host-name (double period)')
    if not all(c in ascii_letters + digits + '.-' for c in value):
        raise ValueError('bad host-name (charset)')
    if len(value) > HOSTNAME_MAX_LENGTH:
        raise ValueError('bad host-name (length)')

    return value


def domainname(tokeniser) -> str:
    value = string(tokeniser)
    if not value:
        raise ValueError('bad domain-name')
    if not value[0].isalnum() or value[0].isdigit():
        raise ValueError('bad domain-name')
    if not value[-1].isalnum() or value[-1].isdigit():
        raise ValueError('bad domain-name')
    if '..' in value:
        raise ValueError('bad domain-name')
    if not all(c in ascii_letters + digits + '.-' for c in value):
        raise ValueError('bad domain-name')
    if len(value) > HOSTNAME_MAX_LENGTH:
        raise ValueError('bad domain-name (length)')
    return value


def description(tokeniser) -> str:
    try:
        return string(tokeniser)
    except Exception:
        raise ValueError('bad neighbor description') from None


def md5(tokeniser) -> str:
    value = tokeniser()
    if not value:
        raise ValueError(
            'value requires the value password as an argument (quoted or unquoted).  FreeBSD users should use "kernel" as the argument.',
        )
    return value  # type: ignore[no-any-return]


def ttl(tokeniser) -> Optional[int]:
    value = tokeniser()
    try:
        attl = int(value)
    except ValueError:
        if value in ('false', 'disable', 'disabled'):
            return None
        raise ValueError(f'invalid ttl-security "{value}"') from None
    if attl < 0:
        raise ValueError('ttl-security can not be negative')
    if attl > HOSTNAME_MAX_LENGTH:
        raise ValueError(f'ttl must be smaller than {HOSTNAME_MAX_LENGTH + 1}')
    return attl


def local_address(tokeniser) -> Optional[IP]:
    if not tokeniser.tokens:
        raise ValueError("an ip address  or 'auto' is required")

    value = tokeniser()
    if value == 'auto':
        return None
    try:
        return IP.create(value)
    except (OSError, IndexError, ValueError):
        raise ValueError(f'"{value}" is an invalid IP address') from None


def source_interface(tokeniser) -> str:
    try:
        return string(tokeniser)
    except Exception:
        raise ValueError('bad source interface') from None


def router_id(tokeniser) -> RouterID:
    value = tokeniser()
    try:
        return RouterID(value)
    except ValueError:
        raise ValueError(f'"{value}" is an invalid router-id') from None


def hold_time(tokeniser) -> HoldTime:
    value = tokeniser()
    try:
        holdtime = HoldTime(int(value))
    except ValueError:
        raise ValueError(f'"{value}" is an invalid hold-time') from None
    if holdtime < MIN_NONZERO_HOLDTIME and holdtime != 0:
        raise ValueError(f'holdtime must be zero or at least {MIN_NONZERO_HOLDTIME} seconds')
    if holdtime > HoldTime.MAX:
        raise ValueError(f'holdtime must be smaller or equal to {HoldTime.MAX}')
    return holdtime


def processes(tokeniser) -> List[str]:
    result: List[str] = []
    token = tokeniser()
    if token != '[':
        raise ValueError('invalid processes, does not start with [')

    while True:
        token = tokeniser()
        if not token:
            raise ValueError('invalid processes, does not end with ]')
        if token == ']':
            break
        if token == ',':
            continue
        result.append(token)

    return result


def processes_match(tokeniser) -> List[str]:
    result: List[str] = []
    token = tokeniser()
    if token != '[':
        raise ValueError('invalid processes-match, does not start with [')

    while True:
        token = tokeniser()
        if not token:
            raise ValueError('invalid processes-match, does not end with ]')
        if token == ']':
            break
        if token == ',':
            continue
        try:
            re.compile(token)
        except re.error:
            raise ValueError(f'"{token}" is not a valid regex, "re" lib returns error {re.error}.') from None
        result.append(token)

    return result


def rate_limit(tokeniser) -> int:
    value = tokeniser().lower()
    if value in ('disable', 'disabled'):
        return 0
    try:
        rate = int(value)
    except ValueError:
        raise ValueError(f'"{value}" is an invalid rate-limit') from None
    if rate <= 0:
        raise ValueError('rate must be zero or at 1 (per second)')
    return rate
