"""shape.py

What a value is, independent of how it is written: the data model of the configuration.

A type reads words; its Shape says what the words stand for once read, the value exabgp
keeps and prints back. An AS number may be written `1.1`, it is the number 65537: the
shape is a 32 bit unsigned integer. A boolean may be written `enable` or `yes`, it is a
boolean.

The model follows YANG (RFC 7950), which is the richer of the two targets, so that a JSON
Schema (json_schema.py) and a YANG module (yang.py) are both printed from it:

    integer        uintN / intN with a range        JSON integer, minimum, maximum
    boolean        boolean                          JSON boolean
    empty          empty (a flag)                   JSON null
    enumeration    enumeration                      JSON string with enum
    string         string, pattern, or a typedef    JSON string, pattern or format
    union          union                            anyOf
    list           leaf-list / list                 array
    container      container                        object
    choice         choice                           oneOf

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

UINT8_MAX = 0xFF
UINT16_MAX = 0xFFFF
UINT32_MAX = 0xFFFFFFFF
UINT64_MAX = 0xFFFFFFFFFFFFFFFF
INT64_MIN = -(2**63)
INT64_MAX = 2**63 - 1
MAX_DEPTH = 32  # a shape nests a handful deep, a route in a list in a container


class Kind(StrEnum):
    INTEGER = 'integer'
    BOOLEAN = 'boolean'
    EMPTY = 'empty'
    ENUMERATION = 'enumeration'
    STRING = 'string'
    UNION = 'union'
    LIST = 'list'
    CONTAINER = 'container'
    CHOICE = 'choice'
    REFUSED = 'refused'  # a keyword which is only there to be refused: no data


@dataclass(frozen=True)
class Shape:
    kind: Kind
    ranges: tuple[tuple[int, int], ...] = ()  # integer: the values allowed, inclusive
    values: tuple[str, ...] = ()  # enumeration
    pattern: str = ''  # string: a regular expression the whole value matches
    formats: tuple[str, ...] = ()  # string: JSON Schema formats, one of which the value has
    typedef: str = ''  # the YANG type which names it, `inet:ipv4-address`
    members: tuple[Shape, ...] = ()  # union: the value is one of these
    fields: tuple[tuple[str, Shape], ...] = ()  # container: its members; choice: its cases
    item: Shape | None = None  # list: each entry
    min_items: int = 0
    max_items: int = 0  # 0: no limit
    key: str = ''  # list of containers: the member naming each entry; none, the entries are in order
    description: str = ''
    # as a member of a container
    mandatory: bool = False
    default: str | None = None  # the word exabgp uses when the statement is not given
    # container: the named shapes whose members it has too (a YANG grouping, a JSON $defs entry)
    uses: tuple[Shape, ...] = ()
    name: str = ''  # a shape used in several places: the name of its grouping
    # container: the members which must be there, as paths (`role/local`), when it uses a
    # grouping which does not require them itself (a neighbor, not a template)
    requires: tuple[str, ...] = ()
    # container: it means something by being there (`role`, `tcp-ao`), its members may be needed
    presence: bool = False

    def described(self, description: str) -> Shape:
        return _replace(self, description=description) if description else self


def _replace(shape: Shape, **changes: Any) -> Shape:
    values = {name: getattr(shape, name) for name in shape.__dataclass_fields__}
    values.update(changes)
    return Shape(**values)


# --------------------------------------------------------------------------- building shapes


def integer(low: int, high: int, typedef: str = '') -> Shape:
    assert low <= high, f'empty range {low}..{high}'
    return Shape(Kind.INTEGER, ranges=((low, high),), typedef=typedef)


def integer_ranges(*ranges: tuple[int, int]) -> Shape:
    assert ranges and all(low <= high for low, high in ranges)
    return Shape(Kind.INTEGER, ranges=tuple(ranges))


def boolean() -> Shape:
    return Shape(Kind.BOOLEAN)


def empty() -> Shape:
    return Shape(Kind.EMPTY)


def enumeration(*values: str) -> Shape:
    assert values, 'an enumeration without a value'
    return Shape(Kind.ENUMERATION, values=tuple(values))


def string(pattern: str = '', typedef: str = '', formats: tuple[str, ...] = ()) -> Shape:
    return Shape(Kind.STRING, pattern=pattern, typedef=typedef, formats=formats)


def union(*members: Shape) -> Shape:
    assert len(members) > 1, 'a union of one shape is that shape'
    return Shape(Kind.UNION, members=tuple(members))


def leaf_list(item: Shape, min_items: int = 0, max_items: int = 0) -> Shape:
    return Shape(Kind.LIST, item=item, min_items=min_items, max_items=max_items)


def container(*fields: tuple[str, Shape], uses: tuple[Shape, ...] = (), requires: tuple[str, ...] = ()) -> Shape:
    names = [name for name, _ in fields]
    assert len(names) == len(set(names)), f'a member named twice in {names}'
    return Shape(Kind.CONTAINER, fields=tuple(fields), uses=uses, requires=requires)


def keyed(item: Shape, key: str) -> Shape:
    """A list of containers, each named by its member `key`."""
    assert item.kind == Kind.CONTAINER and any(name == key for name, _ in item.fields), f'no key {key}'
    return Shape(Kind.LIST, item=item, key=key)


def grouping(name: str, *fields: tuple[str, Shape]) -> Shape:
    """Members shared by several containers, declared once."""
    return Shape(Kind.CONTAINER, fields=tuple(fields), name=name)


def member(shape: Shape, mandatory: bool = False, default: str | None = None, description: str = '') -> Shape:
    """`shape` as a member of a container."""
    return _replace(shape, mandatory=mandatory, default=default, description=description or shape.description)


def choice(*cases: tuple[str, Shape]) -> Shape:
    assert len(cases) > 1, 'a choice of one case is that case'
    return Shape(Kind.CHOICE, fields=tuple(cases))


_IPV4 = r'(\d{1,3}\.){3}\d{1,3}'
_IPV6 = r'[0-9a-fA-F:]*:[0-9a-fA-F:.]*'

UINT8 = integer(0, UINT8_MAX)
UINT16 = integer(0, UINT16_MAX)
UINT32 = integer(0, UINT32_MAX)
UINT64 = integer(0, UINT64_MAX)
AS_NUMBER = integer(0, UINT32_MAX, typedef='inet:as-number')
PORT_NUMBER = integer(1, UINT16_MAX)
IPV4_ADDRESS = string(typedef='inet:ipv4-address', formats=('ipv4',))
IPV6_ADDRESS = string(typedef='inet:ipv6-address', formats=('ipv6',))
IP_ADDRESS = string(typedef='inet:ip-address', formats=('ipv4', 'ipv6'))
IP_PREFIX = string(pattern=rf'({_IPV4}|{_IPV6})/\d{{1,3}}', typedef='inet:ip-prefix')
TEXT = string()
REFUSED = Shape(Kind.REFUSED)


# --------------------------------------------------------------------------- checking a value


def json_value(shape: Shape, word: str) -> Any:
    """The JSON value of a word exabgp prints for a value of `shape`: a number, a boolean, a string."""
    if shape.kind == Kind.UNION:
        for each in shape.members:
            if accepts(each, word):
                return json_value(each, word)
        return word
    if shape.kind == Kind.INTEGER and _is_integer(word):
        return _integer(word)
    if shape.kind == Kind.BOOLEAN:
        return word.lower() in TRUE_WORDS
    return word


def accepts(shape: Shape, word: str) -> bool:
    """Whether the word, as exabgp prints a value, is a value of the scalar `shape`."""
    if shape.kind == Kind.UNION:
        return any(accepts(member, word) for member in shape.members)
    if shape.kind == Kind.INTEGER:
        return _is_integer(word) and any(low <= _integer(word) <= high for low, high in shape.ranges)
    if shape.kind == Kind.BOOLEAN:
        # the model is the boolean; every spelling exabgp prints for one is one
        return word.lower() in BOOLEAN_WORDS
    if shape.kind == Kind.EMPTY:
        return word == ''
    if shape.kind == Kind.ENUMERATION:
        return word in shape.values
    assert shape.kind == Kind.STRING, f'{shape.kind} is not a scalar'
    if shape.pattern and not re.fullmatch(shape.pattern, word):
        return False
    return not shape.formats or any(_has_format(word, each) for each in shape.formats)


TRUE_WORDS = frozenset(('true', 'enable', 'enabled', 'yes'))
BOOLEAN_WORDS = TRUE_WORDS | frozenset(('false', 'disable', 'disabled', 'no'))


def _is_integer(word: str) -> bool:
    # YANG reads an integer in decimal, or in hexadecimal after 0x (RFC 7950 9.2.1)
    return bool(re.fullmatch(r'-?(\d+|0x[0-9a-fA-F]+)', word))


def _has_format(word: str, name: str) -> bool:
    try:
        address = ipaddress.ip_address(word)
    except ValueError:
        return False
    return address.version == (4 if name == 'ipv4' else 6)


def _integer(word: str) -> int:
    negative = word.startswith('-')
    digits = word[1:] if negative else word
    number = int(digits, 16) if digits.startswith('0x') else int(digits)
    return -number if negative else number
