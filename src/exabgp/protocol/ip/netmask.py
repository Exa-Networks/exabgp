"""icmp.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2017-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from typing import ClassVar

from exabgp.protocol.family import AFI
from exabgp.protocol.resource import Resource


class NetMask(Resource):
    NAME: ClassVar[str] = 'netmask'

    maximum: int  # Set by make_netmask() - 32 for IPv4, 128 for IPv6

    # One instance per length and family. Resource caches by value alone, which made every
    # mask of one length a single object, and `maximum` belonged to whichever family asked
    # last: an IPv6 /32 made an IPv4 /32 count 2**96 addresses.
    _by_family: ClassVar[dict[tuple[int, int], NetMask]] = {}

    @classmethod
    def _make(cls, value: int, maximum: int) -> NetMask:
        key = (value, maximum)
        if key not in cls._by_family:
            instance = int.__new__(cls, value)
            instance.maximum = maximum
            cls._by_family[key] = instance
        mask = cls._by_family[key]
        assert mask.maximum == maximum, 'a netmask is only ever made for one family'
        return mask

    # a copy, deep or not, and an unpickled mask are the instance of their family: rebuilt by
    # value, they would come from the Resource cache, which is shared by both families
    def __copy__(self) -> NetMask:
        return self

    def __deepcopy__(self, memo: dict[int, object]) -> NetMask:
        return self

    def __reduce__(self) -> tuple[object, tuple[int, int]]:
        return NetMask._make, (int(self), self.maximum)

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

    names: ClassVar[dict[int, str]] = {
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

    codes: ClassVar[dict[str, int]] = dict([(inst, name) for (name, inst) in names.items()])

    @classmethod
    def make_netmask(cls, string: str | int, afi: AFI) -> NetMask:
        if afi == AFI.ipv4:
            if isinstance(string, str) and string in cls.codes:
                return cls._make(cls.codes[string], 32)
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

        return cls._make(value, maximum)
