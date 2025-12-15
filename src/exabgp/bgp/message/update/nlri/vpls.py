"""vpls.py

Created by Nikita Shirokov on 2014-06-16.
Copyright (c) 2014-2017 Nikita Shirokov. All rights reserved.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack, unpack
from typing import TYPE_CHECKING, Any

from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated
    from exabgp.bgp.message.update.nlri.settings import VPLSSettings

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.protocol.family import AFI, SAFI, Family


@NLRI.register(AFI.l2vpn, SAFI.vpls)
class VPLS(NLRI):
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
    PACKED_LENGTH = 19  # length(2) + RD(8) + endpoint(2) + offset(2) + size(2) + base(3)

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
        action: Action = Action.UNSET,
        addpath: PathInfo = PathInfo.DISABLED,
    ) -> 'VPLS':
        """Factory method to create a VPLS NLRI from components.

        Args:
            rd: Route Distinguisher
            endpoint: VPLS endpoint (VE ID)
            base: Label base
            offset: Label block offset
            size: Label block size
            action: Route action (ANNOUNCE or WITHDRAW)
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
        instance.action = action
        instance.addpath = addpath
        return instance

    @classmethod
    def from_settings(cls, settings: 'VPLSSettings') -> 'VPLS':
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
            action=settings.action,
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
        return unpack('!H', self._packed[10:12])[0]

    @property
    def offset(self) -> int:
        """Label block offset - unpacked from wire bytes."""
        return unpack('!H', self._packed[12:14])[0]

    @property
    def size(self) -> int:
        """Label block size - unpacked from wire bytes."""
        return unpack('!H', self._packed[14:16])[0]

    @property
    def base(self) -> int:
        """Label base - unpacked from wire bytes."""
        return unpack('!L', b'\x00' + self._packed[16:19])[0] >> 4

    def feedback(self, action: Action) -> str:
        """Validate VPLS NLRI-specific constraints.

        Note: nexthop validation is handled by Route.feedback(), not here.
        """
        # Size consistency check (for routes received from wire or created with invalid values)
        if self.base > (0xFFFFF - self.size):  # 20 bits, 3 bytes
            return 'vpls nlri size inconsistency'
        return ''

    def pack_nlri(self, negotiated: Negotiated) -> Buffer:
        # RFC 7911 ADD-PATH is possible for VPLS but not yet implemented
        # TODO: implement addpath support when negotiated.addpath.send(AFI.l2vpn, SAFI.vpls)
        return self._packed

    def index(self) -> bytes:
        return Family.index(self) + self._packed

    def json(self, compact: bool | None = None) -> str:
        # Note: The unique key for VPLS is the combination of all fields (rd, endpoint, base, offset, size).
        # This matches what index() returns for UPDATE withdraw matching.
        content = ', '.join(
            [
                self.rd.json(),
                '"endpoint": {}'.format(self.endpoint),
                '"base": {}'.format(self.base),
                '"offset": {}'.format(self.offset),
                '"size": {}'.format(self.size),
            ],
        )
        return '{{ {} }}'.format(content)

    def extensive(self) -> str:
        return 'vpls{} endpoint {} base {} offset {} size {}'.format(
            self.rd,
            self.endpoint,
            self.base,
            self.offset,
            self.size,
        )

    def __str__(self) -> str:
        return self.extensive()

    def __copy__(self) -> 'VPLS':
        new = self.__class__.__new__(self.__class__)
        # Family/NLRI slots - _packed is in NLRI slots
        self._copy_nlri_slots(new)
        return new

    def __deepcopy__(self, memo: dict[Any, Any]) -> 'VPLS':
        new = self.__class__.__new__(self.__class__)
        memo[id(self)] = new
        # Family/NLRI slots - _packed is in NLRI slots and is immutable bytes
        self._deepcopy_nlri_slots(new, memo)
        return new

    @classmethod
    def unpack_nlri(
        cls, afi: AFI, safi: SAFI, data: Buffer, action: Action, addpath: Any, negotiated: Negotiated
    ) -> tuple[VPLS, Buffer]:
        # Wire format: length(2) + RD(8) + endpoint(2) + offset(2) + size(2) + base(3) = 19 bytes
        if len(data) < 2:
            raise Notify(3, 10, f'VPLS NLRI too short: need at least 2 bytes, got {len(data)}')
        (length,) = unpack('!H', bytes(data[0:2]))
        if len(data) != length + 2:
            raise Notify(3, 10, 'l2vpn vpls message length is not consistent with encoded bgp')

        # Store wire format directly
        packed = bytes(data[0 : 2 + length])
        nlri = cls(packed)
        nlri.action = action
        return nlri, data[2 + length :]
