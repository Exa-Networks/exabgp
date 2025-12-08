"""update/__init__.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import unpack
from typing import TYPE_CHECKING

from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.message import Message
from exabgp.bgp.message.update.attribute import MPRNLRI, MPURNLRI, AttributeCollection
from exabgp.bgp.message.update.collection import (
    EOR_IPV4_UNICAST_LENGTH,
    EOR_WITH_PREFIX_LENGTH,
    UpdateCollection,
)
from exabgp.bgp.message.update.eor import EOR
from exabgp.bgp.message.update.nlri import MPNLRICollection, NLRICollection
from exabgp.logger import lazyformat, log
from exabgp.protocol.family import AFI, SAFI

__all__ = [
    'Update',
    'UpdateCollection',
    'UpdateWire',
    'EOR',
    'NLRICollection',
    'MPNLRICollection',
]


# ======================================================================= Update (Wire)
#
# Wire-format BGP UPDATE message container (bytes-first pattern).
# This class stores the raw payload bytes as the canonical representation.
# Parsing to semantic objects (UpdateCollection) is lazy.


@Message.register
class Update(Message):
    """Wire-format BGP UPDATE message container (bytes-first).

    Stores raw UPDATE message payload as the canonical representation.
    Provides lazy parsing to semantic UpdateCollection when needed.

    This follows the "packed-bytes-first" pattern used by individual
    Attribute classes - the wire format is stored directly, and semantic
    values are derived via properties.

    This is the registered BGP UPDATE message handler.
    """

    ID = Message.CODE.UPDATE
    TYPE = bytes([Message.CODE.UPDATE])
    EOR: bool = False  # Not an End-of-RIB marker

    def __init__(self, packed: Buffer, negotiated: 'Negotiated | None' = None) -> None:
        """Create Update from raw payload bytes.

        Args:
            packed: The UPDATE message payload (after BGP header).
                    Format: withdrawn_len(2) + withdrawn + attr_len(2) + attributes + nlri
                    Can be bytes or memoryview (converted to bytes for storage).
            negotiated: Optional BGP session negotiated parameters for parsing context.
        """
        self._packed = packed
        self._negotiated = negotiated
        self._parsed: 'UpdateCollection | None' = None

    @property
    def payload(self) -> Buffer:
        """Raw UPDATE payload bytes."""
        return self._packed

    @property
    def withdrawn_bytes(self) -> Buffer:
        """Raw bytes of withdrawn routes section."""
        withdrawn_len = unpack('!H', self._packed[:2])[0]
        return self._packed[2 : 2 + withdrawn_len]

    @property
    def attribute_bytes(self) -> Buffer:
        """Raw bytes of path attributes section."""
        withdrawn_len = unpack('!H', self._packed[:2])[0]
        attr_offset = 2 + withdrawn_len
        attr_len = unpack('!H', self._packed[attr_offset : attr_offset + 2])[0]
        return self._packed[attr_offset + 2 : attr_offset + 2 + attr_len]

    @property
    def nlri_bytes(self) -> Buffer:
        """Raw bytes of announced NLRI section."""
        withdrawn_len = unpack('!H', self._packed[:2])[0]
        attr_offset = 2 + withdrawn_len
        attr_len = unpack('!H', self._packed[attr_offset : attr_offset + 2])[0]
        nlri_offset = attr_offset + 2 + attr_len
        return self._packed[nlri_offset:]

    def pack_message(self, negotiated: 'Negotiated | None' = None) -> bytes:
        """Generate complete BGP message with header.

        Args:
            negotiated: Unused, kept for API compatibility with Message.pack_message().

        Returns:
            Complete BGP UPDATE message: marker(16) + length(2) + type(1) + payload
        """
        return self._message(self._packed)

    @property
    def data(self) -> 'UpdateCollection':
        """Access parsed UpdateCollection.

        Returns:
            Parsed UpdateCollection (semantic container) with announces, withdraws, attributes.

        Raises:
            ValueError: If parse() was not called and no negotiated context available.
        """
        if self._parsed is None:
            if self._negotiated is None:
                raise ValueError('Cannot access data: Update not parsed and no negotiated context stored')
            self._parsed = UpdateCollection._parse_payload(bytes(self._packed), self._negotiated)
        return self._parsed

    def parse(self, negotiated: 'Negotiated | None' = None) -> 'UpdateCollection':
        """Parse payload to semantic UpdateCollection with negotiated context.

        Args:
            negotiated: BGP session negotiated parameters. If not provided,
                       uses the negotiated context stored at construction time.

        Returns:
            Parsed UpdateCollection (semantic container).

        Raises:
            ValueError: If no negotiated context available (neither passed nor stored).
        """
        if self._parsed is None:
            neg = negotiated or self._negotiated
            if neg is None:
                raise ValueError('Cannot parse Update: no negotiated context provided or stored')
            self._parsed = UpdateCollection._parse_payload(bytes(self._packed), neg)
        return self._parsed

    @staticmethod
    def split(data: Buffer) -> tuple[Buffer, Buffer, Buffer]:
        """Split UPDATE payload into withdrawn, attributes, announced sections."""
        return UpdateCollection.split(data)

    @classmethod
    def unpack_message(cls, data: Buffer, negotiated: 'Negotiated') -> Message:
        """Unpack raw UPDATE payload to Update or EOR.

        This is the registered message handler called by Message.unpack().

        Args:
            data: Raw UPDATE message payload (after BGP header).
                  Can be bytes or memoryview (zero-copy from network).
            negotiated: BGP session negotiated parameters.

        Returns:
            Update (wire container with lazy parsing) or EOR.
        """
        log.debug(lazyformat('parsing UPDATE', data), 'parser')

        length = len(data)

        # Check for End-of-RIB markers (fast path)
        if length == EOR_IPV4_UNICAST_LENGTH and data == b'\x00\x00\x00\x00':
            return EOR(AFI.ipv4, SAFI.unicast)
        if length == EOR_WITH_PREFIX_LENGTH and bytes(data).startswith(EOR.EOR_NLRI.PREFIX):
            return EOR.unpack_message(data, negotiated)

        # Create wire container with negotiated context and parse
        update = cls(data, negotiated)
        parsed = update.parse()

        # Check if this is actually an EOR after parsing (empty update with MP attributes)
        if not parsed.attributes and not parsed.announces and not parsed.withdraws:
            # Need to check what MP attributes were present before they were popped
            # Re-split to check for MP_REACH/MP_UNREACH
            _, attr_view, _ = UpdateCollection.split(data)
            if attr_view:
                # Parse attributes again to check for MP attributes
                # (this is inefficient but handles edge cases)
                temp_attrs = AttributeCollection.unpack(bytes(attr_view), negotiated)
                unreach = temp_attrs.get(MPURNLRI.ID)
                reach = temp_attrs.get(MPRNLRI.ID)
                if unreach is not None:
                    return EOR(unreach.afi, unreach.safi)
                if reach is not None:
                    return EOR(reach.afi, reach.safi)
            # No MP attributes - this is IPv4 unicast EOR
            return EOR(AFI.ipv4, SAFI.unicast)

        def log_parsed(_: object) -> str:
            # we need the import in the function as otherwise we have an cyclic loop
            from exabgp.reactor.api.response import Response
            from exabgp.version import json as json_version

            return 'json {}'.format(
                Response.JSON(json_version).update(negotiated.neighbor, 'receive', update._parsed, b'', b'', negotiated)
            )

        log.debug(lazyformat('decoded UPDATE', '', log_parsed), 'parser')

        return update


# Backward compatibility alias
UpdateWire = Update
