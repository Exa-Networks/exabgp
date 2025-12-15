"""inet.py

Created by Thomas Mangin on 2014-06-27.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)

RFC References:
===============

RFC 4271 - A Border Gateway Protocol 4 (BGP-4)
https://www.rfc-editor.org/rfc/rfc4271.html

    Section 4.3 - UPDATE Message Format:
    The base NLRI format for IPv4 unicast/multicast routes in the
    UPDATE message NLRI field (after path attributes):

        +---------------------------+
        |   Length (1 octet)        |  <- Prefix length in BITS
        +---------------------------+
        |   Prefix (variable)       |  <- ceiling(Length/8) bytes
        +---------------------------+

    Multiple NLRI can be packed consecutively in the UPDATE.

RFC 4760 - Multiprotocol Extensions for BGP-4
https://www.rfc-editor.org/rfc/rfc4760.html

    Enables BGP to carry routing information for multiple address families.
    Uses MP_REACH_NLRI (type 14) and MP_UNREACH_NLRI (type 15) attributes.

    Key AFI/SAFI values for INET:
        AFI 1 (IPv4), SAFI 1 (unicast)  - IPv4 unicast
        AFI 1 (IPv4), SAFI 2 (multicast) - IPv4 multicast
        AFI 2 (IPv6), SAFI 1 (unicast)  - IPv6 unicast
        AFI 2 (IPv6), SAFI 2 (multicast) - IPv6 multicast

RFC 7911 - Advertisement of Multiple Paths in BGP (ADD-PATH)
https://www.rfc-editor.org/rfc/rfc7911.html

    Adds a 4-byte Path Identifier before each NLRI to allow
    advertising multiple paths for the same prefix:

        +---------------------------+
        |   Path ID (4 octets)      |  <- Only if ADD-PATH negotiated
        +---------------------------+
        |   Length (1 octet)        |
        +---------------------------+
        |   Prefix (variable)       |
        +---------------------------+

Wire Format (_packed):
=====================
    This class stores ONLY the NLRI payload bytes (not BGP message framing).

    _packed stores: [mask_byte][truncated_ip_bytes...]
    - This is the CIDR portion only (same as CIDR class)
    - path_info, nexthop stored separately (not in _packed)
    - labels, rd are None for base INET (subclasses override)

    Note: path_info (ADD-PATH) is parsed separately during unpack and
    stored in self.path_info. It is NOT included in _packed.

Class Hierarchy:
===============
    INET (this class) - base for unicast/multicast
      └── Label (label.py) - adds MPLS label stack (RFC 3107)
            └── IPVPN (ipvpn.py) - adds Route Distinguisher (RFC 4364)
"""

from __future__ import annotations

from struct import unpack
from typing import TYPE_CHECKING, Any

from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated
    from exabgp.bgp.message.update.nlri.settings import INETSettings

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier import Labels, PathInfo, RouteDistinguisher
from exabgp.protocol.family import AFI, SAFI, Family
from exabgp.protocol.ip import IP

# INET NLRI label constants (RFC 3107)
LABEL_SIZE_BITS: int = 24  # Each MPLS label is 24 bits (3 bytes)
LABEL_WITHDRAW_VALUE: int = 0x800000  # Special label value for route withdrawal
LABEL_NEXTHOP_VALUE: int = 0x000000  # Special label value indicating next-hop
LABEL_BOTTOM_OF_STACK_BIT: int = 1  # Bottom of stack bit in label

# AddPath path-info size
PATH_INFO_SIZE: int = 4  # Path Identifier is 4 bytes (RFC 7911)


