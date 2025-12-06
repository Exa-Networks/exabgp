"""nlri.py

Created by Takeru Hayasaka on 2023-01-21.
Copyright (c) 2023 BBSakura Networks Inc. All rights reserved.
"""

from __future__ import annotations

from collections.abc import Buffer
from struct import pack
from typing import TYPE_CHECKING, Any, ClassVar, Type

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.protocol.family import Family
from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.nlri import NLRI

# https://datatracker.ietf.org/doc/draft-mpmz-bess-mup-safi/02/

# +-----------------------------------+
# |    Architecture Type (1 octet)    |
# +-----------------------------------+
# |       Route Type (2 octets)       |
# +-----------------------------------+
# |         Length (1 octet)          |
# +-----------------------------------+
# |  Route Type specific (variable)   |
# +-----------------------------------+


@NLRI.register(AFI.ipv4, SAFI.mup)
@NLRI.register(AFI.ipv6, SAFI.mup)
class MUP(NLRI):
    # MUP has no additional instance attributes beyond NLRI base class
    __slots__ = ()

    registered: ClassVar[dict[str, Type[MUP]]] = dict()

    # NEED to be defined in the subclasses
    ARCHTYPE: ClassVar[int] = 0
    CODE: ClassVar[int] = 0
    NAME: ClassVar[str] = 'Unknown'
    SHORT_NAME: ClassVar[str] = 'unknown'

    def __init__(self, afi: AFI, action: Action = Action.ANNOUNCE) -> None:
        NLRI.__init__(self, afi, SAFI.mup, action)
        self._packed: bytes = b''

    def __hash__(self) -> int:
        return hash('{}:{}:{}:{}:{}'.format(self.afi, self.safi, self.ARCHTYPE, self.CODE, self._packed.hex()))

    def __len__(self) -> int:
        return len(self._packed) + 2

    def __eq__(self, other: Any) -> bool:
        return NLRI.__eq__(self, other) and self.CODE == other.CODE

    def __str__(self) -> str:
        return 'mup:{}:{}'.format(
            self.registered.get(self.CODE, self).SHORT_NAME.lower(),  # type: ignore[call-overload]
            '0x' + ''.join('{:02x}'.format(_) for _ in self._packed),
        )

    def __repr__(self) -> str:
        return str(self)

    def feedback(self, action: int) -> None:
        return None

    def _prefix(self) -> str:
        return 'mup:{}:'.format(self.registered.get(self.CODE, self).SHORT_NAME.lower())  # type: ignore[call-overload]

    def _pack_nlri_simple(self) -> bytes:
        """Pack NLRI without negotiated-dependent data (no addpath)."""
        return pack('!BHB', self.ARCHTYPE, self.CODE, len(self._packed)) + self._packed

    def pack_nlri(self, negotiated: Negotiated) -> bytes:
        # RFC 7911 ADD-PATH is possible for MUP but not yet implemented
        # TODO: implement addpath support when negotiated.addpath.send(self.afi, SAFI.mup)
        return self._pack_nlri_simple()

    def index(self) -> bytes:
        return Family.index(self) + self._pack_nlri_simple()

    def __copy__(self) -> 'MUP':
        new = self.__class__.__new__(self.__class__)
        # Family slots (afi/safi)
        new.afi = self.afi
        new.safi = self.safi
        # NLRI slots
        self._copy_nlri_slots(new)
        # MUP has empty __slots__ - nothing else to copy
        return new

    def __deepcopy__(self, memo: dict[Any, Any]) -> 'MUP':
        new = self.__class__.__new__(self.__class__)
        memo[id(self)] = new
        # Family slots (afi/safi) - immutable enums
        new.afi = self.afi
        new.safi = self.safi
        # NLRI slots
        self._deepcopy_nlri_slots(new, memo)
        # MUP has empty __slots__ - nothing else to copy
        return new

    @classmethod
    def register(cls, klass: Type[MUP]) -> Type[MUP]:  # type: ignore[override]
        key = '{}:{}'.format(klass.ARCHTYPE, klass.CODE)
        if key in cls.registered:
            raise RuntimeError('only one Mup registration allowed')
        cls.registered[key] = klass
        return klass

    @classmethod
    def unpack_nlri(
        cls, afi: AFI, safi: SAFI, bgp: Buffer, action: Action, addpath: Any, negotiated: Negotiated
    ) -> tuple[MUP, Buffer]:
        data = memoryview(bgp) if not isinstance(bgp, memoryview) else bgp
        # MUP NLRI: arch_type(1) + route_type(2) + length(1) + route_data(length)
        if len(data) < 4:
            raise Notify(3, 10, f'MUP NLRI too short: need at least 4 bytes, got {len(data)}')
        arch = data[0]
        code = int.from_bytes(bytes(data[1:3]), 'big')
        length = data[3]

        # arch and code byte size is 4 byte
        end = length + 4
        if len(data) < end:
            raise Notify(3, 10, f'MUP NLRI truncated: need {end} bytes, got {len(data)}')

        key = '{}:{}'.format(arch, code)
        if key in cls.registered:
            klass = cls.registered[key].unpack_mup_route(bytes(data[4:end]), afi)  # type: ignore[attr-defined]
        else:
            klass = GenericMUP(arch, afi, code, bytes(data[4:end]))  # type: ignore[arg-type]
        klass.CODE = code
        klass.action = action
        klass.addpath = addpath

        return klass, data[end:]

    def _raw(self) -> str:
        return ''.join('{:02X}'.format(_) for _ in self._pack_nlri_simple())


class GenericMUP(MUP):
    def __init__(self, afi: AFI, arch: int, code: int, packed: bytes) -> None:
        MUP.__init__(self, afi)
        self.ARCHTYPE = arch  # type: ignore[misc]
        self.CODE = code  # type: ignore[misc]
        self._pack(packed)

    def _pack(self, packed: bytes | None = None) -> bytes:
        if self._packed:
            return self._packed

        if packed:
            self._packed = packed
            return packed

        return b''

    def json(self, compact: bool | None = None) -> str:
        return '{ "arch": %d, "code": %d, "raw": "%s" }' % (self.ARCHTYPE, self.CODE, self._raw())
