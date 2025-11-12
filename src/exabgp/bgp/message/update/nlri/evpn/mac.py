"""mac.py

Created by Thomas Morin on 2014-06-23.
Copyright (c) 2014-2017 Orange. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any, ClassVar, Optional

from exabgp.protocol.ip import IP
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier import Labels
from exabgp.bgp.message.update.nlri.qualifier import ESI
from exabgp.bgp.message.update.nlri.qualifier import EthernetTag
from exabgp.bgp.message.update.nlri.qualifier import MAC as MACQUAL

from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN
from exabgp.bgp.message import Action

from exabgp.bgp.message.notification import Notify

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


@EVPN.register
class MAC(EVPN):
    CODE: ClassVar[int] = 2
    NAME: ClassVar[str] = 'MAC/IP advertisement'
    SHORT_NAME: ClassVar[str] = 'MACAdv'

    def __init__(
        self,
        rd: RouteDistinguisher,
        esi: ESI,
        etag: EthernetTag,
        mac: MACQUAL,
        maclen: int,
        label: Optional[Labels],
        ip: Optional[IP],
        packed: Optional[bytes] = None,
        nexthop: Any = None,
        action: Optional[Action] = None,
        addpath: Any = None,
    ) -> None:
        EVPN.__init__(self, action, addpath)
        self.nexthop = nexthop
        self.rd = rd
        self.esi = esi
        self.etag = etag
        self.maclen = maclen
        self.mac = mac
        self.ip = ip
        self.label = label if label else Labels.NOLABEL
        self._pack(packed)

    # XXX: we have to ignore a part of the route
    def index(self) -> str:
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

    def _pack(self, packed: Optional[bytes] = None) -> bytes:
        if self._packed:
            return self._packed

        if packed:
            self._packed = packed
            return packed

        # maclen: only 48 supported by the draft
        # fmt: off
        self._packed = (
            self.rd.pack()
            + self.esi.pack()
            + self.etag.pack()
            + bytes([self.maclen])
            + self.mac.pack()
            + bytes([len(self.ip) * 8 if self.ip else 0])
            + (self.ip.pack() + self.label.pack() if self.ip else self.label.pack())
        )
        # fmt: on
        return self._packed

    @classmethod
    def unpack(cls, data: bytes) -> MAC:
        datalen = len(data)
        rd = RouteDistinguisher.unpack(data[:8])
        esi = ESI.unpack(data[8:18])
        etag = EthernetTag.unpack(data[18:22])
        maclength = data[22]

        if maclength > MAC_ADDRESS_LEN_BITS or maclength < 0:
            raise Notify(3, 5, 'invalid MAC Address length in {}'.format(cls.NAME))
        end = 23 + 6  # MAC length MUST be 6

        mac = MACQUAL.unpack(data[23:end])

        length = data[end]
        iplen = length / 8

        if datalen in [33, 36]:  # No IP information (1 or 2 labels)
            iplenUnpack = 0
            if iplen != 0:
                raise Notify(3, 5, 'IP length is given as %d, but current MAC route has no IP information' % iplen)
        elif datalen in [37, 40]:  # Using IPv4 addresses (1 or 2 labels)
            iplenUnpack = 4
            if iplen > IPV4_ADDRESS_LEN_BITS or iplen < 0:
                raise Notify(
                    3,
                    5,
                    'IP field length is given as %d, but current MAC route is IPv4 and valus is out of range' % iplen,
                )
        elif datalen in [49, 52]:  # Using IPv6 addresses (1 or 2 labels)
            iplenUnpack = 16
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

        payload = data[end + 1 : end + 1 + iplenUnpack]
        if payload:
            ip = IP.unpack(data[end + 1 : end + 1 + iplenUnpack])
        else:
            ip = None
        label = Labels.unpack(data[end + 1 + iplenUnpack : end + 1 + iplenUnpack + 3])

        return cls(rd, esi, etag, mac, maclength, label, ip, data)

    def json(self, compact: Optional[bool] = None) -> str:
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
