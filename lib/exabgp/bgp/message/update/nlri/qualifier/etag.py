# encoding: utf-8
"""
etag.py

Created by Thomas Mangin on 2014-06-26.
Copyright (c) 2014-2017 Orange. All rights reserved.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# TODO: take into account E-VPN specs that specify the role of the first bit of ESI
# (since draft-ietf-l2vpn-evpn-05)

from struct import pack
from struct import unpack


class EthernetTag(object):
    MAX = pow(2, 32) - 1

    __slots__ = ['tag']

    def __init__(self, tag=0):
        self.tag = tag

    def __eq__(self, other):
        return self.tag == other.tag

    def __neq__(self, other):
        return self.tag != other.tag

    def __lt__(self, other):
        raise RuntimeError('comparing EthernetTag for ordering does not make sense')

    def __le__(self, other):
        raise RuntimeError('comparing EthernetTag for ordering does not make sense')

    def __gt__(self, other):
        raise RuntimeError('comparing EthernetTag for ordering does not make sense')

    def __ge__(self, other):
        raise RuntimeError('comparing EthernetTag for ordering does not make sense')

    def __str__(self):
        return repr(self.tag)

    def __repr__(self):
        return repr(self.tag)

    def pack(self):
        return pack("!L", self.tag)

    def __len__(self):
        return 4

    def __hash__(self):
        return hash(self.tag)

    @classmethod
    def unpack(cls, data):
        return cls(unpack("!L", data[:4])[0])

    def json(self, compact=None):
        return '"ethernet-tag": %s' % self.tag
