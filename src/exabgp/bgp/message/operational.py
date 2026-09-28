"""BGP Operational messages (draft-ietf-idr-bgp-operational-message).

This module implements BGP Operational messages for exchanging operational
state between BGP speakers. These messages enable debugging, monitoring,
and diagnostic capabilities without impacting routing state.

Message categories:
    Advisory: Text messages (ADM/ASM) for operator notifications
    Query: Prefix count requests (RPCQ/APCQ/LPCQ)
    Response: Prefix count replies (RPCP/APCP/LPCP)
    Control: NS (Not Satisfied) error responses

Key classes:
    Operational: Base message class
    OperationalFamily: Messages with AFI/SAFI context
    SequencedOperationalFamily: Messages with router-id and sequence number
    Advisory.ADM/ASM: Advisory Demand/Static Messages
    Query.RPCQ/APCQ/LPCQ: Prefix count queries
    Response.RPCP/APCP/LPCP: Prefix count responses
    NS.*: Error response codes

Created by Thomas Mangin on 2013-09-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.util.types import Buffer
from struct import pack
from struct import unpack
from typing import Any, ClassVar, Type as TypingType, TypeVar, TYPE_CHECKING

from exabgp.protocol.family import AFI, SAFI, FamilyTuple
from exabgp.bgp.message.open.routerid import RouterID
from exabgp.bgp.message.message import Message
from exabgp.bgp.message.notification import Notify
from exabgp.logger import log, lazymsg

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

# TypeVar for register decorator - preserves the specific subclass type
_T = TypeVar('_T', bound='Operational')

# ========================================================================= Type
#

MAX_ADVISORY = 2048  # 2K


class Type(int):
    """Operational message type code (2-byte unsigned integer)."""

    def pack(self) -> bytes:
        return pack('!H', self)

    def extract(self) -> list[bytes]:
        return [pack('!H', self)]

    def __len__(self) -> int:
        return 2

    def __str__(self) -> str:
        # a peer picks this code, and an unregistered one still has to be printable:
        # raising here put a NotImplementedError in the logger rather than in a test
        return f'operational-type-{int(self)}'


# ================================================================== Operational
#


@Message.register
class Operational(Message):
    """Base class for BGP Operational messages.

    Operational messages exchange debugging and monitoring information
    between BGP speakers. Subclasses implement specific message types.

    Wire format: [type(2)][length(2)][payload...], all of it stored as the body.
    """

    ID = Message.CODE.OPERATIONAL
    FIXED_SIZE = 4  # the operational header: a two octet type and a two octet length

    registered_operational: ClassVar[dict[int, TypingType['Operational']]] = dict()

    # the operational types, draft-ietf-idr-operational-message
    class SUBTYPE:
        NOP = 0x00  # Not defined by the RFC
        # ADVISE
        ADM = 0x01  # 01: Advisory Demand Message
        ASM = 0x02  # 02: Advisory Static Message
        # STATE
        RPCQ = 0x03  # 03: Reachable Prefix Count Request
        RPCP = 0x04  # 04: Reachable Prefix Count Reply
        APCQ = 0x05  # 05: Adj-Rib-Out Prefix Count Request
        APCP = 0x06  # 06: Adj-Rib-Out Prefix Count Reply
        LPCQ = 0x07  # 07: BGP Loc-Rib Prefix Count Request
        LPCP = 0x08  # 08: BGP Loc-Rib Prefix Count Reply
        SSQ = 0x09  # 09: Simple State Request
        # DUMP
        DUP = 0x0A  # 10: Dropped Update Prefixes
        MUP = 0x0B  # 11: Malformed Update Prefixes
        MUD = 0x0C  # 12: Malformed Update Dump
        SSP = 0x0D  # 13: Simple State Response
        # CONTROL
        MP = 0xFFFE  # 65534: Max Permitted
        NS = 0xFFFF  # 65535: Not Satisfied

    # what a class is: its type code, its name and how its payload is laid out.  Only a
    # message which is sent has a NAME: a class without one is the layout its group shares
    SUBTYPE_ID: ClassVar[int] = SUBTYPE.NOP
    NAME: ClassVar[str] = ''
    CATEGORY: ClassVar[str] = ''
    HAS_FAMILY: ClassVar[bool] = False
    HAS_ROUTERID: ClassVar[bool] = False
    IS_FAULT: ClassVar[bool] = False

    def __init__(self, packed: Buffer) -> None:
        # what a factory built, or what unpack_message checked: never unchecked bytes
        if len(packed) < self.FIXED_SIZE:
            raise ValueError(f'an operational message needs {self.FIXED_SIZE} octets, got {len(packed)}')
        self._packed = packed

    @staticmethod
    def pack_operational(what: int, payload: Buffer) -> bytes:
        """The body of an operational message: its type, the length of its payload, the payload."""
        return pack('!HH', what, len(payload)) + bytes(payload)

    @property
    def what(self) -> Type:
        return Type(unpack('!H', self._packed[0:2])[0])

    @property
    def payload(self) -> Buffer:
        length = unpack('!H', self._packed[2:4])[0]
        return self._packed[self.FIXED_SIZE : self.FIXED_SIZE + length]

    def pack_body(self, negotiated: Negotiated) -> Buffer:
        return self._packed

    def __str__(self) -> str:
        return self.extensive()

    def extensive(self) -> str:
        return f'operational {self.NAME}'

    @classmethod
    def register_operational(cls, klass: TypingType[_T]) -> TypingType[_T]:
        """Register an Operational subtype (ADM, ASM, RPCQ, etc.) for unpacking.

        Note: This is distinct from Message.register which registers message types.
        """
        if klass.SUBTYPE_ID in cls.registered_operational:
            raise RuntimeError(f'only one class can be registered per operational type ({klass.SUBTYPE_ID})')
        cls.registered_operational[klass.SUBTYPE_ID] = klass
        return klass

    # how many octets each layout needs: the header, then afi and safi, router-id, sequence, counter
    CATEGORY_SIZE: ClassVar[dict[str, tuple[int, str]]] = {
        'advisory': (7, 'an afi, a safi and its advisory'),
        'query': (15, 'an afi, a safi, a router-id and a sequence'),
        'counter': (19, 'an afi, a safi, a router-id, a sequence and a counter'),
    }

    @classmethod
    def unpack_message(cls, data: Buffer, negotiated: Negotiated) -> Operational:  # pylint: disable=W0613
        """Unpack an Operational message from wire format.

        Returns the appropriate Operational subtype based on the message type code,
        or UnknownOperational if the type is not recognized.
        """
        # the header the peer must have sent: a two byte type and a two byte length
        if len(data) < cls.FIXED_SIZE:
            raise Notify.short(5, 0, 'operational message header', cls.FIXED_SIZE, len(data))
        what = Type(unpack('!H', data[0:2])[0])
        length = unpack('!H', data[2:4])[0]
        if len(data) < length + cls.FIXED_SIZE:
            raise Notify(
                5, 0, f'operational message announces {length} bytes of payload but only {len(data) - 4} follow'
            )
        body = data[: length + cls.FIXED_SIZE]

        klass = cls.registered_operational.get(what)
        if klass is None:
            # never write to stdout from a decoder: in daemon mode that is the pipe
            # feeding the API subprocesses, and this would be a line they cannot parse
            log.debug(lazymsg('operational.unknown type={what}', what=int(what)), 'parser')
            return UnknownOperational(body)

        sizes = cls.CATEGORY_SIZE.get(klass.CATEGORY)
        if sizes is None:
            # a category we registered but cannot decode is our bug, not the peer's
            log.debug(lazymsg('operational.CATEGORY.unknown category={category}', category=klass.CATEGORY), 'parser')
            return UnknownOperational(body)

        # every read the class makes is from bytes the peer chose, so their size is checked first
        needed, holds = sizes
        cls._check_size(body, needed, what, holds)
        return klass(body)

    @staticmethod
    def _check_size(data: Buffer, needed: int, what: int, holds: str) -> None:
        if len(data) < needed:
            raise Notify(
                5,
                0,
                f'operational message {int(what)} needs {needed} bytes to hold {holds}, got {len(data)}',
            )


# ============================================================ UnknownOperational


class UnknownOperational(Operational):
    """Unknown or unrecognized operational message type.

    Used when receiving an Operational message with a type code that is not
    registered in registered_operational. This allows graceful handling of
    unknown message types without breaking the type system.
    """

    NAME: ClassVar[str] = 'unknown'
    CATEGORY: ClassVar[str] = 'unknown'

    @classmethod
    def make_unknown(cls, what: int, data: Buffer) -> 'UnknownOperational':
        return cls(cls.pack_operational(what, data))

    @property
    def data(self) -> Buffer:
        return self.payload

    def extensive(self) -> str:
        return f'operational unknown type={self.what}'


# ============================================================ OperationalFamily


class OperationalFamily(Operational):
    """Operational message with AFI/SAFI address family context.

    Payload: [afi(2)][safi(1)][data...]
    """

    FAMILY_SIZE: ClassVar[int] = 3
    HAS_FAMILY: ClassVar[bool] = True

    @staticmethod
    def pack_family(afi: int | AFI, safi: int | SAFI) -> bytes:
        return AFI.from_int(afi).pack_afi() + SAFI.from_int(safi).pack_safi()

    @property
    def afi(self) -> AFI:
        return AFI.from_int(unpack('!H', self.payload[0:2])[0])

    @property
    def safi(self) -> SAFI:
        return SAFI.from_int(self.payload[2])

    @property
    def data(self) -> Buffer:
        return self.payload[self.FAMILY_SIZE :]

    def family(self) -> FamilyTuple:
        return (self.afi, self.safi)

    @classmethod
    def from_values(cls, values: dict[str, Any]) -> 'OperationalFamily':
        """Build one from what the configuration read, each category naming what it needs."""
        raise NotImplementedError(f'{cls.__qualname__} is built by its category')


# =================================================== SequencedOperationalFamily


class SequencedOperationalFamily(OperationalFamily):
    """Operational message with router-id and sequence number for request/response matching.

    Payload: [afi(2)][safi(1)][router-id(4)][sequence(4)][data...]

    A router-id or a sequence of zero is one we were not given: pack_body fills it for the
    session it is sent on, the router-id of our OPEN and the next sequence for it.
    """

    HAS_ROUTERID: ClassVar[bool] = True
    ROUTERID_OFFSET: ClassVar[int] = OperationalFamily.FAMILY_SIZE
    SEQUENCE_OFFSET: ClassVar[int] = ROUTERID_OFFSET + 4
    DATA_OFFSET: ClassVar[int] = SEQUENCE_OFFSET + 4
    SEQUENCE_MAX: ClassVar[int] = 0xFFFFFFFF

    # the last sequence we sent, per router-id
    _sequence_sent: ClassVar[dict[RouterID, int]] = {}

    @classmethod
    def pack_sequenced(
        cls, what: int, afi: int | AFI, safi: int | SAFI, routerid: RouterID | None, sequence: int | None, data: bytes
    ) -> bytes:
        routerid_packed = bytes(routerid.pack_ip()) if routerid else bytes(4)
        payload = cls.pack_family(afi, safi) + routerid_packed + pack('!L', sequence or 0) + data
        return cls.pack_operational(what, payload)

    @property
    def routerid(self) -> RouterID | None:
        packed = self.payload[self.ROUTERID_OFFSET : self.SEQUENCE_OFFSET]
        if not any(packed):
            return None
        return RouterID.unpack_routerid(packed)

    @property
    def sequence(self) -> int | None:
        sequence: int = unpack('!L', self.payload[self.SEQUENCE_OFFSET : self.DATA_OFFSET])[0]
        return sequence or None

    @property
    def data(self) -> Buffer:
        return self.payload[self.DATA_OFFSET :]

    @classmethod
    def next_sequence(cls, routerid: RouterID) -> int:
        """The sequence of the next message sent as `routerid`, never zero, which means unset."""
        sequence = cls._sequence_sent.get(routerid, 0) % cls.SEQUENCE_MAX + 1
        cls._sequence_sent[routerid] = sequence
        assert 0 < sequence <= cls.SEQUENCE_MAX
        return sequence

    def pack_body(self, negotiated: Negotiated) -> Buffer:
        routerid = self.routerid
        sequence = self.sequence
        if routerid is not None and sequence is not None:
            return self._packed
        if routerid is None:
            if negotiated.sent_open is None:
                raise ValueError('Cannot pack operational message: no routerid and negotiated.sent_open is None')
            routerid = negotiated.sent_open.router_id
        if sequence is None:
            sequence = self.next_sequence(routerid)
        return self.pack_sequenced(self.what, self.afi, self.safi, routerid, sequence, bytes(self.data))


# =========================================================================== NS


class NS:
    """Not Satisfied (NS) error response codes.

    Sent when an operational request cannot be fulfilled.
    Each nested class represents a specific error condition.
    """

    MALFORMED = 0x01  # Request TLV Malformed
    UNSUPPORTED = 0x02  # TLV Unsupported for this neighbor
    MAXIMUM = 0x03  # Max query frequency exceeded
    PROHIBITED = 0x04  # Administratively prohibited
    BUSY = 0x05  # Busy
    NOTFOUND = 0x06  # Not Found

    class NS(OperationalFamily):
        SUBTYPE_ID: ClassVar[int] = Operational.SUBTYPE.NS
        IS_FAULT: ClassVar[bool] = True
        ERROR_SUBCODE: ClassVar[bytes]

        @classmethod
        def make_ns(cls, afi: int | AFI, safi: int | SAFI, sequence: Buffer) -> 'NS.NS':
            payload = cls.pack_family(afi, safi) + bytes(sequence) + cls.ERROR_SUBCODE
            return cls(cls.pack_operational(cls.SUBTYPE_ID, payload))

        def extensive(self) -> str:
            return f'operational NS {self.NAME} {self.afi}/{self.safi}'

    class Malformed(NS):
        NAME: ClassVar[str] = 'NS malformed'
        ERROR_SUBCODE: ClassVar[bytes] = b'\x00\x01'  # pack('!H',MALFORMED)

    class Unsupported(NS):
        NAME: ClassVar[str] = 'NS unsupported'
        ERROR_SUBCODE: ClassVar[bytes] = b'\x00\x02'  # pack('!H',UNSUPPORTED)

    class Maximum(NS):
        NAME: ClassVar[str] = 'NS maximum'
        ERROR_SUBCODE: ClassVar[bytes] = b'\x00\x03'  # pack('!H',MAXIMUM)

    class Prohibited(NS):
        NAME: ClassVar[str] = 'NS prohibited'
        ERROR_SUBCODE: ClassVar[bytes] = b'\x00\x04'  # pack('!H',PROHIBITED)

    class Busy(NS):
        NAME: ClassVar[str] = 'NS busy'
        ERROR_SUBCODE: ClassVar[bytes] = b'\x00\x05'  # pack('!H',BUSY)

    class NotFound(NS):
        NAME: ClassVar[str] = 'NS notfound'
        ERROR_SUBCODE: ClassVar[bytes] = b'\x00\x06'  # pack('!H',NOTFOUND)


# ===================================================================== Advisory


class Advisory:
    """Advisory messages for operator notifications.

    ADM (Advisory Demand Message): One-time notification
    ASM (Advisory Static Message): Persistent notification
    """

    class Advisory(OperationalFamily):
        CATEGORY: ClassVar[str] = 'advisory'

        @classmethod
        def make_advisory(
            cls, afi: int | AFI, safi: int | SAFI, advisory: str | bytes, routerid: RouterID | None = None
        ) -> 'Advisory.Advisory':
            utf8 = advisory if isinstance(advisory, bytes) else advisory.encode('utf-8')
            if len(utf8) > MAX_ADVISORY:
                utf8 = utf8[: MAX_ADVISORY - 3] + b'...'
            return cls(cls.pack_operational(cls.SUBTYPE_ID, cls.pack_family(afi, safi) + utf8))

        @classmethod
        def from_values(cls, values: dict[str, Any]) -> 'OperationalFamily':
            return cls.make_advisory(values['afi'], values['safi'], values['advisory'], values.get('routerid'))

        def extensive(self) -> str:
            return f'operational {self.NAME} afi {self.afi} safi {self.safi} "{bytes(self.data).hex()}"'

    @Operational.register_operational
    class ADM(Advisory):
        NAME: ClassVar[str] = 'ADM'
        SUBTYPE_ID: ClassVar[int] = Operational.SUBTYPE.ADM

    @Operational.register_operational
    class ASM(Advisory):
        NAME: ClassVar[str] = 'ASM'
        SUBTYPE_ID: ClassVar[int] = Operational.SUBTYPE.ASM


# ======================================================================== Query


class Query:
    """Prefix count query messages.

    RPCQ: Reachable Prefix Count Query (RIB-In)
    APCQ: Adj-RIB-Out Prefix Count Query
    LPCQ: Loc-RIB Prefix Count Query
    """

    class Query(SequencedOperationalFamily):
        CATEGORY: ClassVar[str] = 'query'

        @classmethod
        def make_query(
            cls, afi: int | AFI, safi: int | SAFI, routerid: RouterID | None, sequence: int | None
        ) -> 'Query.Query':
            return cls(cls.pack_sequenced(cls.SUBTYPE_ID, afi, safi, routerid, sequence, b''))

        @classmethod
        def from_values(cls, values: dict[str, Any]) -> 'OperationalFamily':
            return cls.make_query(values['afi'], values['safi'], values.get('routerid'), values['sequence'])

        def extensive(self) -> str:
            if self.routerid and self.sequence:
                return f'operational {self.NAME} afi {self.afi} safi {self.safi} router-id {self.routerid} sequence {self.sequence}'
            return f'operational {self.NAME} afi {self.afi} safi {self.safi}'

    @Operational.register_operational
    class RPCQ(Query):
        NAME: ClassVar[str] = 'RPCQ'
        SUBTYPE_ID: ClassVar[int] = Operational.SUBTYPE.RPCQ

    @Operational.register_operational
    class APCQ(Query):
        NAME: ClassVar[str] = 'APCQ'
        SUBTYPE_ID: ClassVar[int] = Operational.SUBTYPE.APCQ

    @Operational.register_operational
    class LPCQ(Query):
        NAME: ClassVar[str] = 'LPCQ'
        SUBTYPE_ID: ClassVar[int] = Operational.SUBTYPE.LPCQ


# ===================================================================== Response


class Response:
    """Prefix count response messages.

    RPCP: Reachable Prefix Count Reply (RIB-In)
    APCP: Adj-RIB-Out Prefix Count Reply
    LPCP: Loc-RIB Prefix Count Reply
    """

    class Counter(SequencedOperationalFamily):
        CATEGORY: ClassVar[str] = 'counter'
        COUNTER_SIZE: ClassVar[int] = 4

        @classmethod
        def make_counter(
            cls, afi: int | AFI, safi: int | SAFI, routerid: RouterID | None, sequence: int | None, counter: int
        ) -> 'Response.Counter':
            return cls(cls.pack_sequenced(cls.SUBTYPE_ID, afi, safi, routerid, sequence, pack('!L', counter)))

        @classmethod
        def from_values(cls, values: dict[str, Any]) -> 'OperationalFamily':
            return cls.make_counter(
                values['afi'], values['safi'], values.get('routerid'), values['sequence'], values['counter']
            )

        @property
        def counter(self) -> int:
            counter: int = unpack('!L', self.data[: self.COUNTER_SIZE])[0]
            return counter

        def extensive(self) -> str:
            if self.routerid and self.sequence:
                return f'operational {self.NAME} afi {self.afi} safi {self.safi} router-id {self.routerid} sequence {self.sequence} counter {self.counter}'
            return f'operational {self.NAME} afi {self.afi} safi {self.safi} counter {self.counter}'

    @Operational.register_operational
    class RPCP(Counter):
        NAME: ClassVar[str] = 'RPCP'
        SUBTYPE_ID: ClassVar[int] = Operational.SUBTYPE.RPCP

    @Operational.register_operational
    class APCP(Counter):
        NAME: ClassVar[str] = 'APCP'
        SUBTYPE_ID: ClassVar[int] = Operational.SUBTYPE.APCP

    @Operational.register_operational
    class LPCP(Counter):
        NAME: ClassVar[str] = 'LPCP'
        SUBTYPE_ID: ClassVar[int] = Operational.SUBTYPE.LPCP


# ========================================================================= Dump


class Dump:
    """Dump messages for debugging (DUP, MUP, MUD - not yet implemented)."""

    pass
