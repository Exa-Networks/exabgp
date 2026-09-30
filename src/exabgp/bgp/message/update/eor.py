"""eor.py

Created by Thomas Mangin on 2010-01-16.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated
    from exabgp.bgp.message.update.collection import UpdateCollection

from exabgp.bgp.message.update.update import Update
from exabgp.bgp.message.update.attribute import AttributeCollection
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP

# =================================================================== End-Of-RIB
# RFC 4724 2: an UPDATE, the one a speaker sends once it has sent its whole RIB for a family


class EORNLRI(NLRI):
    """What the encoders show for an End-of-RIB: the family, and nothing else."""

    IS_EOR: ClassVar[bool] = True  # Override class variable

    nexthop: ClassVar = IP.NoNextHop

    def __init__(self, afi: AFI, safi: SAFI) -> None:
        NLRI.__init__(self, afi, safi)

    def pack_nlri(self, negotiated: 'Negotiated') -> Buffer:
        return EOR.make_eor(self.afi, self.safi).payload

    def __repr__(self) -> str:
        return self.extensive()

    def extensive(self) -> str:
        return 'eor %ld/%ld (%s %s)' % (int(self.afi), int(self.safi), self.afi, self.safi)

    def json(self, announced: bool = True, compact: bool = False) -> str:
        # every other NLRI renders an object because the caller puts the result
        # in a list, so a bare key and value here made the whole line unparseable
        return '{{ "eor": {{ "afi" : "{}", "safi" : "{}" }} }}'.format(self.afi, self.safi)

    def __len__(self) -> int:
        if self.afi == AFI.ipv4 and self.safi == SAFI.unicast:
            # May not have been the size read on the wire if MP was used for IPv4 unicast
            return len(EOR.IPV4_UNICAST)
        return EOR.MP_SIZE


class EOR(Update):
    """An End-of-RIB marker: an UPDATE, stored as its body like any other.

    For IPv4 unicast the body is an UPDATE with nothing in it.  For any other family it
    carries one attribute, an MP_UNREACH_NLRI naming the family and withdrawing nothing.
    """

    IS_EOR: ClassVar[bool] = True

    # RFC 4724 2: no withdrawn routes, no attributes, no NLRI
    IPV4_UNICAST: ClassVar[bytes] = b'\x00\x00\x00\x00'
    # no withdrawn routes, 7 octets of attributes: optional + extended length (0x90),
    # MP_UNREACH_NLRI (15), a length of 3, then the AFI and SAFI of the family
    MP_PREFIX: ClassVar[bytes] = b'\x00\x00\x00\x07\x90\x0f\x00\x03'
    MP_SIZE: ClassVar[int] = len(MP_PREFIX) + 3

    EOR_NLRI: ClassVar[type[EORNLRI]] = EORNLRI

    def __init__(self, packed: Buffer) -> None:
        # what make_eor built, or what Update.unpack_message recognised: never unchecked bytes
        if not self.is_eor_body(packed):
            raise ValueError('an End-of-RIB body is one of the two RFC 4724 forms')
        Update.__init__(self, packed)

    @classmethod
    def is_eor_body(cls, data: Buffer) -> bool:
        """Whether this UPDATE body is an End-of-RIB in one of the two forms RFC 4724 gives."""
        if len(data) == len(cls.IPV4_UNICAST):
            return bytes(data) == cls.IPV4_UNICAST
        return len(data) == cls.MP_SIZE and bytes(data[: len(cls.MP_PREFIX)]) == cls.MP_PREFIX

    @classmethod
    def make_eor(cls, afi: AFI, safi: SAFI) -> 'EOR':
        if afi == AFI.ipv4 and safi == SAFI.unicast:
            return cls(cls.IPV4_UNICAST)
        return cls(cls.MP_PREFIX + afi.pack_afi() + safi.pack_safi())

    @property
    def afi(self) -> AFI:
        if len(self._packed) == len(self.IPV4_UNICAST):
            return AFI.ipv4
        offset = len(self.MP_PREFIX)
        return AFI.unpack_afi(self._packed[offset : offset + 2])

    @property
    def safi(self) -> SAFI:
        if len(self._packed) == len(self.IPV4_UNICAST):
            return SAFI.unicast
        offset = len(self.MP_PREFIX) + 2
        return SAFI.unpack_safi(self._packed[offset : offset + 1])

    @property
    def nlris(self) -> list[NLRI]:
        return [EOR.EOR_NLRI(self.afi, self.safi)]

    @property
    def attributes(self) -> AttributeCollection:
        return AttributeCollection()

    @property
    def data(self) -> 'UpdateCollection':
        from exabgp.bgp.message.update.collection import UpdateCollection

        return UpdateCollection.make_eor(self.afi, self.safi)

    def parse(self, negotiated: 'Negotiated | None' = None) -> 'UpdateCollection':
        return self.data

    def __str__(self) -> str:
        return f'EOR {self.afi} {self.safi}'

    def __repr__(self) -> str:
        return 'EOR'
