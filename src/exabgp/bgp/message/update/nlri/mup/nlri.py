"""nlri.py

Created by Takeru Hayasaka on 2023-01-21.
Copyright (c) 2023 BBSakura Networks Inc. All rights reserved.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, ClassVar

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

    # Set by decorator, override in GenericMUP
    ARCHTYPE: ClassVar[int] = 0
    CODE: ClassVar[int] = 0
    NAME: ClassVar[str] = 'Unknown'
    SHORT_NAME: ClassVar[str] = 'unknown'

    def __init__(self, afi: AFI) -> None:
        """Create a MUP NLRI.

        Note: action defaults to UNSET, set after creation (announce/withdraw).
        """
        NLRI.__init__(self, afi, SAFI.mup)
        self._packed: Buffer = b''

    def __hash__(self) -> int:
        return hash('{}:{}:{}:{}:{}'.format(self.afi, self.safi, self.ARCHTYPE, self.CODE, self._packed.hex()))

    def __len__(self) -> int:
        # _packed includes 4-byte header: arch_type(1) + route_type(2) + length(1)
        return len(self._packed)

    def __eq__(self, other: Any) -> bool:
        return NLRI.__eq__(self, other) and self.CODE == other.CODE

    def __str__(self) -> str:
        # Use the class's own SHORT_NAME since it's defined on all MUP subclasses
        # _packed includes 4-byte header, payload starts at offset 4
        payload = self._packed[4:] if len(self._packed) > 4 else b''
        return 'mup:{}:{}'.format(
            self.SHORT_NAME.lower(),
            '0x' + ''.join('{:02x}'.format(_) for _ in payload),
        )

    def __repr__(self) -> str:
        return str(self)

    def feedback(self, action: Action) -> str:
        # Nexthop validation handled by Route.feedback()
        return ''

    def _prefix(self) -> str:
        return 'mup:{}:'.format(self.SHORT_NAME.lower())

    def pack_nlri(self, negotiated: Negotiated) -> Buffer:
        # RFC 7911 ADD-PATH is possible for MUP but not yet implemented
        # TODO: implement addpath support when negotiated.addpath.send(self.afi, SAFI.mup)
        # Wire format: [arch_type(1)][route_type(2)][length(1)][payload] - _packed includes header
        return self._packed

    def index(self) -> bytes:
        # Wire format: [family][arch_type(1)][route_type(2)][length(1)][payload] - _packed includes header
        return bytes(Family.index(self)) + self._packed

    def __copy__(self) -> 'MUP':
        new = self.__class__.__new__(self.__class__)
        # NLRI slots (includes Family slots: _afi, _safi)
        self._copy_nlri_slots(new)
        # MUP has empty __slots__ - nothing else to copy
        return new

    def __deepcopy__(self, memo: dict[Any, Any]) -> 'MUP':
        new = self.__class__.__new__(self.__class__)
        memo[id(self)] = new
        # NLRI slots (includes Family slots: _afi, _safi)
        self._deepcopy_nlri_slots(new, memo)
        # MUP has empty __slots__ - nothing else to copy
        return new

    @classmethod
    def register_mup_route(cls, archtype: int, code: int) -> Callable[[type[MUP]], type[MUP]]:
        """Register a MUP route type subclass by its archtype:code key."""

        def decorator(klass: type[MUP]) -> type[MUP]:
            # Set class attributes
            klass.ARCHTYPE = archtype
            klass.CODE = code
            # Register
            key = f'{archtype}:{code}'
            if key in cls.registered_mup:
                raise RuntimeError('only one MUP registration allowed')
            cls.registered_mup[key] = klass
            return klass

        return decorator

    @classmethod
    def unpack_nlri(
        cls, afi: AFI, safi: SAFI, data: Buffer, action: Action, addpath: Any, negotiated: Negotiated
    ) -> tuple[NLRI, Buffer]:
        # MUP NLRI: arch_type(1) + route_type(2) + length(1) + route_data(length)
        if len(data) < 4:
            raise Notify(3, 10, f'MUP NLRI too short: need at least 4 bytes, got {len(data)}')
        arch = data[0]
        code = int.from_bytes(data[1:3], 'big')
        length = data[3]

        # arch and code byte size is 4 byte
        end = length + 4
        if len(data) < end:
            raise Notify(3, 10, f'MUP NLRI truncated: need {end} bytes, got {len(data)}')

        key = '{}:{}'.format(arch, code)
        if key in cls.registered_mup:
            registered_cls = cls.registered_mup[key]
            # Pass complete wire format (including 4-byte header) to subclass
            mup_instance, _ = registered_cls.unpack_nlri(afi, safi, data[0:end], action, addpath, negotiated)
            return mup_instance, data[end:]

        # Generic MUP for unrecognized route types - pass complete wire format
        mup = GenericMUP(afi, data[0:end])
        mup.addpath = addpath
        return mup, data[end:]

    def _raw(self) -> str:
        # _packed includes 4-byte header
        return ''.join('{:02X}'.format(_) for _ in self._packed)


class GenericMUP(MUP):
    """Generic MUP for unrecognized route types."""

    # No additional slots - arch/code extracted from _packed on demand
    __slots__ = ()

    def __init__(self, afi: AFI, packed: Buffer) -> None:
        """Create GenericMUP with complete wire format.

        Args:
            afi: Address family
            packed: Complete wire format including 4-byte header [arch(1)][code(2)][length(1)][payload]
        """
        MUP.__init__(self, afi)
        self._packed = packed

    @property
    def ARCHTYPE(self) -> int:
        # Extract from packed header on demand
        return self._packed[0]

    @property
    def CODE(self) -> int:
        # Extract from packed header on demand
        return int.from_bytes(self._packed[1:3], 'big')

    def json(self, compact: bool | None = None) -> str:
        return '{ "arch": %d, "code": %d, "raw": "%s" }' % (self.ARCHTYPE, self.CODE, self._raw())
