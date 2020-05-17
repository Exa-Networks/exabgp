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

    return '0x' + ''.join(spaced(value))


def hexbytes(value):
    return bytes(hexstring(str(value, 'ascii')), 'ascii')


def string_is_hex(s):
    if s[:2].lower() != '0x':
        return False
    if len(s) <= 2:
        return False
    return all(c in string.hexdigits for c in s[2:])


def split(data, step):
    return (data[i : i + step] for i in range(0, len(data), step))
