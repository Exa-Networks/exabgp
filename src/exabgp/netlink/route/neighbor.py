# encoding: utf-8
"""
neighbor.py

Created by Thomas Mangin on 2015-03-31.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import socket
from struct import calcsize
from collections import namedtuple

from exabgp.netlink.message import Message


# 0                   1                   2                   3
# 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |   Family    |    Reserved1  |           Reserved2           |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |                     Interface Index                         |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |           State             |     Flags     |     Type      |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+


class Neighbor(Message):
    class Header(object):
        # linux/if_addr.h
        PACK = 'BxxxiHBB'
        LEN = calcsize(PACK)

    format = namedtuple('Neighbor', 'family index state flags type attributes')

    class Command(object):
        RTM_NEWNEIGH = 0x1C
        RTM_DELNEIGH = 0x1D
        RTM_GETNEIGH = 0x1E

    class Type(object):
        class Family(object):
            AF_INET = socket.AF_INET
            AF_INET6 = socket.AF_INET6

        class State(object):
            NUD_INCOMPLETE = 0x01  # Still attempting to resolve
            NUD_REACHABLE = 0x02  # A confirmed working cache entry
            NUD_STALE = 0x04  # an expired cache entry
            NUD_DELAY = 0x08  # Neighbor no longer reachable.  Traffic sent, waiting for confirmatio.
            NUD_PROBE = 0x10  # A cache entry that is currently being re-solicited
            NUD_FAILED = 0x20  # An invalid cache entry
            # Dummy states
            NUD_NOARP = 0x40  # A device which does not do neighbor discovery (ARP)
            NUD_PERMANENT = 0x80  # A static entry
            NUD_NONE = 0x00

        class Flag(object):
            NTF_USE = 0x01
            NTF_PROXY = 0x08  # A proxy ARP entry
            NTF_ROUTER = 0x80  # An IPv6 router

        class Attribute(object):
            # XXX : Not sure - starts at zero or one ... ??
            NDA_UNSPEC = 0x00  # Unknown type
            NDA_DST = 0x01  # A neighbour cache network. layer destination address
            NDA_LLADDR = 0x02  # A neighbor cache link layer address.
            NDA_CACHEINFO = 0x03  # Cache statistics
            NDA_PROBES = 0x04

    @classmethod
    def getNeighbors(cls):
        return cls.extract(Neighbor.Command.RTM_GETNEIGH)
