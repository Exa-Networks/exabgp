"""update/update.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import unpack
from typing import TYPE_CHECKING, ClassVar

from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.message import Message
from exabgp.bgp.message.update.collection import UpdateCollection
from exabgp.bgp.message.update.nlri import MPNLRICollection, NLRICollection
from exabgp.logger import lazyformat, log

__all__ = [
    'Update',
    'UpdateCollection',
    'UpdateWire',
    'NLRICollection',
    'MPNLRICollection',
]


# ======================================================================= Update (Wire)
#
# Wire-format BGP UPDATE message container (bytes-first pattern).
# This class stores the raw payload bytes as the canonical representation.
# Parsing to semantic objects (UpdateCollection) is lazy.


class Update(Message):
    """Wire-format BGP UPDATE message container (bytes-first).

    Stores raw UPDATE message payload as the canonical representation.
    Provides lazy parsing to semantic UpdateCollection when needed.

    This follows the "packed-bytes-first" pattern used by individual
    Attribute classes - the wire format is stored directly, and semantic
    values are derived via properties.

    This is the registered BGP UPDATE message handler.
    """

    ID: ClassVar = Message.CODE.UPDATE
    IS_EOR: ClassVar[bool] = False  # EOR, the End-of-RIB marker, says True
    FIXED_SIZE: ClassVar[int] = 4  # RFC 4271 4.3: the two length fields, withdrawn routes and path attributes

    def __init__(self, packed: Buffer) -> None:
        """Create Update from raw payload bytes.

        Args:
            packed: The UPDATE message payload (after BGP header).
                    Format: withdrawn_len(2) + withdrawn + attr_len(2) + attributes + nlri
                    Can be bytes or memoryview.

        What it means depends on the session (ADD-PATH, ASN4, ...), so it is decoded by
        parse(negotiated), once, and read through data afterwards.
        """
        self._packed = packed
        self._parsed: 'UpdateCollection | None' = None

    @classmethod
    def from_collection(cls, collection: 'UpdateCollection') -> 'Update':
        """An UPDATE told to the API which the peer never sent as such: no bytes, only routes.

        RFC 8955 6 revalidation announces or withdraws a flow specification because a
        unicast route changed, and that change has to reach the API like any other.
        """
        update = cls(b'')
        update._parsed = collection
        return update

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

    def pack_body(self, negotiated: 'Negotiated') -> Buffer:
        return self._packed

    @property
    def data(self) -> 'UpdateCollection':
        """Access parsed UpdateCollection.

        Returns:
            Parsed UpdateCollection (semantic container) with announces, withdraws, attributes.

        Raises:
            ValueError: If parse() was not called.
        """
        if self._parsed is None:
            raise ValueError('Cannot access data: Update not parsed, call parse(negotiated) first')
        return self._parsed

    def parse(self, negotiated: 'Negotiated') -> 'UpdateCollection':
        """Parse payload to semantic UpdateCollection with negotiated context, once."""
        if self._parsed is None:
            self._parsed = UpdateCollection._parse_payload(bytes(self._packed), negotiated)
        return self._parsed

    @staticmethod
    def split(data: Buffer) -> tuple[Buffer, Buffer, Buffer]:
        """Split UPDATE payload into withdrawn, attributes, announced sections."""
        return UpdateCollection.split(data)

    @classmethod
    def unpack_message(cls, data: Buffer, negotiated: 'Negotiated') -> Update:
        """Unpack raw UPDATE payload to Update, or EOR which is one.

        This is the registered message handler called by Message.unpack().

        Args:
            data: Raw UPDATE message payload (after BGP header).
                  Can be bytes or memoryview (zero-copy from network).
            negotiated: BGP session negotiated parameters.

        Returns:
            Update (wire container with lazy parsing) or EOR.
        """
        log.debug(lazyformat('parsing UPDATE', data), 'parser')

        # RFC 4724 2: the marker is what the peer sent, never what is left once decoded
        eor = EOR.from_body(data)
        if eor is not None:
            return eor

        update = cls(data)
        update.parse(negotiated)

        def log_parsed(_: object) -> str:
            # we need the import in the function as otherwise we have an cyclic loop
            from exabgp.reactor.api.response import Response
            from exabgp.version import json as json_version

            assert update._parsed is not None  # Always set after parsing
            return 'json {}'.format(
                Response.JSON(json_version).update(negotiated.neighbor, 'receive', update._parsed, b'', b'', negotiated)
            )

        log.debug(lazyformat('decoded UPDATE', '', log_parsed), 'parser')

        return update


Message.register(Update)


# Backward compatibility alias
UpdateWire = Update


# EOR is an Update, so it is defined once Update is: eor.py imports it from this module
from exabgp.bgp.message.update.eor import EOR  # noqa: E402
