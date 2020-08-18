# encoding: utf-8
"""
enumeration.py

Created by Thomas Mangin on 2013-03-18.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""


# int are immutable once created: can not set ._str in __init__
class _integer(int):
    def __str__(self):
        return self._str


class Enumeration(object):
    def __init__(self, *names):
        for number, name in enumerate(names):
            # doing the .parent thing here instead
            number = _integer(pow(2, number))
            number._str = name
            setattr(self, name, number)


# Taken from Vincent Bernat
def Enum(*sequential):
    return type(str("Enum"), (), dict(zip(sequential, sequential)))
