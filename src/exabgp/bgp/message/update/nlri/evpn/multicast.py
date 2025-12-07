"""multicast.py

Created by Thomas Morin on 2014-06-23.
Copyright (c) 2014-2017 Orange. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import ClassVar

from exabgp.bgp.message import Action
from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN
from exabgp.bgp.message.update.nlri.qualifier import EthernetTag, RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.protocol.ip import IP

# +---------------------------------------+
# |      RD   (8 octets)                  |
# +---------------------------------------+
# |  Ethernet Tag ID (4 octets)           |
# +---------------------------------------+
# |  IP Address Length (1 octet)          |
# +---------------------------------------+
# |   Originating Router's IP Addr        |
# |          (4 or 16 octets)             |
# +---------------------------------------+

# ===================================================================== EVPNNLRI


@EVPN.register_evpn_route
class Multicast(EVPN):
    """EVPN Route Type 3: Inclusive Multicast Ethernet Tag.

    Wire format: type(1) + length(1) + RD(8) + ETag(4) + IPlen(1) + IP(4/16)
    Uses packed-bytes-first pattern for zero-copy routing.
    """

    CODE: ClassVar[int] = 3
    NAME: ClassVar[str] = 'Inclusive Multicast Ethernet Tag'
    SHORT_NAME: ClassVar[str] = 'Multicast'

    def __init__(self, packed: bytes) -> None:
        """Create Multicast from complete wire-format bytes.

        Args:
            packed: Complete wire format (type + length + payload)
        """
        EVPN.__init__(self, packed)

    @classmethod
    def make_multicast(
        cls,
        rd: RouteDistinguisher,
        etag: EthernetTag,
        ip: IP,
        action: Action = Action.UNSET,
        addpath: PathInfo = PathInfo.DISABLED,
    ) -> 'Multicast':
        """Factory method to create Multicast from semantic parameters.

        Packs fields into wire format immediately (packed-bytes-first pattern).
        Note: nexthop is not part of NLRI - set separately after creation.
        """
        payload = bytes(rd.pack_rd()) + etag.pack_etag() + bytes([len(ip) * 8]) + ip.pack_ip()
        # Include type + length header for zero-copy pack
        packed = bytes([cls.CODE, len(payload)]) + payload
        instance = cls(packed)
        instance.action = action
        instance.addpath = addpath
        return instance

    # Wire format offsets (after 2-byte type+length header):
    # RD: 2-10, ETag: 10-14, IPlen: 14, IP: 15+

    @property
    def rd(self) -> RouteDistinguisher:
        """Route Distinguisher - unpacked from wire bytes."""
        return RouteDistinguisher.unpack_routedistinguisher(self._packed[2:10])

    @property
    def etag(self) -> EthernetTag:
        """Ethernet Tag - unpacked from wire bytes."""
        return EthernetTag.unpack_etag(self._packed[10:14])

    @property
    def ip(self) -> IP:
        """Originating Router IP - unpacked from wire bytes."""
        iplen = self._packed[14]
        return IP.unpack_ip(self._packed[15 : 15 + iplen // 8])

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __str__(self) -> str:
        return '{}:{}:{}:{}'.format(
            self._prefix(),
            self.rd._str(),
            self.etag,
            self.ip,
        )

    def __hash__(self) -> int:
        return hash((self.afi, self.safi, self.CODE, self.rd, self.etag, self.ip))

    @classmethod
    def unpack_evpn(cls, packed: bytes) -> EVPN:
        """Unpack Multicast from complete wire format bytes.

        Args:
            packed: Complete wire format (type + length + payload)

        Returns:
            Multicast instance with stored wire bytes
        """
        # IPlen is at offset 14 (after 2-byte header + 8-byte RD + 4-byte ETag)
        iplen = packed[14]
        if iplen not in (4 * 8, 16 * 8):
            raise Exception('IP len is %d, but EVPN route currently support only IPv4 or IPv6' % iplen)
        return cls(packed)

    def json(self, compact: bool | None = None) -> str:
        content = ' "code": %d, ' % self.CODE
        content += '"parsed": true, '
        content += '"raw": "{}", '.format(self._raw())
        content += '"name": "{}", '.format(self.NAME)
        content += '{}, '.format(self.rd.json())
        content += self.etag.json()
        if self.ip:
            content += ', "ip": "{}"'.format(str(self.ip))
        return '{{{} }}'.format(content)
