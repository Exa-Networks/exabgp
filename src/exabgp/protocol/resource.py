"""resource.py

Created by Thomas Mangin on 2015-05-15.
Copyright (c) 2015-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Iterator, ClassVar
from exabgp.util import string_is_hex
from exabgp.util.intvalue import IntValue

# Resource value range constants
RESOURCE_VALUE_MAX: int = 0xFFFF  # Maximum 16-bit unsigned integer value


class BaseValue(IntValue):
    """Base class for the numbers which provide short() for display.

    Flow values need two things:
    1. a number - for byte encoding (bytes([value]), pack('!H', value)), see IntValue
    2. short() -> str - for string formatting
    """

    def short(self) -> str:
        """Return short string representation for display.

        Default implementation returns the integer as string.
        Subclasses may override for named representations.
        """
        return str(self.value)


class Resource(BaseValue):
    NAME: ClassVar[str] = ''
    codes: ClassVar[dict[str, int]] = {}
    names: ClassVar[dict[int, str]] = {}

    # NOTE: Do not convert to f-strings! Using f-strings in __str__() methods
    # that call str() on self causes infinite recursion.
    def short(self) -> str:
        return self.names.get(self.value, '%ld' % self.value)

    def __str__(self) -> str:
        return self.names.get(self.value, 'unknown %s type %ld' % (self.NAME, self.value))

    @classmethod
    def _ensure_loaded(cls) -> None:
        """Fill codes and names before they are read: Port loads them from a file on first use."""

    @classmethod
    def _value(cls, string: str) -> int:
        # a hook rather than an override calling super(): mypyc passes the wrong cls to
        # super() in a classmethod, and Port's names were read from `type`
        cls._ensure_loaded()
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

        Used for bitmask values like TCP flags: "syn+ack" → 0x12. The bits are OR-ed: a
        bit named twice is that bit, where adding them carried it into the next one
        ("syn+syn" was rst, "is-fragment+is-fragment" first-fragment).
        """
        value = 0
        for name in string.split('+'):
            value |= cls._value(name)
        return cls(value)

    def named_bits(self) -> Iterator[str]:
        value = self.value
        for bit in self.names.keys():
            if value & bit or value == bit:
                yield self.names[bit]
                value -= bit
        if value:
            yield self.names.get(self.value, f'unknown {self.NAME} type {self.value}')

    def bits(self) -> Iterator[str]:
        value = self.value
        for bit in self.names.keys():
            if value & bit or value == bit:
                yield self.names[bit]
                value -= bit
        if value:
            yield self.names.get(self.value, hex(self.value))

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
        return str(self.value)
