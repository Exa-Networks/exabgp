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
from exabgp.bgp.message.update.attribute import Attribute, AttributeCollection
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
    # the same marker with a one octet attribute length (flag 0x80), as most peers send it:
    # the two length fields, the attribute header of three octets, then the AFI and SAFI
    LENGTHS_SIZE: ClassVar[int] = 4
    FAMILY_SIZE: ClassVar[int] = 3
    MP_SHORT_SIZE: ClassVar[int] = LENGTHS_SIZE + 3 + FAMILY_SIZE
    # Optional, Transitive and Extended Length: the low four bits are unused and ignored
    # (RFC 4271 4.3), and so is the Partial bit of an optional non-transitive attribute
    # (RFC 7606 3(c)), which the decoder ignores too, so the marker must not depend on it.
    FLAG_KIND_MASK: ClassVar[int] = 0xD0

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
    def from_body(cls, data: Buffer) -> 'EOR | None':
        """The End-of-RIB this UPDATE body is, read from the wire alone, or None.

        RFC 4724 2 defines the marker by what the peer sent, so it is never decided from
        what a decode kept: an UPDATE whose only attribute was discarded, or whose only
        withdrawal was refused, is empty once decoded and is still not a marker. The
        MP_UNREACH_NLRI form may come with a one or a two octet attribute length, and is
        kept as received only in the second, the one make_eor builds.
        """
        if cls.is_eor_body(data):
            return cls(data)
        family = cls._mp_unreach_family(data)
        if family is None:
            return None
        return cls.make_eor(*family)

    @classmethod
    def _mp_unreach_family(cls, data: Buffer) -> tuple[AFI, SAFI] | None:
        """The family of a body holding only an MP_UNREACH_NLRI with only an AFI and SAFI."""
        if len(data) not in (cls.MP_SHORT_SIZE, cls.MP_SIZE) or bytes(data[:2]) != b'\x00\x00':
            return None
        flag, code = data[4], data[5]
        # optional and not transitive, whatever the Partial bit: an O/T conflict is malformed
        # (RFC 7606 3(c)), so it is for the decoder to refuse, never an End-of-RIB
        kinds = (Attribute.Flag.OPTIONAL, Attribute.Flag.OPTIONAL | Attribute.Flag.EXTENDED_LENGTH)
        if code != Attribute.CODE.MP_UNREACH_NLRI or flag & cls.FLAG_KIND_MASK not in kinds:
            return None
        extended = bool(flag & Attribute.Flag.EXTENDED_LENGTH)
        expected = cls.MP_SIZE if extended else cls.MP_SHORT_SIZE
        if len(data) != expected or int.from_bytes(data[2:4], 'big') != expected - cls.LENGTHS_SIZE:
            return None
        length = int.from_bytes(data[6:8], 'big') if extended else data[6]
        if length != cls.FAMILY_SIZE:
            return None
        # the length checks above leave exactly the AFI and the SAFI at the end
        return AFI.unpack_afi(data[expected - 3 : expected - 1]), SAFI.unpack_safi(data[expected - 1 : expected])

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
