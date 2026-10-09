"""operational.py

The operational messages a neighbor sends (draft-ietf-idr-operational-message):

    operational {
        asm|adm afi <afi> safi <safi> advisory <text>;
        rpcq|apcq|lpcq afi <afi> safi <safi> sequence <n>;
        rpcp|apcp|lpcp afi <afi> safi <safi> sequence <n> counter <n>;
    }

A message is its values, each `<name> <value>` once, in any order, with an optional
`router-id <ip>`.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import struct
from typing import Any, Callable

from exabgp.bgp.message.open.routerid import RouterID
from exabgp.bgp.message.operational import Advisory, OperationalFamily, Query, Response
from exabgp.configuration.grammar import shape
from exabgp.configuration.grammar.context import ReadContext
from exabgp.configuration.grammar.error import ConfigError
from exabgp.configuration.grammar.nodes import Block, Leaf
from exabgp.configuration.grammar.section import Collector, Pending, Values
from exabgp.configuration.grammar.shape import Shape
from exabgp.configuration.grammar.types.base import Type, WordOrSyntax
from exabgp.configuration.grammar.words import Words
from exabgp.configuration.grammar.types.word import decimal
from exabgp.protocol.family import AFI, SAFI
from exabgp.util.ip import isipv4

U32_MAX = 0xFFFFFFFF
MESSAGES = 'routes'  # legacy: the section keeps its messages as its routes


def _afi(word: str) -> AFI:
    afi = AFI.from_name(word)
    if afi is None:
        raise ValueError('invalid operational value for afi')
    return afi


def _safi(word: str) -> SAFI:
    safi = SAFI.from_name(word)
    if safi is None:
        raise ValueError('invalid operational value for safi')
    return safi


def _bounded(name: str, maximum: int) -> Callable[[str], int]:
    def convert(word: str) -> int:
        number = decimal(word)
        if number > maximum:
            raise ValueError(f'invalid operational value for {name}')
        return number

    return convert


CONVERT: dict[str, Callable[[str], Any]] = {
    'afi': _afi,
    'safi': _safi,
    'sequence': _bounded('sequence', U32_MAX),
    # packed in four octets: 64 bits were accepted here and the message failed when packed
    'counter': _bounded('counter', U32_MAX),
    # legacy: the advisory is not checked against MAX_ADVISORY
    'advisory': lambda word: word.encode('utf-8'),
}


# what each value of a message is, for the data model
PARAMETER_SHAPES: dict[str, Shape] = {
    'afi': shape.enumeration(*AFI.codes).described('the address family the message is about'),
    'safi': shape.enumeration(*SAFI.codes).described('the subsequent address family the message is about'),
    'advisory': shape.TEXT.described('the text of the advisory'),
    'sequence': shape.UINT32.described('the sequence number, which pairs a reply with its query, 0 for the next one'),
    'counter': shape.UINT32.described('the number of prefixes'),
}


def _values(words: list[str], parameters: tuple[str, ...]) -> dict[str, Any]:
    """The values of a message, each given once as `<name> <value>`, and an optional router-id.

    Two words were read per value named, in order, and the rest ignored: a `router-id <ip>`
    took the place of a value, so a message giving one was always short of one.
    """
    if len(words) % 2:
        raise ValueError(f"invalid operational syntax, '{words[-1]}' has no value")
    data: dict[str, Any] = {}
    for index in range(0, len(words), 2):
        name, value = words[index].lower(), words[index + 1]
        if name in data or (name == 'router-id' and 'routerid' in data):
            raise ValueError(f'invalid operational syntax, {name} is given twice')
        if name == 'router-id':
            if not isipv4(value):
                raise ValueError(f'invalid operational value for {name}')
            data['routerid'] = RouterID(value)
        elif name in parameters:
            data[name] = CONVERT[name](value)
        elif 'advisory' in data:
            # `advisory x y z` sent `x`: the words after it were dropped
            raise ValueError(
                f"invalid operational syntax, '{name}' follows the advisory: one of several words is quoted"
            )
        else:
            raise ValueError(f'invalid operational syntax, unknown argument {name}')
    missing = [parameter for parameter in parameters if parameter not in data]
    if missing:
        raise ValueError(f'invalid operational syntax, missing argument(s) {", ".join(missing)}')
    data.setdefault('routerid', None)
    return data


class OperationalLine(Type[OperationalFamily]):
    """`afi <afi> safi <safi> <value> <value> ...`: one operational message."""

    def __init__(self, keyword: str, klass: type[OperationalFamily], parameters: tuple[str, ...]) -> None:
        self.klass = klass
        self.parameters = parameters
        self.name = f'{keyword} message'

    def parse(self, words: Words) -> OperationalFamily:
        where = words.where()
        given = [token.word for token in words.rest()]
        try:
            message: OperationalFamily = self.klass.from_values(_values(given, self.parameters))
        except ConfigError:
            raise  # positioned already, by the value which failed
        except (ValueError, TypeError, struct.error) as exc:
            raise ConfigError(where, str(exc) or f'invalid {self.name}') from None
        return message

    def render(self, value: OperationalFamily) -> list[WordOrSyntax]:
        words: list[WordOrSyntax] = ['afi', value.afi.name(), 'safi', value.safi.name()]
        message: Any = value
        # the router-id given, which none could be until a message read one
        if getattr(message, 'routerid', None) is not None:
            words += ['router-id', str(message.routerid)]
        for parameter in self.parameters[2:]:
            if parameter == 'advisory':
                words += ['advisory', bytes(message.data).decode('utf-8')]
            elif parameter == 'sequence':
                words += ['sequence', str(message.sequence or 0)]
            else:
                words += ['counter', str(message.counter)]
        return words

    def hint(self) -> str:
        return ' '.join(f'{parameter} <{parameter}>' for parameter in self.parameters)

    def examples(self) -> list[str]:
        values = {'afi': 'ipv4', 'safi': 'unicast', 'advisory': '"text"', 'sequence': '1', 'counter': '10'}
        return [' '.join(f'{parameter} {values[parameter]}' for parameter in self.parameters)]

    def shape(self) -> Shape:
        return shape.container(*((parameter, PARAMETER_SHAPES[parameter]) for parameter in self.parameters))


ADVISORY = ('afi', 'safi', 'advisory')
QUERY = ('afi', 'safi', 'sequence')
RESPONSE = ('afi', 'safi', 'sequence', 'counter')

KINDS: dict[str, tuple[type[OperationalFamily], tuple[str, ...], str]] = {
    'asm': (Advisory.ASM, ADVISORY, 'Advisory State Message'),
    'adm': (Advisory.ADM, ADVISORY, 'Advisory Dump Message'),
    'rpcq': (Query.RPCQ, QUERY, 'Reachable Prefix Count Query'),
    'rpcp': (Response.RPCP, RESPONSE, 'Reachable Prefix Count Reply'),
    'apcq': (Query.APCQ, QUERY, 'Adj-RIB-Out Prefix Count Query'),
    'apcp': (Response.APCP, RESPONSE, 'Adj-RIB-Out Prefix Count Reply'),
    'lpcq': (Query.LPCQ, QUERY, 'Local Prefix Count Query'),
    'lpcp': (Response.LPCP, RESPONSE, 'Local Prefix Count Reply'),
}


MESSAGE = Pending()


class OperationalSection(Collector[Values]):
    def collected(self, name: Any, values: Values, entries: list[tuple[Any, Any]], context: ReadContext) -> Values:
        # the messages of a second block add to the first: they replaced them, unless it had none
        values.setdefault(MESSAGES, []).extend(message for _, message in entries)
        return values


def kind(message: OperationalFamily) -> str:
    """The statement which reads `message` back."""
    for keyword, (klass, _, _) in KINDS.items():
        if message.SUBTYPE_ID == klass.SUBTYPE_ID:
            return keyword
    raise ValueError(f'no statement writes a {type(message).__name__} message')


OPERATIONAL = Block(
    'operational',
    field='operational',
    section=OperationalSection(),
    doc='the operational messages sent to the peer',
    children=tuple(
        Leaf(
            keyword,
            OperationalLine(keyword, klass, parameters),
            field=f'_{keyword}',
            store=MESSAGE,
            doc=doc,
            multiple=True,
        )
        for keyword, (klass, parameters, doc) in KINDS.items()
    ),
)
