"""esi.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2014-2017 Orange. All rights reserved.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# TODO: take into account E-VPN specs that specify the role of the first bit of ESI
# (since draft-ietf-l2vpn-evpn-05)


# Ethernet Segment Identifier
class ESI:
    LENGTH = 10  # RFC 7432 - Ethernet Segment Identifier is always 10 bytes

    DEFAULT = bytes([0x00] * LENGTH)  # All zeros
    MAX = bytes([0xFF] * LENGTH)  # All ones

    def __init__(self, esi=None):
        self.esi = self.DEFAULT if esi is None else esi
        if len(self.esi) != self.LENGTH:
            raise Exception(f'incorrect ESI, len {len(esi)} instead of {self.LENGTH}')

    def __eq__(self, other):
        return self.esi == other.esi

    def __neq__(self, other):
        return self.esi != other.esi

    def __lt__(self, other):
        raise RuntimeError('comparing ESI for ordering does not make sense')

    def __le__(self, other):
        raise RuntimeError('comparing ESI for ordering does not make sense')

    def __gt__(self, other):
        raise RuntimeError('comparing ESI for ordering does not make sense')

    def __ge__(self, other):
        raise RuntimeError('comparing ESI for ordering does not make sense')

    def __str__(self):
        if self.esi == self.DEFAULT:
            return '-'
        return ':'.join('{:02x}'.format(_) for _ in self.esi)

    def __repr__(self):
        return self.__str__()

    def pack(self):
        return self.esi

    def __len__(self):
        return self.LENGTH

    def __hash__(self):
        return hash(self.esi)

    @classmethod
    def unpack(cls, data):
        return cls(data[: cls.LENGTH])

    def json(self, compact=None):
        return '"esi": "{}"'.format(str(self))