@NLRI.register(AFI.ipv4, SAFI.unicast)
@NLRI.register(AFI.ipv6, SAFI.unicast)
@NLRI.register(AFI.ipv4, SAFI.multicast)
@NLRI.register(AFI.ipv6, SAFI.multicast)
class INET(NLRI):
    """INET NLRI using packed-bytes-first pattern.

    Wire format stored in _packed: [addpath:4?][mask:1][prefix:var]
    - If _has_addpath is True: addpath bytes are at [0:4], mask at [4]
    - If _has_addpath is False: mask is at [0], no addpath bytes

    Properties extract data from _packed lazily:
    - path_info: extracts PathInfo from [0:4] if _has_addpath, else DISABLED
    - cidr: extracts CIDR from [M:] where M = 4 if _has_addpath else 0
    """

    __slots__ = ('_has_addpath', 'labels', 'rd')

    def __init__(self, packed: Buffer, afi: AFI, safi: SAFI = SAFI.unicast, *, has_addpath: bool = False) -> None:
        """Create an INET NLRI from packed wire format bytes.

        Args:
            packed: Wire format bytes [addpath:4?][mask:1][prefix:var]
            afi: Address Family Identifier (required - cannot be reliably inferred)
            safi: Subsequent Address Family Identifier (defaults to unicast)
            has_addpath: If True, packed includes 4-byte path identifier at start

        The packed bytes include the complete wire format:
        - If has_addpath=True: [path_id:4][mask:1][prefix:var]
        - If has_addpath=False: [mask:1][prefix:var]

        Use factory methods (from_cidr, from_settings) when creating INET instances.
        """
        NLRI.__init__(self, afi, safi, Action.UNSET)
        self._packed = packed  # Complete wire format
        self._has_addpath = has_addpath
        self.labels: Labels | None = None
        self.rd: RouteDistinguisher | None = None

    @property
    def _mask_offset(self) -> int:
        """Offset where mask byte starts (0 or 4 depending on AddPath)."""
        return PATH_INFO_SIZE if self._has_addpath else 0

    @property
    def path_info(self) -> PathInfo:
        """Extract PathInfo from wire bytes if AddPath present."""
        if not self._has_addpath:
            return PathInfo.DISABLED
        path_bytes = self._packed[:PATH_INFO_SIZE]
        # Return NOPATH singleton for all-zero path ID
        if path_bytes == b'\x00\x00\x00\x00':
            return PathInfo.NOPATH
        return PathInfo(path_bytes)

    @property
    def cidr(self) -> CIDR:
        """Unpack CIDR from stored wire format bytes."""
        offset = self._mask_offset
        cidr_bytes = self._packed[offset:]
        if self.afi == AFI.ipv4:
            return CIDR.from_ipv4(cidr_bytes)
        return CIDR.from_ipv6(cidr_bytes)

    @classmethod
    def from_cidr(
        cls,
        cidr: CIDR,
        afi: AFI,
        safi: SAFI,
        action: Action = Action.UNSET,
        path_info: PathInfo = PathInfo.DISABLED,
    ) -> 'INET':
        """Factory method to create INET from a CIDR object.

        Args:
            cidr: CIDR prefix
            afi: Address Family Identifier
            safi: Subsequent Address Family Identifier
            action: Route action (ANNOUNCE/WITHDRAW)
            path_info: AddPath path identifier

        Returns:
            New INET instance with wire format in _packed
        """
        # Build wire format: [addpath:4?][mask:1][prefix:var]
        cidr_packed = cidr.pack_nlri()

        # Determine if AddPath should be included
        has_addpath = path_info is not PathInfo.DISABLED
        if has_addpath:
            packed = bytes(path_info.pack_path()) + cidr_packed
        else:
            packed = cidr_packed

        instance = object.__new__(cls)
        NLRI.__init__(instance, afi, safi, action)
        instance._packed = packed
        instance._has_addpath = has_addpath
        instance.labels = None
        instance.rd = None
        return instance

    @classmethod
    def make_route(
        cls,
        afi: AFI,
        safi: SAFI,
        packed: Buffer,
        mask: int,
        action: Action = Action.UNSET,
        path_info: PathInfo = PathInfo.DISABLED,
        nexthop: 'IP | None' = None,
    ) -> 'INET':
        """Factory method to create an INET route.

        Args:
            afi: Address Family Identifier
            safi: Subsequent Address Family Identifier
            packed: Packed IP address bytes (full length)
            mask: Prefix length
            action: Route action (ANNOUNCE/WITHDRAW)
            path_info: AddPath path identifier
            nexthop: Next-hop IP address

        Returns:
            New INET instance
        """
        cidr = CIDR.make_cidr(packed, mask)
        instance = cls.from_cidr(cidr, afi, safi, action, path_info)
        # Note: nexthop parameter is deprecated - nexthop should be stored in Route, not NLRI
        return instance

    @classmethod
    def from_settings(cls, settings: 'INETSettings') -> 'INET':
        """Create INET NLRI from validated settings.

        This factory method validates settings and creates an immutable INET
        instance. Use this for deferred construction where all values are
        collected during parsing, then validated and used to create the NLRI.

        Args:
            settings: INETSettings with all required fields set

        Returns:
            Immutable INET NLRI instance

        Raises:
            ValueError: If settings validation fails
        """
        error = settings.validate()
        if error:
            raise ValueError(error)

        # Assertions for type narrowing after validation
        assert settings.cidr is not None
        assert settings.afi is not None
        assert settings.safi is not None

        instance = cls.from_cidr(
            cidr=settings.cidr,
            afi=settings.afi,
            safi=settings.safi,
            action=settings.action,
            path_info=settings.path_info,
        )
        # Note: settings.nexthop is now passed to Route, not stored in NLRI
        return instance

    def __len__(self) -> int:
        # _packed includes AddPath if present
        return len(self._packed)

    def __str__(self) -> str:
        return self.extensive()

    def __repr__(self) -> str:
        return self.extensive()

    def __hash__(self) -> int:
        # _packed includes AddPath if present; use _has_addpath as discriminator
        # for DISABLED vs actually having no path bytes
        if self._has_addpath:
            return hash(self._packed)
        return hash(b'disabled' + self._packed)

    def __copy__(self) -> 'INET':
        new = self.__class__.__new__(self.__class__)
        # Family slots (afi, safi)
        new.afi = self.afi
        new.safi = self.safi
        # NLRI slots
        self._copy_nlri_slots(new)
        # INET slots
        new._has_addpath = self._has_addpath
        new.labels = self.labels
        new.rd = self.rd
        return new

    def __deepcopy__(self, memo: dict[Any, Any]) -> 'INET':
        from copy import deepcopy

        new = self.__class__.__new__(self.__class__)
        memo[id(self)] = new
        # Family slots (afi, safi) - immutable enums
        new.afi = self.afi
        new.safi = self.safi
        # NLRI slots
        self._deepcopy_nlri_slots(new, memo)
        # INET slots
        new._has_addpath = self._has_addpath  # bool - immutable
        new.labels = deepcopy(self.labels, memo) if self.labels else None
        new.rd = deepcopy(self.rd, memo) if self.rd else None
        return new

    def feedback(self, action: Action) -> str:
        # Nexthop validation handled by Route.feedback()
        return ''

    def pack_nlri(self, negotiated: 'Negotiated') -> bytes:
        """Pack NLRI for wire transmission.

        Handles AddPath based on negotiated capability vs stored format:
        - If negotiated.send=True AND _has_addpath: return _packed directly
        - If negotiated.send=True AND NOT _has_addpath: prepend NOPATH
        - If negotiated.send=False AND _has_addpath: strip AddPath (return from offset 4)
        - If negotiated.send=False AND NOT _has_addpath: return _packed directly
        """
        send_addpath = negotiated.addpath.send(self.afi, self.safi)

        if send_addpath:
            if self._has_addpath:
                return self._packed  # Already has AddPath, return directly
            # Need to prepend NOPATH (4 zero bytes)
            return bytes(PathInfo.NOPATH.pack_path()) + self._packed
        else:
            if self._has_addpath:
                # Strip AddPath bytes (first 4 bytes)
                return self._packed[PATH_INFO_SIZE:]
            return self._packed  # No AddPath in either, return directly

    def index(self) -> bytes:
        """Generate unique index for RIB lookup.

        Includes family, AddPath status, and wire bytes.
        """
        if self._has_addpath:
            # _packed already includes path bytes
            return bytes(Family.index(self)) + self._packed
        # No AddPath - add discriminator to distinguish from has_addpath=True with 0x00000000
        return bytes(Family.index(self)) + b'disabled' + self._packed

    def prefix(self) -> str:
        return '{}{}'.format(self.cidr.prefix(), str(self.path_info))

    def extensive(self) -> str:
        return self.prefix()

    def _internal(self, announced: bool = True) -> list[str]:
        return [self.path_info.json()]

    # The announced feature is not used by ExaBGP, is it by BAGPIPE ?

    # XXX: need to review this API
    def json(self, announced: bool = True, compact: bool = False) -> str:
        internal = ', '.join([_ for _ in self._internal(announced) if _])
        if internal:
            return '{{ "nlri": "{}", {} }}'.format(self.cidr.prefix(), internal)
        if compact:
            return '"{}"'.format(self.cidr.prefix())
        return '{{ "nlri": "{}" }}'.format(self.cidr.prefix())

    @classmethod
    def _pathinfo(cls, data: Buffer, addpath: Any) -> tuple[PathInfo, bytes]:
        if addpath:
            return PathInfo(data[:4]), data[4:]
        return PathInfo.DISABLED, data

    # @classmethod
    # def unpack_inet (cls, afi, safi, data, action, addpath):
    # 	pathinfo, data = cls._pathinfo(data,addpath)
    # 	nlri,data = cls.unpack_range(data,action,addpath)
    # 	nlri.path_info = pathinfo
    # 	return nlri,data

    @classmethod
    def unpack_nlri(
        cls, afi: AFI, safi: SAFI, bgp: Buffer, action: Action, addpath: Any, negotiated: Negotiated
    ) -> tuple[INET, Buffer]:
        data = memoryview(bgp) if not isinstance(bgp, memoryview) else bgp
        # Parse path_info if AddPath is enabled
        if addpath:
            if len(data) <= PATH_INFO_SIZE:
                raise ValueError('Trying to extract path-information but we do not have enough data')
            path_info = PathInfo(bytes(data[:PATH_INFO_SIZE]))
            data = data[PATH_INFO_SIZE:]
        else:
            path_info = PathInfo.DISABLED

        mask = data[0]
        data = data[1:]

        _, rd_size = Family.size.get((afi, safi), (0, 0))
        rd_mask = rd_size * 8

        # Parse labels if present
        labels_list: list[int] | None = None
        if safi.has_label():
            labels_list = []
            while mask - rd_mask >= LABEL_SIZE_BITS:
                label = int(unpack('!L', bytes([0]) + bytes(data[:3]))[0])
                data = data[3:]
                mask -= LABEL_SIZE_BITS  # 3 bytes
                # The last 4 bits are the bottom of Stack
                # The last bit is set for the last label
                labels_list.append(label >> 4)
                # This is a route withdrawal
                if label == LABEL_WITHDRAW_VALUE and action == Action.WITHDRAW:
                    break
                # This is a next-hop
                if label == LABEL_NEXTHOP_VALUE:
                    break
                if label & LABEL_BOTTOM_OF_STACK_BIT:
                    break

        # Parse route distinguisher if present
        rd: RouteDistinguisher | None = None
        if rd_size:
            mask -= rd_mask  # the route distinguisher
            rd = RouteDistinguisher(bytes(data[:rd_size]))
            data = data[rd_size:]

        if mask < 0:
            raise Notify(3, 10, 'invalid length in NLRI prefix')

        if not data and mask:
            raise Notify(3, 10, 'not enough data for the mask provided to decode the NLRI')

        size = CIDR.size(mask)

        if len(data) < size:
            raise Notify(
                3,
                10,
                'could not decode nlri with family %s (AFI %d) %s (SAFI %d)'
                % (AFI(afi), int(afi), SAFI(safi), int(safi)),
            )

        network, data = data[:size], data[size:]

        # Create NLRI from CIDR
        if afi == AFI.ipv4:
            cidr = CIDR.from_ipv4(bytes([mask]) + bytes(network))
        else:
            cidr = CIDR.from_ipv6(bytes([mask]) + bytes(network))

        # Build kwargs for from_cidr - subclasses accept labels and rd
        kwargs: dict[str, Labels | RouteDistinguisher] = {}
        if labels_list is not None:
            kwargs['labels'] = Labels.make_labels(labels_list)
        if rd is not None:
            kwargs['rd'] = rd

        nlri = cls.from_cidr(cidr, afi, safi, action, path_info, **kwargs)
        return nlri, data
