# encoding: utf-8
"""
address.py

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
# |   Family    |     Length    |     Flags     |    Scope      |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |                     Interface Index                         |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+


class Address(Message):
    class Header(object):
        PACK = '4Bi'
        LEN = calcsize(PACK)

    format = namedtuple('Address', 'family prefixlen flags scope index attributes')

    class Command(object):
        RTM_NEWADDR = 0x14
        RTM_DELADDR = 0x15
        RTM_GETADDR = 0x16

    class Type(object):
        class Family(object):
            AF_INET = socket.AF_INET
            AF_INET6 = socket.AF_INET6

        class Flag(object):
            IFA_F_SECONDARY = 0x00  # For secondary address (alias interface)
            IFA_F_PERMANENT = 0x00  # For a permanent address set by the user.  When this is not set, it means the address was dynamically created (e.g., by stateless autoconfiguration).
            IFA_F_DEPRECATED = 0x00  # Defines deprecated (IPV4) address
            IFA_F_TENTATIVE = (
                0x00  # Defines tentative (IPV4) address (duplicate address detection is still in progress)
            )

        class Scope(object):
            RT_SCOPE_UNIVERSE = 0x00  # Global route
            RT_SCOPE_SITE = 0x00  # Interior route in the local autonomous system
            RT_SCOPE_LINK = 0x00  # Route on this link
            RT_SCOPE_HOST = 0x00  # Route on the local host
            RT_SCOPE_NOWHERE = 0x00  # Destination does not exist

        class Attribute(object):
            IFLA_UNSPEC = 0x00
            IFLA_ADDRESS = 0x01
            IFLA_BROADCAST = 0x02
            IFLA_IFNAME = 0x03
            IFLA_MTU = 0x04
            IFLA_LINK = 0x05
            IFLA_QDISC = 0x06
            IFLA_STATS = 0x07
            IFLA_COST = 0x08
            IFLA_PRIORITY = 0x09
            IFLA_MASTER = 0x0A
            IFLA_WIRELESS = 0x0B
            IFLA_PROTINFO = 0x0C
            IFLA_TXQLEN = 0x0D
            IFLA_MAP = 0x0E
            IFLA_WEIGHT = 0x0F
            IFLA_OPERSTATE = 0x10
            IFLA_LINKMODE = 0x11
            IFLA_LINKINFO = 0x12
            IFLA_NET_NS_PID = 0x13
            IFLA_IFALIAS = 0x14
            IFLA_NUM_VF = 0x15
            IFLA_VFINFO_LIST = 0x16
            IFLA_STATS64 = 0x17
            IFLA_VF_PORTS = 0x18
            IFLA_PORT_SELF = 0x19

    @classmethod
    def getAddresses(cls):
        return cls.extract(Address.Command.RTM_GETADDR)
