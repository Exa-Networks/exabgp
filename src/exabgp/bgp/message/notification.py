"""notification.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import string
from collections.abc import Buffer
from typing import ClassVar, TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.util import hexbytes
from exabgp.util import hexstring

from exabgp.bgp.message.message import Message


# ================================================================== Notification
# A Notification received from our peer.
# RFC 4271 Section 4.5

# 0                   1                   2                   3
# 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# | Error code    | Error subcode |   Data (variable)             |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+


@Message.register
class Notification(Message, Exception):
    ID: ClassVar[int] = Message.CODE.NOTIFICATION  # type: ignore[misc]
    TYPE: ClassVar[bytes] = bytes([Message.CODE.NOTIFICATION])  # type: ignore[misc]

    # RFC 8203 / RFC 9003 - Shutdown Communication
    SHUTDOWN_COMM_MAX_LEGACY: ClassVar[int] = 128  # RFC 8203 - legacy max length
    SHUTDOWN_COMM_MAX_EXTENDED: ClassVar[int] = 255  # RFC 9003 - extended max length

    _str_code: ClassVar[dict[int, str]] = {
        1: 'Message header error',
        2: 'OPEN message error',
        3: 'UPDATE message error',
        4: 'Hold timer expired',
        5: 'State machine error',
        6: 'Cease',
    }

    _str_subcode: ClassVar[dict[tuple[int, int], str]] = {
        (1, 0): 'Unspecific',
        (1, 1): 'Connection Not Synchronized',
        (1, 2): 'Bad Message Length',
        (1, 3): 'Bad Message Type',
        (2, 0): 'Unspecific',
        (2, 1): 'Unsupported Version Number',
        (2, 2): 'Bad Peer AS',
        (2, 3): 'Bad BGP Identifier',
        (2, 4): 'Unsupported Optional Parameter',
        (2, 5): 'Authentication Notification (Deprecated)',
        (2, 6): 'Unacceptable Hold Time',
        # RFC 5492 - https://tools.ietf.org/html/rfc5492
        (2, 7): 'Unsupported Capability',
        # draft-ietf-idr-bgp-multisession-06
        (2, 8): 'Grouping Conflict',
        (2, 9): 'Grouping Required',
        (2, 10): 'Capability Value Mismatch',
        (3, 0): 'Unspecific',
        (3, 1): 'Malformed Attribute List',
        (3, 2): 'Unrecognized Well-known Attribute',
        (3, 3): 'Missing Well-known Attribute',
        (3, 4): 'Attribute Flags Error',
        (3, 5): 'Attribute Length Error',
        (3, 6): 'Invalid ORIGIN Attribute',
        (3, 7): 'AS Routing Loop',
        (3, 8): 'Invalid NEXT_HOP Attribute',
        (3, 9): 'Optional Attribute Error',
        (3, 10): 'Invalid Network Field',
        (3, 11): 'Malformed AS_PATH',
        (4, 0): 'Unspecific',
        (5, 0): 'Unspecific',
        # RFC 6608 - https://tools.ietf.org/html/rfc6608
        (5, 1): 'Receive Unexpected Message in OpenSent State',
        (5, 2): 'Receive Unexpected Message in OpenConfirm State',
        (5, 3): 'Receive Unexpected Message in Established State',
        (6, 0): 'Unspecific',
        # RFC 4486 - https://tools.ietf.org/html/rfc4486
        (6, 1): 'Maximum Number of Prefixes Reached',
        (6, 2): 'Administrative Shutdown',  # augmented with draft-ietf-idr-shutdown
        (6, 3): 'Peer De-configured',
        (6, 4): 'Administrative Reset',
        (6, 5): 'Connection Rejected',
        (6, 6): 'Other Configuration Change',
        (6, 7): 'Connection Collision Resolution',
        (6, 8): 'Out of Resources',
        # draft-keyur-bgp-enhanced-route-refresh-00
        (7, 1): 'Invalid Message Length',
        (7, 2): 'Malformed Message Subtype',
    }

    def __init__(self, packed: Buffer) -> None:
        # Convert to bytearray first - this gives us length and ownership
        self._buffer = bytearray(packed)
        if len(self._buffer) < 2:
            raise ValueError(f'Notification requires at least 2 bytes, got {len(self._buffer)}')
        Exception.__init__(self)
        # Two-buffer pattern: bytearray owns data, memoryview provides zero-copy slicing
        self._packed = memoryview(self._buffer)

    @classmethod
    def make_notification(cls, code: int, subcode: int, data: bytes = b'') -> 'Notification':
        return cls(bytes([code, subcode]) + data)

    @property
    def code(self) -> int:
        return self._packed[0]

    @property
    def subcode(self) -> int:
        return self._packed[1]

    @property
    def raw_data(self) -> bytes:
        return bytes(self._packed[2:])

    @property
    def data(self) -> bytes:
        """Parse raw_data into human-readable form for display."""
        raw = self.raw_data
        code = self.code
        subcode = self.subcode

        if (code, subcode) not in [(6, 2), (6, 4)]:
            return raw if not len([_ for _ in str(raw) if _ not in string.printable]) else hexbytes(raw)

        if len(raw) == 0:
            # shutdown without shutdown communication (the old fashioned way)
            return b''

        # draft-ietf-idr-shutdown or the peer was using 6,2 with data
        shutdown_length = raw[0]
        payload = raw[1:]

        if shutdown_length == 0:
            return b'empty Shutdown Communication.'

        if len(payload) < shutdown_length:
            return f'invalid Shutdown Communication (buffer underrun) length : {shutdown_length} [{hexstring(payload)}]'.encode()

        if shutdown_length > self.SHUTDOWN_COMM_MAX_LEGACY:
            return (
                f'invalid Shutdown Communication (too large) length : {shutdown_length} [{hexstring(payload)}]'.encode()
            )

        try:
            decoded_msg = payload[:shutdown_length].decode('utf-8').replace('\r', ' ').replace('\n', ' ')
            result = f'Shutdown Communication: "{decoded_msg}"'.encode()
        except UnicodeDecodeError:
            return f'invalid Shutdown Communication (invalid UTF-8) length : {shutdown_length} [{hexstring(payload)}]'.encode()

        trailer = payload[shutdown_length:]
        if trailer:
            result += (', trailing data: ' + hexstring(trailer)).encode('utf-8')
        return result

    def __str__(self) -> str:
        code_str = self._str_code.get(self.code, 'unknown error')
        subcode_str = self._str_subcode.get((self.code, self.subcode), 'unknow reason')
        data_str = f' / {self.data.decode("ascii")}' if self.data else ''
        return f'{code_str} / {subcode_str}{data_str}'

    @classmethod
    def unpack_message(cls, data: Buffer, negotiated: Negotiated) -> Notification:
        return cls(data)


# =================================================================== Notify
# A Notification we need to inform our peer of.


class Notify(Notification):
    def __init__(self, code: int, subcode: int, data: str | None = None) -> None:
        if data is None:
            data = self._str_subcode.get((code, subcode), 'unknown notification type')
        if (code, subcode) in [(6, 2), (6, 4)]:
            data = chr(len(data)) + data
        # Build packed bytes directly: code + subcode + data
        packed = bytes([code, subcode]) + bytes(data, 'ascii')
        Notification.__init__(self, packed)

    @classmethod
    def make_notify(cls, code: int, subcode: int, data: str | None = None) -> 'Notify':
        return cls(code, subcode, data)

    def pack_message(self, negotiated: Negotiated) -> bytes:
        return self._message(self._packed)

    @property
    def data(self) -> bytes:
        """For Notify (sending), data is the raw wire-format data, not parsed."""
        return self.raw_data
