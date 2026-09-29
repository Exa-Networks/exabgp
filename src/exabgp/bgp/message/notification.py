"""notification.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import string
from typing import TYPE_CHECKING, ClassVar

from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.message import Message
from exabgp.util import hexbytes, hexstring

# ================================================================== Notification
# The NOTIFICATION message, RFC 4271 Section 4.5: what we send, and what a peer sends us.

# 0                   1                   2                   3
# 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# | Error code    | Error subcode |   Data (variable)             |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+


@Message.register
class Notification(Message):
    """The NOTIFICATION message, whichever way it goes: a message, never an exception.

    Notify is the exception we raise to send one; NotificationReceived the one the reactor
    raises when a peer sent one.  Neither is a Notification: each holds one.
    """

    ID: ClassVar[int] = Message.CODE.NOTIFICATION

    # RFC 9003 - Shutdown Communication, carried by these two Cease subcodes only
    SHUTDOWN_SUBCODES: ClassVar[tuple[tuple[int, int], ...]] = ((6, 2), (6, 4))
    SHUTDOWN_COMM_MAX_LEGACY: ClassVar[int] = 128  # RFC 9003 3: most we send to a peer not known to support it
    SHUTDOWN_COMM_MAX_EXTENDED: ClassVar[int] = 255  # RFC 9003 2: what the one octet Length can say
    UNSUPPORTED_CAPABILITY: ClassVar[tuple[int, int]] = (2, 7)  # RFC 5492 5
    MAXIMUM_NUMBER_OF_PREFIXES_REACHED: ClassVar[tuple[int, int]] = (6, 1)  # RFC 4486 3

    # The IANA "BGP Error (Notification) Codes" and "BGP Error Subcodes" registries,
    # https://www.iana.org/assignments/bgp-parameters (updated 2026-09-09).  These names
    # are what the log, the API and the text of a Notify we send are built from, so they
    # follow the registry rather than our own wording.  A deprecated value keeps its old
    # name in brackets: a peer running old code may still send it.
    _str_code: ClassVar[dict[int, str]] = {
        1: 'Message Header Error',
        2: 'OPEN Message Error',
        3: 'UPDATE Message Error',
        4: 'Hold Timer Expired',
        5: 'Finite State Machine Error',
        6: 'Cease',
        7: 'ROUTE-REFRESH Message Error',  # RFC 7313
        8: 'Send Hold Timer Expired',  # RFC 9687
        9: 'Loss of LSDB Synchronization',  # RFC 9815
    }

    _str_subcode: ClassVar[dict[tuple[int, int], str]] = {
        # RFC 4271 4.5: a code with no subcode defined uses zero, Unspecific
        (1, 0): 'Unspecific',
        (1, 1): 'Connection Not Synchronized',
        (1, 2): 'Bad Message Length',
        (1, 3): 'Bad Message Type',
        (2, 0): 'Unspecific',
        (2, 1): 'Unsupported Version Number',
        (2, 2): 'Bad Peer AS',
        (2, 3): 'Bad BGP Identifier',
        (2, 4): 'Unsupported Optional Parameter',
        (2, 5): '[Deprecated] Authentication Failure',
        (2, 6): 'Unacceptable Hold Time',
        (2, 7): 'Unsupported Capability',  # RFC 5492
        # draft-ietf-idr-bgp-multisession, deprecated by RFC 9234
        (2, 8): '[Deprecated] Grouping Conflict',
        (2, 9): '[Deprecated] Grouping Required',
        (2, 10): '[Deprecated] Capability Value Mismatch',
        (2, 11): 'Role Mismatch',  # RFC 9234
        (3, 0): 'Unspecific',
        (3, 1): 'Malformed Attribute List',
        (3, 2): 'Unrecognized Well-known Attribute',
        (3, 3): 'Missing Well-known Attribute',
        (3, 4): 'Attribute Flags Error',
        (3, 5): 'Attribute Length Error',
        (3, 6): 'Invalid ORIGIN Attribute',
        (3, 7): '[Deprecated] AS Routing Loop',
        (3, 8): 'Invalid NEXT_HOP Attribute',
        (3, 9): 'Optional Attribute Error',
        (3, 10): 'Invalid Network Field',
        (3, 11): 'Malformed AS_PATH',
        (4, 0): 'Unspecific',
        # RFC 6608
        (5, 0): 'Unspecified Error',
        (5, 1): 'Receive Unexpected Message in OpenSent State',
        (5, 2): 'Receive Unexpected Message in OpenConfirm State',
        (5, 3): 'Receive Unexpected Message in Established State',
        # RFC 4486, RFC 9003 for 2 and 4
        (6, 0): 'Reserved',
        (6, 1): 'Maximum Number of Prefixes Reached',
        (6, 2): 'Administrative Shutdown',
        (6, 3): 'Peer De-configured',
        (6, 4): 'Administrative Reset',
        (6, 5): 'Connection Rejected',
        (6, 6): 'Other Configuration Change',
        (6, 7): 'Connection Collision Resolution',
        (6, 8): 'Out of Resources',
        (6, 9): 'Hard Reset',  # RFC 8538
        (6, 10): 'BFD Down',  # RFC 9384
        # RFC 7313
        (7, 0): 'Reserved',
        (7, 1): 'Invalid Message Length',
        (8, 0): 'Unspecific',
        (9, 0): 'Unspecific',
    }

    FIXED_SIZE: ClassVar[int] = 2  # RFC 4271 4.5: an error code and an error subcode

    def __init__(self, packed: Buffer) -> None:
        # this guards our own construction, not the wire: unpack_message pads a short body
        # rather than letting a peer reach it, because a raw exception here is answered
        # with a NOTIFICATION and RFC 4271 6.5 forbids that
        if len(packed) < self.FIXED_SIZE:
            raise ValueError(f'Notification requires at least {self.FIXED_SIZE} bytes, got {len(packed)}')
        self._packed = packed

    def pack_body(self, negotiated: Negotiated) -> Buffer:
        return self._packed

    @classmethod
    def is_assigned(cls, code: int, subcode: int) -> bool:
        """Whether IANA assigns this code and subcode (a deprecated value still counts)."""
        return (code, subcode) in cls._str_subcode and cls._str_subcode[(code, subcode)] != 'Reserved'

    @classmethod
    def make_notification(cls, code: int, subcode: int, data: Buffer = b'') -> 'Notification':
        return cls(bytes([code, subcode]) + data)

    @property
    def code(self) -> int:
        return self._packed[0]

    @property
    def subcode(self) -> int:
        return self._packed[1]

    @property
    def data(self) -> bytes:
        """The Data field, as it is on the wire."""
        return bytes(self._packed[self.FIXED_SIZE :])

    @property
    def text(self) -> bytes:
        """The Data field made readable: an RFC 9003 Shutdown Communication decoded, else hex."""
        raw = self.data
        code = self.code
        subcode = self.subcode

        if (code, subcode) not in self.SHUTDOWN_SUBCODES:
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
        text = self.text
        try:
            data_str = f' / {text.decode("ascii")}' if text else ''
        except UnicodeDecodeError:
            data_str = f' / {hexstring(text)}'
        return f'{code_str} / {subcode_str}{data_str}'

    @classmethod
    def unpack_message(cls, data: Buffer, negotiated: Negotiated) -> Notification:
        """A NOTIFICATION the peer truncated is still the peer closing the session.

        RFC 4271 6.5 is explicit that an error found while processing a NOTIFICATION must
        not be reported back with a NOTIFICATION.  So this cannot raise Notify, and it must
        not raise anything raw either: a ValueError out of __init__ reached
        reactor/protocol.py's catch-all, which turned it into

            Notify(1, 0, 'can not decode update message of type "3"')

        and sent the peer exactly the message the RFC forbids, naming the wrong error.

        Returning a Notification instead lets protocol.py raise NotificationReceived, and
        the reactor closes the session without replying, which is what the RFC asks for.  A body too short to
        hold a code renders as "unknown error / unknow reason", which is accurate: the peer
        did not say.
        """
        if len(data) < cls.FIXED_SIZE:
            return cls(bytes(cls.FIXED_SIZE))
        return cls(data)


# ========================================================== NotificationReceived
# A peer told us it is closing the session.


class NotificationReceived(Exception):
    """The peer sent a NOTIFICATION: the session ends and nothing is sent back (RFC 4271 6.5).

    Raised by the reactor when it reads one.  It is not a Notify, so no handler meant for the
    errors we report can catch it by accident, whatever order the handlers are in.
    """

    def __init__(self, notification: Notification) -> None:
        super().__init__(str(notification))
        self.notification = notification

    @property
    def code(self) -> int:
        return self.notification.code

    @property
    def subcode(self) -> int:
        return self.notification.subcode

    def __str__(self) -> str:
        return str(self.notification)


# =================================================================== Notify
# A Notification we need to inform our peer of.


class Notify(Exception):
    """An error we tell the peer about: raising it sends `notification`, then resets.

    `detail` is our explanation, for str() and so for the log.  It is appended to the
    IANA names of the code and subcode, so a caller writes only what the names do not say.

    `data` is the Data field, for the subcodes whose content an RFC defines: the erroneous
    Length for a Bad Message Length (RFC 4271 6.1), the complete message for an Invalid
    Message Length (RFC 7313 5).  Given, the octets go to the peer and the detail stays
    local.  Not given, the detail goes to the peer as text, and with no detail the Data
    field is empty: the peer already has the code and subcode, and their names add nothing.

    (6, 2) and (6, 4) are the exception: their detail is an RFC 9003 Shutdown Communication.
    """

    UNSUPPORTED_CAPABILITY: ClassVar[tuple[int, int]] = Notification.UNSUPPORTED_CAPABILITY
    MAXIMUM_NUMBER_OF_PREFIXES_REACHED: ClassVar[tuple[int, int]] = Notification.MAXIMUM_NUMBER_OF_PREFIXES_REACHED

    # RFC 4271 4.1: a message is at most 4096 octets, header 19, code and subcode 2.  An
    # attribute with an extended length can be larger than that, and is cut to fit
    DATA_MAX_OCTETS: ClassVar[int] = Message.STANDARD_MAX - Message.HEADER_LEN - Notification.FIXED_SIZE

    def __init__(self, code: int, subcode: int, detail: str = '', *, data: Buffer | None = None) -> None:
        self.detail = detail
        self.has_defined_data = data is not None
        if data is None:
            data = self._wire_text(code, subcode, detail)
        self.notification = Notification(bytes([code, subcode]) + bytes(data[: self.DATA_MAX_OCTETS]))
        super().__init__(str(self))

    @classmethod
    def _wire_text(cls, code: int, subcode: int, detail: str) -> bytes:
        if (code, subcode) not in Notification.SHUTDOWN_SUBCODES:
            # A Notify is raised while handling an error, so its own text must not raise:
            # a character ASCII cannot hold goes out escaped rather than failing the send
            return detail.encode('ascii', 'backslashreplace')
        if not detail:
            return b''
        # RFC 9003 2: UTF-8, and 3: at most 128 octets as we cannot know the peer takes 255.
        # Cut on a character boundary, so what is sent still decodes
        communication = detail.encode('utf-8')[: Notification.SHUTDOWN_COMM_MAX_LEGACY]
        communication = communication.decode('utf-8', 'ignore').encode('utf-8')
        assert len(communication) <= Notification.SHUTDOWN_COMM_MAX_LEGACY
        return bytes([len(communication)]) + communication

    @classmethod
    def short(cls, code: int, subcode: int, what: str, need_octets: int, got_octets: int) -> 'Notify':
        """The commonest malformation there is: fewer octets arrived than the field needs."""
        assert got_octets < need_octets, 'a payload which is not short is a different error'
        return cls(code, subcode, f'{what} needs {need_octets} octets, got {got_octets}')

    @classmethod
    def make_notify(cls, code: int, subcode: int, detail: str = '') -> 'Notify':
        return cls(code, subcode, detail)

    @classmethod
    def is_assigned(cls, code: int, subcode: int) -> bool:
        return Notification.is_assigned(code, subcode)

    @property
    def code(self) -> int:
        return self.notification.code

    @property
    def subcode(self) -> int:
        return self.notification.subcode

    @property
    def data(self) -> bytes:
        """The Data field sent to the peer."""
        return self.notification.data

    def __str__(self) -> str:
        code_name = Notification._str_code.get(self.code, f'unknown error code {self.code}')
        subcode_name = Notification._str_subcode.get((self.code, self.subcode), f'unknown subcode {self.subcode}')
        # Subcode 0 is "Unspecific" (RFC 4271 4.5): it names nothing the code does not
        names = code_name if self.subcode == 0 else f'{code_name} / {subcode_name}'
        return f'{names}: {self.detail}' if self.detail else names


class NLRIDiscard(Notify):
    """An error inside one NLRI whose length is honest: that NLRI is dropped, not the session.

    RFC 9552 8.2.2 (and RFC 7606 5.4's "NLRI discard"): when a rule inside the NLRI is
    broken but its length still says where it ends, the NLRI is discarded and the rest of
    the UPDATE processed. The decoder which knows where the NLRI ends sets `skip`, the
    octets it took; where nothing does, it is a Notify like any other and resets the session.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(3, 10, detail)
        self.skip = 0
