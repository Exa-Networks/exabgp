"""vpls.py

Created by Nikita Shirokov on 2014-06-16.
Copyright (c) 2014-2017 Nikita Shirokov. All rights reserved.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.util.types import Buffer
from struct import unpack
from struct import pack
from typing import Any, ClassVar, Iterator, cast, TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.protocol.family import Family
from exabgp.protocol.ip import IP
from exabgp.bgp.message.action import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo


def _unique() -> Iterator[int]:
    value = 0
    while True:
        yield value
        value += 1


unique: Iterator[int] = _unique()


@NLRI.register(AFI.l2vpn, SAFI.vpls)
class VPLS(NLRI):
    """VPLS NLRI using packed-bytes-first pattern.

    This class uses class-level AFI/SAFI constants to minimize per-instance
    storage, preparing for eventual buffer protocol sharing.

    Two modes:
    - Packed mode: created from wire bytes, fields unpacked on property access
    - Builder mode: created empty for configuration, fields assigned via setters
    """

    __slots__ = ('_rd', '_endpoint', '_base', '_offset', '_size_value', 'unique')

    # Fixed AFI/SAFI for this single-family NLRI type (class attributes shadow slots)
    afi: ClassVar[AFI] = AFI.l2vpn
    safi: ClassVar[SAFI] = SAFI.vpls

    # Wire format length (excluding 2-byte length prefix)
    PACKED_LENGTH = 17  # RD(8) + endpoint(2) + offset(2) + size(2) + base(3)

    def __init__(self, packed: bytes | None) -> None:
        """Create a VPLS NLRI from packed wire-format bytes or empty for configuration.

        Args:
            packed: 17 bytes wire format (RD + endpoint + offset + size + base), or None for builder mode
        """
        # Family.__init__ detects afi/safi properties and skips setting them
        NLRI.__init__(self, AFI.l2vpn, SAFI.vpls)
        self.action = Action.ANNOUNCE
        self.nexthop = IP.NoNextHop

        self._packed: bytes | None = packed

        # Builder mode storage (used when _packed is None)
        self._rd: RouteDistinguisher | None = None
        self._endpoint: int | None = None
        self._base: int | None = None
        self._offset: int | None = None
        self._size_value: int | None = None  # '_size' would shadow Family.size ClassVar

        self.unique = next(unique)

    @classmethod
    def make_vpls(
        cls,
        rd: RouteDistinguisher,
        endpoint: int,
        base: int,
        offset: int,
        size: int,
        action: Action = Action.ANNOUNCE,
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
            rd.pack_rd()
            + pack('!HHH', endpoint, offset, size)
            + pack('!L', (base << 4) | 0x1)[1:]  # 3 bytes with BOS bit
        )
        instance = cls(packed)
        instance.action = action
        instance.addpath = addpath
        return instance

    @classmethod
    def make_empty(
        cls,
        action: Action = Action.ANNOUNCE,
        addpath: PathInfo = PathInfo.DISABLED,
    ) -> 'VPLS':
        """Factory method for configuration - creates empty VPLS for field assignment.

        Args:
            action: Route action (ANNOUNCE or WITHDRAW)
            addpath: ADD-PATH path identifier

        Returns:
            New VPLS instance in builder mode (packed=None)
        """
        instance = cls(None)
        instance.action = action
        instance.addpath = addpath
        return instance

    @property
    def rd(self) -> RouteDistinguisher | None:
        """Route Distinguisher - unpacked from wire bytes or from builder storage."""
        if self._packed is not None:
            return RouteDistinguisher(self._packed[0:8])
        return self._rd

    @rd.setter
    def rd(self, value: RouteDistinguisher | None) -> None:
        """Set Route Distinguisher (builder mode only)."""
        self._rd = value
        self._packed = None  # Switch to builder mode

    @property
    def endpoint(self) -> int | None:
        """VPLS endpoint (VE ID) - unpacked from wire bytes or from builder storage."""
        if self._packed is not None:
            value: int = unpack('!H', self._packed[8:10])[0]
            return value
        return self._endpoint

    @endpoint.setter
    def endpoint(self, value: int | None) -> None:
        """Set VPLS endpoint (builder mode only)."""
        self._endpoint = value
        self._packed = None  # Switch to builder mode

    @property
    def offset(self) -> int | None:
        """Label block offset - unpacked from wire bytes or from builder storage."""
        if self._packed is not None:
            value: int = unpack('!H', self._packed[10:12])[0]
            return value
        return self._offset

    @offset.setter
    def offset(self, value: int | None) -> None:
        """Set label block offset (builder mode only)."""
        self._offset = value
        self._packed = None  # Switch to builder mode

    @property
    def size(self) -> int | None:
        """Label block size - unpacked from wire bytes or from builder storage."""
        if self._packed is not None:
            value: int = unpack('!H', self._packed[12:14])[0]
            return value
        return self._size_value

    @size.setter
    def size(self, value: int | None) -> None:
        """Set label block size (builder mode only)."""
        self._size_value = value
        self._packed = None  # Switch to builder mode

    @property
    def base(self) -> int | None:
        """Label base - unpacked from wire bytes or from builder storage."""
        if self._packed is not None:
            value: int = unpack('!L', b'\x00' + self._packed[14:17])[0] >> 4
            return value
        return self._base

    @base.setter
    def base(self, value: int | None) -> None:
        """Set label base (builder mode only)."""
        self._base = value
        self._packed = None  # Switch to builder mode

    def feedback(self, action: Action) -> str:
        if self.nexthop is IP.NoNextHop and action == Action.ANNOUNCE:
            return 'vpls nlri next-hop missing'
        if self.endpoint is None:
            return 'vpls nlri endpoint missing'
        if self.base is None:
            return 'vpls nlri base missing'
        if self.offset is None:
            return 'vpls nlri offset missing'
        if self.size is None:
            return 'vpls nlri size missing'
        if self.rd is None:
            return 'vpls nlri route-distinguisher missing'
        # At this point base and size are known to be non-None (checked above)
        # Cast needed because self.size shadows Family.size ClassVar (dict type)
        size = cast(int, self.size)
        if self.base > (0xFFFFF - size):  # 20 bits, 3 bytes
            return 'vpls nlri size inconsistency'
        return ''

    def assign(self, name: str, value: Any) -> None:
        setattr(self, name, value)

    def _pack_nlri_simple(self) -> bytes:
        """Pack NLRI without negotiated-dependent data (no addpath)."""
        if self._packed is not None:
            # Packed mode - use stored wire bytes
            return b'\x00\x11' + self._packed
        else:
            # Builder mode - pack from individual fields
            return (
                b'\x00\x11'  # pack('!H',17)
                + self._rd.pack_rd()
                + pack('!HHH', self._endpoint, self._offset, self._size_value)
                + pack('!L', (self._base << 4) | 0x1)[1:]  # setting the bottom of stack
            )

    def pack_nlri(self, negotiated: Negotiated) -> bytes:
        # RFC 7911 ADD-PATH is possible for VPLS but not yet implemented
        # TODO: implement addpath support when negotiated.addpath.send(AFI.l2vpn, SAFI.vpls)
        return self._pack_nlri_simple()

    def index(self) -> bytes:
        return Family.index(self) + self._pack_nlri_simple()

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
        return 'vpls{} endpoint {} base {} offset {} size {} {}'.format(
            self.rd,
            self.endpoint,
            self.base,
            self.offset,
            self.size,
            '' if self.nexthop is IP.NoNextHop else 'next-hop {}'.format(self.nexthop),
        )

    def __str__(self) -> str:
        return self.extensive()

    def __copy__(self) -> 'VPLS':
        new = self.__class__.__new__(self.__class__)
        # Family/NLRI slots (afi/safi are class-level)
        self._copy_nlri_slots(new)
        # VPLS slots
        new._rd = self._rd
        new._endpoint = self._endpoint
        new._base = self._base
        new._offset = self._offset
        new._size_value = self._size_value
        new.unique = self.unique
        return new

    def __deepcopy__(self, memo: dict[Any, Any]) -> 'VPLS':
        from copy import deepcopy

        new = self.__class__.__new__(self.__class__)
        memo[id(self)] = new
        # Family/NLRI slots (afi/safi are class-level)
        self._deepcopy_nlri_slots(new, memo)
        # VPLS slots
        new._rd = deepcopy(self._rd, memo) if self._rd else None
        new._endpoint = self._endpoint
        new._base = self._base
        new._offset = self._offset
        new._size_value = self._size_value
        new.unique = self.unique
        return new

    @classmethod
    def unpack_nlri(
        cls, afi: AFI, safi: SAFI, bgp: Buffer, action: Action, addpath: Any, negotiated: Negotiated
    ) -> tuple[VPLS, Buffer]:
        data = memoryview(bgp) if not isinstance(bgp, memoryview) else bgp
        # Wire format: length(2) + RD(8) + endpoint(2) + offset(2) + size(2) + base(3) = 19 bytes
        if len(data) < 2:
            raise Notify(3, 10, f'VPLS NLRI too short: need at least 2 bytes, got {len(data)}')
        (length,) = unpack('!H', bytes(data[0:2]))
        if len(data) != length + 2:
            raise Notify(3, 10, 'l2vpn vpls message length is not consistent with encoded bgp')

        # Create VPLS from packed wire format (17 bytes, excluding length prefix)
        packed = bytes(data[2 : 2 + length])
        nlri = cls(packed)
        nlri.action = action
        return nlri, data[2 + length :]
