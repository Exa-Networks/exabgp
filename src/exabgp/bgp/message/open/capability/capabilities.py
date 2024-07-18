# encoding: utf-8
"""
capabilities.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message.open.capability.capability import Capability
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

# =================================================================== Parameter
#


class Parameter(int):
    AUTHENTIFICATION_INFORMATION = 0x01  # Depreciated
    CAPABILITIES = 0x02

    def __str__(self):
        if self == 0x01:
            return "AUTHENTIFICATION INFORMATION"
        if self == 0x02:
            return "OPTIONAL"
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


class Capabilities(dict):
    _ADD_PATH = [
        (AFI.ipv4, SAFI.unicast),
        (AFI.ipv6, SAFI.unicast),
        (AFI.ipv4, SAFI.nlri_mpls),
        (AFI.ipv6, SAFI.nlri_mpls),
        (AFI.ipv4, SAFI.mpls_vpn),
        (AFI.ipv6, SAFI.mpls_vpn),
        (AFI.ipv4, SAFI.mup),
        (AFI.ipv6, SAFI.mup),
    ]

    _NEXTHOP = [
        (AFI.ipv4, SAFI.unicast, AFI.ipv6),
        (AFI.ipv4, SAFI.multicast, AFI.ipv6),
        (AFI.ipv4, SAFI.nlri_mpls, AFI.ipv6),
        (AFI.ipv4, SAFI.mpls_vpn, AFI.ipv6),
    ]

    def announced(self, capability):
        return capability in self

    def __str__(self):
        r = []
        for key in sorted(self.keys()):
            r.append(str(self[key]))
        return ', '.join(r)

    def _protocol(self, neighbor):
        families = neighbor.families()
        mp = MultiProtocol()
        mp.extend(families)
        self[Capability.CODE.MULTIPROTOCOL] = mp

    def _asn4(self, neighbor):
        if not neighbor['capability']['asn4']:
            return

        self[Capability.CODE.FOUR_BYTES_ASN] = ASN4(neighbor['local-as'])

    def _nexthop(self, neighbor):
        if not neighbor['capability']['nexthop']:
            return

        nexthops = neighbor.nexthops()
        nh_pairs = []
        for allowed in self._NEXTHOP:
            if allowed not in nexthops:
                continue
            nh_pairs.append(allowed)
        self[Capability.CODE.NEXTHOP] = NextHop(nh_pairs)

    def _addpath(self, neighbor):
        if not neighbor['capability']['add-path']:
            return

        families = neighbor.addpaths()
        ap_families = []
        for allowed in self._ADD_PATH:
            if allowed in families:
                ap_families.append(allowed)
        self[Capability.CODE.ADD_PATH] = AddPath(ap_families, neighbor['capability']['add-path'])

    def _graceful(self, neighbor, restarted):
        if not neighbor['capability']['graceful-restart']:
            return

        self[Capability.CODE.GRACEFUL_RESTART] = Graceful().set(
            Graceful.RESTART_STATE if restarted else 0x0,
            neighbor['capability']['graceful-restart'],
            [(afi, safi, Graceful.FORWARDING_STATE) for (afi, safi) in neighbor.families()],
        )

    def _refresh(self, neighbor):
        if not neighbor['capability']['route-refresh']:
            return
        self[Capability.CODE.ROUTE_REFRESH] = RouteRefresh()
        self[Capability.CODE.ENHANCED_ROUTE_REFRESH] = EnhancedRouteRefresh()

    def _extended_message(self, neighbor):
        if not neighbor['capability']['extended-message']:
            return

        self[Capability.CODE.EXTENDED_MESSAGE] = ExtendedMessage()

    def _hostname(self, neighbor):
        self[Capability.CODE.HOSTNAME] = HostName(neighbor['host-name'], neighbor['domain-name'])

    def _software_version(self, neighbor):
        if not neighbor['capability']['software-version']:
            return

        self[Capability.CODE.SOFTWARE_VERSION] = Software()

    def _operational(self, neighbor):
        if not neighbor['capability']['operational']:
            return
        self[Capability.CODE.OPERATIONAL] = Operational()

    def _session(self, neighbor):
        if not neighbor['capability']['multi-session']:
            return
        # XXX: FIXME: should it not be the RFC version ?
        self[Capability.CODE.MULTISESSION] = MultiSession().set([Capability.CODE.MULTIPROTOCOL])

    def new(self, neighbor, restarted):
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
        self._session(neighbor)  # MUST be the last key added, really !?! dict is not ordered !
        return self

    def pack(self):
        parameters = b''
        for k, capabilities in self.items():
            for capability in capabilities.extract():
                if len(capability) == 0:
                    continue
                encoded = bytes([k, len(capability)]) + capability
                parameters += bytes([2, len(encoded)]) + encoded

        if len(parameters) < 255:
            return bytes([len(parameters)]) + parameters

        # If this is an extended optional parameters version, re-encode
        # the OPEN message.

        parameters = b''
        for k, capabilities in self.items():
            for capability in capabilities.extract():
                if len(capability) == 0:
                    continue
                encoded = bytes([k, len(capability)]) + capability
                parameters += pack('!BH', 2, len(encoded)) + encoded

        return pack('!BBH', 255, 255, len(parameters)) + parameters

    @staticmethod
    def unpack(data):
        def _extended_type_length(name, data):
            if len(data) < 3:
                raise Notify(2, 0, "Bad length for OPEN (extended) %s (<3) %s" % (name, Capability.hex(data)))
            # Optional parameters length
            ld = unpack('!H', data[1:3])[0]
            boundary = ld + 3
            if len(data) < boundary:
                raise Notify(
                    2, 0, "Bad length for OPEN (extended) %s (buffer underrun) %s" % (name, Capability.hex(data))
                )
            key = data[0]
            value = data[3:boundary]
            rest = data[boundary:]
            return key, value, rest

        def _key_values(name, data):
            if len(data) < 2:
                raise Notify(2, 0, "Bad length for OPEN %s (<2) %s" % (name, Capability.hex(data)))
            ld = data[1]
            boundary = ld + 2
            if len(data) < boundary:
                raise Notify(2, 0, "Bad length for OPEN %s (buffer underrun) %s" % (name, Capability.hex(data)))
            key = data[0]
            value = data[2:boundary]
            rest = data[boundary:]
            return key, value, rest

        capabilities = Capabilities()

        # Extended optional parameters
        option_len = data[0]
        option_type = data[1]

        if option_len == 255 and option_type == 255:
            option_len = unpack('!H', data[2:4])[0]
            data = data[4 : option_len + 4]
            decoder = _extended_type_length
        else:
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
                    capabilities[capability] = Capability.unpack(capability, capabilities, capv)
            else:
                raise Notify(2, 0, 'Unknow OPEN parameter %s' % hex(key))
        return capabilities
