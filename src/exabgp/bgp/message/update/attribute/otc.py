"""Only to Customer path attribute and route-generation instructions (RFC 9234)."""

from __future__ import annotations

from struct import pack, unpack
from typing import TYPE_CHECKING

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.role import RoleValue
from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated


@Attribute.register()
class OTC(Attribute):
    """A four-octet ASN, regardless of negotiated AS_PATH encoding."""

    ID = Attribute.CODE.OTC
    FLAG = Attribute.Flag.OPTIONAL | Attribute.Flag.TRANSITIVE
    CACHING = True
    TREAT_AS_WITHDRAW = True

    def __init__(self, packed: Buffer) -> None:
        """Store trusted wire bytes; use the factories at input boundaries."""
        self._packed = bytes(packed)

    @classmethod
    def from_packet(cls, data: Buffer) -> OTC:
        if len(data) != ASN.SIZE_4BYTE:
            raise Notify(3, 5, f'OTC requires exactly four bytes, got {len(data)}')
        return cls(data)

    @classmethod
    def make_otc(cls, asn: int) -> OTC:
        if not 0 <= asn <= ASN.MAX_4BYTE:
            raise ValueError(f'OTC ASN out of range: {asn}')
        return cls(pack('!L', asn))

    @property
    def asn(self) -> ASN:
        return ASN(unpack('!L', self._packed)[0])

    def pack_attribute(self, negotiated: Negotiated | None = None) -> bytes:
        return self._attribute(self._packed)

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated) -> OTC:
        return cls.from_packet(data)

    def __len__(self) -> int:
        return len(self._packed)

    def __repr__(self) -> str:
        return str(self.asn)

    def json(self) -> str:
        return str(self.asn)

    def __hash__(self) -> int:
        return hash(self._comparable())


class OTCSelf(Attribute):
    """Resolve the local ASN only when serializing for an established session."""

    ID = Attribute.CODE.OTC
    FLAG = OTC.FLAG

    def __init__(self, role: RoleValue = RoleValue.NO_ROLE) -> None:
        self.role = role

    def pack_attribute(self, negotiated: Negotiated) -> bytes:
        if not negotiated.local_as:
            raise ValueError('OTC self requires a resolved local ASN')
        return OTC.make_otc(negotiated.local_as).pack_attribute(negotiated)

    def _comparable(self) -> tuple[int, int, object]:
        return (self.ID, self.FLAG, ('self', self.role))

    def __repr__(self) -> str:
        return 'self' if self.role == RoleValue.NO_ROLE else str(self.role)

    def json(self) -> str:
        return f'"{self}"'

    def __hash__(self) -> int:
        return hash(self._comparable())


class OTCNone(Attribute):
    """Internal instruction suppressing automatic OTC insertion for this route."""

    ID = Attribute.CODE.INTERNAL_OTC_NONE
    NO_GENERATION = True

    def pack_attribute(self, negotiated: Negotiated) -> bytes:
        return b''

    def _comparable(self) -> tuple[int, int, object]:
        return (self.ID, self.FLAG, None)

    def __repr__(self) -> str:
        return ''

    def json(self) -> str:
        return ''

    def __hash__(self) -> int:
        return hash(self._comparable())
