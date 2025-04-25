# encoding: utf-8
"""
resource.py

Created by Thomas Mangin on 2015-05-15.
Copyright (c) 2015-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.util import string_is_hex


class Resource(int):
    NAME = ''
    codes = {}
    names = {}

    cache = {}

    def __new__(cls, *args):
        key = '//'.join((str(_) for _ in args))
        if key in Resource.cache.setdefault(cls, {}):
            return Resource.cache[cls][key]
        instance = int.__new__(cls, *args)
        Resource.cache[cls][key] = instance
        return instance

    def short(self):
        return self.names.get(self, '%ld' % self)

    def __str__(self):
        return self.names.get(self, 'unknown %s type %ld' % (self.NAME, self))

    @classmethod
    def _value(cls, string):
        name = string.lower().replace('_', '-')
        if name in cls.codes:
            return cls.codes[name]
        if string.isdigit():
            value = int(string)
            if 0 <= value <= 0xFFFF:
                return value
        if string_is_hex(string):
            value = int(string[2:], 16)
            if 0 <= value <= 0xFFFF:
                return value
        raise ValueError('unknown %s %s' % (cls.NAME, name))

    @classmethod
    def named(cls, string):
        value = 0
        for name in string.split('+'):
            value += cls._value(name)
        return cls(value)


class BitResource(Resource):
    def named_bits(self):
        value = int(self)
        for bit in self.names.keys():
            if value & bit or value == bit:
                yield self.names[bit]
                value -= bit
        if value:
            yield self.names.get(self, 'unknown %s type %ld' % (self.NAME, int(self)))

    def bits(self):
        value = int(self)
        for bit in self.names.keys():
            if value & bit or value == bit:
                yield self.names[bit]
                value -= bit
        if value:
            yield self.names.get(self, '%s' % hex(self))

    def short(self):
        return '+'.join(self.bits())

    def __str__(self):
        return '+'.join(self.named_bits())
