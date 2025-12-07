"""update/__init__.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack, unpack
from typing import TYPE_CHECKING, Generator

from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.message import Message
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute import MPRNLRI, MPURNLRI, Attribute, AttributeCollection
from exabgp.bgp.message.update.eor import EOR
from exabgp.bgp.message.update.nlri import NLRI, MPNLRICollection, NLRICollection
from exabgp.logger import lazyformat, lazymsg, log
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP

__all__ = [
    'Update',
    'UpdateCollection',
    'UpdateWire',
    'EOR',
    'NLRICollection',
    'MPNLRICollection',
]

# Update message header offsets and constants
UPDATE_WITHDRAWN_LENGTH_OFFSET = 2  # Offset to start of withdrawn routes
UPDATE_ATTR_LENGTH_HEADER_SIZE = 4  # Size of withdrawn length (2) + attr length (2)

# EOR (End-of-RIB) message length constants
EOR_IPV4_UNICAST_LENGTH = 4  # Length of IPv4 unicast EOR marker
EOR_WITH_PREFIX_LENGTH = 11  # Length of EOR with NLRI prefix


# ======================================================================= Update (Wire)
#
# Wire-format BGP UPDATE message container (bytes-first pattern).
# This class stores the raw payload bytes as the canonical representation.
# Parsing to semantic objects (UpdateCollection) is lazy.


@Message.register
class Update(Message):
    """Wire-format BGP UPDATE message container (bytes-first).

    Stores raw UPDATE message payload as the canonical representation.
    Provides lazy parsing to semantic UpdateCollection when needed.

    This follows the "packed-bytes-first" pattern used by individual
    Attribute classes - the wire format is stored directly, and semantic
    values are derived via properties.

    This is the registered BGP UPDATE message handler.
    """

    ID = Message.CODE.UPDATE
    TYPE = bytes([Message.CODE.UPDATE])
    EOR: bool = False  # Not an End-of-RIB marker

    def __init__(self, packed: Buffer, parsed: 'UpdateCollection | None' = None) -> None:
        """Create Update from raw payload bytes.

        Args:
            payload: The UPDATE message payload (after BGP header).
                     Format: withdrawn_len(2) + withdrawn + attr_len(2) + attributes + nlri
                     Can be bytes or memoryview (converted to bytes for storage).
            parsed: Optional pre-parsed UpdateCollection (used internally).
        """
        # Two-buffer pattern: bytearray owns data, memoryview provides zero-copy slicing
        self._packed = packed
        # Initialize with empty collection if not provided - properties always work
        self._parsed: 'UpdateCollection' = (
            parsed if parsed is not None else UpdateCollection([], [], AttributeCollection())
        )

    @property
    def payload(self) -> bytes:
        """Raw UPDATE payload bytes."""
        return bytes(self._packed)

    @property
    def withdrawn_bytes(self) -> bytes:
        """Raw bytes of withdrawn routes section."""
        withdrawn_len = unpack('!H', self._packed[:2])[0]
        return bytes(self._packed[2 : 2 + withdrawn_len])

    @property
    def attribute_bytes(self) -> bytes:
        """Raw bytes of path attributes section."""
        withdrawn_len = unpack('!H', self._packed[:2])[0]
        attr_offset = 2 + withdrawn_len
        attr_len = unpack('!H', self._packed[attr_offset : attr_offset + 2])[0]
        return bytes(self._packed[attr_offset + 2 : attr_offset + 2 + attr_len])

    @property
    def nlri_bytes(self) -> bytes:
        """Raw bytes of announced NLRI section."""
        withdrawn_len = unpack('!H', self._packed[:2])[0]
        attr_offset = 2 + withdrawn_len
        attr_len = unpack('!H', self._packed[attr_offset : attr_offset + 2])[0]
        nlri_offset = attr_offset + 2 + attr_len
        return bytes(self._packed[nlri_offset:])

    def pack_message(self, negotiated: 'Negotiated | None' = None) -> bytes:
        """Generate complete BGP message with header.

        Args:
            negotiated: Unused, kept for API compatibility with Message.pack_message().

        Returns:
            Complete BGP UPDATE message: marker(16) + length(2) + type(1) + payload
        """
        return self._message(self._packed)

    @property
    def data(self) -> 'UpdateCollection':
        """Access parsed UpdateCollection.

        Returns:
            Parsed UpdateCollection (semantic container) with announces, withdraws, attributes.
            Returns empty collection if parse() was not called.
        """
        return self._parsed

    def parse(self, negotiated: 'Negotiated') -> 'UpdateCollection':
        """Parse payload to semantic UpdateCollection with negotiated context.

        Args:
            negotiated: BGP session negotiated parameters.

        Returns:
            Parsed UpdateCollection (semantic container).
        """
        # Only parse if we have an empty placeholder
        if not self._parsed.announces and not self._parsed.withdraws and not self._parsed.attributes:
            self._parsed = UpdateCollection._parse_payload(bytes(self._packed), negotiated)
        return self._parsed

    @property
    def nlris(self) -> list[NLRI]:
        """Get all NLRIs (announces + withdraws)."""
        return self._parsed.nlris

    @property
    def announces(self) -> list[NLRI]:
        """Get announced NLRIs."""
        return self._parsed.announces

    @property
    def withdraws(self) -> list[NLRI]:
        """Get withdrawn NLRIs."""
        return self._parsed.withdraws

    @property
    def attributes(self) -> AttributeCollection:
        """Get path attributes."""
        return self._parsed.attributes

    @staticmethod
    def split(data: Buffer) -> tuple[Buffer, Buffer, Buffer]:
        """Split UPDATE payload into withdrawn, attributes, announced sections."""
        return UpdateCollection.split(data)

    @classmethod
    def unpack_message(cls, data: Buffer, negotiated: 'Negotiated') -> Message:
        """Unpack raw UPDATE payload to Update or EOR.

        This is the registered message handler called by Message.unpack().

        Args:
            data: Raw UPDATE message payload (after BGP header).
                  Can be bytes or memoryview (zero-copy from network).
            negotiated: BGP session negotiated parameters.

        Returns:
            Update (wire container with lazy parsing) or EOR.
        """
        log.debug(lazyformat('parsing UPDATE', data), 'parser')

        length = len(data)

        # Check for End-of-RIB markers (fast path)
        if length == EOR_IPV4_UNICAST_LENGTH and data == b'\x00\x00\x00\x00':
            return EOR(AFI.ipv4, SAFI.unicast)
        if length == EOR_WITH_PREFIX_LENGTH and bytes(data).startswith(EOR.NLRI.PREFIX):
            return EOR.unpack_message(data, negotiated)

        # Create wire container and parse
        update = cls(data)
        parsed = update.parse(negotiated)

        # Check if this is actually an EOR after parsing (empty update with MP attributes)
        if not parsed.attributes and not parsed.announces and not parsed.withdraws:
            # Need to check what MP attributes were present before they were popped
            # Re-split to check for MP_REACH/MP_UNREACH
            _, attr_view, _ = UpdateCollection.split(data)
            if attr_view:
                # Parse attributes again to check for MP attributes
                # (this is inefficient but handles edge cases)
                temp_attrs = AttributeCollection.unpack(bytes(attr_view), negotiated)
                unreach = temp_attrs.get(MPURNLRI.ID)
                reach = temp_attrs.get(MPRNLRI.ID)
                if unreach is not None:
                    return EOR(unreach.afi, unreach.safi)
                if reach is not None:
                    return EOR(reach.afi, reach.safi)
            # No MP attributes - this is IPv4 unicast EOR
            return EOR(AFI.ipv4, SAFI.unicast)

        def log_parsed(_: object) -> str:
            # we need the import in the function as otherwise we have an cyclic loop
            from exabgp.reactor.api.response import Response
            from exabgp.version import json as json_version

            return 'json {}'.format(
                Response.JSON(json_version).update(negotiated.neighbor, 'receive', update._parsed, b'', b'', negotiated)
            )

        log.debug(lazyformat('decoded UPDATE', '', log_parsed), 'parser')

        return update


# ======================================================================= Update

# +-----------------------------------------------------+
# |   Withdrawn Routes Length (2 octets)                |
# +-----------------------------------------------------+
# |   Withdrawn Routes (variable)                       |
# +-----------------------------------------------------+
# |   Total Path Attribute Length (2 octets)            |
# +-----------------------------------------------------+
# |   Path Attributes (variable)                        |
# +-----------------------------------------------------+
# |   Network Layer Reachability Information (variable) |
# +-----------------------------------------------------+

# Withdrawn Routes:

# +---------------------------+
# |   Length (1 octet)        |
# +---------------------------+
# |   Prefix (variable)       |
# +---------------------------+


class UpdateCollection(Message):
    """Semantic container for BGP UPDATE message data.

    Holds announces, withdraws, and attributes as semantic objects.
    Used as a builder to construct UPDATE messages from semantic data.

    Note: This class inherits from Message for backward compatibility
    (uses _message() method) but is NOT registered as the UPDATE handler.
    The Update class is the registered handler.
    """

    ID = Message.CODE.UPDATE
    TYPE = bytes([Message.CODE.UPDATE])
    EOR: bool = False

    def __init__(
        self,
        announces: list[NLRI],
        withdraws: list[NLRI],
        attributes: AttributeCollection,
    ) -> None:
        # UpdateCollection is a composite container - NLRIs and Attributes are already packed-bytes-first
        # No single _packed representation exists because messages() can generate multiple
        # wire-format messages from one UpdateCollection due to size limits
        self._announces: list[NLRI] = announces
        self._withdraws: list[NLRI] = withdraws
        self._attributes: AttributeCollection = attributes

    @property
    def nlris(self) -> list[NLRI]:
        # Backward compat: combine announces and withdraws
        return self._announces + self._withdraws

    @property
    def announces(self) -> list[NLRI]:
        return self._announces

    @property
    def withdraws(self) -> list[NLRI]:
        return self._withdraws

    @property
    def attributes(self) -> AttributeCollection:
        return self._attributes

    # message not implemented we should use messages below.

    def __str__(self) -> str:
        return '\n'.join(['{}{}'.format(str(self.nlris[n]), str(self.attributes)) for n in range(len(self.nlris))])

    @staticmethod
    def prefix(data: bytes) -> bytes:
        # This function needs renaming
        return pack('!H', len(data)) + data

    @staticmethod
    def split(data: Buffer) -> tuple[Buffer, Buffer, Buffer]:
        """Split UPDATE payload into withdrawn, attributes, announced sections.

        Returns memoryview slices for zero-copy access. Converts input to memoryview
        if not already one.
        """
        # Convert to memoryview for zero-copy slicing (memoryview() accepts any Buffer)
        length = len(data)

        # UPDATE minimum: withdrawn_len(2) + attr_len(2) = 4 bytes
        if length < UPDATE_ATTR_LENGTH_HEADER_SIZE:
            raise Notify(3, 1, f'UPDATE message too short: need {UPDATE_ATTR_LENGTH_HEADER_SIZE} bytes, got {length}')

        len_withdrawn = unpack('!H', data[0:UPDATE_WITHDRAWN_LENGTH_OFFSET])[0]

        # Verify we have enough data for withdrawn routes + attr length field
        if length < UPDATE_ATTR_LENGTH_HEADER_SIZE + len_withdrawn:
            raise Notify(3, 1, f'UPDATE withdrawn length {len_withdrawn} exceeds available data')

        withdrawn = data[UPDATE_WITHDRAWN_LENGTH_OFFSET : len_withdrawn + UPDATE_WITHDRAWN_LENGTH_OFFSET]

        start_attributes = len_withdrawn + UPDATE_ATTR_LENGTH_HEADER_SIZE
        len_attributes = unpack('!H', data[len_withdrawn + UPDATE_WITHDRAWN_LENGTH_OFFSET : start_attributes])[0]

        # Verify we have enough data for attributes
        if length < start_attributes + len_attributes:
            raise Notify(3, 1, f'UPDATE attributes length {len_attributes} exceeds available data')

        start_announced = len_withdrawn + len_attributes + UPDATE_ATTR_LENGTH_HEADER_SIZE
        attributes = data[start_attributes:start_announced]
        announced = data[start_announced:]

        if (
            UPDATE_WITHDRAWN_LENGTH_OFFSET
            + len_withdrawn
            + UPDATE_WITHDRAWN_LENGTH_OFFSET
            + len_attributes
            + len(announced)
            != length
        ):
            raise Notify(3, 1, 'error in BGP message length, not enough data for the size announced')

        return withdrawn, attributes, announced

    # The routes MUST have the same attributes ...
    def messages(self, negotiated: Negotiated, include_withdraw: bool = True) -> Generator[bytes, None, None]:
        # Sort and classify NLRIs into IPv4 and MP categories
        v4_announces: list = []
        v4_withdraws: list = []
        mp_nlris: dict[tuple, dict] = {}

        # Process announces
        for nlri in sorted(self._announces):
            if nlri.family().afi_safi() not in negotiated.families:
                continue

            is_v4 = nlri.afi == AFI.ipv4
            is_v4 = is_v4 and nlri.safi in [SAFI.unicast, SAFI.multicast]
            is_v4 = is_v4 and nlri.nexthop.afi == AFI.ipv4

            if is_v4:
                v4_announces.append(nlri)
                continue

            if nlri.nexthop.afi != AFI.undefined:
                mp_nlris.setdefault(nlri.family().afi_safi(), {}).setdefault(Action.ANNOUNCE, []).append(nlri)
                continue

            if nlri.safi in (SAFI.flow_ip, SAFI.flow_vpn):
                mp_nlris.setdefault(nlri.family().afi_safi(), {}).setdefault(Action.ANNOUNCE, []).append(nlri)
                continue

            raise ValueError('unexpected nlri definition ({})'.format(nlri))

        # Process withdraws
        for nlri in sorted(self._withdraws):
            if nlri.family().afi_safi() not in negotiated.families:
                continue

            is_v4 = nlri.afi == AFI.ipv4
            is_v4 = is_v4 and nlri.safi in [SAFI.unicast, SAFI.multicast]

            if is_v4:
                v4_withdraws.append(nlri)
                continue

            # MP withdraws
            mp_nlris.setdefault(nlri.family().afi_safi(), {}).setdefault(Action.WITHDRAW, []).append(nlri)

        # Check if we have anything to send
        has_v4 = v4_announces or v4_withdraws
        if not has_v4 and not mp_nlris:
            return

        # If all we have is MP_UNREACH_NLRI, we do not need the default
        # attributes. See RFC4760 that states the following:
        #
        #   An UPDATE message that contains the MP_UNREACH_NLRI is not required
        #   to carry any other path attributes.
        #
        include_defaults = True

        # Check if we only have withdraws (v4 or mp)
        only_withdraws = not v4_announces
        if mp_nlris and only_withdraws:
            for family, actions in mp_nlris.items():
                afi, safi = family
                if safi not in (SAFI.unicast, SAFI.multicast):
                    break
                if set(actions.keys()) != {Action.WITHDRAW}:
                    break
            # no break
            else:
                include_defaults = False

        attr = self.attributes.pack_attribute(negotiated, include_defaults)

        # Withdraws/NLRIS (IPv4 unicast and multicast)
        msg_size = negotiated.msg_size - 19 - 2 - 2 - len(attr)  # 2 bytes for each of the two prefix() header

        if msg_size < 0:
            # raise Notify(6,0,'attributes size is so large we can not even pack one NLRI')
            log.critical(lazymsg('update.pack.error reason=attributes_too_large'), 'parser')
            return

        if msg_size == 0 and (has_v4 or mp_nlris):
            # raise Notify(6,0,'attributes size is so large we can not even pack one NLRI')
            log.critical(lazymsg('update.pack.error reason=attributes_too_large'), 'parser')
            return

        withdraws = b''
        announced = b''
        # Track sizes progressively to avoid O(n) len() on concatenation
        # See lab/benchmark_update_size.py for benchmark (1.3-1.5x speedup)
        withdraws_size = 0
        announced_size = 0

        # First pack all announces
        for nlri in v4_announces:
            packed = nlri.pack_nlri(negotiated)
            packed_size = len(packed)
            if announced_size + withdraws_size + packed_size <= msg_size:
                announced += packed
                announced_size += packed_size
                continue

            if not withdraws and not announced:
                log.critical(lazymsg('update.pack.error reason=attributes_too_large'), 'parser')
                return

            yield self._message(UpdateCollection.prefix(withdraws) + UpdateCollection.prefix(attr) + announced)
            announced = packed
            announced_size = packed_size
            withdraws = b''
            withdraws_size = 0

        # Then pack all withdraws (if include_withdraw is True)
        if include_withdraw:
            for nlri in v4_withdraws:
                packed = nlri.pack_nlri(negotiated)
                packed_size = len(packed)
                if announced_size + withdraws_size + packed_size <= msg_size:
                    withdraws += packed
                    withdraws_size += packed_size
                    continue

                if not withdraws and not announced:
                    log.critical(lazymsg('update.pack.error reason=attributes_too_large'), 'parser')
                    return

                if announced:
                    yield self._message(UpdateCollection.prefix(withdraws) + UpdateCollection.prefix(attr) + announced)
                else:
                    yield self._message(UpdateCollection.prefix(withdraws) + UpdateCollection.prefix(b'') + announced)
                withdraws = packed
                withdraws_size = packed_size
                announced = b''
                announced_size = 0

        if announced or withdraws:
            if announced:
                yield self._message(UpdateCollection.prefix(withdraws) + UpdateCollection.prefix(attr) + announced)
            else:
                yield self._message(UpdateCollection.prefix(withdraws) + UpdateCollection.prefix(b'') + announced)

        for family in mp_nlris.keys():
            afi, safi = family
            mp_reach = b''
            mp_unreach = b''
            context = negotiated.nlri_context(afi, safi)
            mp_announce = MPRNLRI.make_mprnlri(context, mp_nlris[family].get(Action.ANNOUNCE, []))
            mp_withdraw = MPURNLRI.make_mpurnlri(context, mp_nlris[family].get(Action.WITHDRAW, []))

            for mprnlri in mp_announce.packed_attributes(negotiated, msg_size - len(withdraws + announced)):
                if mp_reach:
                    yield self._message(
                        UpdateCollection.prefix(withdraws) + UpdateCollection.prefix(attr + mp_reach) + announced
                    )
                    announced = b''
                    withdraws = b''
                mp_reach = mprnlri

            if include_withdraw:
                for mpurnlri in mp_withdraw.packed_attributes(
                    negotiated,
                    msg_size - len(withdraws + announced + mp_reach),
                ):
                    if mp_unreach:
                        yield self._message(
                            UpdateCollection.prefix(withdraws)
                            + UpdateCollection.prefix(attr + mp_unreach + mp_reach)
                            + announced,
                        )
                        mp_reach = b''
                        announced = b''
                        withdraws = b''
                    mp_unreach = mpurnlri

            yield self._message(
                UpdateCollection.prefix(withdraws) + UpdateCollection.prefix(attr + mp_unreach + mp_reach) + announced,
            )  # yield mpr/mpur per family
            withdraws = b''
            announced = b''

    def pack_messages(self, negotiated: Negotiated, include_withdraw: bool = True) -> Generator['Update', None, None]:
        """Pack this UpdateCollection into wire-format Update messages.

        One UpdateCollection can produce multiple Update messages due to BGP
        message size limits.

        Args:
            negotiated: BGP session negotiated parameters.
            include_withdraw: Whether to include withdrawals in output.

        Yields:
            Update objects containing serialized UPDATE payloads.
        """
        for msg_bytes in self.messages(negotiated, include_withdraw):
            # BGP message format: marker(16) + length(2) + type(1) + payload
            # Extract payload by removing 19-byte header
            payload = msg_bytes[19:]
            yield Update(payload)

    # Note: This method can raise ValueError, IndexError, TypeError, struct.error (from unpack).
    # These exceptions are caught by the caller in reactor/protocol.py:read_message() which
    # wraps them in a Notify(1, 0) to signal a malformed message to the peer.
    @classmethod
    def _parse_payload(cls, data: bytes, negotiated: Negotiated) -> UpdateCollection:
        """Parse raw UPDATE payload bytes into semantic UpdateCollection.

        This is an internal method called by Update.parse().

        Args:
            data: Raw UPDATE message payload (after BGP header).
            negotiated: BGP session negotiated parameters.

        Returns:
            UpdateCollection with parsed announces, withdraws, and attributes.
        """
        withdrawn_view, attr_view, announced_view = cls.split(data)

        if not withdrawn_view:
            log.debug(lazymsg('update.withdrawn status=none'), 'routes')

        # Convert memoryview slices to bytes for downstream parsing
        # (NLRI.unpack_nlri and AttributeCollection.unpack still use bytes)
        withdrawn_bytes = bytes(withdrawn_view)
        announced_bytes = bytes(announced_view)
        attributes = AttributeCollection.unpack(bytes(attr_view), negotiated)

        if not announced_view:
            log.debug(lazymsg('update.announced status=none'), 'routes')

        # Is the peer going to send us some Path Information with the route (AddPath)
        addpath = negotiated.required(AFI.ipv4, SAFI.unicast)

        # empty string for IP.NoNextHop, the packed IP otherwise (without the 3/4 bytes of attributes headers)
        nexthop = attributes.get(Attribute.CODE.NEXT_HOP, IP.NoNextHop)
        # nexthop = NextHop.unpack(_nexthop.ton())

        # RFC 4271 Section 5.1.3: NEXT_HOP MUST NOT be the IP address of the receiving speaker
        # Log warning but don't kill session - peer may have misconfigured next-hop
        neighbor = getattr(negotiated, 'neighbor', None)
        if nexthop is not IP.NoNextHop and neighbor is not None:
            try:
                local_address = neighbor.session.local_address
                nexthop_packed = getattr(nexthop, '_packed', b'')
                local_packed = getattr(local_address, '_packed', b'')
                if local_address is not None and nexthop_packed and local_packed:
                    if nexthop_packed == local_packed:
                        log.warning(
                            lambda: 'received NEXT_HOP {} equals our local address (RFC 4271 violation)'.format(
                                nexthop
                            ),
                            'parser',
                        )
            except (TypeError, KeyError):
                # negotiated.neighbor may be a mock or not support subscripting
                pass

        announces: list[NLRI] = []
        withdraws: list[NLRI] = []

        while withdrawn_bytes:
            nlri, left = NLRI.unpack_nlri(AFI.ipv4, SAFI.unicast, withdrawn_bytes, Action.WITHDRAW, addpath, negotiated)
            log.debug(lazymsg('withdrawn NLRI {nlri}', nlri=nlri), 'routes')
            withdrawn_bytes = left
            if nlri is not NLRI.INVALID:
                withdraws.append(nlri)

        while announced_bytes:
            nlri, left = NLRI.unpack_nlri(AFI.ipv4, SAFI.unicast, announced_bytes, Action.ANNOUNCE, addpath, negotiated)
            if nlri is not NLRI.INVALID:
                nlri.nexthop = nexthop
                log.debug(lazymsg('announced NLRI {nlri}', nlri=nlri), 'routes')
                announces.append(nlri)
            announced_bytes = left

        unreach = attributes.pop(MPURNLRI.ID, None)
        reach = attributes.pop(MPRNLRI.ID, None)

        if unreach is not None:
            withdraws.extend(unreach.nlris)

        if reach is not None:
            announces.extend(reach.nlris)

        return cls(announces, withdraws, attributes)

    @classmethod
    def unpack_message(cls, data: Buffer, negotiated: Negotiated) -> Message:
        """Parse raw UPDATE payload bytes into UpdateCollection or EOR.

        Deprecated: Use Update.unpack_message() for the registered handler.

        This method is kept for backward compatibility.
        """
        # Convert to bytes for comparison and downstream parsing
        length = len(data)

        # Check for End-of-RIB markers (fast path)
        if length == EOR_IPV4_UNICAST_LENGTH and data == b'\x00\x00\x00\x00':
            return EOR(AFI.ipv4, SAFI.unicast)
        if length == EOR_WITH_PREFIX_LENGTH and bytes(data).startswith(EOR.NLRI.PREFIX):
            return EOR.unpack_message(data, negotiated)

        # Parse normally
        return cls._parse_payload(data, negotiated)


# Backward compatibility aliases
UpdateWire = Update  # Old wire container name
UpdateData = UpdateCollection  # Old semantic container name
