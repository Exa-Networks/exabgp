# encoding: utf-8
"""
icmp.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2017-2017 Exa Networks. All rights reserved.
"""

import sys

from exabgp.protocol.family import AFI
from exabgp.protocol.resource import Resource


if sys.version_info > (3,):
    long = int


class NetMask(Resource):
    NAME = 'netmask'

    def size(self):
        return pow(2, self.maximum - self)

    def andmask(self):
        return pow(2, self.maximum) - 1

    def hostmask(self):
        return pow(2, self.maximum - self) - 1

    def networkmask(self):
        return self.hostmask() ^ self.andmask()

    def __str__(self):
        # return self.names.get(self,'%d' % int(self))
        return '%d' % int(self)

    names = {
        32: '255.255.255.255',
        31: '255.255.255.254',
        30: '255.255.255.252',
        29: '255.255.255.248',
        28: '255.255.255.240',
        27: '255.255.255.224',
        26: '255.255.255.192',
        25: '255.255.255.128',
        24: '255.255.255.0',
        23: '255.255.254.0',
        22: '255.255.252.0',
        21: '255.255.248.0',
        20: '255.255.240.0',
        19: '255.255.224.0',
        18: '255.255.192.0',
        17: '255.255.128.0',
        16: '255.255.0.0',
        15: '255.254.0.0',
        14: '255.252.0.0',
        13: '255.248.0.0',
        12: '255.240.0.0',
        11: '255.224.0.0',
        10: '255.192.0.0',
        9: '255.128.0.0',
        8: '255.0.0.0',
        7: '254.0.0.0',
        6: '252.0.0.0',
        5: '248.0.0.0',
        4: '240.0.0.0',
        3: '224.0.0.0',
        2: '192.0.0.0',
        1: '128.0.0.0',
        0: '0.0.0.0',
    }

    codes = dict([(r, l) for (l, r) in names.items()])

    @classmethod
    def create(cls, string, afi):
        if afi == AFI.ipv4:
            if string is cls.codes:
                klass = cls(cls.codes[string], 32)
                klass.maximum = 32
                return klass
            maximum = 32
        elif afi == AFI.ipv6:
            if string in cls.codes:
                raise ValueError('IPv4 mask used with an IPv6 address')
            maximum = 128
        else:
            raise ValueError('invalid address family')

        if not string.isdigit():
            raise ValueError('invalid netmask %s' % string)

        value = long(string)
        if value < 0 or value > maximum:
            raise ValueError('invalid netmask %s' % string)

        klass = cls(value)
        klass.maximum = maximum
        return klass
