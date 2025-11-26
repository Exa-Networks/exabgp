"""operational.py

Created by Thomas Mangin on 2013-09-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import sys
from struct import pack
from struct import unpack
from typing import ClassVar, Dict, Tuple, Type as TypingType, TypeVar, TYPE_CHECKING

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.bgp.message.open.routerid import RouterID
from exabgp.bgp.message.message import Message

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

# TypeVar for register decorator - preserves the specific subclass type
_T = TypeVar('_T', bound='Operational')

# ========================================================================= Type
#

MAX_ADVISORY = 2048  # 2K


class Type(int):
    def pack(self) -> bytes:
        return pack('!H', self)

    def extract(self) -> list[bytes]:
        return [pack('!H', self)]

    def __len__(self) -> int:
        return 2

    def __str__(self) -> str:
        raise NotImplementedError('Type.__str__ must be implemented by subclasses')


# ================================================================== Operational
#


@Message.register
class Operational(Message):
    ID = Message.CODE.OPERATIONAL
    TYPE = bytes([Message.CODE.OPERATIONAL])

    registered_operational: ClassVar[Dict[int, Tuple[str, TypingType['Operational']]]] = dict()

    has_family: ClassVar[bool] = False
    has_routerid: ClassVar[bool] = False
    is_fault: ClassVar[bool] = False

    # really this should be called ID if not for the naming conflict
    class CODE:
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

    # XXX: FIXME: should be upper case
    name: ClassVar[str] = ''
    category: ClassVar[str] = ''
    code: ClassVar[int] = CODE.NOP  # type: ignore[assignment]  # shadows Message.code() method intentionally

    def __init__(self, what: int) -> None:
        Message.__init__(self)
        self.what: Type = Type(what)

    def _message(self, data: bytes) -> bytes:
        return Message._message(self, self.what.pack() + pack('!H', len(data)) + data)

    def __str__(self) -> str:
        return self.extensive()

    def extensive(self) -> str:
        return f'operational {self.name}'

    @staticmethod
    def register(klass: TypingType[_T]) -> TypingType[_T]:  # type: ignore[override]
        # klass.code is an int, not Message.code() method - the attr shadows the parent method
        Operational.registered_operational[klass.code] = (klass.category, klass)
        return klass

    @classmethod
    def unpack_message(cls, data: bytes, negotiated: Negotiated) -> Operational | None:  # pylint: disable=W0613
        what = Type(unpack('!H', data[0:2])[0])
        length = unpack('!H', data[2:4])[0]

        decode, klass = cls.registered_operational.get(what, ('unknown', None))

        if decode == 'advisory':
            afi = unpack('!H', data[4:6])[0]
            safi = data[6]
            data = data[7 : length + 4]
            return klass(afi, safi, data)  # type: ignore[call-arg,misc]
        if decode == 'query':
            afi = unpack('!H', data[4:6])[0]
            safi = data[6]
            routerid = RouterID.unpack_routerid(data[7:11])
            sequence = unpack('!L', data[11:15])[0]
            return klass(afi, safi, routerid, sequence)  # type: ignore[call-arg,misc]
        if decode == 'counter':
            afi = unpack('!H', data[4:6])[0]
            safi = data[6]
            routerid = RouterID.unpack_routerid(data[7:11])
            sequence = unpack('!L', data[11:15])[0]
            counter = unpack('!L', data[15:19])[0]
            return klass(afi, safi, routerid, sequence, counter)  # type: ignore[call-arg,misc]
        sys.stdout.write('ignoring ATM this kind of message\n')
        return None


# ============================================================ OperationalFamily
#


class OperationalFamily(Operational):
    has_family: ClassVar[bool] = True

    def __init__(self, what: int, afi: int | AFI, safi: int | SAFI, data: bytes = b'') -> None:
        Operational.__init__(self, what)
        self.afi: AFI = AFI.create(afi)
        self.safi: SAFI = SAFI.create(safi)
        self.data: bytes = data

    def family(self) -> Tuple[AFI, SAFI]:
        return (self.afi, self.safi)

    def _message(self, data: bytes) -> bytes:
        return Operational._message(self, self.afi.pack_afi() + self.safi.pack_safi() + data)

    def pack_message(self, negotiated: Negotiated) -> bytes:
        return self._message(self.data)


# =================================================== SequencedOperationalFamily
#


class SequencedOperationalFamily(OperationalFamily):
    __sequence_number: ClassVar[Dict[RouterID | None, int]] = {}
    has_routerid: ClassVar[bool] = True

    def __init__(
        self,
        what: int,
        afi: int | AFI,
        safi: int | SAFI,
        routerid: RouterID | None,
        sequence: int | None,
        data: bytes = b'',
    ) -> None:
        OperationalFamily.__init__(self, what, afi, safi, data)
        self.routerid: RouterID | None = routerid if routerid else None
        self.sequence: int | None = sequence if sequence else None
        self._sequence: int | None = self.sequence
        self._routerid: RouterID | None = self.routerid

    def pack_message(self, negotiated: Negotiated) -> bytes:
        if self.routerid:
            self.sent_routerid: RouterID = self.routerid
        elif negotiated.sent_open is not None:
            self.sent_routerid = negotiated.sent_open.router_id
        else:
            raise ValueError('Cannot pack operational message: no routerid and negotiated.sent_open is None')
        if self.sequence is None:
            self.sent_sequence: int = (self.__sequence_number.setdefault(self.routerid, 0) + 1) % 0xFFFFFFFF
            self.__sequence_number[self.sent_routerid] = self.sent_sequence
        else:
            self.sent_sequence = self.sequence

        return self._message(self.sent_routerid.pack_ip() + pack('!L', self.sent_sequence) + self.data)


# =========================================================================== NS
#


class NS:
    MALFORMED = 0x01  # Request TLV Malformed
    UNSUPPORTED = 0x02  # TLV Unsupported for this neighbor
    MAXIMUM = 0x03  # Max query frequency exceeded
    PROHIBITED = 0x04  # Administratively prohibited
    BUSY = 0x05  # Busy
    NOTFOUND = 0x06  # Not Found

    class _NS(OperationalFamily):
        is_fault: ClassVar[bool] = True
        ERROR_SUBCODE: ClassVar[bytes]

        def __init__(self, afi: int | AFI, safi: int | SAFI, sequence: bytes) -> None:
            OperationalFamily.__init__(self, Operational.CODE.NS, afi, safi, sequence + self.ERROR_SUBCODE)

        def extensive(self) -> str:
            return f'operational NS {self.name} {self.afi}/{self.safi}'

    class Malformed(_NS):
        name: ClassVar[str] = 'NS malformed'
        ERROR_SUBCODE: ClassVar[bytes] = b'\x00\x01'  # pack('!H',MALFORMED)

    class Unsupported(_NS):
        name: ClassVar[str] = 'NS unsupported'
        ERROR_SUBCODE: ClassVar[bytes] = b'\x00\x02'  # pack('!H',UNSUPPORTED)

    class Maximum(_NS):
        name: ClassVar[str] = 'NS maximum'
        ERROR_SUBCODE: ClassVar[bytes] = b'\x00\x03'  # pack('!H',MAXIMUM)

    class Prohibited(_NS):
        name: ClassVar[str] = 'NS prohibited'
        ERROR_SUBCODE: ClassVar[bytes] = b'\x00\x04'  # pack('!H',PROHIBITED)

    class Busy(_NS):
        name: ClassVar[str] = 'NS busy'
        ERROR_SUBCODE: ClassVar[bytes] = b'\x00\x05'  # pack('!H',BUSY)

    class NotFound(_NS):
        name: ClassVar[str] = 'NS notfound'
        ERROR_SUBCODE: ClassVar[bytes] = b'\x00\x06'  # pack('!H',NOTFOUND)


# ===================================================================== Advisory
#


class Advisory:
    class _Advisory(OperationalFamily):
        category: ClassVar[str] = 'advisory'

        def extensive(self) -> str:
            return f'operational {self.name} afi {self.afi} safi {self.safi} "{self.data.hex()}"'

    @Operational.register
    class ADM(_Advisory):
        name: ClassVar[str] = 'ADM'
        code: ClassVar[int] = Operational.CODE.ADM  # type: ignore[assignment]

        def __init__(
            self,
            afi: int | AFI,
            safi: int | SAFI,
            advisory: str | bytes,
            routerid: RouterID | None = None,
        ) -> None:
            # Handle both string and bytes input
            if isinstance(advisory, bytes):
                utf8 = advisory
            else:
                utf8 = advisory.encode('utf-8')
            if len(utf8) > MAX_ADVISORY:
                utf8 = utf8[: MAX_ADVISORY - 3] + b'...'
            Advisory._Advisory.__init__(self, Operational.CODE.ADM, afi, safi, utf8)

    @Operational.register
    class ASM(_Advisory):
        name: ClassVar[str] = 'ASM'
        code: ClassVar[int] = Operational.CODE.ASM  # type: ignore[assignment]

        def __init__(
            self,
            afi: int | AFI,
            safi: int | SAFI,
            advisory: str | bytes,
            routerid: RouterID | None = None,
        ) -> None:
            # Handle both string and bytes input
            if isinstance(advisory, bytes):
                utf8 = advisory
            else:
                utf8 = advisory.encode('utf-8')
            if len(utf8) > MAX_ADVISORY:
                utf8 = utf8[: MAX_ADVISORY - 3] + b'...'
            Advisory._Advisory.__init__(self, Operational.CODE.ASM, afi, safi, utf8)


# ======================================================================== Query
#


class Query:
    class _Query(SequencedOperationalFamily):
        category: ClassVar[str] = 'query'
        code: ClassVar[int]  # type: ignore[assignment]

        def __init__(self, afi: int | AFI, safi: int | SAFI, routerid: RouterID | None, sequence: int | None) -> None:
            SequencedOperationalFamily.__init__(self, self.code, afi, safi, routerid, sequence)

        def extensive(self) -> str:
            if self._routerid and self._sequence:
                return f'operational {self.name} afi {self.afi} safi {self.safi} router-id {self._routerid} sequence {self._sequence}'
            return f'operational {self.name} afi {self.afi} safi {self.safi}'

    @Operational.register
    class RPCQ(_Query):
        name: ClassVar[str] = 'RPCQ'
        code: ClassVar[int] = Operational.CODE.RPCQ

    @Operational.register
    class APCQ(_Query):
        name: ClassVar[str] = 'APCQ'
        code: ClassVar[int] = Operational.CODE.APCQ

    @Operational.register
    class LPCQ(_Query):
        name: ClassVar[str] = 'LPCQ'
        code: ClassVar[int] = Operational.CODE.LPCQ


# ===================================================================== Response
#


class Response:
    class _Counter(SequencedOperationalFamily):
        category: ClassVar[str] = 'counter'
        code: ClassVar[int]  # type: ignore[assignment]

        def __init__(
            self,
            afi: int | AFI,
            safi: int | SAFI,
            routerid: RouterID | None,
            sequence: int | None,
            counter: int,
        ) -> None:
            self.counter: int = counter
            SequencedOperationalFamily.__init__(self, self.code, afi, safi, routerid, sequence, pack('!L', counter))

        def extensive(self) -> str:
            if self._routerid and self._sequence:
                return f'operational {self.name} afi {self.afi} safi {self.safi} router-id {self._routerid} sequence {self._sequence} counter {self.counter}'
            return f'operational {self.name} afi {self.afi} safi {self.safi} counter {self.counter}'

    @Operational.register
    class RPCP(_Counter):
        name: ClassVar[str] = 'RPCP'
        code: ClassVar[int] = Operational.CODE.RPCP

    @Operational.register
    class APCP(_Counter):
        name: ClassVar[str] = 'APCP'
        code: ClassVar[int] = Operational.CODE.APCP

    @Operational.register
    class LPCP(_Counter):
        name: ClassVar[str] = 'LPCP'
        code: ClassVar[int] = Operational.CODE.LPCP


# ========================================================================= Dump
#


class Dump:
    pass
