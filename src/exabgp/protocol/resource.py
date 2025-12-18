"""resource.py

Created by Thomas Mangin on 2015-05-15.
Copyright (c) 2015-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any, Type, Iterator, ClassVar
from exabgp.util import string_is_hex

# Resource value range constants
RESOURCE_VALUE_MAX: int = 0xFFFF  # Maximum 16-bit unsigned integer value


class BaseValue(int):
    """Base class for int types that provide short() for display.

    Flow values need two things:
    1. int behavior - for byte encoding (bytes([value]), pack('!H', value))
    2. short() -> str - for string formatting
    """

    def short(self) -> str:
        """Return short string representation for display.

        Default implementation returns the integer as string.
        Subclasses may override for named representations.
        """
        return str(int(self))


class Resource(BaseValue):
    NAME: ClassVar[str] = ''
    codes: ClassVar[dict[str, int]] = {}
    names: ClassVar[dict[int, str]] = {}

    cache: ClassVar[dict[Type[Resource], dict[str, Resource]]] = {}

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
    def from_string(cls, string: str) -> Resource:
        """Parse a single name/number/hex string to a Resource instance."""
        return cls(cls._value(string))


class BitResource(Resource):
    @classmethod
    def named(cls, string: str) -> BitResource:
        """Parse a '+'-separated string of names/values and combine them.

        Used for bitmask values like TCP flags: "syn+ack" → 0x12
        """
        value = 0
        for name in string.split('+'):
            value += cls._value(name)
        return cls(value)

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


class NumericValue(BaseValue):
    """Plain numeric value without named constants.

    Used in FlowSpec rules where the value doesn't have a named registry
    (like arbitrary port numbers or packet lengths).
    """

    def short(self) -> str:
        return str(int(self))
