"""pmsi.py

Created by Thomas Morin on 2014-06-10.
Copyright (c) 2014-2017 Orange. All rights reserved.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack
from struct import unpack
from typing import TYPE_CHECKING, ClassVar, Dict, Optional, Type

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.protocol.ip import IPv4
from exabgp.bgp.message.update.attribute.attribute import Attribute

# https://tools.ietf.org/html/rfc6514#section-5
#
#  +---------------------------------+
#  |  Flags (1 octet)                |
#  +---------------------------------+
#  |  Tunnel Type (1 octets)         |
#  +---------------------------------+
#  |  MPLS Label (3 octets)          |
#  +---------------------------------+
#  |  Tunnel Identifier (variable)   |
#  +---------------------------------+


# ========================================================================= PMSI
# RFC 6514


@Attribute.register()
class PMSI(Attribute):
    ID = Attribute.CODE.PMSI_TUNNEL
    FLAG = Attribute.Flag.OPTIONAL | Attribute.Flag.TRANSITIVE
    CACHING = True
    TUNNEL_TYPE: ClassVar[int] = -1

    # TUNNEL_TYPE MUST NOT BE DEFINED HERE ( it allows to set it up as a self. value)

    _pmsi_known: ClassVar[Dict[int, Type[PMSI]]] = dict()
    _name: ClassVar[Dict[int, str]] = {
        0: 'No tunnel',
        1: 'RSVP-TE P2MP LSP',
        2: 'mLDP P2MP LSP',
        3: 'PIM-SSM Tree',
        4: 'PIM-SM Tree',
        5: 'BIDIR-PIM Tree',
        6: 'Ingress Replication',
        7: 'mLDP MP2MP LSP',
    }

    def __init__(self, tunnel: bytes, label: int, flags: int, raw_label: Optional[int] = None) -> None:
        self.label: int = label  # integer
        self.raw_label: Optional[int] = raw_label  # integer
        self.flags: int = flags  # integer
        self.tunnel: bytes = tunnel  # tunnel id, packed data

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PMSI):
            return False
        return (
            self.ID == other.ID
            and self.FLAG == other.FLAG
            and self.label == other.label
            and self.flags == other.flags
            and self.tunnel == other.tunnel
        )

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    @staticmethod
    def name(tunnel_type: int) -> str:
        return PMSI._name.get(tunnel_type, 'unknown')

    def pack(self, negotiated: Negotiated) -> bytes:
        if self.raw_label:
            packed_label = pack('!L', self.raw_label)[1:4]
        else:
            packed_label = pack('!L', self.label << 4)[1:4]
        return self._attribute(pack('!BB3s', self.flags, self.TUNNEL_TYPE, packed_label) + self.tunnel)

    # XXX: FIXME: Orange code had 4 (and another reference to it in the code elsewhere)
    def __len__(self) -> int:
        return len(self.tunnel) + 5  # label:1, tunnel type: 1, MPLS label:3

    def prettytunnel(self) -> str:
        return '0x' + ''.join('{:02X}'.format(_) for _ in self.tunnel) if self.tunnel else ''

    def __repr__(self) -> str:
        if self.raw_label:
            label_repr = '%d(%d)' % (self.label, self.raw_label)
        else:
            label_repr = str(self.label) if self.label else '0'
        return 'pmsi:{}:{}:{}:{}'.format(
            self.name(self.TUNNEL_TYPE).replace(' ', '').lower(),
            str(self.flags),
            label_repr,
            self.prettytunnel(),
        )

    @classmethod
    def register(cls, klass: Type[PMSI]) -> Type[PMSI]:
        if klass.TUNNEL_TYPE in cls._pmsi_known:
            raise RuntimeError('only one registration for PMSI')
        cls._pmsi_known[klass.TUNNEL_TYPE] = klass
        return klass

    @staticmethod
    def pmsi_unknown(subtype: int, tunnel: bytes, label: int, flags: int, raw_label: Optional[int]) -> PMSI:
        pmsi = PMSI(tunnel, label, flags)
        pmsi.TUNNEL_TYPE = subtype  # type: ignore[misc]
        return pmsi

    @classmethod
    def unpack(cls, data: bytes, direction: int, negotiated: Negotiated) -> PMSI:
        flags, subtype = unpack('!BB', data[:2])
        raw_label = unpack('!L', b'\0' + data[2:5])[0]
        label = raw_label >> 4
        # should we check for bottom of stack before the shift ?
        if subtype in cls._pmsi_known:
            return cls._pmsi_known[subtype].unpack(data[5:], label, flags, raw_label)  # type: ignore[call-arg]
        return cls.pmsi_unknown(subtype, data[5:], label, flags, raw_label)


# ================================================================= PMSINoTunnel
# RFC 6514


@PMSI.register
class PMSINoTunnel(PMSI):
    TUNNEL_TYPE: ClassVar[int] = 0

    def __init__(self, label: int = 0, flags: int = 0, raw_label: Optional[int] = None) -> None:
        PMSI.__init__(self, b'', label, flags, raw_label=None)

    def prettytunnel(self) -> str:
        return ''

    @classmethod
    def unpack(cls, tunnel: bytes, label: int, flags: int, raw_label: Optional[int] = None) -> PMSINoTunnel:
        return cls(label, flags, raw_label)


# ======================================================= PMSIIngressReplication
# RFC 6514


@PMSI.register
class PMSIIngressReplication(PMSI):
    TUNNEL_TYPE: ClassVar[int] = 6

    def __init__(
        self, ip: str, label: int = 0, flags: int = 0, tunnel: Optional[bytes] = None, raw_label: Optional[int] = None
    ) -> None:
        self.ip: str = ip  # looks like a bad name
        PMSI.__init__(self, tunnel if tunnel else IPv4.pton(ip), label, flags, raw_label)

    def prettytunnel(self) -> str:
        return self.ip

    @classmethod
    def unpack(cls, tunnel: bytes, label: int, flags: int, raw_label: Optional[int]) -> PMSIIngressReplication:
        ip = IPv4.ntop(tunnel)
        return cls(ip, label, flags, tunnel, raw_label)
