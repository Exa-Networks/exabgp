"""notification.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import string
from typing import ClassVar, Dict, Tuple, TYPE_CHECKING

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

    _str_code: ClassVar[Dict[int, str]] = {
        1: 'Message header error',
        2: 'OPEN message error',
        3: 'UPDATE message error',
        4: 'Hold timer expired',
        5: 'State machine error',
        6: 'Cease',
    }

    _str_subcode: ClassVar[Dict[Tuple[int, int], str]] = {
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

    def __init__(self, code: int, subcode: int, data: bytes = b'', parse_data: bool = True) -> None:
        Exception.__init__(self)
        self.code = code  # type: ignore[assignment,method-assign]
        self.subcode = subcode

        if not parse_data:
            self.data = data
            return

        if (code, subcode) not in [(6, 2), (6, 4)]:
            self.data = data if not len([_ for _ in str(data) if _ not in string.printable]) else hexbytes(data)
            return

        if len(data) == 0:
            # shutdown without shutdown communication (the old fashioned way)
            self.data = b''
            return

        # draft-ietf-idr-shutdown or the peer was using 6,2 with data

        shutdown_length = data[0]
        data = data[1:]

        if shutdown_length == 0:
            self.data = b'empty Shutdown Communication.'
            # move offset past length field
            return

        if len(data) < shutdown_length:
            self.data = f'invalid Shutdown Communication (buffer underrun) length : {shutdown_length} [{hexstring(data)}]'.encode()
            return

        if shutdown_length > self.SHUTDOWN_COMM_MAX_LEGACY:
            self.data = (
                f'invalid Shutdown Communication (too large) length : {shutdown_length} [{hexstring(data)}]'.encode()
            )
            return

        try:
            decoded_msg = data[:shutdown_length].decode('utf-8').replace('\r', ' ').replace('\n', ' ')
            self.data = f'Shutdown Communication: "{decoded_msg}"'.encode()
        except UnicodeDecodeError:
            self.data = f'invalid Shutdown Communication (invalid UTF-8) length : {shutdown_length} [{hexstring(data)}]'.encode()
            return

        trailer = data[shutdown_length:]
        if trailer:
            self.data += (', trailing data: ' + hexstring(trailer)).encode('utf-8')

    def __str__(self) -> str:
        code_str = self._str_code.get(self.code, 'unknown error')  # type: ignore[call-overload]
        subcode_str = self._str_subcode.get((self.code, self.subcode), 'unknow reason')  # type: ignore[arg-type]
        data_str = f' / {self.data.decode("ascii")}' if self.data else ''
        return f'{code_str} / {subcode_str}{data_str}'

    @classmethod
    def unpack_message(cls, data: bytes, negotiated: Negotiated) -> Notification:
        return cls(data[0], data[1], data[2:])


# =================================================================== Notify
# A Notification we need to inform our peer of.


class Notify(Notification):
    def __init__(self, code: int, subcode: int, data: str | None = None) -> None:
        if data is None:
            data = self._str_subcode.get((code, subcode), 'unknown notification type')
        if (code, subcode) in [(6, 2), (6, 4)]:
            data = chr(len(data)) + data
        Notification.__init__(self, code, subcode, bytes(data, 'ascii'), False)

    def pack_message(self, negotiated: Negotiated) -> bytes:
        return self._message(bytes([self.code, self.subcode]) + self.data)  # type: ignore[list-item]
