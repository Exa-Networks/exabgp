"""enumeration.py

Created by Thomas Mangin on 2013-03-18.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Type


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
def enum(*sequential: str) -> Type:
    return type(str('Enum'), (), dict(zip(sequential, sequential)))
