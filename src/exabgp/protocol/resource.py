"""resource.py

Created by Thomas Mangin on 2015-05-15.
Copyright (c) 2015-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Dict, Any, Type, Iterator, ClassVar
from exabgp.util import string_is_hex

# Resource value range constants
RESOURCE_VALUE_MAX: int = 0xFFFF  # Maximum 16-bit unsigned integer value


class Resource(int):
    NAME: ClassVar[str] = ''
    codes: ClassVar[Dict[str, int]] = {}
    names: ClassVar[Dict[int, str]] = {}

    cache: ClassVar[Dict[Type[Resource], Dict[str, Resource]]] = {}

    def __new__(cls, *args: Any) -> Resource:
        key = '//'.join(str(_) for _ in args)
        if key in Resource.cache.setdefault(cls, {}):
            return Resource.cache[cls][key]
        instance: Resource = int.__new__(cls, *args)
        Resource.cache[cls][key] = instance
        return instance

    # NOTE: Do not convert to f-strings! Using f-strings in __str__() methods
    # that call str() on self causes infinite recursion.
    def short(self) -> str:
        return self.names.get(self, '%ld' % self)

    def __str__(self) -> str:
        return self.names.get(self, 'unknown %s type %ld' % (self.NAME, self))

    @classmethod
    def _value(cls, string: str) -> int:
        name = string.lower().replace('_', '-')
        if name in cls.codes:
            return cls.codes[name]
        if string.isdigit():
            value = int(string)
            if 0 <= value <= RESOURCE_VALUE_MAX:
                return value
        if string_is_hex(string):
            value = int(string[2:], 16)
            if 0 <= value <= RESOURCE_VALUE_MAX:
                return value
        raise ValueError(f'unknown {cls.NAME} {name}')

    @classmethod
    def named(cls, string: str) -> Resource:
        value = 0
        for name in string.split('+'):
            value += cls._value(name)
        return cls(value)


class BitResource(Resource):
    def named_bits(self) -> Iterator[str]:
        value = int(self)
        for bit in self.names.keys():
            if value & bit or value == bit:
                yield self.names[bit]
                value -= bit
        if value:
            yield self.names.get(self, f'unknown {self.NAME} type {int(self)}')

    def bits(self) -> Iterator[str]:
        value = int(self)
        for bit in self.names.keys():
            if value & bit or value == bit:
                yield self.names[bit]
                value -= bit
        if value:
            yield self.names.get(self, hex(self))

    def short(self) -> str:
        return '+'.join(self.bits())

    def __str__(self) -> str:
        return '+'.join(self.named_bits())
