# encoding: utf-8
"""
network.py

Created by Thomas Mangin on 2015-03-31.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import socket
from struct import calcsize
from collections import namedtuple

from exabgp.netlink.message import NetLink
from exabgp.netlink.message import Message

# from exabgp.netlink.attributes import Attributes


# 0                   1                   2                   3
# 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |   Family    |  Src length   |  Dest length  |     TOS       |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |  Table ID   |   Protocol    |     Scope     |     Type      |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |                          Flags                              |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+


class Network(Message):
    class Header(object):
        # linux/if_addr.h
        PACK = '8BI'  # or is it 8Bi ?
        LEN = calcsize(PACK)

    format = namedtuple('Neighbor', 'family src_len dst_len tos table proto scope type flags attributes')

    class Command(object):
        RTM_NEWROUTE = 0x18
        RTM_DELROUTE = 0x19
        RTM_GETROUTE = 0x1A

    class Type(object):
        class Table(object):
            RT_TABLE_UNSPEC = 0x00  # An unspecified routing table
            RT_TABLE_DEFAULT = 0xFD  # The default table
            RT_TABLE_MAIN = 0xFE  # The main table
            RT_TABLE_LOCAL = 0xFF  # The local table

        class Protocol(object):
            RTPROT_UNSPEC = 0x00  # Identifies what/who added the route
            RTPROT_REDIRECT = 0x01  # By an ICMP redirect
            RTPROT_KERNEL = 0x02  # By the kernel
            RTPROT_BOOT = 0x03  # During bootup
            RTPROT_STATIC = 0x04  # By the administrator
            RTPROT_GATED = 0x08  # GateD
            RTPROT_RA = 0x09  # RDISC/ND router advertissements
            RTPROT_MRT = 0x0A  # Merit MRT
            RTPROT_ZEBRA = 0x0B  # ZEBRA
            RTPROT_BIRD = 0x0C  # BIRD
            RTPROT_DNROUTED = 0x0D  # DECnet routing daemon
            RTPROT_XORP = 0x0E  # XORP
            RTPROT_NTK = 0x0F  # Netsukuku
            RTPROT_DHCP = 0x10  # DHCP client
            # Self allocating ourself a kernel table :p
            # http://lxr.free-electrons.com/source/include/uapi/linux/rtnetlink.h#L237
            # YES WE CAN !
            RTPROT_EXABGP = 0x11  # Exa Networks ExaBGP

        class Scope(object):
            RT_SCOPE_UNIVERSE = 0x00  # Global route
            RT_SCOPE_SITE = 0xC8  # Interior route in the local autonomous system
            RT_SCOPE_LINK = 0xFD  # Route on this link
            RT_SCOPE_HOST = 0xFE  # Route on the local host
            RT_SCOPE_NOWHERE = 0xFF  # Destination does not exist

        class Type(object):
            RTN_UNSPEC = 0x00  # Unknown route.
            RTN_UNICAST = 0x01  # A gateway or direct route.
            RTN_LOCAL = 0x02  # A local interface route.
            RTN_BROADCAST = 0x03  # A local broadcast route (sent as a broadcast).
            RTN_ANYCAST = 0x04  # An anycast route.
            RTN_MULTICAST = 0x05  # A multicast route.
            RTN_BLACKHOLE = 0x06  # A silent packet dropping route.
            RTN_UNREACHABLE = 0x07  # An unreachable destination.  Packets dropped and host unreachable ICMPs are sent to the originator.
            RTN_PROHIBIT = 0x08  # A packet rejection route.  Packets are dropped and communication prohibited ICMPs are sent to the originator.
            RTN_THROW = 0x09  # When used with policy routing, continue routing lookup in another table.  Under normal routing, packets are dropped and net unreachable ICMPs are sent to the originator.
            RTN_NAT = 0x0A  # A network address translation rule.
            RTN_XRESOLVE = 0x0B  # Refer to an external resolver (not implemented).

        class Flag(object):
            RTM_F_NOTIFY = 0x100  # If the route changes, notify the user
            RTM_F_CLONED = 0x200  # Route is cloned from another route
            RTM_F_EQUALIZE = (
                0x400  # Allow randomization of next hop path in multi-path routing (currently not implemented)
            )
            RTM_F_PREFIX = 0x800  # Prefix Address

        class Attribute(object):
            RTA_UNSPEC = 0x00  # Ignored.
            RTA_DST = 0x01  # Protocol address for route destination address.
            RTA_SRC = 0x02  # Protocol address for route source address.
            RTA_IIF = 0x03  # Input interface index.
            RTA_OIF = 0x04  # Output interface index.
            RTA_GATEWAY = 0x05  # Protocol address for the gateway of the route
            RTA_PRIORITY = 0x06  # Priority of route.
            RTA_PREFSRC = 0x07  # Preferred source address in cases where more than one source address could be used.
            RTA_METRICS = 0x08  # Route metrics attributed to route and associated protocols (e.g., RTT, initial TCP window, etc.).
            RTA_MULTIPATH = 0x09  # Multipath route next hop's attributes.
            # RTA_PROTOINFO   = 0x0A  # Firewall based policy routing attribute.
            RTA_FLOW = 0x0B  # Route realm.
            RTA_CACHEINFO = 0x0C  # Cached route information.
            # RTA_SESSION     = 0x0D
            # RTA_MP_ALGO     = 0x0E
            RTA_TABLE = 0x0F

    @classmethod
    def getRoutes(cls):
        return cls.extract(Network.Command.RTM_GETROUTE)

    @classmethod
    def newRoute(cls):
        network_flags = NetLink.Flags.NLM_F_REQUEST
        network_flags |= NetLink.Flags.NLM_F_ACK
        network_flags |= NetLink.Flags.NLM_F_CREATE
        # 		network_flags |= NetLink.Flags.NLM_F_EXCL

        family = socket.AF_INET

        prefix = '\x0a\1\0\0'
        prefix_len = 24
        gateway = '\x0a\0\0\1'

        attributes = {
            Network.Type.Attribute.RTA_DST: prefix,
            Network.Type.Attribute.RTA_GATEWAY: gateway,
        }

        # format = namedtuple('Address', 'family prefixlen flags scope index attributes')
        # format = namedtuple('Neighbor', 'family src_len dst_len tos table proto scope type flags attributes')

        neighbor = cls.format(
            family,
            0,  # src_len
            prefix_len,  # dst_len ( only /32 atm)
            0,  # tos
            Network.Type.Table.RT_TABLE_MAIN,
            Network.Type.Protocol.RTPROT_EXABGP,
            Network.Type.Scope.RT_SCOPE_UNIVERSE,
            Network.Type.Type.RTN_UNICAST,
            Network.Type.Flag.RTM_F_PREFIX,  # this may be wrong
            attributes,
        )

        return cls.extract(Network.Command.RTM_NEWROUTE, network_flags, family, neighbor)

    @classmethod
    def delRoute(cls):
        return cls.extract(Network.Command.RTM_DELROUTE)
