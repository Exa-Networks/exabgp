"""nlri.py

Created by Takeru Hayasaka on 2023-01-21.
Copyright (c) 2023 BBSakura Networks Inc. All rights reserved.
"""

from __future__ import annotations

from typing import Any, Callable, ClassVar, TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.protocol.ip import IP
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import NLRIDiscard, Notify
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI, Family
from exabgp.util.types import Buffer

# https://datatracker.ietf.org/doc/html/draft-mpmz-bess-mup-safi-05

# +-----------------------------------+
# |    Architecture Type (1 octet)    |
# +-----------------------------------+
# |       Route Type (2 octets)       |
# +-----------------------------------+
# |         Length (1 octet)          |
# +-----------------------------------+
# |  Route Type specific (variable)   |
# +-----------------------------------+


class MUP(NLRI):
    # MUP has no additional instance attributes beyond NLRI base class
    __slots__ = ()

    # Registry for MUP route types, keyed by "archtype:code" string
    # Values are MUP subclasses that implement unpack_mup_route classmethod
    registered_mup: ClassVar[dict[str, type[MUP]]] = dict()

    # Set by the decorator
    ARCHTYPE: ClassVar[int] = 0
    CODE: ClassVar[int] = 0
    NAME: ClassVar[str] = 'Unknown'
    SHORT_NAME: ClassVar[str] = 'unknown'

    def v4_text(self, nexthop: IP | None = None) -> str:
        """As 5.x wrote it: the route without its next-hop."""
        return self.extensive()

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

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MUP):
            return NotImplemented
        return NLRI.__eq__(self, other) and self.CODE == other.CODE

    # written out: mypyc fails to derive __ne__ from __eq__ for the subclasses. The operator,
    # not a call to __eq__, so NotImplemented is answered the way Python answers it.
    def __ne__(self, other: object) -> bool:
        return not self == other

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
        # RFC 7911 ADD-PATH is possible for MUP but not yet implemented, so MUP is kept out
        # of Capabilities._ADD_PATH: a peer must never be told to expect a path identifier
        # this returns without. Add it back to that list in the same change as the encoder.
        # Wire format: [arch_type(1)][route_type(2)][length(1)][payload] - _packed includes header
        return self._packed

    def index(self) -> bytes:
        # Wire format: [family][arch_type(1)][route_type(2)][length(1)][payload] - _packed includes header
        return bytes(Family.index(self)) + self._packed

    def __copy__(self) -> 'MUP':
        new = self._fresh()
        # NLRI slots (includes Family slots: _afi, _safi)
        self._copy_nlri_slots(new)
        # MUP has empty __slots__ - nothing else to copy
        return new

    def __deepcopy__(self, memo: dict[Any, Any]) -> 'MUP':
        new = self._fresh()
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

    # [arch(1)][code(2)][length(1)][RD(8)] before the route type specific fields
    PAYLOAD_OFFSET: ClassVar[int] = 12

    @classmethod
    def check_length(cls, data: Buffer, minimum: int) -> None:
        """Reject wire data too short for this route type.

        Args:
            data: Complete wire format, header included
            minimum: Smallest acceptable size, header included

        Raises:
            Notify: If the data is shorter than the minimum
        """
        if len(data) < minimum:
            raise Notify.short(3, 10, f'{cls.NAME} MUP NLRI', minimum, len(data))

    @classmethod
    def unpack_nlri(
        cls, afi: AFI, safi: SAFI, data: Buffer, action: Action, addpath: bool, negotiated: Negotiated
    ) -> tuple[NLRI, Buffer]:
        original_size = len(data)
        # RFC 7911 3: with ADD-PATH negotiated the peer puts a four byte Path
        # Identifier in front of every NLRI of this family, and it has to come off
        # before the NLRI is read.
        path_info, data = NLRI.consume_path_information(data, addpath)
        # MUP NLRI: arch_type(1) + route_type(2) + length(1) + route_data(length)
        if len(data) < 4:
            raise Notify.short(3, 10, 'MUP NLRI', 4, len(data))
        arch = data[0]
        code = int.from_bytes(data[1:3], 'big')
        length = data[3]

        # arch and code byte size is 4 byte
        end = length + 4
        if len(data) < end:
            raise Notify.short(3, 10, 'MUP NLRI', end, len(data))

        key = '{}:{}'.format(arch, code)
        if key not in cls.registered_mup:
            # draft-mpmz-bess-mup-safi-05 3.1: "Any other Route Types MUST be silently
            # ignored upon a receipt if a BGP speaker supports only 3gpp-5G architecture
            # type".  A route type is defined for an architecture, so an unknown pair of the
            # two is one exabgp cannot read.  It reached the RIB and the API as raw octets.
            # The skip logs it, which the section allows: "MAY log an error".
            ignored = NLRIDiscard(f'MUP architecture {arch} route type {code} is not one exabgp supports')
            ignored.skip = original_size - len(data) + end
            raise ignored
        registered_cls = cls.registered_mup[key]
        # Pass complete wire format (including 4-byte header) to subclass
        # the path identifier is already off, so the subclass must not look for one
        try:
            mup_instance, _ = registered_cls.unpack_nlri(afi, safi, data[0:end], action, False, negotiated)
        except Notify as error:
            # draft-mpmz-bess-mup-safi-05 3.1.1 to 3.1.4: a malformed route type body
            # is "Treat-as-withdraw", and "A BGP speaker MUST skip such NLRIs and
            # continue processing of rest of the Update message".  The Length checked
            # above says where the next NLRI starts, so only this one goes; a Length
            # which does not fit, refused above, leaves nowhere to continue from.
            framed = NLRIDiscard(error.detail)
            framed.skip = original_size - len(data) + end
            assert framed.skip > 0, 'a discarded NLRI is stepped over, not re-read'
            raise framed from error
        mup_instance.addpath = path_info
        return mup_instance, data[end:]

    def _raw(self) -> str:
        # _packed includes 4-byte header
        return ''.join('{:02X}'.format(_) for _ in self._packed)


NLRI.register(AFI.ipv6, SAFI.mup)(MUP)
NLRI.register(AFI.ipv4, SAFI.mup)(MUP)
