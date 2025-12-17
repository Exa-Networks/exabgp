"""operational/__init__.py

Created by Thomas Mangin on 2015-06-23.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from exabgp.configuration.core.parser import Tokeniser

from exabgp.util.ip import isipv4

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message.open.routerid import RouterID
from exabgp.bgp.message.operational import MAX_ADVISORY
from exabgp.bgp.message.operational import Advisory
from exabgp.bgp.message.operational import Query
from exabgp.bgp.message.operational import Response
from exabgp.bgp.message.operational import Operational

# Operational message advisory overhead (including quotes)
ADVISORY_QUOTE_OVERHEAD = 2  # Two quote characters surrounding advisory


def _operational(klass: type[Operational], parameters: list[str], tokeniser: Tokeniser) -> Operational:
    def utf8(string: str) -> bytes:
        return string.encode('utf-8')

    def valid(_: str) -> bool:
        return True

    # Maximum values for unsigned integer types
    MAX_U32 = 0xFFFFFFFF  # Maximum 32-bit unsigned integer
    MAX_U64 = 0xFFFFFFFFFFFFFFFF  # Maximum 64-bit unsigned integer

    def u32(_: str) -> bool:
        return int(_) <= MAX_U32

    def u64(_: str) -> bool:
        return int(_) <= MAX_U64

    def advisory(_: str) -> bool:
        return len(_.encode('utf-8')) <= MAX_ADVISORY + ADVISORY_QUOTE_OVERHEAD  # the two quotes

    convert: dict[str, Callable[[str], Any]] = {
        'afi': AFI.value,
        'safi': SAFI.value,
        'sequence': int,
        'counter': int,
        'advisory': utf8,
    }

    validate: dict[str, Callable[[str], Any]] = {
        'afi': AFI.value,
        'safi': SAFI.value,
        'sequence': u32,
        'counter': u64,
    }

    number = len(parameters) * 2
    tokens: list[str] = []
    while len(tokens) != number:
        tokens.append(tokeniser())

    data: dict[str, Any] = {}

    while tokens and parameters:
        command = tokens.pop(0).lower()
        value = tokens.pop(0)

        if command == 'router-id':
            if isipv4(value):
                data['routerid'] = RouterID(value)
            else:
                raise ValueError('invalid operational value for {}'.format(command))
            continue

        expected = parameters.pop(0)

        if command != expected:
            raise ValueError('invalid operational syntax, unknown argument {}'.format(command))
        if not validate.get(command, valid)(value):
            raise ValueError('invalid operational value for {}'.format(command))

        data[command] = convert[command](value)

    if tokens or parameters:
        raise ValueError('invalid advisory syntax, missing argument(s) {}'.format(', '.join(parameters)))

    if 'routerid' not in data:
        data['routerid'] = None

    return klass(**data)


_dispatch: dict[str, Callable[[Tokeniser], Operational]] = {}


def register(name: str) -> Callable[[Callable[[Tokeniser], Operational]], Callable[[Tokeniser], Operational]]:
    def inner(function: Callable[[Tokeniser], Operational]) -> Callable[[Tokeniser], Operational]:
        _dispatch[name] = function
        return function

    return inner


@register('asm')
def asm(tokeniser: Tokeniser) -> Operational:
    return _operational(Advisory.ASM, ['afi', 'safi', 'advisory'], tokeniser)


@register('adm')
def adm(tokeniser: Tokeniser) -> Operational:
    return _operational(Advisory.ADM, ['afi', 'safi', 'advisory'], tokeniser)


@register('rpcq')
def rpcq(tokeniser: Tokeniser) -> Operational:
    return _operational(Query.RPCQ, ['afi', 'safi', 'sequence'], tokeniser)


@register('rpcp')
def rpcp(tokeniser: Tokeniser) -> Operational:
    return _operational(Response.RPCP, ['afi', 'safi', 'sequence', 'counter'], tokeniser)


@register('apcq')
def apcq(tokeniser: Tokeniser) -> Operational:
    return _operational(Query.APCQ, ['afi', 'safi', 'sequence'], tokeniser)


@register('apcp')
def apcp(tokeniser: Tokeniser) -> Operational:
    return _operational(Response.APCP, ['afi', 'safi', 'sequence', 'counter'], tokeniser)


@register('lpcq')
def lpcq(tokeniser: Tokeniser) -> Operational:
    return _operational(Query.LPCQ, ['afi', 'safi', 'sequence'], tokeniser)


@register('lpcp')
def lpcp(tokeniser: Tokeniser) -> Operational:
    return _operational(Response.LPCP, ['afi', 'safi', 'sequence', 'counter'], tokeniser)


def operational(what: str, tokeniser: Tokeniser) -> Operational | None:
    dispatch_func = _dispatch.get(what)
    if dispatch_func is None:
        return None
    return dispatch_func(tokeniser)
