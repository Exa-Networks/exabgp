# encoding: utf-8
"""
neighbor/parser.py

Created by Thomas Mangin on 2014-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import socket
from string import ascii_letters
from string import digits

from exabgp.bgp.message.open.routerid import RouterID
from exabgp.bgp.message.open.holdtime import HoldTime
from exabgp.configuration.parser import string
from exabgp.protocol.ip import IP


def inherit(tokeniser):
    if len(tokeniser.tokens) == 2:
        return [tokeniser()]
    if len(tokeniser.tokens) < 4 or tokeniser.tokens[1] != '[' or tokeniser.tokens[-1] != ']':
        raise ValueError('invalid inherit list')
    return tokeniser.tokens[2:-1]


def hostname(tokeniser):
    value = string(tokeniser)
    if not value[0].isalnum():
        raise ValueError('bad host-name (alphanumeric)')
    if not value[-1].isalnum() or value[-1].isdigit():
        raise ValueError('bad host-name (alphanumeric)')
    if '..' in value:
        raise ValueError('bad host-name (double period)')
    if not all(True if c in ascii_letters + digits + '.-' else False for c in value):
        raise ValueError('bad host-name (charset)')
    if len(value) > 255:
        raise ValueError('bad host-name (length)')

    return value


def domainname(tokeniser):
    value = string(tokeniser)
    if not value:
        raise ValueError('bad domain-name')
    if not value[0].isalnum() or value[0].isdigit():
        raise ValueError('bad domain-name')
    if not value[-1].isalnum() or value[-1].isdigit():
        raise ValueError('bad domain-name')
    if '..' in value:
        raise ValueError('bad domain-name')
    if not all(True if c in ascii_letters + digits + '.-' else False for c in value):
        raise ValueError('bad domain-name')
    if len(value) > 255:
        raise ValueError('bad domain-name (length)')
    return value


def description(tokeniser):
    try:
        return string(tokeniser)
    except Exception:
        raise ValueError('bad neighbor description')


def md5(tokeniser):
    value = tokeniser()
    if not value:
        raise ValueError(
            'value requires the value password as an argument (quoted or unquoted).  FreeBSD users should use "kernel" as the argument.'
        )
    return value


def ttl(tokeniser):
    value = tokeniser()
    try:
        attl = int(value)
    except ValueError:
        if value in ('false', 'disable', 'disabled'):
            return None
        raise ValueError('invalid ttl-security "%s"' % value)
    if attl < 0:
        raise ValueError('ttl-security can not be negative')
    if attl > 255:
        raise ValueError('ttl must be smaller than 256')
    return attl


def local_address(tokeniser):
    if not tokeniser.tokens:
        raise ValueError("an ip address  or 'auto' is required")

    value = tokeniser()
    if value == 'auto':
        return None
    try:
        return IP.create(value)
    except (IndexError, ValueError, socket.error):
        raise ValueError('"%s" is an invalid IP address' % value)


def router_id(tokeniser):
    value = tokeniser()
    try:
        return RouterID(value)
    except ValueError:
        raise ValueError('"%s" is an invalid router-id' % value)


def hold_time(tokeniser):
    value = tokeniser()
    try:
        holdtime = HoldTime(int(value))
    except ValueError:
        raise ValueError('"%s" is an invalid hold-time' % value)
    if holdtime < 3 and holdtime != 0:
        raise ValueError('holdtime must be zero or at least three seconds')
    if holdtime > HoldTime.MAX:
        raise ValueError('holdtime must be smaller or equal to %d' % HoldTime.MAX)
    return holdtime


def processes(tokeniser):
    result = []
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


def rate_limit(tokeniser):
    value = tokeniser().lower()
    if value in ('disable', 'disabled'):
        return 0
    try:
        rate = int(value)
    except ValueError:
        raise ValueError('"%s" is an invalid rate-limit' % value)
    if rate <= 0:
        raise ValueError('rate must be zero or at 1 (per second)')
    return rate
