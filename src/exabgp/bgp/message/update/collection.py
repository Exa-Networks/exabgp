"""update/collection.py - UpdateCollection semantic container

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from dataclasses import dataclass
from struct import pack, unpack
from typing import TYPE_CHECKING, Generator

from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated
    from exabgp.bgp.message.update import Update

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.message import Message
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute import MPRNLRI, MPURNLRI, Attribute, AttributeCollection
from exabgp.bgp.message.update.nlri import NLRI, MPNLRICollection
from exabgp.logger import lazymsg, log
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP


@dataclass(frozen=True, slots=True)
class RoutedNLRI:
    """NLRI with associated nexthop for wire format encoding.

    This is a lightweight immutable container used by UpdateCollection
    to group NLRIs with their nexthops for wire format generation.
    It does not include action (determined by list placement: announces vs withdraws)
    or attributes (handled separately by UpdateCollection).

    Using this instead of storing nexthop in NLRI allows NLRI to be immutable
    and reusable across different nexthop contexts.
    """

    nlri: NLRI
    nexthop: IP


# Update message header offsets and constants
UPDATE_WITHDRAWN_LENGTH_OFFSET = 2  # Offset to start of withdrawn routes
UPDATE_ATTR_LENGTH_HEADER_SIZE = 4  # Size of withdrawn length (2) + attr length (2)

# EOR (End-of-RIB) message length constants
EOR_IPV4_UNICAST_LENGTH = 4  # Length of IPv4 unicast EOR marker
EOR_WITH_PREFIX_LENGTH = 11  # Length of EOR with NLRI prefix


# ======================================================================= UpdateCollection

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

    Announces are stored as RoutedNLRI (nlri + nexthop) because nexthop
    is needed for MP_REACH_NLRI wire format encoding.

    Withdraws are stored as bare NLRI because MP_UNREACH_NLRI doesn't
    include nexthop.

    Note: This class inherits from Message for backward compatibility
    (uses _message() method) but is NOT registered as the UPDATE handler.
    The Update class is the registered handler.
    """

    ID = Message.CODE.UPDATE
    TYPE = bytes([Message.CODE.UPDATE])
    EOR: bool = False

    def __init__(
        self,
        announces: list[RoutedNLRI],
        withdraws: list[NLRI],
        attributes: AttributeCollection,
    ) -> None:
        # UpdateCollection is a composite container - NLRIs and Attributes are already packed-bytes-first
        # No single _packed representation exists because messages() can generate multiple
        # wire-format messages from one UpdateCollection due to size limits
        self._announces: list[RoutedNLRI] = announces
        self._withdraws: list[NLRI] = withdraws
        self._attributes: AttributeCollection = attributes

    @property
    def nlris(self) -> list[NLRI]:
        # Backward compat: combine announces and withdraws (extract NLRI from RoutedNLRI)
        return [routed.nlri for routed in self._announces] + self._withdraws

    @property
    def announces(self) -> list[RoutedNLRI]:
        return self._announces

    @property
    def withdraws(self) -> list[NLRI]:
        return self._withdraws

    @property
    def attributes(self) -> AttributeCollection:
        return self._attributes

    def get_nexthop(self) -> IP:
        """Get the nexthop IP from attributes (NEXT_HOP attribute).

        Returns the IP from the NEXT_HOP attribute if present,
        otherwise returns IP.NoNextHop.

        For MP routes, nexthop is in MP_REACH_NLRI, not NEXT_HOP attribute.
        """
        from exabgp.protocol.ip import IPv4, IPv6

        nexthop_attr = self._attributes.get(Attribute.CODE.NEXT_HOP, None)
        if nexthop_attr is None:
            return IP.NoNextHop
        # NextHop attribute has pack_ip() method - convert to IP
        packed = nexthop_attr.pack_ip()
        if len(packed) == IPv4.BYTES:
            return IPv4(packed)
        elif len(packed) == IPv6.BYTES:
            return IPv6(packed)
        return IP.NoNextHop

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
        # Import here to avoid circular import
        from exabgp.bgp.message.update.nlri.empty import Empty

        # Sort and classify NLRIs into IPv4 and MP categories
        # v4_announces/v4_withdraws store bare NLRIs (nexthop is in NEXT_HOP attribute for IPv4)
        # mp_announces stores RoutedNLRI by family (nexthop needed for MP_REACH_NLRI encoding)
        # mp_withdraws stores bare NLRI by family (MP_UNREACH_NLRI has no nexthop)
        v4_announces: list[NLRI] = []
        v4_withdraws: list[NLRI] = []
        mp_announces: dict[tuple[AFI, SAFI], list[RoutedNLRI]] = {}
        mp_withdraws: dict[tuple[AFI, SAFI], list[NLRI]] = {}

        # Track if we have Empty NLRI (attributes-only UPDATE)
        has_empty_nlri = False

        # Process announces - self._announces contains RoutedNLRI
        # Sort by nlri for deterministic ordering
        for routed in sorted(self._announces, key=lambda r: r.nlri):
            nlri = routed.nlri
            nexthop = routed.nexthop

            # Skip Empty NLRI but remember we had one
            if isinstance(nlri, Empty):
                has_empty_nlri = True
                continue

            if nlri.family().afi_safi() not in negotiated.families:
                continue

            is_v4 = nlri.afi == AFI.ipv4
            is_v4 = is_v4 and nlri.safi in [SAFI.unicast, SAFI.multicast]
            is_v4 = is_v4 and nexthop.afi == AFI.ipv4

            if is_v4:
                v4_announces.append(nlri)
                continue

            if nexthop.afi != AFI.undefined:
                mp_announces.setdefault(nlri.family().afi_safi(), []).append(routed)
                continue

            if nlri.safi in (SAFI.flow_ip, SAFI.flow_vpn):
                mp_announces.setdefault(nlri.family().afi_safi(), []).append(routed)
                continue

            raise ValueError('unexpected nlri definition ({})'.format(nlri))

        # Process withdraws - bare NLRIs (no nexthop needed)
        for nlri in sorted(self._withdraws):
            # Skip Empty NLRI in withdraws
            if isinstance(nlri, Empty):
                has_empty_nlri = True
                continue

            if nlri.family().afi_safi() not in negotiated.families:
                continue

            is_v4 = nlri.afi == AFI.ipv4
            is_v4 = is_v4 and nlri.safi in [SAFI.unicast, SAFI.multicast]

            if is_v4:
                v4_withdraws.append(nlri)
                continue

            # MP withdraws
            mp_withdraws.setdefault(nlri.family().afi_safi(), []).append(nlri)

        # Check if we have anything to send
        has_v4 = v4_announces or v4_withdraws
        has_mp = mp_announces or mp_withdraws
        if not has_v4 and not has_mp:
            # Attributes-only UPDATE (Empty NLRI case)
            if has_empty_nlri and self._attributes:
                attr = self.attributes.pack_attribute(negotiated, with_default=True)
                # Generate UPDATE with no withdrawn routes and no NLRI, just attributes
                yield self._message(UpdateCollection.prefix(b'') + UpdateCollection.prefix(attr))
            return

        # If all we have is MP_UNREACH_NLRI, we do not need the default
        # attributes. See RFC4760 that states the following:
        #
        #   An UPDATE message that contains the MP_UNREACH_NLRI is not required
        #   to carry any other path attributes.
        #
        include_defaults = True

        # Check if we only have withdraws (v4 or mp)
        only_withdraws = not v4_announces and not mp_announces
        if mp_withdraws and only_withdraws:
            # Check if all MP withdraws are unicast/multicast (simple case)
            for family in mp_withdraws.keys():
                afi, safi = family
                if safi not in (SAFI.unicast, SAFI.multicast):
                    break
            # no break - all families are unicast/multicast
            else:
                include_defaults = False

        attr = self.attributes.pack_attribute(negotiated, include_defaults)

        # Withdraws/NLRIS (IPv4 unicast and multicast)
        msg_size = negotiated.msg_size - 19 - 2 - 2 - len(attr)  # 2 bytes for each of the two prefix() header

        if msg_size < 0:
            # raise Notify(6,0,'attributes size is so large we can not even pack one NLRI')
            log.critical(lazymsg('update.pack.error reason=attributes_too_large'), 'parser')
            return

        if msg_size == 0 and (has_v4 or has_mp):
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

        # Get all families that have MP announces or withdraws
        all_mp_families = set(mp_announces.keys()) | set(mp_withdraws.keys())

        for family in all_mp_families:
            afi, safi = family
            mp_reach = b''
            mp_unreach = b''

            # Use MPNLRICollection for reach/unreach attribute generation
            # mp_announces contains RoutedNLRI, mp_withdraws contains bare NLRI
            announce_routed = mp_announces.get(family, [])
            withdraw_nlris = mp_withdraws.get(family, [])

            mp_announce = MPNLRICollection.from_routed(announce_routed, {}, afi, safi)
            mp_withdraw = MPNLRICollection(withdraw_nlris, {}, afi, safi)

            for mprnlri in mp_announce.packed_reach_attributes(negotiated, msg_size - len(withdraws + announced)):
                if mp_reach:
                    yield self._message(
                        UpdateCollection.prefix(withdraws) + UpdateCollection.prefix(attr + mp_reach) + announced
                    )
                    announced = b''
                    withdraws = b''
                mp_reach = mprnlri

            if include_withdraw:
                for mpurnlri in mp_withdraw.packed_unreach_attributes(
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
        # Import here to avoid circular import
        from exabgp.bgp.message.update import Update

        for msg_bytes in self.messages(negotiated, include_withdraw):
            # BGP message format: marker(16) + length(2) + type(1) + payload
            # Extract payload by removing 19-byte header
            payload = msg_bytes[19:]
            yield Update(payload, negotiated)

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

        announces: list[RoutedNLRI] = []
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
                # Set nlri.nexthop for backward compat (JSON API reads it)
                nlri.nexthop = nexthop
                # Wrap NLRI with nexthop in RoutedNLRI for UpdateCollection
                routed = RoutedNLRI(nlri, nexthop)
                log.debug(lazymsg('announced NLRI {nlri}', nlri=nlri), 'routes')
                announces.append(routed)
            announced_bytes = left

        unreach = attributes.pop(MPURNLRI.ID, None)
        reach = attributes.pop(MPRNLRI.ID, None)

        if unreach is not None:
            withdraws.extend(unreach)  # Uses __iter__

        if reach is not None:
            # MP_REACH_NLRI contains nexthop - use iter_routed() for RoutedNLRI
            announces.extend(reach.iter_routed())

        return cls(announces, withdraws, attributes)

    @classmethod
    def unpack_message(cls, data: Buffer, negotiated: Negotiated) -> Message:
        """Parse raw UPDATE payload bytes into UpdateCollection or EOR.

        Deprecated: Use Update.unpack_message() for the registered handler.

        This method is kept for backward compatibility.
        """
        # Import here to avoid circular import
        from exabgp.bgp.message.update.eor import EOR

        # Convert to bytes for comparison and downstream parsing
        length = len(data)

        # Check for End-of-RIB markers (fast path)
        if length == EOR_IPV4_UNICAST_LENGTH and data == b'\x00\x00\x00\x00':
            return EOR(AFI.ipv4, SAFI.unicast)
        if length == EOR_WITH_PREFIX_LENGTH and bytes(data).startswith(EOR.EOR_NLRI.PREFIX):
            return EOR.unpack_message(data, negotiated)

        # Parse normally
        return cls._parse_payload(data, negotiated)
