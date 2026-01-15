"""capabilities.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.util.types import Buffer
from typing import ClassVar, TYPE_CHECKING

from exabgp.protocol.family import AFI, SAFI, FamilyTuple

from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.capability import CapabilityCode
from exabgp.bgp.message.open.capability.nexthop import NextHop
from exabgp.bgp.message.open.capability.addpath import AddPath
from exabgp.bgp.message.open.capability.asn4 import ASN4
from exabgp.bgp.message.open.capability.graceful import Graceful
from exabgp.bgp.message.open.capability.mp import MultiProtocol
from exabgp.bgp.message.open.capability.ms import MultiSession
from exabgp.bgp.message.open.capability.operational import Operational
from exabgp.bgp.message.open.capability.refresh import RouteRefresh
from exabgp.bgp.message.open.capability.refresh import EnhancedRouteRefresh
from exabgp.bgp.message.open.capability.extended import ExtendedMessage
from exabgp.bgp.message.open.capability.hostname import HostName
from exabgp.bgp.message.open.capability.software import Software

from exabgp.bgp.message.notification import Notify

from struct import pack, unpack

if TYPE_CHECKING:
    from exabgp.bgp.neighbor import Neighbor

# BGP OPEN message parameter size constants (RFC 4271, RFC 9072)
OPEN_PARAM_LEN_MAX: int = 255  # Maximum parameter length for standard OPEN (8-bit field)
OPEN_EXTENDED_MARKER: int = 255  # Marker value indicating extended optional parameters format
MIN_EXTENDED_PARAM_LEN: int = 3  # Minimum length for extended parameter (type + 2-byte length)
MIN_PARAM_LEN: int = 2  # Minimum length for standard parameter (type + length)

# =================================================================== Parameter
#


class Parameter(int):
    AUTHENTIFICATION_INFORMATION: ClassVar[int] = 0x01  # Depreciated
    CAPABILITIES: ClassVar[int] = 0x02

    def __str__(self) -> str:
        if self == self.AUTHENTIFICATION_INFORMATION:
            return 'AUTHENTIFICATION INFORMATION'
        if self == self.CAPABILITIES:
            return 'OPTIONAL'
        return 'UNKNOWN'


# =================================================================== Capabilities
# https://www.iana.org/assignments/capability-codes/

# +------------------------------+
# | Capability Code (1 octet)    |
# +------------------------------+
# | Capability Length (1 octet)  |
# +------------------------------+
# | Capability Value (variable)  |
# +------------------------------+


class Capabilities(dict[int, Capability]):
    # RFC 9072 - Extended Optional Parameters Length
    EXTENDED_LENGTH: ClassVar[int] = 0xFF  # IANA Extended Length type code - indicates extended format in use

    _ADD_PATH: ClassVar[list[FamilyTuple]] = [
        (AFI.ipv4, SAFI.unicast),
        (AFI.ipv6, SAFI.unicast),
        (AFI.ipv4, SAFI.nlri_mpls),
        (AFI.ipv6, SAFI.nlri_mpls),
        (AFI.ipv4, SAFI.mpls_vpn),
        (AFI.ipv6, SAFI.mpls_vpn),
        (AFI.ipv4, SAFI.mup),
        (AFI.ipv6, SAFI.mup),
    ]

    _NEXTHOP: ClassVar[list[tuple[AFI, SAFI, AFI]]] = [
        (AFI.ipv4, SAFI.unicast, AFI.ipv6),
        (AFI.ipv4, SAFI.multicast, AFI.ipv6),
        (AFI.ipv4, SAFI.nlri_mpls, AFI.ipv6),
        (AFI.ipv4, SAFI.mpls_vpn, AFI.ipv6),
    ]

    def announced(self, capability: int) -> bool:
        return capability in self

    def __str__(self) -> str:
        r: list[str] = []
        for key in sorted(self.keys()):
            r.append(str(self[key]))
        return ', '.join(r)

    def _protocol(self, neighbor: Neighbor) -> None:
        families = neighbor.families()
        mp = MultiProtocol()
        mp.extend(families)
        self[Capability.CODE.MULTIPROTOCOL] = mp

    def _asn4(self, neighbor: Neighbor) -> None:
        if not neighbor.capability.asn4.is_enabled():
            return

        self[Capability.CODE.FOUR_BYTES_ASN] = ASN4(neighbor.session.local_as)

    def _nexthop(self, neighbor: Neighbor) -> None:
        if not neighbor.capability.nexthop.is_enabled():
            return

        nexthops = neighbor.nexthops()
        nh_pairs: list[tuple[AFI, SAFI, AFI]] = []
        for allowed in self._NEXTHOP:
            if allowed not in nexthops:
                continue
            nh_pairs.append(allowed)
        self[Capability.CODE.NEXTHOP] = NextHop(tuple(nh_pairs))

    def _addpath(self, neighbor: Neighbor) -> None:
        if not neighbor.capability.add_path:
            return

        families = neighbor.addpaths()
        ap_families: list[FamilyTuple] = []
        for allowed in self._ADD_PATH:
            if allowed in families:
                ap_families.append(allowed)
        self[Capability.CODE.ADD_PATH] = AddPath(ap_families, neighbor.capability.add_path)

    def _graceful(self, neighbor: Neighbor, restarted: bool) -> None:
        if not neighbor.capability.graceful_restart:
            return

        self[Capability.CODE.GRACEFUL_RESTART] = Graceful().set(
            Graceful.RESTART_STATE if restarted else 0x0,
            neighbor.capability.graceful_restart.time,
            [(afi, safi, Graceful.FORWARDING_STATE) for (afi, safi) in neighbor.families()],
        )

    def _refresh(self, neighbor: Neighbor) -> None:
        if not neighbor.capability.route_refresh:
            return
        self[Capability.CODE.ROUTE_REFRESH] = RouteRefresh()
        self[Capability.CODE.ENHANCED_ROUTE_REFRESH] = EnhancedRouteRefresh()

    def _extended_message(self, neighbor: Neighbor) -> None:
        if not neighbor.capability.extended_message.is_enabled():
            return

        self[Capability.CODE.EXTENDED_MESSAGE] = ExtendedMessage()

    def _hostname(self, neighbor: Neighbor) -> None:
        self[Capability.CODE.HOSTNAME] = HostName(neighbor.host_name, neighbor.domain_name)

    def _software_version(self, neighbor: Neighbor) -> None:
        if not neighbor.capability.software_version:
            return

        self[Capability.CODE.SOFTWARE_VERSION] = Software()

    def _operational(self, neighbor: Neighbor) -> None:
        if not neighbor.capability.operational.is_enabled():
            return
        self[Capability.CODE.OPERATIONAL] = Operational()

    def _linklocal(self, neighbor: Neighbor) -> None:
        if not neighbor.capability.link_local_nexthop.is_enabled():
            return
        from exabgp.bgp.message.open.capability.linklocal import LinkLocalNextHop

        self[Capability.CODE.LINK_LOCAL_NEXTHOP] = LinkLocalNextHop()

    def _session(self, neighbor: Neighbor) -> None:
        if not neighbor.capability.multi_session.is_enabled():
            return
        # Uses IETF draft code (0x44) - draft-ietf-idr-bgp-multisession expired 2013, never became RFC
        self[Capability.CODE.MULTISESSION] = MultiSession().set([Capability.CODE.MULTIPROTOCOL])

    def new(self, neighbor: Neighbor, restarted: bool) -> Capabilities:
        self._protocol(neighbor)
        self._asn4(neighbor)
        self._nexthop(neighbor)
        self._addpath(neighbor)
        self._graceful(neighbor, restarted)
        self._refresh(neighbor)
        self._operational(neighbor)
        self._extended_message(neighbor)
        self._hostname(neighbor)  # https://datatracker.ietf.org/doc/html/draft-walton-bgp-hostname-capability-02
        self._software_version(neighbor)  # https://datatracker.ietf.org/doc/html/draft-abraitis-bgp-version-capability
        self._linklocal(neighbor)  # https://datatracker.ietf.org/doc/html/draft-ietf-idr-linklocal-capability
        self._session(neighbor)  # MUST be the last key added, really !?! dict is not ordered !
        return self

    def pack_capabilities(self) -> bytes:
        parameters = b''
        for k, capabilities in self.items():
            for capability in capabilities.extract_capability_bytes():
                if len(capability) == 0:
                    continue
                encoded = bytes([k, len(capability)]) + capability
                parameters += bytes([2, len(encoded)]) + encoded

        if len(parameters) < OPEN_PARAM_LEN_MAX:
            return bytes([len(parameters)]) + parameters

        # If this is an extended optional parameters version, re-encode
        # the OPEN message.

        parameters = b''
        for k, capabilities in self.items():
            for capability in capabilities.extract_capability_bytes():
                if len(capability) == 0:
                    continue
                encoded = bytes([k, len(capability)]) + capability
                parameters += pack('!BH', 2, len(encoded)) + encoded

        return pack('!BBH', OPEN_EXTENDED_MARKER, OPEN_EXTENDED_MARKER, len(parameters)) + parameters

    @staticmethod
    def unpack(data: Buffer) -> Capabilities:
        def _extended_type_length(name: str, data: Buffer) -> tuple[int, Buffer, Buffer]:
            if len(data) < MIN_EXTENDED_PARAM_LEN:
                raise Notify(
                    2,
                    0,
                    'Bad length for OPEN (extended) {} (<{}) {}'.format(
                        name, MIN_EXTENDED_PARAM_LEN, Capability.hex(data)
                    ),
                )
            # Optional parameters length
            ld: int = unpack('!H', data[1:3])[0]
            boundary: int = ld + 3
            if len(data) < boundary:
                raise Notify(
                    2,
                    0,
                    'Bad length for OPEN (extended) {} (buffer underrun) {}'.format(name, Capability.hex(data)),
                )
            key: int = data[0]
            value: Buffer = data[3:boundary]
            rest: Buffer = data[boundary:]
            return key, value, rest

        def _key_values(name: str, data: Buffer) -> tuple[int, Buffer, Buffer]:
            if len(data) < MIN_PARAM_LEN:
                raise Notify(2, 0, 'Bad length for OPEN {} (<{}) {}'.format(name, MIN_PARAM_LEN, Capability.hex(data)))
            ld: int = data[1]
            boundary: int = ld + 2
            if len(data) < boundary:
                raise Notify(2, 0, 'Bad length for OPEN {} (buffer underrun) {}'.format(name, Capability.hex(data)))
            key: int = data[0]
            value: Buffer = data[2:boundary]
            rest: Buffer = data[boundary:]
            return key, value, rest

        capabilities = Capabilities()

        # Empty optional parameters is valid
        if not data:
            return capabilities

        # Need at least 1 byte for option_len
        if len(data) < 1:
            raise Notify(2, 0, 'OPEN optional parameters too short')

        # Extended optional parameters (RFC 9072)
        option_len: int = data[0]

        # Check for extended format marker
        if option_len == Capabilities.EXTENDED_LENGTH:
            # Extended format needs at least 4 bytes: marker + type + 2-byte length
            if len(data) < 4:
                raise Notify(2, 0, f'OPEN extended parameters too short: need 4 bytes, got {len(data)}')
            option_type: int = data[1]
            if option_type == Capabilities.EXTENDED_LENGTH:
                option_len = unpack('!H', data[2:4])[0]
                if len(data) < option_len + 4:
                    raise Notify(
                        2, 0, f'OPEN extended parameters truncated: need {option_len + 4} bytes, got {len(data)}'
                    )
                data = data[4 : option_len + 4]
                decoder = _extended_type_length
            else:
                # Standard format with option_len=255
                if len(data) < option_len + 1:
                    raise Notify(2, 0, f'OPEN parameters truncated: need {option_len + 1} bytes, got {len(data)}')
                data = data[1 : option_len + 1]
                decoder = _key_values
        else:
            # Standard format
            if len(data) < option_len + 1:
                raise Notify(2, 0, f'OPEN parameters truncated: need {option_len + 1} bytes, got {len(data)}')
            data = data[1 : option_len + 1]
            decoder = _key_values

        if not option_len:
            return capabilities

        while data:
            key, value, data = decoder('parameter', data)

            # Parameters must only be sent once.
            if key == Parameter.AUTHENTIFICATION_INFORMATION:
                raise Notify(2, 5)

            if key == Parameter.CAPABILITIES:
                while value:
                    capability, capv, value = _key_values('capability', value)
                    capabilities[capability] = Capability.unpack(CapabilityCode(capability), capabilities, capv)
            else:
                raise Notify(2, 0, 'Unknow OPEN parameter {}'.format(hex(key)))
        return capabilities
