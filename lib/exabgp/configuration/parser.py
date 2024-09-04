# encoding: utf-8
"""
generic/parser.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import socket

from exabgp.bgp.message.open.asn import ASN
from exabgp.protocol.ip import IP
from exabgp.protocol.ip import IPRange


def string(tokeniser):
    return tokeniser()


def boolean(tokeniser, default):
    status = tokeniser().lower()
    if not status:
        return default
    if status in ('true', 'enable', 'enabled'):
        return True
    if status in ('false', 'disable', 'disabled'):
        return False
    raise ValueError('invalid value (%s) for a boolean' % status)


def auto_boolean(tokeniser, default):
    status = tokeniser().lower()
    if not status:
        return default
    if status in ('true', 'enable', 'enabled'):
        return True
    if status in ('false', 'disable', 'disabled'):
        return False
    if status in ('auto',):
        return None
    raise ValueError('invalid value (%s) for a boolean' % status)


def port(tokeniser):
    if not tokeniser.tokens:
        raise ValueError('a port number is required')

    value = tokeniser()
    try:
        return int(value)
    except ValueError:
        raise ValueError('"%s" is an invalid port' % value)
    if value < 0:
        raise ValueError('the port must be positive')
    if value >= pow(2, 16):
        raise ValueError('the port must be smaller than %d' % pow(2, 16))
    return value


def auto_asn(tokeniser, value=None):
    if value is None:
        if not tokeniser.tokens:
            raise ValueError("an asn or 'auto' is required")

    if tokeniser.peek() == 'auto':
        tokeniser()
        return None

    return asn(tokeniser)


def asn(tokeniser, value=None):
    if value is None:
        if not tokeniser.tokens:
            raise ValueError('an asn is required')

    value = tokeniser()
    try:
        if value.count('.'):
            high, low = value.split('.', 1)
            as_number = (int(high) << 16) + int(low)
        else:
            as_number = int(value)
        return ASN(as_number)
    except ValueError:
        raise ValueError('"%s" is an invalid ASN' % value)


def peer_ip(tokeniser):
    if not tokeniser.tokens:
        raise ValueError('an ip address is required')

    value = tokeniser()
    if '/' in value:
        value, mask = value.split('/', 1)
    else:
        # XXX: This only works as no port are allowed, improve
        mask = '128' if ':' in value else '32'

    try:
        return IPRange.create(value, mask)
    except (IndexError, ValueError, socket.error):
        raise ValueError('"%s" is an invalid IP address' % value)


def ip(tokeniser):
    if not tokeniser.tokens:
        raise ValueError('an ip address is required')

    value = tokeniser()
    try:
        return IP.create(value)
    except (IndexError, ValueError, socket.error):
        raise ValueError('"%s" is an invalid IP address' % value)
