"""nlri.py

Created by Takeru Hayasaka on 2023-01-21.
Copyright (c) 2023 BBSakura Networks Inc. All rights reserved.
"""

from __future__ import annotations

from struct import pack
from typing import TYPE_CHECKING, Any, ClassVar, Dict, Optional, Type

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.bgp.message import Action
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
    registered: ClassVar[Dict[str, Type[MUP]]] = dict()

    # NEED to be defined in the subclasses
    ARCHTYPE: ClassVar[int] = 0
    CODE: ClassVar[int] = 0
    NAME: ClassVar[str] = 'Unknown'
    SHORT_NAME: ClassVar[str] = 'unknown'

    def __init__(self, afi: AFI, action: Action = Action.ANNOUNCE) -> None:
        NLRI.__init__(self, afi, SAFI.mup, action)
        self._packed: bytes = b''

    def __hash__(self) -> int:
        return hash('{}:{}:{}:{}:{}'.format(self.afi, self.safi, self.ARCHTYPE, self.CODE, self._packed))  # type: ignore[str-bytes-safe]

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

    def feedback(self, action: Action) -> str:
        return ''

    def _prefix(self) -> str:
        return 'mup:{}:'.format(self.registered.get(self.CODE, self).SHORT_NAME.lower())  # type: ignore[call-overload]

    def pack_nlri(self, negotiated: Negotiated = None) -> bytes:  # type: ignore[assignment]
        return pack('!BHB', self.ARCHTYPE, self.CODE, len(self._packed)) + self._packed

    @classmethod
    def register(cls, klass: Type[MUP]) -> Type[MUP]:
        key = '{}:{}'.format(klass.ARCHTYPE, klass.CODE)
        if key in cls.registered:
            raise RuntimeError('only one Mup registration allowed')
        cls.registered[key] = klass
        return klass

    @classmethod
    def unpack_nlri(
        cls, afi: AFI, safi: SAFI, bgp: bytes, action: Action, addpath: Any, negotiated: Negotiated
    ) -> tuple[MUP, bytes]:
        arch = bgp[0]
        code = int.from_bytes(bgp[1:3], 'big')
        length = bgp[3]

        # arch and code byte size is 4 byte
        end = length + 4
        key = '{}:{}'.format(arch, code)
        if key in cls.registered:
            klass = cls.registered[key].unpack(bgp[4:end], afi)
        else:
            klass = GenericMUP(arch, afi, code, bgp[4:end])  # type: ignore[arg-type]
        klass.CODE = code
        klass.action = action
        klass.addpath = addpath

        return klass, bgp[end:]

    def _raw(self) -> str:
        return ''.join('{:02X}'.format(_) for _ in self.pack_nlri())


class GenericMUP(MUP):
    def __init__(self, afi: AFI, arch: int, code: int, packed: bytes) -> None:
        MUP.__init__(self, afi)
        self.ARCHTYPE = arch
        self.CODE = code
        self._pack(packed)

    def _pack(self, packed: Optional[bytes] = None) -> bytes:
        if self._packed:
            return self._packed

        if packed:
            self._packed = packed
            return packed

        return b''

    def json(self, compact: Optional[bool] = None) -> str:
        return '{ "arch": %d, "code": %d, "raw": "%s" }' % (self.ARCHTYPE, self.CODE, self._raw())
