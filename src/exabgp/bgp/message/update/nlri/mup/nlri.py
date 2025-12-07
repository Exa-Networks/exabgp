"""nlri.py

Created by Takeru Hayasaka on 2023-01-21.
Copyright (c) 2023 BBSakura Networks Inc. All rights reserved.
"""

from __future__ import annotations

from struct import pack
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI, Family
from exabgp.util.types import Buffer

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

    # Registry for MUP route types, keyed by "archtype:code" string
    # Values are MUP subclasses that implement unpack_mup_route classmethod
    registered_mup: ClassVar[dict[str, type[MUP]]] = dict()

    # NEED to be defined in the subclasses
    ARCHTYPE: ClassVar[int] = 0
    CODE: ClassVar[int] = 0
    NAME: ClassVar[str] = 'Unknown'
    SHORT_NAME: ClassVar[str] = 'unknown'

    def __init__(self, afi: AFI) -> None:
        """Create a MUP NLRI.

        Note: action defaults to UNSET, set after creation (announce/withdraw).
        """
        NLRI.__init__(self, afi, SAFI.mup)
        self._packed: bytes = b''

    def __hash__(self) -> int:
        return hash('{}:{}:{}:{}:{}'.format(self.afi, self.safi, self.ARCHTYPE, self.CODE, self._packed.hex()))

    def __len__(self) -> int:
        return len(self._packed) + 2

    def __eq__(self, other: Any) -> bool:
        return NLRI.__eq__(self, other) and self.CODE == other.CODE

    def __str__(self) -> str:
        # Use the class's own SHORT_NAME since it's defined on all MUP subclasses
        return 'mup:{}:{}'.format(
            self.SHORT_NAME.lower(),
            '0x' + ''.join('{:02x}'.format(_) for _ in self._packed),
        )

    def __repr__(self) -> str:
        return str(self)

    def feedback(self, action: Action) -> str:
        return ''

    def _prefix(self) -> str:
        return 'mup:{}:'.format(self.SHORT_NAME.lower())

    def _pack_nlri_simple(self) -> bytes:
        """Pack NLRI without negotiated-dependent data (no addpath)."""
        return pack('!BHB', self.ARCHTYPE, self.CODE, len(self._packed)) + self._packed

    def pack_nlri(self, negotiated: Negotiated) -> Buffer:
        # RFC 7911 ADD-PATH is possible for MUP but not yet implemented
        # TODO: implement addpath support when negotiated.addpath.send(self.afi, SAFI.mup)
        return self._pack_nlri_simple()

    def index(self) -> Buffer:
        return bytes(Family.index(self)) + self._pack_nlri_simple()

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
    def register_mup_route(cls, klass: type[MUP]) -> type[MUP]:
        """Register a MUP route type subclass by its ARCHTYPE:CODE key."""
        key = '{}:{}'.format(klass.ARCHTYPE, klass.CODE)
        if key in cls.registered_mup:
            raise RuntimeError('only one MUP registration allowed')
        cls.registered_mup[key] = klass
        return klass

    @classmethod
    def unpack_nlri(
        cls, afi: AFI, safi: SAFI, data: Buffer, action: Action, addpath: Any, negotiated: Negotiated
    ) -> tuple[NLRI, Buffer]:
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
        if key in cls.registered_mup:
            registered_cls = cls.registered_mup[key]
            # Subclass processes trimmed data; we return (mup, remaining from original buffer)
            # Call unpack_mup_route if defined, otherwise fall back to unpack_nlri
            mup_instance, _ = registered_cls.unpack_nlri(afi, safi, bytes(data[4:end]), action, addpath, negotiated)
            return mup_instance, data[end:]

        # Generic MUP for unrecognized route types
        mup = GenericMUP(afi, arch, code, bytes(data[4:end]))
        mup.action = action
        mup.addpath = addpath
        return mup, data[end:]

    def _raw(self) -> str:
        return ''.join('{:02X}'.format(_) for _ in self._pack_nlri_simple())


class GenericMUP(MUP):
    """Generic MUP for unrecognized route types."""

    # Instance variables for arch/code since GenericMUP can have any values
    __slots__ = ('_arch', '_code')

    def __init__(self, afi: AFI, arch: int, code: int, packed: bytes) -> None:
        MUP.__init__(self, afi)
        self._arch = arch
        self._code = code
        self._packed = packed

    @property
    def ARCHTYPE(self) -> int:  # type: ignore[override]
        return self._arch

    @property
    def CODE(self) -> int:  # type: ignore[override]
        return self._code

    def json(self, compact: bool | None = None) -> str:
        return '{ "arch": %d, "code": %d, "raw": "%s" }' % (self.ARCHTYPE, self.CODE, self._raw())
