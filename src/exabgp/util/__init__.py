
"""__init__.py

Created by Thomas Mangin on 2015-05-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import string

# Hexadecimal string prefix length
HEX_PREFIX_LENGTH = 2  # Length of '0x' prefix


def hexstring(value):
    def spaced(value):
        for v in value:
            yield '{:02X}'.format(v)

    return '0x' + ''.join(spaced(value))


def hexbytes(value):
    return bytes(hexstring(str(value, 'ascii')), 'ascii')


def string_is_hex(s):
    if s[:HEX_PREFIX_LENGTH].lower() != '0x':
        return False
    if len(s) <= HEX_PREFIX_LENGTH:
        return False
    return all(c in string.hexdigits for c in s[HEX_PREFIX_LENGTH:])


def split(data, step):
    return (data[i : i + step] for i in range(0, len(data), step))
