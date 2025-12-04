"""neighbor/parser.py

Created by Thomas Mangin on 2014-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import re
from string import ascii_letters
from string import digits

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


def inherit(tokeniser) -> list[str]:
    if len(tokeniser.tokens) == INHERIT_SINGLE_TOKEN_COUNT:
        return [tokeniser()]
    if (
        len(tokeniser.tokens) < INHERIT_MIN_LIST_TOKEN_COUNT
        or tokeniser.tokens[1] != '['
        or tokeniser.tokens[-1] != ']'
    ):
        raise ValueError('invalid inherit list\n  Format: inherit <template> or inherit [ template1, template2, ... ]')
    return tokeniser.tokens[2:-1]  # type: ignore[no-any-return]


def hostname(tokeniser) -> str:
    value = string(tokeniser)
    if not value[0].isalnum():
        raise ValueError(f"'{value}' is not a valid hostname\n  Must start with alphanumeric character")
    if not value[-1].isalnum() or value[-1].isdigit():
        raise ValueError(f"'{value}' is not a valid hostname\n  Must end with a letter")
    if '..' in value:
        raise ValueError(f"'{value}' is not a valid hostname\n  Cannot contain consecutive periods (..)")
    if not all(c in ascii_letters + digits + '.-' for c in value):
        raise ValueError(f"'{value}' is not a valid hostname\n  Allowed characters: a-z, A-Z, 0-9, '.', '-'")
    if len(value) > HOSTNAME_MAX_LENGTH:
        raise ValueError(f"'{value}' is not a valid hostname\n  Maximum length is {HOSTNAME_MAX_LENGTH} characters")

    return value


def domainname(tokeniser) -> str:
    value = string(tokeniser)
    if not value:
        raise ValueError('a domain name is required')
    if not value[0].isalnum() or value[0].isdigit():
        raise ValueError(f"'{value}' is not a valid domain name\n  Must start with a letter")
    if not value[-1].isalnum() or value[-1].isdigit():
        raise ValueError(f"'{value}' is not a valid domain name\n  Must end with a letter")
    if '..' in value:
        raise ValueError(f"'{value}' is not a valid domain name\n  Cannot contain consecutive periods (..)")
    if not all(c in ascii_letters + digits + '.-' for c in value):
        raise ValueError(f"'{value}' is not a valid domain name\n  Allowed characters: a-z, A-Z, 0-9, '.', '-'")
    if len(value) > HOSTNAME_MAX_LENGTH:
        raise ValueError(f"'{value}' is not a valid domain name\n  Maximum length is {HOSTNAME_MAX_LENGTH} characters")
    return value


def description(tokeniser) -> str:
    try:
        return string(tokeniser)
    except StopIteration:
        raise ValueError('bad neighbor description') from None


def md5(tokeniser) -> str:
    value = tokeniser()
    if not value:
        raise ValueError(
            'value requires the value password as an argument (quoted or unquoted).  FreeBSD users should use "kernel" as the argument.',
        )
    return value  # type: ignore[no-any-return]


def ttl(tokeniser) -> int | None:
    value = tokeniser()
    try:
        attl = int(value)
    except ValueError:
        if value in ('false', 'disable', 'disabled'):
            return None
        raise ValueError(f"'{value}' is not a valid TTL\n  Valid options: 0-255, disable, disabled, false") from None
    if attl < 0:
        raise ValueError(f'TTL {attl} is invalid\n  Must be 0-255')
    if attl > 255:
        raise ValueError(f'TTL {attl} is invalid\n  Must be 0-255')
    return attl


def local_address(tokeniser) -> IP | None:
    if not tokeniser.tokens:
        raise ValueError("an IP address or 'auto' is required (e.g., 192.0.2.1 or auto)")

    value = tokeniser()
    if value == 'auto':
        return None
    try:
        return IP.from_string(value)
    except (OSError, IndexError, ValueError):
        raise ValueError(
            f"'{value}' is not a valid IP address\n  Format: <ip> or 'auto' (e.g., 192.0.2.1 or 2001:db8::1)"
        ) from None


def source_interface(tokeniser) -> str:
    try:
        return string(tokeniser)
    except StopIteration:
        raise ValueError('bad source interface') from None


def router_id(tokeniser) -> RouterID:
    value = tokeniser()
    try:
        return RouterID(value)
    except ValueError:
        raise ValueError(f"'{value}' is not a valid router-id\n  Format: IPv4 address (e.g., 192.0.2.1)") from None


def hold_time(tokeniser) -> HoldTime:
    value = tokeniser()
    try:
        holdtime = HoldTime(int(value))
    except ValueError:
        raise ValueError(
            f"'{value}' is not a valid hold-time\n"
            f'  Must be 0 (disabled) or {MIN_NONZERO_HOLDTIME}-{HoldTime.MAX} seconds'
        ) from None
    if holdtime < MIN_NONZERO_HOLDTIME and holdtime != 0:
        raise ValueError(
            f'hold-time {holdtime} is invalid\n'
            f'  Must be 0 (disabled) or at least {MIN_NONZERO_HOLDTIME} seconds (RFC 4271)'
        )
    if holdtime > HoldTime.MAX:
        raise ValueError(f'hold-time {holdtime} is invalid\n  Maximum is {HoldTime.MAX} seconds')
    return holdtime


def processes(tokeniser) -> list[str]:
    result: list[str] = []
    token = tokeniser()
    if token != '[':
        raise ValueError('invalid processes list\n  Format: [ process1, process2, ... ]')

    while True:
        token = tokeniser()
        if not token:
            raise ValueError("invalid processes list - missing closing ']'\n  Format: [ process1, process2, ... ]")
        if token == ']':
            break
        if token == ',':
            continue
        result.append(token)

    return result


def processes_match(tokeniser) -> list[str]:
    result: list[str] = []
    token = tokeniser()
    if token != '[':
        raise ValueError('invalid processes-match list\n  Format: [ regex1, regex2, ... ]')

    while True:
        token = tokeniser()
        if not token:
            raise ValueError("invalid processes-match list - missing closing ']'\n  Format: [ regex1, regex2, ... ]")
        if token == ']':
            break
        if token == ',':
            continue
        try:
            re.compile(token)
        except re.error as e:
            raise ValueError(f"'{token}' is not a valid regular expression\n  Error: {e}") from None
        result.append(token)

    return result


def rate_limit(tokeniser) -> int:
    value = tokeniser().lower()
    if value in ('disable', 'disabled'):
        return 0
    try:
        rate = int(value)
    except ValueError:
        raise ValueError(
            f"'{value}' is not a valid rate-limit\n  Valid options: <number> (messages/sec), disable, disabled"
        ) from None
    if rate <= 0:
        raise ValueError(f"rate-limit {rate} is invalid\n  Must be at least 1 (messages/sec) or use 'disable'")
    return rate
