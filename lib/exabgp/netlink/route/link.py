# encoding: utf-8
"""
link.py

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
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |   Family    |   Reserved  |          Device Type              |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |                     Interface Index                           |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |                      Device Flags                             |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |                      Change Mask                              |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+


class Link(Message):
    class Header(object):
        PACK = 'BxHiII'
        LEN = calcsize(PACK)

    # linux/if_link.h
    format = namedtuple('Info', 'family type index flags change attributes')

    class Command(object):
        # linux/rtnetlink.h
        RTM_NEWLINK = 0x10  # Create a new network interface
        RTM_DELLINK = 0x11  # Destroy a network interface
        RTM_GETLINK = 0x12  # Retrieve information about a network interface (ifinfomsg)
        RTM_SETLINK = 0x13  # -

    class Type(object):
        class Family(object):
            AF_INET = socket.AF_INET
            AF_INET6 = socket.AF_INET6

        class Device(object):
            IFF_UP = 0x0001  # Interface is administratively up.
            IFF_BROADCAST = 0x0002  # Valid broadcast address set.
            IFF_DEBUG = 0x0004  # Internal debugging flag.
            IFF_LOOPBACK = 0x0008  # Interface is a loopback interface.
            IFF_POINTOPOINT = 0x0010  # Interface is a point-to-point link.
            IFF_NOTRAILERS = 0x0020  # Avoid use of trailers.
            IFF_RUNNING = 0x0040  # Interface is operationally up.
            IFF_NOARP = 0x0080  # No ARP protocol needed for this interface.
            IFF_PROMISC = 0x0100  # Interface is in promiscuous mode.
            IFF_ALLMULTI = 0x0200  # Receive all multicast packets.
            IFF_MASTER = 0x0400  # Master of a load balancing bundle.
            IFF_SLAVE = 0x0800  # Slave of a load balancing bundle.
            IFF_MULTICAST = 0x1000  # Supports multicast.

            IFF_PORTSEL = 0x2000  # Is able to select media type via ifmap.
            IFF_AUTOMEDIA = 0x4000  # Auto media selection active.
            IFF_DYNAMIC = 0x8000  # Interface was dynamically created.

            IFF_LOWER_UP = 0x10000  # driver signals L1 up
            IFF_DORMANT = 0x20000  # driver signals dormant
            IFF_ECHO = 0x40000  # echo sent packet

        class Attribute(object):
            IFLA_UNSPEC = 0x00
            IFLA_ADDRESS = 0x01
            IFLA_BROADCAST = 0x02
            IFLA_IFNAME = 0x03
            IFLA_MTU = 0x04
            IFLA_LINK = 0x05
            IFLA_QDISC = 0x06
            IFLA_STATS = 0x07

    @classmethod
    def getLinks(cls):
        return cls.extract(Link.Command.RTM_GETLINK)
