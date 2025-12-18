"""aggregator.py

Created by Thomas Mangin on 2012-07-14.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.util.types import Buffer
from struct import unpack
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.open.asn import AS_TRANS, ASN
from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.protocol.ip import IPv4

# =============================================================== AGGREGATOR (7)
#


@Attribute.register()
class Aggregator(Attribute):
    """Aggregator attribute (code 7).

    Stores packed wire-format bytes. The wire format can be either 2-byte or 4-byte
    ASNs depending on the negotiated capability. The _asn4 flag tracks which format
    is stored.

    Wire format:
    - 2-byte ASN: 2 bytes ASN + 4 bytes IPv4 = 6 bytes
    - 4-byte ASN: 4 bytes ASN + 4 bytes IPv4 = 8 bytes
    """

    ID = Attribute.CODE.AGGREGATOR
    FLAG = Attribute.Flag.TRANSITIVE | Attribute.Flag.OPTIONAL
    CACHING = True
    DISCARD = True

    def __init__(self, packed: Buffer, asn4: bool = True) -> None:
        """Initialize from packed wire-format bytes.

        NO validation - trusted internal use only.
        Use from_packet() for wire data or make_aggregator() for semantic construction.

        Args:
            packed: Raw attribute value bytes (6 or 8 bytes depending on ASN size)
            asn4: True if packed uses 4-byte ASN, False for 2-byte
        """
        self._packed: Buffer = packed
        self._asn4: bool = asn4

    @classmethod
    def from_packet(cls, data: Buffer, asn4: bool) -> 'Aggregator':
        """Validate and create from wire-format bytes.

        Args:
            data: Raw attribute value bytes from wire
            asn4: True if data uses 4-byte ASN, False for 2-byte

        Returns:
            Aggregator instance

        Raises:
            ValueError: If data length is invalid
        """
        expected_len = 8 if asn4 else 6
        if len(data) != expected_len:
            raise ValueError(f'Aggregator must be {expected_len} bytes for asn4={asn4}, got {len(data)}')
        return cls(data, asn4)

    @classmethod
    def make_aggregator(cls, asn: ASN, speaker: IPv4) -> 'Aggregator':
        """Create from ASN and speaker address.

        Always stores in 4-byte ASN format internally. Conversion to 2-byte
        format happens at pack time based on negotiated capability.

        Args:
            asn: Aggregator ASN
            speaker: Aggregator router ID (IPv4)

        Returns:
            Aggregator instance
        """
        # Always store in 4-byte format internally
        packed = asn.pack_asn4() + speaker.pack_ip()
        return cls(packed, asn4=True)

    @property
    def asn(self) -> ASN:
        """Get the ASN by unpacking from bytes."""
        if self._asn4:
            return ASN(unpack('!L', self._packed[:4])[0])
        else:
            return ASN(unpack('!H', self._packed[:2])[0])

    @property
    def speaker(self) -> IPv4:
        """Get the speaker address by unpacking from bytes."""
        return IPv4.unpack_ipv4(self._packed[-4:])

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Aggregator):
            return False
        # Compare semantic values, not packed bytes (different formats may represent same value)
        return (
            self.ID == other.ID and self.FLAG == other.FLAG and self.asn == other.asn and self.speaker == other.speaker
        )

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __len__(self) -> int:
        return len(self._packed)

    def __repr__(self) -> str:
        return f'{self.asn}:{self.speaker}'

    def json(self) -> str:
        return '{ "asn" : %d, "speaker" : "%s" }' % (self.asn, self.speaker)

    def pack_attribute(self, negotiated: Negotiated) -> bytes:
        """Pack for sending to peer.

        Handles format conversion based on negotiated capability:
        - If peer supports ASN4: send with 4-byte ASN
        - If peer doesn't support ASN4 AND ASN fits in 2 bytes: send with 2-byte ASN
        - If peer doesn't support ASN4 AND ASN doesn't fit: use AS_TRANS + add AS4_AGGREGATOR
        """
        asn = self.asn
        speaker_packed = self._packed[-4:]  # IPv4 is always last 4 bytes

        if negotiated.asn4:
            # Peer supports ASN4, send with 4-byte format
            if self._asn4:
                return self._attribute(self._packed)
            else:
                # Convert from 2-byte to 4-byte format
                return self._attribute(asn.pack_asn4() + speaker_packed)

        # Peer doesn't support ASN4
        if not asn.asn4():
            # ASN fits in 2 bytes
            return self._attribute(asn.pack_asn2() + speaker_packed)
        else:
            # ASN doesn't fit, use AS_TRANS and add AS4_AGGREGATOR
            return self._attribute(AS_TRANS.pack_asn2() + speaker_packed) + Aggregator4.make_aggregator(
                asn, self.speaker
            ).pack_attribute(negotiated)

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated) -> 'Aggregator':
        return cls.from_packet(data, negotiated.asn4)


# ============================================================== AGGREGATOR (18)
#


@Attribute.register()
class Aggregator4(Aggregator):
    """AS4_AGGREGATOR attribute (code 18). Always uses 4-byte ASNs."""

    ID = Attribute.CODE.AS4_AGGREGATOR

    def __init__(self, packed: Buffer, asn4: bool = True) -> None:
        """Initialize from packed wire-format bytes.

        AS4_AGGREGATOR always uses 4-byte ASNs, so asn4 parameter is ignored.
        """
        super().__init__(packed, asn4=True)

    @classmethod
    def from_packet(cls, data: Buffer, asn4: bool = True) -> 'Aggregator4':
        """Validate and create from wire-format bytes.

        AS4_AGGREGATOR always uses 4-byte ASNs.
        """
        if len(data) != 8:
            raise ValueError(f'AS4_AGGREGATOR must be 8 bytes, got {len(data)}')
        return cls(data)

    @classmethod
    def make_aggregator(cls, asn: ASN, speaker: IPv4) -> 'Aggregator4':
        """Create from ASN and speaker address."""
        packed = asn.pack_asn4() + speaker.pack_ip()
        return cls(packed)

    def pack_attribute(self, negotiated: Negotiated) -> bytes:
        """Pack AS4_AGGREGATOR. Always uses 4-byte format."""
        return self._attribute(self._packed)

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated) -> 'Aggregator4':
        return cls.from_packet(data)
