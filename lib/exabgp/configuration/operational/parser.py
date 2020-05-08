# encoding: utf-8
"""
operational/__init__.py

Created by Thomas Mangin on 2015-06-23.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import sys

from exabgp.util.ip import isipv4

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message.open.routerid import RouterID
from exabgp.bgp.message.operational import MAX_ADVISORY
from exabgp.bgp.message.operational import Advisory
from exabgp.bgp.message.operational import Query
from exabgp.bgp.message.operational import Response


if sys.version_info > (3,):
    long = int


def _operational(klass, parameters, tokeniser):
    def utf8(string):
        return string.encode('utf-8')

    def valid(_):
        return True

    def u32(_):
        return int(_) <= 0xFFFFFFFF

    def u64(_):
        return long(_) <= 0xFFFFFFFFFFFFFFFF

    def advisory(_):
        return len(_.encode('utf-8')) <= MAX_ADVISORY + 2  # the two quotes

    convert = {'afi': AFI.value, 'safi': SAFI.value, 'sequence': int, 'counter': long, 'advisory': utf8}

    validate = {
        'afi': AFI.value,
        'safi': SAFI.value,
        'sequence': u32,
        'counter': u64,
    }

    number = len(parameters) * 2
    tokens = []
    while len(tokens) != number:
        tokens.append(tokeniser())

    data = {}

    while tokens and parameters:
        command = tokens.pop(0).lower()
        value = tokens.pop(0)

        if command == 'router-id':
            if isipv4(value):
                data['routerid'] = RouterID(value)
            else:
                raise ValueError('invalid operational value for %s' % command)
            continue

        expected = parameters.pop(0)

        if command != expected:
            raise ValueError('invalid operational syntax, unknown argument %s' % command)
        if not validate.get(command, valid)(value):
            raise ValueError('invalid operational value for %s' % command)

        data[command] = convert[command](value)

    if tokens or parameters:
        raise ValueError('invalid advisory syntax, missing argument(s) %s' % ', '.join(parameters))

    if 'routerid' not in data:
        data['routerid'] = None

    return klass(**data)


_dispatch = {}


def register(name):
    def inner(function):
        _dispatch[name] = function
        return function

    return inner


@register('asm')
def asm(tokeniser):
    return _operational(Advisory.ASM, ['afi', 'safi', 'advisory'], tokeniser)


@register('adm')
def adm(tokeniser):
    return _operational(Advisory.ADM, ['afi', 'safi', 'advisory'], tokeniser)


@register('rpcq')
def rpcq(tokeniser):
    return _operational(Query.RPCQ, ['afi', 'safi', 'sequence'], tokeniser)


@register('rpcp')
def rpcp(tokeniser):
    return _operational(Response.RPCP, ['afi', 'safi', 'sequence', 'counter'], tokeniser)


@register('apcq')
def apcq(tokeniser):
    return _operational(Query.APCQ, ['afi', 'safi', 'sequence'], tokeniser)


@register('apcp')
def apcp(tokeniser):
    return _operational(Response.APCP, ['afi', 'safi', 'sequence', 'counter'], tokeniser)


@register('lpcq')
def lpcq(tokeniser):
    return _operational(Query.LPCQ, ['afi', 'safi', 'sequence'], tokeniser)


@register('lpcp')
def lpcp(tokeniser):
    return _operational(Response.LPCP, ['afi', 'safi', 'sequence', 'counter'], tokeniser)


def operational(what, tokeniser):
    return _dispatch.get(what, lambda _: None)(tokeniser)
