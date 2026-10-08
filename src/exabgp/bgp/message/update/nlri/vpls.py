"""vpls.py

Created by Nikita Shirokov on 2014-06-16.
Copyright (c) 2014-2017 Nikita Shirokov. All rights reserved.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations


from struct import pack, unpack
from typing import Any, ClassVar, Self, TYPE_CHECKING

from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated
    from exabgp.bgp.message.update.nlri.settings import VPLSSettings

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.notification import NLRIDiscard, Notify
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.protocol.family import AFI, SAFI, Family


# RD(8) + endpoint(2) + offset(2) + size(2) + base(3), the length the two byte header announces
VPLS_PAYLOAD_SIZE = 17
# RD(8) + VSI-ID(4), the BGP-AD NLRI of RFC 6074 3.2.2, which shares the family (section 7)
BGP_AD_PAYLOAD_SIZE = 12


class VPLSBase(NLRI):
    """VPLS NLRI using packed-bytes-first pattern.

    _packed stores wire format:
    [length(2)][RD(8)][endpoint(2)][offset(2)][size(2)][base(3)] = 19 bytes

    AFI/SAFI set via Family parent class in __init__.

    Factory methods:
    - make_vpls(): Create from components (packs to wire format)
    - from_settings(): Create from VPLSSettings (validates before creation)
    - unpack_nlri(): Create from wire bytes (network receive path)
    """

    __slots__ = ()

    # Wire format length (including 2-byte length prefix)
    PACKED_LENGTH: ClassVar[int] = 19  # length(2) + RD(8) + endpoint(2) + offset(2) + size(2) + base(3)

    def __init__(self, packed: Buffer) -> None:
        """Create a VPLS NLRI from packed wire-format bytes.

        Args:
            packed: 19 bytes: [length(2)][RD(8)][endpoint(2)][offset(2)][size(2)][base(3)]

        Note: action defaults to UNSET, set after creation (announce/withdraw).
        """
        NLRI.__init__(self, AFI.l2vpn, SAFI.vpls)
        self._packed: Buffer = bytes(packed)  # Ensure bytes for storage

    @classmethod
    def make_vpls(
        cls,
        rd: RouteDistinguisher,
        endpoint: int,
        base: int,
        offset: int,
        size: int,
        addpath: PathInfo = PathInfo.DISABLED,
    ) -> Self:
        """Factory method to create a VPLS NLRI from components.

        Args:
            rd: Route Distinguisher
            endpoint: VPLS endpoint (VE ID)
            base: Label base
            offset: Label block offset
            size: Label block size
            addpath: ADD-PATH path identifier

        Returns:
            New VPLS instance with packed wire format
        """
        packed = (
            b'\x00\x11'  # length prefix (17)
            + bytes(rd.pack_rd())
            + pack('!HHH', endpoint, offset, size)
            + pack('!L', (base << 4) | 0x1)[1:]  # 3 bytes with BOS bit
        )
        instance = cls(packed)
        instance.addpath = addpath
        return instance

    @classmethod
    def from_settings(cls, settings: 'VPLSSettings') -> Self:
        """Create VPLS NLRI from validated settings.

        This factory method validates settings and creates an immutable VPLS
        instance. Use this for deferred construction where all values are
        collected during parsing, then validated and used to create the NLRI.

        Args:
            settings: VPLSSettings with all required fields set

        Returns:
            Immutable VPLS NLRI instance

        Raises:
            ValueError: If settings validation fails
        """
        error = settings.validate()
        if error:
            raise ValueError(error)

        # Delegate to make_vpls which creates packed bytes
        assert settings.rd is not None
        assert settings.endpoint is not None
        assert settings.base is not None
        assert settings.offset is not None
        assert settings.size is not None

        instance = cls.make_vpls(
            rd=settings.rd,
            endpoint=settings.endpoint,
            base=settings.base,
            offset=settings.offset,
            size=settings.size,
        )
        # Note: settings.nexthop is now passed to Route, not stored in NLRI
        return instance

    @property
    def rd(self) -> RouteDistinguisher:
        """Route Distinguisher - unpacked from wire bytes."""
        return RouteDistinguisher(self._packed[2:10])

    @property
    def endpoint(self) -> int:
        """VPLS endpoint (VE ID) - unpacked from wire bytes."""
        return int(unpack('!H', bytes(self._packed[10:12]))[0])

    @property
    def offset(self) -> int:
        """Label block offset - unpacked from wire bytes."""
        return int(unpack('!H', bytes(self._packed[12:14]))[0])

    @property
    def block_size(self) -> int:
        """Label block size - unpacked from wire bytes."""
        return int(unpack('!H', bytes(self._packed[14:16]))[0])

    @property
    def base(self) -> int:
        """Label base - unpacked from wire bytes."""
        return int(unpack('!L', b'\x00' + bytes(self._packed[16:19]))[0]) >> 4

    def feedback(self, action: Action) -> str:
        """Validate VPLS NLRI-specific constraints.

        Note: nexthop validation is handled by Route.feedback(), not here.
        """
        # Size consistency check (for routes received from wire or created with invalid values)
        if self.base > (0xFFFFF - self.block_size):  # 20 bits, 3 bytes
            return 'vpls nlri size inconsistency'
        return ''

    def pack_nlri(self, negotiated: Negotiated) -> Buffer:
        # RFC 7911 ADD-PATH is possible for VPLS but not yet implemented
        # TODO: implement addpath support when negotiated.addpath.send(AFI.l2vpn, SAFI.vpls)
        assert len(self._packed) == VPLS_PAYLOAD_SIZE + 2, 'a VPLS NLRI is its two byte length and seventeen bytes'
        return self._packed

    def index(self) -> bytes:
        return Family.index(self) + self._packed

    def json(self, announced: bool = True, compact: bool | None = None) -> str:
        # Note: The unique key for VPLS is the combination of all fields (rd, endpoint, base, offset, size).
        # This matches what index() returns for UPDATE withdraw matching.
        content = ', '.join(
            [
                self.rd.json(),
                '"endpoint": {}'.format(self.endpoint),
                '"base": {}'.format(self.base),
                '"offset": {}'.format(self.offset),
                '"size": {}'.format(self.block_size),
            ],
        )
        return '{{ {} }}'.format(content)

    def extensive(self) -> str:
        return 'vpls{} endpoint {} base {} offset {} size {}'.format(
            self.rd,
            self.endpoint,
            self.base,
            self.offset,
            self.block_size,
        )

    def __str__(self) -> str:
        return self.extensive()

    def _fresh(self) -> Self:
        return type(self)(self._packed)

    def __copy__(self) -> Self:
        new = self._fresh()
        # Family/NLRI slots - _packed is in NLRI slots
        self._copy_nlri_slots(new)
        return new

    def __deepcopy__(self, memo: dict[Any, Any]) -> Self:
        new = self._fresh()
        memo[id(self)] = new
        # Family/NLRI slots - _packed is in NLRI slots and is immutable bytes
        self._deepcopy_nlri_slots(new, memo)
        return new

    @staticmethod
    def _short_nlri(length: int, path_size: int) -> NLRIDiscard:
        """An NLRI shorter than RFC 4761's, stepped over rather than a session reset.

        RFC 6074 7: BGP-AD and VPLS-BGP share AFI 25 / SAFI 65 and "the NLRI length must be
        used as a demultiplexer".  Twelve octets are a BGP-AD NLRI (RD and VSI-ID), which
        exabgp does not implement, and refusing it with a Notify reset any session to a
        peer running both.  Its two octet length frames it, as it frames any other short
        NLRI, so the NLRI after it in the same attribute is still read.
        """
        if length == BGP_AD_PAYLOAD_SIZE:
            detail = 'l2vpn vpls NLRI of %d octets is a BGP-AD NLRI (RFC 6074), not decoded' % length
        else:
            detail = 'l2vpn vpls length is %d, it needs at least %d' % (length, VPLS_PAYLOAD_SIZE)
        discard = NLRIDiscard(detail)
        discard.skip = path_size + 2 + length
        assert discard.skip > 0, 'a discarded NLRI is stepped over, not re-read'
        return discard

    @classmethod
    def unpack_nlri(
        cls, afi: AFI, safi: SAFI, data: Buffer, action: Action, addpath: bool, negotiated: Negotiated
    ) -> tuple[Self, Buffer]:
        # RFC 7911 3: with ADD-PATH negotiated the peer puts a four byte Path
        # Identifier in front of every NLRI of this family, and it has to come off
        # before the NLRI is read.
        path_info, data = NLRI.consume_path_information(data, addpath)
        # Wire format: length(2) + RD(8) + endpoint(2) + offset(2) + size(2) + base(3) = 19 bytes
        if len(data) < 2:
            raise Notify.short(3, 10, 'VPLS NLRI', 2, len(data))
        (length,) = unpack('!H', bytes(data[0:2]))
        # what follows this NLRI is the next one: an MP_REACH_NLRI carries as many as fit,
        # so only a length running past the data is inconsistent, and only that one leaves
        # nothing to step over: it is checked first, so it stays a session reset.
        if len(data) < length + 2:
            raise Notify(3, 10, 'l2vpn vpls message length is not consistent with encoded bgp')
        # every accessor reads a fixed offset inside the first VPLS_PAYLOAD_SIZE bytes, so
        # what has to hold is that they are there. Demanding the length be exactly that
        # refused a longer NLRI which this decoder has always read correctly, and which a
        # peer is entitled to send: RFC 4761 gives the layout, not a maximum, and a sender
        # may carry a field we do not know about yet.
        if length < VPLS_PAYLOAD_SIZE:
            raise cls._short_nlri(length, PathInfo.LENGTH if addpath else 0)

        # Only what the accessors read is kept, so what is packed back is what was
        # understood. The length prefix is rewritten rather than copied, because it has to
        # describe what is kept: copying a longer length verbatim left pack_nlri emitting
        # nineteen bytes behind a header announcing more, which this decoder refuses and so
        # would the peer we re-advertised it to. It also split index(), which is these
        # bytes, between two NLRI a withdraw cannot tell apart.
        packed = pack('!H', VPLS_PAYLOAD_SIZE) + bytes(data[2 : 2 + VPLS_PAYLOAD_SIZE])
        nlri = cls(packed)
        nlri.addpath = path_info
        return nlri, data[2 + length :]


class VPLS(VPLSBase):
    """The registered form of VPLSBase, which holds the code.

    The split is not architectural: mutmut does not mutate the methods of a decorated class,
    and every decoder here carries a register decorator, so the code which parses what a
    peer sends was the one part of this tree mutation testing could not see. Keeping the
    body in an undecorated base and registering an empty subclass puts it back in reach.

    __slots__ is empty on purpose. Without it every instance would grow a __dict__,
    which is the memory the packed-bytes-first work went to some trouble to avoid.
    """

    __slots__ = ()


NLRI.register(AFI.l2vpn, SAFI.vpls)(VPLS)
