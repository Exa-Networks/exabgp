"""mac.py

Created by Thomas Morin on 2014-06-23.
Copyright (c) 2014-2017 Orange. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import ClassVar

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN
from exabgp.bgp.message.update.nlri.qualifier import ESI, EthernetTag, Labels, RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier import MAC as MACQUAL
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.protocol.ip import IP
from exabgp.util.types import Buffer

# EVPN MAC address and IP address length constants (in bits)
MAC_ADDRESS_LEN_BITS = 48  # Standard MAC address length in bits
IPV4_ADDRESS_LEN_BITS = 32  # IPv4 address length in bits
IPV6_ADDRESS_LEN_BITS = 128  # IPv6 address length in bits

# +---------------------------------------+
# |      RD   (8 octets)                  |
# +---------------------------------------+
# |Ethernet Segment Identifier (10 octets)|
# +---------------------------------------+
# |  Ethernet Tag ID (4 octets)           |
# +---------------------------------------+
# |  MAC Address Length (1 octet)         |
# +---------------------------------------+
# |  MAC Address (6 octets)               |  48 bits is 6 bytes
# +---------------------------------------+
# |  IP Address Length (1 octet)          |  zero if IP Address field absent
# +---------------------------------------+
# |  IP Address (4 or 16 octets)          |
# +---------------------------------------+
# |  MPLS Label (3 octets)                |
# +---------------------------------------+

# ===================================================================== EVPNNLRI


@EVPN.register_evpn_route
class MAC(EVPN):
    """EVPN Route Type 2: MAC/IP Advertisement.

    Wire format: type(1) + length(1) + RD(8) + ESI(10) + ETag(4) + MAClen(1) + MAC(6)
                 + IPlen(1) + IP(0/4/16) + Label(3+)
    Uses packed-bytes-first pattern for zero-copy routing.
    """

    CODE: ClassVar[int] = 2
    NAME: ClassVar[str] = 'MAC/IP advertisement'
    SHORT_NAME: ClassVar[str] = 'MACAdv'

    def __init__(self, packed: bytes) -> None:
        """Create MAC from complete wire-format bytes.

        Args:
            packed: Complete wire format (type + length + payload)
        """
        EVPN.__init__(self, packed)

    @classmethod
    def make_mac(
        cls,
        rd: RouteDistinguisher,
        esi: ESI,
        etag: EthernetTag,
        mac: MACQUAL,
        maclen: int,
        label: Labels | None,
        ip: IP | None,
        action: Action = Action.ANNOUNCE,
        addpath: PathInfo = PathInfo.DISABLED,
    ) -> 'MAC':
        """Factory method to create MAC from semantic parameters.

        Packs fields into wire format immediately (packed-bytes-first pattern).
        Note: nexthop is not part of NLRI - set separately after creation.
        """
        label_to_use = label if label else Labels.NOLABEL
        # fmt: off
        payload = (
            bytes(rd.pack_rd())
            + esi.pack_esi()
            + etag.pack_etag()
            + bytes([maclen])
            + mac.pack_mac()
            + bytes([len(ip) * 8 if ip else 0])
            + (bytes(ip.pack_ip()) + label_to_use.pack_labels() if ip else label_to_use.pack_labels())
        )
        # fmt: on
        # Include type + length header for zero-copy pack
        packed = bytes([cls.CODE, len(payload)]) + payload
        instance = cls(packed)
        instance.action = action
        instance.addpath = addpath
        return instance

    # Wire format offsets (after 2-byte type+length header):
    # RD: 2-10, ESI: 10-20, ETag: 20-24, MAClen: 24, MAC: 25-31, IPlen: 31, IP: 32+, Label: after IP

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
    def maclen(self) -> int:
        """MAC address length in bits - unpacked from wire bytes."""
        return self._packed[24]

    @property
    def mac(self) -> MACQUAL:
        """MAC address - unpacked from wire bytes."""
        return MACQUAL.unpack_mac(self._packed[25:31])

    @property
    def ip(self) -> IP | None:
        """IP address - unpacked from wire bytes (None if not present)."""
        iplen_bits = self._packed[31]
        if iplen_bits == 0:
            return None
        iplen_bytes = iplen_bits // 8
        return IP.unpack_ip(self._packed[32 : 32 + iplen_bytes])

    @property
    def label(self) -> Labels:
        """MPLS Labels - unpacked from wire bytes."""
        iplen_bits = self._packed[31]
        iplen_bytes = iplen_bits // 8 if iplen_bits else 0
        label_start = 32 + iplen_bytes
        return Labels.unpack_labels(self._packed[label_start : label_start + 3])

    def index(self) -> Buffer:
        # Note: Per RFC 7432 Section 7.2, the route key for Type 2 should only include
        # etag, mac, and ip (ESI and labels are attributes, not key). However, this
        # implementation uses full packed bytes for index. The __eq__ method correctly
        # excludes ESI and label for semantic equality comparisons.
        return EVPN.index(self)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, MAC)
            and self.CODE == other.CODE
            and self.rd == other.rd
            and self.etag == other.etag
            and self.mac == other.mac
            and self.ip == other.ip
        )
        # esi and label must not be part of the comparaison

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __str__(self) -> str:
        return '{}:{}:{}:{}:{}{}:{}:{}'.format(
            self._prefix(),
            self.rd._str(),
            self.esi,
            self.etag,
            self.mac,
            '' if len(self.mac) == MAC_ADDRESS_LEN_BITS else '/%d' % self.maclen,
            self.ip if self.ip else '',
            self.label,
        )

    def __hash__(self) -> int:
        # esi and label MUST *NOT* be part of the hash
        return hash((self.rd, self.etag, self.mac, self.ip))

    @classmethod
    def unpack_evpn(cls, packed: bytes) -> EVPN:
        """Unpack MAC from complete wire format bytes.

        Args:
            packed: Complete wire format (type + length + payload)

        Returns:
            MAC instance with stored wire bytes
        """
        # Validate the data before creating the instance
        # Offsets include 2-byte header: MAClen at 24, IPlen at 31
        datalen = len(packed)
        maclength = packed[24]

        if maclength > MAC_ADDRESS_LEN_BITS or maclength < 0:
            raise Notify(3, 5, 'invalid MAC Address length in {}'.format(cls.NAME))

        iplen_byte = 31  # After MAC address (2+8+10+4+1+6 = 31)
        iplen_bits = packed[iplen_byte]
        iplen = iplen_bits / 8

        # Total lengths include 2-byte header, so add 2 to previous payload lengths
        if datalen in [35, 38]:  # No IP information (1 or 2 labels): 33+2, 36+2
            if iplen != 0:
                raise Notify(3, 5, 'IP length is given as %d, but current MAC route has no IP information' % iplen)
        elif datalen in [39, 42]:  # Using IPv4 addresses (1 or 2 labels): 37+2, 40+2
            if iplen > IPV4_ADDRESS_LEN_BITS or iplen < 0:
                raise Notify(
                    3,
                    5,
                    'IP field length is given as %d, but current MAC route is IPv4 and valus is out of range' % iplen,
                )
        elif datalen in [51, 54]:  # Using IPv6 addresses (1 or 2 labels): 49+2, 52+2
            if iplen > IPV6_ADDRESS_LEN_BITS or iplen < 0:
                raise Notify(
                    3,
                    5,
                    'IP field length is given as %d, but current MAC route is IPv6 and valus is out of range' % iplen,
                )
        else:
            raise Notify(
                3,
                5,
                'Data field length is given as %d, but does not match one of the expected lengths' % datalen,
            )

        return cls(packed)

    def json(self, compact: bool | None = None) -> str:
        content = ' "code": %d, ' % self.CODE
        content += '"parsed": true, '
        content += '"raw": "{}", '.format(self._raw())
        content += '"name": "{}", '.format(self.NAME)
        content += '{}, '.format(self.rd.json())
        content += '{}, '.format(self.esi.json())
        content += '{}, '.format(self.etag.json())
        content += '{}, '.format(self.mac.json())
        content += self.label.json()
        if self.ip:
            content += ', "ip": "{}"'.format(str(self.ip))
        return '{{{} }}'.format(content)
