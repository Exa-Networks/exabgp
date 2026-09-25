"""ipreach.py

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations


from exabgp.bgp.message.notification import Notify
from struct import unpack
from ipaddress import ip_address

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

# Protocol ID for IPv6
PROTOCOL_ID_IPV6 = 4  # IPv6 protocol identifier

IPV4_MAX_PREFIX_BITS = 32
IPV6_MAX_PREFIX_BITS = 128


class IpReach:
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

        if not data:
            raise Notify(3, 10, 'invalid BGP-LS IP reachability sub-TLV, no prefix length')
        plength = unpack('!B', data[0:1])[0]
        # octet = int(math.ceil(plength / 8))
        octet = len(data[1:])

        # Neither the prefix length nor the octet count was bounded by the address family.
        # An IPv6 sub-TLV carrying more than sixteen octets built an address string of nine
        # or more hextet groups, where the padding term below goes negative and Python
        # quietly yields an empty list, and ip_address() then raised ValueError out of the
        # decoder.  BGPLS.unpack_nlri does not convert that one, so the session was reset
        # without the NOTIFICATION the peer is owed, from a thirty-six byte NLRI.  The IPv4
        # branch did not raise at all: it put "1.1.1.1.1/32" into the API output, and a
        # prefix length of 255 was reported verbatim as a /255.
        maximum_plength = IPV6_MAX_PREFIX_BITS if code == PROTOCOL_ID_IPV6 else IPV4_MAX_PREFIX_BITS
        if plength > maximum_plength:
            raise Notify(3, 10, 'BGP-LS ip reachability prefix length %d is over %d' % (plength, maximum_plength))

        # RFC 7752 section 3.2.3.2 derives the IP Prefix field size from the prefix length:
        # one octet for bits 1 to 8, two for 9 to 16, and so on.  The FIXME above records
        # that IOS XR sends one octet FEWER than that, so an equality check would drop every
        # prefix from a deployed router and shorter values stay accepted.  Extra octets have
        # no such justification: they describe bits outside the advertised prefix, and let a
        # /8 decode from four address octets.
        maximum_octets = (plength + 7) // 8
        if octet > maximum_octets:
            raise Notify(
                3,
                10,
                'BGP-LS ip reachability sub-TLV carries %d prefix octets, at most %d' % (octet, maximum_octets),
            )

        if code == PROTOCOL_ID_IPV6:
            # IPv6
            if len(data[1 : octet + 1]) % 2 == 1:
                # Not an even number.
                # So we add an empty octet.
                data += bytearray.fromhex('00')
                octet += 1
            prefix_list = unpack('!%dH' % (octet / 2), data[1 : octet + 1])
            prefix_list = [str(format(x, 'x')) for x in prefix_list]
            # fill out to a complete 128-bit address
            prefix_list = prefix_list + ['0'] * (8 - len(prefix_list))
            prefix = ':'.join(prefix_list)
            prefix = ip_address(prefix).compressed
        else:
            # IPv4
            prefix_list = unpack('!%dB' % octet, data[1 : octet + 1])
            prefix_list = [str(x) for x in prefix_list]
            # fill the rest of the octets with 0 to construct
            # a 4 octet IP prefix
            prefix_list = prefix_list + ['0'] * (4 - len(prefix_list))
            prefix = '.'.join(prefix_list)

        return cls(prefix=prefix, plength=plength)

    def json(self, compact=None):
        return ', '.join(
            [
                '"ip-reachability-tlv": "{}"'.format(str(self.prefix)),
                '"ip-reach-prefix": "{}/{}"'.format(str(self.prefix), str(self.plength)),
            ],
        )

    def as_dict(self):
        return {
            'ip-reachability-tlv': str(self.prefix),
            'ip-reach-prefix': f'{self.prefix}/{self.plength}',
        }

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
        return ':'.join('{:02X}'.format(_) for _ in self._packed)

    def __repr__(self):
        return self.__str__()

    def __len__(self):
        return len(self._packed)

    def __hash__(self):
        return hash(str(self))

    def pack(self):
        return self._packed
