"""icmp.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2017-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from typing import ClassVar, Dict, Union

from exabgp.protocol.family import AFI
from exabgp.protocol.resource import Resource


class NetMask(Resource):
    NAME: ClassVar[str] = 'netmask'

    maximum: int  # Set by create() - 32 for IPv4, 128 for IPv6

    def size(self) -> int:
        return int(pow(2, self.maximum - int(self)))

    def andmask(self) -> int:
        return int(pow(2, self.maximum)) - 1

    def hostmask(self) -> int:
        return int(pow(2, self.maximum - int(self))) - 1

    def networkmask(self) -> int:
        return self.hostmask() ^ self.andmask()

    def __str__(self) -> str:
        # return self.names.get(self,'%d' % int(self))
        return '%d' % int(self)

    names: ClassVar[Dict[int, str]] = {
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

    codes: ClassVar[Dict[str, int]] = dict([(inst, name) for (name, inst) in names.items()])

    @classmethod
    def create(cls, string: Union[str, int], afi: AFI) -> NetMask:
        if afi == AFI.ipv4:
            if isinstance(string, str) and string in cls.codes:
                klass = cls(cls.codes[string])
                klass.maximum = 32
                return klass
            maximum = 32
        elif afi == AFI.ipv6:
            if isinstance(string, str) and string in cls.codes:
                raise ValueError('IPv4 mask used with an IPv6 address')
            maximum = 128
        else:
            raise ValueError('invalid address family')

        if not str(string).isdigit():
            raise ValueError('invalid netmask {}'.format(string))

        value = int(string)
        if value < 0 or value > maximum:
            raise ValueError('invalid netmask {}'.format(string))

        klass = cls(value)
        klass.maximum = maximum
        return klass
