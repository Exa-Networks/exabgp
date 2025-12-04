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

from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.protocol.ip import IP
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier import Labels
from exabgp.bgp.message.update.nlri.qualifier import ESI
from exabgp.bgp.message.update.nlri.qualifier import EthernetTag

from exabgp.bgp.message.update.nlri import NLRI
from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN
from exabgp.bgp.message import Action

from exabgp.bgp.message.notification import Notify


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


@EVPN.register
class Prefix(EVPN):
    CODE: ClassVar[int] = 5
    NAME: ClassVar[str] = 'IP Prefix Advertisement'
    SHORT_NAME: ClassVar[str] = 'PrfxAdv'

    def __init__(
        self,
        packed: bytes,
        nexthop: IP = IP.NoNextHop,
        action: Action | None = None,
        addpath: PathInfo | None = None,
    ) -> None:
        EVPN.__init__(self, action, addpath)  # type: ignore[arg-type]
        self._packed = packed
        self.nexthop = nexthop

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
        nexthop: IP = IP.NoNextHop,
        action: Action | None = None,
        addpath: PathInfo | None = None,
    ) -> 'Prefix':
        """Factory method to create Prefix from semantic parameters.

        rd: a RouteDistinguisher
        esi: an EthernetSegmentIdentifier
        etag: an EthernetTag
        label: a LabelStackEntry
        ip: an IP address (dotted quad string notation)
        iplen: prefixlength for ip (defaults to 32)
        gwip: an IP address (dotted quad string notation)
        """
        label_to_use = label if label else Labels.NOLABEL
        packed = (
            rd.pack_rd()
            + esi.pack_esi()
            + etag.pack_etag()
            + bytes([iplen])
            + ip.pack_ip()
            + gwip.pack_ip()
            + label_to_use.pack_labels()
        )
        return cls(packed, nexthop, action, addpath)

    @property
    def rd(self) -> RouteDistinguisher:
        return RouteDistinguisher.unpack_routedistinguisher(self._packed[:8])

    @property
    def esi(self) -> ESI:
        return ESI.unpack_esi(self._packed[8:18])

    @property
    def etag(self) -> EthernetTag:
        return EthernetTag.unpack_etag(self._packed[18:22])

    @property
    def iplen(self) -> int:
        return self._packed[22]

    @property
    def ip(self) -> IP:
        # IP address is either 4 or 16 bytes based on total length
        datalen = len(self._packed)
        if datalen == 34:  # IPv4: 8+10+4+1+4+4+3
            return IP.unpack_ip(self._packed[23:27])
        else:  # IPv6: 8+10+4+1+16+16+3 = 58
            return IP.unpack_ip(self._packed[23:39])

    @property
    def gwip(self) -> IP:
        datalen = len(self._packed)
        if datalen == 34:  # IPv4
            return IP.unpack_ip(self._packed[27:31])
        else:  # IPv6
            return IP.unpack_ip(self._packed[39:55])

    @property
    def label(self) -> Labels:
        datalen = len(self._packed)
        if datalen == 34:  # IPv4
            return Labels.unpack_labels(self._packed[31:34])
        else:  # IPv6
            return Labels.unpack_labels(self._packed[55:58])

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Prefix):
            return False
        return (
            NLRI.__eq__(self, other)
            and self.CODE == other.CODE
            and self.rd == other.rd
            and self.etag == other.etag
            and self.ip == other.ip
            and self.iplen == other.iplen
        )
        # esi, label and gwip must not be compared

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

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

    def __hash__(self) -> int:
        # esi, and label, gwip must *not* be part of the hash
        return hash('{}:{}:{}:{}'.format(self.rd, self.etag, self.ip, self.iplen))

    @classmethod
    def unpack_evpn_route(cls, exdata: bytes) -> Prefix:
        # Get the data length to understand if addresses are IPv4 or IPv6
        datalen = len(exdata)

        if datalen not in (34, 58):  # 34 for IPv4, 58 for IPv6
            raise Notify(
                3,
                5,
                'Data field length is given as %d, but EVPN route currently support only IPv4 or IPv6(34 or 58)'
                % datalen,
            )

        return cls(exdata)

    def json(self, compact: bool = False) -> str:
        content = ' "code": %d, ' % self.CODE
        content += '"parsed": true, '
        content += '"raw": "{}", '.format(self._raw())
        content += '"name": "{}", '.format(self.NAME)
        content += '{}, '.format(self.rd.json())
        content += '{}, '.format(self.esi.json())
        content += '{}, '.format(self.etag.json())
        content += '{}, '.format(self.label.json())
        content += '"ip": "{}", '.format(str(self.ip))
        content += '"iplen": %d, ' % self.iplen
        content += '"gateway": "{}" '.format(str(self.gwip))
        return '{{{}}}'.format(content)
