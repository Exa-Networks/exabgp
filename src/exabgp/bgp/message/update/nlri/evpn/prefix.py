"""prefix.py

Created by Diego Garcia del Rio on 2015-03-12.
Copyright (c) 2015 Alcatel-Lucent. All rights reserved.

Based on work by Thomas Morin on mac.py
Copyright (c) 2014-2017 Orange. All rights reserved.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import ClassVar

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN
from exabgp.bgp.message.update.nlri.qualifier import ESI, EthernetTag, Labels, RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.protocol.ip import IP
from exabgp.util.types import Buffer

# ------------ EVPN Prefix Advertisement NLRI ------------
# As described here:
# https://tools.ietf.org/html/draft-ietf-bess-evpn-prefix-advertisement-01

# +---------------------------------------+
# |      RD   (8 octets)                  |
# +---------------------------------------+
# |Ethernet Segment Identifier (10 octets)|
# +---------------------------------------+
# |  Ethernet Tag ID (4 octets)           |
# +---------------------------------------+
# |  IP Prefix Length (1 octet)           |
# +---------------------------------------+
# |  IP Prefix (4 or 16 octets)           |
# +---------------------------------------+
# |  GW IP Address (4 or 16 octets)       |
# +---------------------------------------+
# |  MPLS Label (3 octets)                |
# +---------------------------------------+
# total NLRI length is 34 bytes for IPv4 or 58 bytes for IPv6

# ======================================================================= Prefix

# https://tools.ietf.org/html/draft-rabadan-l2vpn-evpn-prefix-advertisement-03


IPV4_ROUTE_SIZE = 36  # header(2) + RD(8) + ESI(10) + ETag(4) + IPlen(1) + IP(4) + GW(4) + label(3)
IPV4_PREFIX_BITS = 32
IPV6_PREFIX_BITS = 128


class Prefix(EVPN):
    """EVPN Route Type 5: IP Prefix Advertisement.

    Wire format: type(1) + length(1) + RD(8) + ESI(10) + ETag(4) + IPlen(1)
                 + IP(4/16) + GwIP(4/16) + Label(3)
    Total: 36 bytes for IPv4, 60 bytes for IPv6 (including 2-byte header)
    Uses packed-bytes-first pattern for zero-copy routing.
    """

    NAME: ClassVar[str] = 'IP Prefix Advertisement'
    SHORT_NAME: ClassVar[str] = 'PrfxAdv'

    def __init__(self, packed: Buffer) -> None:
        """Create Prefix from complete wire-format bytes.

        Args:
            packed: Complete wire format (type + length + payload)
        """
        EVPN.__init__(self, packed)

    @classmethod
    def make_prefix(
        cls,
        rd: RouteDistinguisher,
        esi: ESI,
        etag: EthernetTag,
        label: Labels | None,
        ip: IP,
        iplen: int,
        gwip: IP,
        action: Action = Action.UNSET,
        addpath: PathInfo = PathInfo.DISABLED,
    ) -> 'Prefix':
        """Factory method to create Prefix from semantic parameters.

        Packs fields into wire format immediately (packed-bytes-first pattern).
        Note: nexthop is not part of NLRI - set separately after creation.

        rd: a RouteDistinguisher
        esi: an EthernetSegmentIdentifier
        etag: an EthernetTag
        label: a LabelStackEntry
        ip: an IP address (dotted quad string notation)
        iplen: prefixlength for ip (defaults to 32)
        gwip: an IP address (dotted quad string notation)
        """
        label_to_use = label if label else Labels.NOLABEL
        payload = (
            bytes(rd.pack_rd())
            + esi.pack_esi()
            + etag.pack_etag()
            + bytes([iplen])
            + ip.pack_ip()
            + gwip.pack_ip()
            + label_to_use.pack_labels()
        )
        # Include type + length header for zero-copy pack
        packed = bytes([cls.CODE, len(payload)]) + payload
        instance = cls(packed)
        instance.addpath = addpath
        return instance

    # Wire format offsets (after 2-byte type+length header):
    # RD: 2-10, ESI: 10-20, ETag: 20-24, IPlen: 24, IP: 25+, GwIP: after IP, Label: after GwIP
    # Total: 36 bytes for IPv4, 60 bytes for IPv6

    @property
    def rd(self) -> RouteDistinguisher:
        """Route Distinguisher - unpacked from wire bytes."""
        return RouteDistinguisher.unpack_routedistinguisher(self._packed[2:10])

    @property
    def esi(self) -> ESI:
        """Ethernet Segment Identifier - unpacked from wire bytes."""
        return ESI.unpack_esi(self._packed[10:20])

    @property
    def etag(self) -> EthernetTag:
        """Ethernet Tag - unpacked from wire bytes."""
        return EthernetTag.unpack_etag(self._packed[20:24])

    @property
    def iplen(self) -> int:
        """IP prefix length - unpacked from wire bytes."""
        return self._packed[24]

    @property
    def ip(self) -> IP:
        """IP prefix - unpacked from wire bytes."""
        # IP address is either 4 or 16 bytes based on total length
        datalen = len(self._packed)
        if datalen == 36:  # IPv4: 2+8+10+4+1+4+4+3
            return IP.create_ip(self._packed[25:29])
        else:  # IPv6: 2+8+10+4+1+16+16+3 = 60
            return IP.create_ip(self._packed[25:41])

    @property
    def gwip(self) -> IP:
        """Gateway IP - unpacked from wire bytes."""
        datalen = len(self._packed)
        if datalen == 36:  # IPv4
            return IP.create_ip(self._packed[29:33])
        else:  # IPv6
            return IP.create_ip(self._packed[41:57])

    @property
    def label(self) -> Labels:
        """MPLS Labels - unpacked from wire bytes."""
        datalen = len(self._packed)
        if datalen == 36:  # IPv4
            return Labels.unpack_labels(self._packed[33:36])
        else:  # IPv6
            return Labels.unpack_labels(self._packed[57:60])

    def __str__(self) -> str:
        return '{}:{}:{}:{}:{}{}:{}:{}'.format(
            self._prefix(),
            self.rd._str(),
            self.esi,
            self.etag,
            self.ip,
            '/%d' % self.iplen,
            self.gwip,
            self.label,
        )

    def _route_key(self) -> bytes:
        # RFC 9136 3.1: the RD, Ethernet Tag, IP prefix length and IP prefix; the ESI, the
        # gateway and the label are attributes
        packed = bytes(self._packed)
        ip_end = 29 if len(packed) == IPV4_ROUTE_SIZE else 41
        return packed[0:1] + packed[2:10] + packed[20:ip_end]

    @classmethod
    def unpack_evpn(cls, packed: Buffer) -> EVPN:
        """Unpack Prefix from complete wire format bytes.

        Args:
            packed: Complete wire format (type + length + payload)

        Returns:
            Prefix instance with stored wire bytes
        """
        # Get the data length to understand if addresses are IPv4 or IPv6
        # Lengths include 2-byte header: 36 for IPv4 (34+2), 60 for IPv6 (58+2)
        datalen = len(packed)

        if datalen not in (36, 60):  # 36 for IPv4, 60 for IPv6
            raise Notify(
                3,
                5,
                'Data field length is given as %d, but EVPN route currently support only IPv4 or IPv6 (36 or 60)'
                % datalen,
            )

        # RFC 9136 3.1: "between 0 and 32 (bits) for IPv4 and between 0 and 128 for IPv6",
        # and "The value MUST NOT be greater than 128". A longer one was accepted and then
        # published as 10.0.0.0/200, a prefix no IP-VRF can hold.
        maximum = IPV4_PREFIX_BITS if datalen == IPV4_ROUTE_SIZE else IPV6_PREFIX_BITS
        if packed[24] > maximum:
            raise Notify(
                3, 10, 'IP prefix length %d in %s is longer than the %d bits it holds' % (packed[24], cls.NAME, maximum)
            )

        return cls(packed)

    def json(self, announced: bool = True, compact: bool = False) -> str:
        """Serialise to JSON.

        The members are collected and joined rather than concatenated with their own
        separators: a member which renders empty, an EVPN route with no label stack being
        the one Hypothesis found, otherwise leaves a stray comma behind and the line is
        not JSON any more.
        """
        members = [
            '"code": %d' % self.CODE,
            '"parsed": true',
            '"raw": "{}"'.format(self._raw()),
            '"name": "{}"'.format(self.NAME),
        ]
        members.append(self.rd.json())
        members.append(self.esi.json())
        members.append(self.etag.json())
        members.append(self.label.json())
        members.append('"ip": "{}"'.format(str(self.ip)))
        members.append('"iplen": %d' % self.iplen)
        members.append('"gateway": "{}"'.format(str(self.gwip)))
        return '{{ {} }}'.format(', '.join(member for member in members if member))


EVPN.register_evpn_route(code=5)(Prefix)
