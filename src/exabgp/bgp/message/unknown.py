"""unknown.py

Created by Thomas Mangin on 2013-07-20.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.message import Message

# ================================================================= UnknownMessage
#


class UnknownMessage(Message):
    # Make sure we have a value, which is not defined in any RFC !

    def __init__(self, code: int, packed: Buffer = b'', negotiated: Negotiated | None = None) -> None:
        self._code = code
        self._type_bytes = bytes([code])
        self.data = packed

    @property
    def ID(self) -> int:  # type: ignore[override]
        """Return message type code (instance-specific for unknown messages)."""
        return self._code

    @property
    def TYPE(self) -> bytes:  # type: ignore[override]
        """Return message type as bytes (instance-specific for unknown messages)."""
        return self._type_bytes

    def pack_message(self, negotiated: Negotiated) -> bytes:
        return self._message(self.data)

    def __str__(self) -> str:
        return 'UNKNOWN'

    @classmethod
    def unpack_message(cls, data: Buffer) -> UnknownMessage:  # pylint: disable=W0613
        raise RuntimeError('should not have been used')


UnknownMessage.klass_unknown = UnknownMessage
