# encoding: utf-8
"""
yang/datatypes.py

Created by Thomas Mangin on 2020-09-01.
Copyright (c) 2020 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import decimal


words = (
    'bit',
    'boolean',
    'contact',
    'container',
    'default',
    'description',
    'enumeration',
    'key',
    'import',
    'enum',
    'extension',
    'grouping',
    'leaf',
    'leaf-list',
    'length',
    'list',
    'mandatory',
    'namespace',
    'organization',
    'revision',
    'path',
    'pattern',
    'prefix',
    'refine',
    'type',
    'typedef',
    'union',
    'uses',
    'range',
    'reference',
    'require-instance',
    'value',
    'yang-version',
)

restriction = {
    'binary': ['length'],
    'bits': ['bit'],
    'boolean': [],
    'decimal64': ['range'],
    'empty': [],
    'enumeration': ['enum'],
    'identityref': [],
    'instance-identifier': ['require-instance'],
    'int8': [],
    'int16': [],
    'int32': [],
    'int64': [],
    'leafref': ['path', 'require-instance'],
    'string': ['pattern', 'length'],
    'uint8': [],
    'uint16': [],
    'uint32': [],
    'uint64': [],
    'union': [],
}

types = list(restriction.keys())

# the yang keywords
kw = dict((w, f'[{w}]') for w in words)
# the yang module loaded
kw['loaded'] = '[loaded]'
# the root of the configuration
kw['root'] = '[root]'
# to differenciate with pattern
kw['match'] = '[match]'

ranges = {
    'int8': (0, pow(2, 8) - 1),
    'int16': (0, pow(2, 16) - 1),
    'int32': (0, pow(2, 32) - 1),
    'int64': (0, pow(2, 64) - 1),
    'uint8': (-pow(2, 7), pow(2, 7) - 1),
    'uint16': (-pow(2, 7), pow(2, 15) - 1),
    'uint32': (-pow(2, 7), pow(2, 31) - 1),
    'uint64': (-pow(2, 7), pow(2, 64) - 1),
}


class Boolean(int):
    def __new__(cls, value):
        return int.__new__(cls, value not in ('false', False, 0))

    def __init__(self, boolean):
        self.string = boolean

    def __str__(self):
        return self.string


class Decimal64(decimal.Decimal):
    def __init__(cls, value, frac=0):
        raise RuntimeError()
        # look at https://github.com/CZ-NIC/yangson/blob/master/yangson/datatype.py#L682
        # return super().__init__(decimal.Decimal(value))


klass = {
    'binary': ['length'],
    'bits': ['bit'],
    'boolean': Boolean,
    'decimal64': Decimal64,
    'empty': None,
    'enumeration': None,
    'identityref': str,
    'instance-identifier': str,
    'int8': int,
    'int16': int,
    'int32': int,
    'int64': int,
    'leafref': str,
    'string': str,
    'uint8': int,
    'uint16': int,
    'uint32': int,
    'uint64': int,
    'union': None,
}
