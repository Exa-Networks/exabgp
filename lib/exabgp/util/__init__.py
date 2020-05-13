# encoding: utf-8
"""
__init__.py

Created by Thomas Mangin on 2015-05-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import string


def hexstring(value):
    def spaced(value):
        for v in value:
            yield '%02X' % v

    return '0x' + concat_strs_i(spaced(value))


def hexbytes(value):
    return bytes_ascii(hexstring(str_ascii(value)))


def string_is_hex(s):
    if s[:2].lower() != '0x':
        return False
    if len(s) <= 2:
        return False
    return all(c in string.hexdigits for c in s[2:])


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


def str_ascii(bytestring):
    return str(bytestring, 'ascii')


def bytes_ascii(bytestring):
    return bytes(bytestring, 'ascii')
