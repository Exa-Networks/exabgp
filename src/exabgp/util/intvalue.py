"""intvalue.py

A number with a type and a name: what AFI, SAFI, ASN and the message codes are.

These were subclasses of int. mypyc cannot compile a class which inherits from int, so
the number now lives in `.value` and IntValue gives back what the int base provided and
the code relies on:

- equal to, and hashed like, the plain int with the same value, so a dict keyed by the
  number finds the object and the other way round
- int(x) and '%d' % x give the number (`__int__`). There is no `__index__`: mypyc does
  not compile it, so struct.pack, bytes(), hex() and slicing take `.value`, always
- ordered against another IntValue or an int
- false when zero
- formatted like an int subclass: f'{x}' is str(x), f'{x:04x}' formats the number

Arithmetic is deliberately absent: the caller says `.value` and gets an int back, rather
than a result whose type depends on which side of the operator the object was.

See plan/wip-mypyc.md, section 2.3.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import operator
from typing import Final


class IntValue:
    __slots__ = ('value',)

    # zero by default, as int() is: a capability is built empty, then filled by unpack
    def __init__(self, value: int = 0) -> None:
        # as int() does, take anything which is an integer (another IntValue, a bool) and
        # refuse what is not (a str, a float): the value itself is always a plain int
        if type(value) is not int:
            value = value.value if isinstance(value, IntValue) else int(operator.index(value))
        self.value: Final[int] = value

    def __int__(self) -> int:
        return self.value

    def __bool__(self) -> bool:
        return self.value != 0

    def __hash__(self) -> int:
        return hash(self.value)

    def __eq__(self, other: object) -> bool:
        # the known AFI, SAFI and codes are one object each, so most comparisons end here
        if other is self:
            return True
        if isinstance(other, IntValue):
            return self.value == other.value
        if isinstance(other, (int, float)):
            return self.value == other
        return NotImplemented

    def __ne__(self, other: object) -> bool:
        if isinstance(other, IntValue):
            return self.value != other.value
        if isinstance(other, (int, float)):
            return self.value != other
        return NotImplemented

    # other is compared as it is, never through int(): int(179.5) would make 180 < 179.5
    def __lt__(self, other: IntValue | float) -> bool:
        return self.value < (other.value if isinstance(other, IntValue) else other)

    def __le__(self, other: IntValue | float) -> bool:
        return self.value <= (other.value if isinstance(other, IntValue) else other)

    def __gt__(self, other: IntValue | float) -> bool:
        return self.value > (other.value if isinstance(other, IntValue) else other)

    def __ge__(self, other: IntValue | float) -> bool:
        return self.value >= (other.value if isinstance(other, IntValue) else other)

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return str(self.value)

    def __format__(self, spec: str) -> str:
        # an int subclass with its own __str__ formats as its name when no spec is given
        if not spec:
            return str(self)
        return format(self.value, spec)


def json_number(value: object) -> int:
    """The `default` of json.dumps: an IntValue is written as its number, as the int was.

    json.dumps wrote an int subclass as a bare number without asking; IntValue it refuses.
    """
    if isinstance(value, IntValue):
        return value.value
    raise TypeError(f'Object of type {type(value).__name__} is not JSON serializable')
