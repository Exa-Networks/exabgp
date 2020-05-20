# encoding: utf-8
"""
ipreach.py

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import division
from struct import unpack
import math
from exabgp.vendoring import ipaddress

from exabgp.protocol.ip import IP
from exabgp.util import ordinal

#   The IP Reachability Information TLV is a mandatory TLV that contains
#   one IP address prefix (IPv4 or IPv6) originally advertised in the IGP
#   topology.  Its purpose is to glue a particular BGP service NLRI by
#   virtue of its BGP next hop to a given node in the LSDB.  A router
#   SHOULD advertise an IP Prefix NLRI for each of its BGP next hops.
#   The format of the IP Reachability Information TLV is shown in the
#   following figure:
#
#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |              Type             |             Length            |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     | Prefix Length | IP Prefix (variable)                         //
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# ================================================================== IP REACHABILITY INFORMATION


class IpReach(object):
    def __init__(self, prefix, plength=None, packed=None):
        self.prefix = prefix
        self._packed = packed
        self.plength = plength

    @classmethod
    def unpack(cls, data, code):
        # FIXME
        # There seems to be a bug in the Cisco Xr implementation
        # that causes the Prefix IP field to be one octet less than
        # indicated by the Prefix Length field. Once the bug is fixed we'll change
        # the calculation to be rfc compliant. See below for correct way:
        #
        # The IP Prefix field contains the most significant
        # octets of the prefix, i.e., 1 octet for prefix length 1 up to 8, 2
        # octets for prefix length 9 to 16, 3 octets for prefix length 17 up to
        # 24, 4 octets for prefix length 25 up to 32, etc.

        plength = unpack('!B', data[0:1])[0]
        # octet = int(math.ceil(plength / 8))
        octet = len(data[1:])

        if code == 4:
            # IPv6
            if len(data[1 : octet + 1]) % 2 == 1:
                # Not an even number.
                # So we add an empty octet.
                data += bytearray.fromhex('00')
                octet += 1
            prefix_list = unpack("!%dH" % (octet / 2), data[1 : octet + 1])
            prefix_list = [str(format(x, 'x')) for x in prefix_list]
            # fill out to a complete 128-bit address
            prefix_list = prefix_list + ["0"] * (8 - len(prefix_list))
            prefix = u":".join(prefix_list)
            prefix = ipaddress.ip_address(prefix).compressed
        else:
            # IPv4
            prefix_list = unpack("!%dB" % octet, data[1 : octet + 1])
            prefix_list = [str(x) for x in prefix_list]
            # fill the rest of the octets with 0 to construct
            # a 4 octet IP prefix
            prefix_list = prefix_list + ["0"] * (4 - len(prefix_list))
            prefix = '.'.join(prefix_list)

        return cls(prefix=prefix, plength=plength)

    def json(self, compact=None):
        return ', '.join(
            [
                '"ip-reachability-tlv": "%s"' % str(self.prefix),
                '"ip-reach-prefix": "%s/%s"' % (str(self.prefix), str(self.plength)),
            ]
        )

    def __eq__(self, other):
        return self.prefix == other.prefix

    def __neq__(self, other):
        return self.prefix != other.prefix

    def __lt__(self, other):
        raise RuntimeError('Not implemented')

    def __le__(self, other):
        raise RuntimeError('Not implemented')

    def __gt__(self, other):
        raise RuntimeError('Not implemented')

    def __ge__(self, other):
        raise RuntimeError('Not implemented')

    def __str__(self):
        return ':'.join('%02X' % ordinal(_) for _ in self._packed)

    def __repr__(self):
        return self.__str__()

    def __len__(self):
        return len(self._packed)

    def __hash__(self):
        return hash(str(self))

    def pack(self):
        return self._packed
