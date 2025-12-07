"""enumeration.py

Created by Thomas Mangin on 2013-03-18.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from enum import IntEnum


class TriState(IntEnum):
    """Tri-state value: True, False, or Unset.

    Used when a value can be:
    - TRUE (1): Confirmed enabled/yes
    - FALSE (0): Confirmed disabled/no
    - UNSET (-1): Not yet determined
    """

    UNSET = -1
    FALSE = 0
    TRUE = 1

    @classmethod
    def from_bool(cls, value: bool | None) -> 'TriState':
        """Convert bool | None to TriState."""
        if value is None:
            return cls.UNSET
        return cls.TRUE if value else cls.FALSE

    def to_bool(self) -> bool | None:
        """Convert TriState to bool | None."""
        if self == TriState.UNSET:
            return None
        return self == TriState.TRUE

    def is_enabled(self) -> bool:
        """Check if capability is enabled (TRUE). UNSET and FALSE return False."""
        return self == TriState.TRUE

    def is_disabled(self) -> bool:
        """Check if capability is explicitly disabled (FALSE). UNSET returns False."""
        return self == TriState.FALSE

    def is_unset(self) -> bool:
        """Check if capability is not yet determined."""
        return self == TriState.UNSET


# int are immutable once created: can not set ._str in __init__
class _integer(int):
    _str: str

    def __str__(self) -> str:
        return self._str


class Enumeration:
    def __init__(self, *names: str) -> None:
        for number, name in enumerate(names):
            # doing the .parent thing here instead
            number = _integer(pow(2, number))
            number._str = name
            setattr(self, name, number)


# Taken from Vincent Bernat
def enum(*sequential: str) -> type[object]:
    return type(str('Enum'), (), dict(zip(sequential, sequential)))
