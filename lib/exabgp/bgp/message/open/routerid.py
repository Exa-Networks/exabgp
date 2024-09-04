# encoding: utf-8
"""
routerid.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.protocol.family import AFI
from exabgp.protocol.ip import IPv4

from exabgp.util import ordinal

# ===================================================================== RouterID
#


class RouterID(IPv4):
    def __init__(self, ip, packed=None):
        if IPv4.toafi(ip) != AFI.ipv4:
            raise ValueError('wrong address family')
        IPv4.__init__(self, ip, packed)

    @classmethod
    def unpack(cls, data):  # pylint: disable=W0221
        return cls('.'.join(str(ordinal(_)) for _ in data), data)
