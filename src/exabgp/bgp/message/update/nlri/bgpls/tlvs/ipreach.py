"""ipreach.py

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations


from struct import unpack
from ipaddress import ip_address

from exabgp.bgp.message.notification import Notify
from exabgp.util.types import Buffer

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
    def __init__(self, prefix: str, plength: int, packed: Buffer) -> None:
        self.prefix = prefix
        self.plength = plength
        self._packed = packed

    @classmethod
    def unpack_ipreachability(cls, data: Buffer, code: int) -> 'IpReach':
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

        # Store original data for _packed before any modification
        original_data = bytes(data)

        if len(data) < 1:
            raise Notify(3, 10, 'BGP-LS ip reachability sub-tlv is empty, expected at least a prefix length byte')
        plength = unpack('!B', data[0:1])[0]
        # octet = int(math.ceil(plength / 8))
        octet = len(data[1:])

        # Neither the prefix length nor the octet count was bounded by the address family.
        # An IPv6 sub-tlv carrying more than sixteen octets built an address string of nine
        # or more hextet groups, where the padding term goes negative and Python quietly
        # yields an empty list, and ip_address() then raised ValueError out of the decoder.
        # unpack_nlri does not catch that, so the session reset without the NOTIFICATION the
        # peer is owed. The IPv4 branch did not raise at all: it put "1.1.1.1.1/32" into the
        # API output, and a prefix length of 255 was reported verbatim as a /255.
        maximum_plength = IPV6_MAX_PREFIX_BITS if code == PROTOCOL_ID_IPV6 else IPV4_MAX_PREFIX_BITS
        if plength > maximum_plength:
            raise Notify(3, 10, f'BGP-LS ip reachability prefix length {plength} is over {maximum_plength}')

        # RFC 7752 derives the IP Prefix field size from the prefix length:
        # one octet for bits 1-8, two for 9-16, and so on. IOS XR is known
        # to send one octet fewer than that relationship requires, so an
        # equality check would reject deployed peers and shorter values remain
        # accepted. Extra octets have no such interoperability justification:
        # they describe bits outside the advertised prefix and previously let,
        # for example, a /8 decode from four address octets.
        maximum_octets = (plength + 7) // 8
        if octet > maximum_octets:
            raise Notify(
                3,
                10,
                f'BGP-LS ip reachability sub-tlv carries {octet} prefix octets, at most {maximum_octets}',
            )

        if code == PROTOCOL_ID_IPV6:
            # IPv6
            if len(data[1 : octet + 1]) % 2 == 1:
                # Not an even number.
                # So we add an empty octet.
                data = bytes(data) + bytearray.fromhex('00')
                octet += 1
            prefix_tuple = unpack('!%dH' % (octet / 2), data[1 : octet + 1])
            prefix_parts = [str(format(x, 'x')) for x in prefix_tuple]
            # fill out to a complete 128-bit address
            prefix_parts = prefix_parts + ['0'] * (8 - len(prefix_parts))
            prefix = ':'.join(prefix_parts)
            prefix = ip_address(prefix).compressed
        else:
            # IPv4
            prefix_tuple = unpack('!%dB' % octet, data[1 : octet + 1])
            prefix_parts = [str(x) for x in prefix_tuple]
            # fill the rest of the octets with 0 to construct
            # a 4 octet IP prefix
            prefix_parts = prefix_parts + ['0'] * (4 - len(prefix_parts))
            prefix = '.'.join(prefix_parts)

        return cls(prefix=prefix, plength=plength, packed=original_data)

    def json(self, compact: bool = False) -> str:
        return ', '.join(
            [
                '"ip-reachability-tlv": "{}/{}"'.format(str(self.prefix), str(self.plength)),
                '"ip-reach-prefix": "{}/{}"'.format(str(self.prefix), str(self.plength)),
            ],
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, IpReach):
            return NotImplemented
        return self.prefix == other.prefix

    def __lt__(self, other: IpReach) -> bool:
        raise RuntimeError('Not implemented')

    def __le__(self, other: IpReach) -> bool:
        raise RuntimeError('Not implemented')

    def __gt__(self, other: IpReach) -> bool:
        raise RuntimeError('Not implemented')

    def __ge__(self, other: IpReach) -> bool:
        raise RuntimeError('Not implemented')

    def __str__(self) -> str:
        return ':'.join('{:02X}'.format(_) for _ in self._packed)

    def __repr__(self) -> str:
        return self.__str__()

    def __len__(self) -> int:
        return len(self._packed)

    def __hash__(self) -> int:
        return hash(str(self))

    def pack_tlv(self) -> Buffer:
        return self._packed
