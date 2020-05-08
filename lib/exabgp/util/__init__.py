# encoding: utf-8
"""
__init__.py

Created by Thomas Mangin on 2015-05-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import string
import sys

PY2 = sys.version_info[0] < 3


def hexstring(value):
    def spaced(value):
        for v in value:
            yield '%02X' % ordinal(v)

    return '0x' + concat_strs_i(spaced(value))


def hexbytes(value):
    return bytes_ascii(hexstring(str_ascii(value)))


def string_is_hex(s):
    if s[:2].lower() != '0x':
        return False
    if len(s) <= 2:
        return False
    return all(c in string.hexdigits for c in s[2:])


# for Python3+, let's redefine ord into something
# that plays along nicely with ord(data[42]) with
# data being of type 'bytes'


if PY2:
    ordinal = ord
else:

    def ordinal(x):
        return x if type(x) == int else ord(x)


if PY2:
    character = chr
else:

    def character(x):
        return bytes([x])


if PY2:

    def padding(n):
        return '\0' * n


else:

    def padding(n):
        return bytes(n)


# Each item is an 'str' in py2 or a 'bytes' in py3


def concat_strs(*items):
    return ''.join(items)


def concat_bytes(*items):
    return b''.join(items)


# same with iterators/lists


def concat_strs_i(iterable):
    return ''.join(iterable)


def concat_bytes_i(iterable):
    return b''.join(iterable)


# helpers for converting between string and bytestring

if PY2:

    def str_ascii(string):
        return string


else:

    def str_ascii(bytestring):
        return str(bytestring, 'ascii')


if PY2:

    def bytes_ascii(string):
        return string


else:

    def bytes_ascii(bytestring):
        return bytes(bytestring, 'ascii')
