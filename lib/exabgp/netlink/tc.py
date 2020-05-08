# encoding: utf-8
"""
tc.py

Created by Thomas Mangin on 2015-03-31.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# import socket
from struct import calcsize

# from collections import namedtuple

from exabgp.netlink.message import Message


# 0                   1                   2                   3
# 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |   Family    |  Reserved1    |         Reserved2             |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |                     Interface Index                         |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |                      Qdisc handle                           |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |                     Parent Qdisc                            |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |                        TCM Info                             |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+


class TC(Message):
    class Header(object):
        PACK = "BxxxiIII"
        LEN = calcsize(PACK)

    class Command(object):
        RTM_NEWQDISC = 36
        RTM_DELQDISC = 37
        RTM_GETQDISC = 38

    class Type(object):
        class Attribute(object):
            TCA_UNSPEC = 0x00
            TCA_KIND = 0x01
            TCA_OPTIONS = 0x02
            TCA_STATS = 0x03
            TCA_XSTATS = 0x04
            TCA_RATE = 0x05
            TCA_FCNT = 0x06
            TCA_STATS2 = 0x07
