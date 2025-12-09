"""neighbor/__init__.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# import sys
from __future__ import annotations

from copy import deepcopy
from typing import Any

from exabgp.bgp.message import Action
from exabgp.bgp.message.update.nlri.flow import NLRI
from exabgp.bgp.neighbor import Neighbor
from exabgp.bgp.neighbor.capability import GracefulRestartConfig
from exabgp.configuration.core import Error, Parser, Scope, Section
from exabgp.configuration.neighbor.api import ParseAPI
from exabgp.configuration.neighbor.family import ParseAddPath, ParseFamily
from exabgp.configuration.neighbor.parser import (
    hold_time,
    inherit,
    local_address,
    router_id,
    ttl,
)

# from exabgp.configuration.parser import asn
from exabgp.configuration.parser import auto_asn, auto_boolean

# Removed imports migrated to schema validators:
# description, domainname, hostname, md5, rate_limit, source_interface
from exabgp.configuration.schema import Container, Leaf, ValueType

# Removed imports migrated to schema validators: boolean, ip, peer_ip, port
from exabgp.environment import getenv
from exabgp.logger import lazymsg, log
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP, IPRange
from exabgp.util.enumeration import TriState


class ParseNeighbor(Section):
    TTL_SECURITY = 255

    # Schema definition for BGP neighbor configuration
    schema = Container(
        description='BGP neighbor (peer) configuration',
        children={
            # Session parameters
            'peer-address': Leaf(
                type=ValueType.IP_RANGE,
                description='IP address or range of the BGP peer',
                mandatory=True,
                action='set-command',
                example='127.0.0.1',
            ),
            'local-address': Leaf(
                type=ValueType.IP_ADDRESS,
                description='Local IP address for the BGP session',
            ),
            'local-as': Leaf(
                type=ValueType.ASN,
                description='Local AS number (or "auto" to copy peer-as)',
                mandatory=True,
            ),
            'peer-as': Leaf(
                type=ValueType.ASN,
                description='Peer AS number (or "auto" to copy local-as)',
                mandatory=True,
            ),
            'router-id': Leaf(
                type=ValueType.IP_ADDRESS,
                description='BGP router ID (defaults to local-address)',
            ),
            'description': Leaf(
                type=ValueType.STRING,
                description='Neighbor description',
                action='set-command',
            ),
            'host-name': Leaf(
                type=ValueType.STRING,
                description='Hostname capability value',
                action='set-command',
            ),
            'domain-name': Leaf(
                type=ValueType.STRING,
                description='Domain name capability value',
                action='set-command',
            ),
            # Timers
            'hold-time': Leaf(
                type=ValueType.INTEGER,
                description='BGP hold time in seconds (0 disables)',
                default=180,
                min_value=0,
                max_value=65535,
            ),
            'rate-limit': Leaf(
                type=ValueType.INTEGER,
                description='Rate limit for updates (messages per second)',
                action='set-command',
            ),
            # Connection options
            'passive': Leaf(
                type=ValueType.BOOLEAN,
                description='Wait for incoming connections',
                default=True,
                action='set-command',
            ),
            'listen': Leaf(
                type=ValueType.PORT,
                description='Local TCP port to listen on',
                default=179,
                action='set-command',
            ),
            'connect': Leaf(
                type=ValueType.PORT,
                description='Remote TCP port to connect to',
                default=179,
                action='set-command',
            ),
            'source-interface': Leaf(
                type=ValueType.STRING,
                description='Source interface for BGP session',
                action='set-command',
            ),
            # TTL security
            'outgoing-ttl': Leaf(
                type=ValueType.INTEGER,
                description='TTL for outgoing packets (255 for GTSM)',
                min_value=1,
                max_value=255,
            ),
            'incoming-ttl': Leaf(
                type=ValueType.INTEGER,
                description='Minimum TTL for incoming packets (GTSM)',
                min_value=1,
                max_value=255,
            ),
            # Authentication
            'md5-password': Leaf(
                type=ValueType.STRING,
                description='TCP MD5 authentication password',
                action='set-command',
            ),
            'md5-base64': Leaf(
                type=ValueType.BOOLEAN,
                description='Password is base64 encoded',
                default=False,
            ),
            'md5-ip': Leaf(
                type=ValueType.IP_ADDRESS,
                description='IP address for MD5 authentication',
                action='set-command',
            ),
            # Behavior options
            'group-updates': Leaf(
                type=ValueType.BOOLEAN,
                description='Group updates for efficiency',
                default=True,
                action='set-command',
            ),
            'auto-flush': Leaf(
                type=ValueType.BOOLEAN,
                description='Auto-flush updates',
                default=True,
                action='set-command',
            ),
            'adj-rib-out': Leaf(
                type=ValueType.BOOLEAN,
                description='Maintain Adj-RIB-Out',
                default=False,
                action='set-command',
            ),
            'adj-rib-in': Leaf(
                type=ValueType.BOOLEAN,
                description='Maintain Adj-RIB-In',
                default=False,
                action='set-command',
            ),
            'manual-eor': Leaf(
                type=ValueType.BOOLEAN,
                description='Manual End-of-RIB control',
                default=False,
                action='set-command',
            ),
            'inherit': Leaf(
                type=ValueType.STRING,
                description='Inherit from template',
            ),
            # Subsections
            'family': Container(description='Address families to negotiate'),
            'capability': Container(description='BGP capabilities'),
            'add-path': Container(description='ADD-PATH configuration'),
            'nexthop': Container(description='Next-hop encoding options'),
            'api': Container(description='External process API'),
            'static': Container(description='Static routes to announce'),
            'flow': Container(description='FlowSpec rules'),
            'l2vpn': Container(description='L2VPN/VPLS configuration'),
            'operational': Container(description='Operational messages'),
            'announce': Container(description='Route announcements'),
        },
    )

    syntax = ''

    known = {
        # Cannot migrate (return complex types or optional values):
        'inherit': inherit,  # returns list[str]
        'router-id': router_id,  # returns RouterID object
        'hold-time': hold_time,  # returns HoldTime object
        'local-address': local_address,  # returns IP|None
        'local-as': auto_asn,  # returns ASN|None
        'peer-as': auto_asn,  # returns ASN|None
        'outgoing-ttl': ttl,  # returns int|None
        'incoming-ttl': ttl,  # returns int|None
        'md5-base64': auto_boolean,  # returns bool|None
        # Migrated to schema validators:
        # description, host-name, domain-name, source-interface, md5-password,
        # passive, listen, connect, group-updates, auto-flush, adj-rib-out,
        # adj-rib-in, manual-eor, peer-address, md5-ip, rate-limit
    }

    action = {
        # Cannot migrate (return complex types or optional values):
        'inherit': 'extend-command',
        'router-id': 'set-command',
        'hold-time': 'set-command',
        'local-address': 'set-command',
        'local-as': 'set-command',
        'peer-as': 'set-command',
        'outgoing-ttl': 'set-command',
        'incoming-ttl': 'set-command',
        'md5-base64': 'set-command',
        'route': 'append-name',
        # Migrated to schema: description, host-name, domain-name, source-interface,
        # md5-password, passive, listen, connect, group-updates, auto-flush,
        # adj-rib-out, adj-rib-in, manual-eor, peer-address, md5-ip, rate-limit
    }

    default = {
        'md5-base64': False,
        'passive': True,
        'group-updates': True,
        'auto-flush': True,
        'adj-rib-out': False,
        'adj-rib-in': False,
        'manual-eor': False,
    }

    name = 'neighbor'

    def __init__(self, parser: Parser, scope: Scope, error: Error) -> None:
        Section.__init__(self, parser, scope, error)
        self._neighbors: list[str] = []
        self.neighbors: dict[str, Neighbor] = {}

    def clear(self) -> None:
        self._neighbors = []
        self.neighbors = {}

    def pre(self) -> bool:
        return self.parse(self.name, 'peer-address')

    def _post_get_scope(self) -> dict[str, Any]:
        for inherited in self.scope.pop('inherit', []):
            data = self.scope.template('neighbor', inherited)
            self.scope.inherit(data)
        return self.scope.get()

    # Map config keys to Neighbor attributes (BGP policy)
    _CONFIG_TO_NEIGHBOR: dict[str, str] = {
        'description': 'description',
        'hold-time': 'hold_time',
        'rate-limit': 'rate_limit',
        'host-name': 'host_name',
        'domain-name': 'domain_name',
        'group-updates': 'group_updates',
        'auto-flush': 'auto_flush',
        'adj-rib-in': 'adj_rib_in',
        'adj-rib-out': 'adj_rib_out',
        'manual-eor': 'manual_eor',
    }

    # Map config keys to Session attributes (connection config)
    _CONFIG_TO_SESSION: dict[str, str] = {
        'router-id': 'router_id',
        'local-address': 'local_address',
        'source-interface': 'source_interface',
        'peer-address': 'peer_address',
        'local-as': 'local_as',
        'peer-as': 'peer_as',
        'passive': 'passive',
        'listen': 'listen',
        'connect': 'connect',
        'md5-password': 'md5_password',
        'md5-base64': 'md5_base64',
        'md5-ip': 'md5_ip',
        'outgoing-ttl': 'outgoing_ttl',
        'incoming-ttl': 'incoming_ttl',
    }

    def _post_neighbor(self, local: dict[str, Any], families: list[tuple[AFI, SAFI]]) -> Neighbor:
        neighbor = Neighbor()

        # Set neighbor (BGP policy) attributes
        for config_key, attr_name in self._CONFIG_TO_NEIGHBOR.items():
            conf = local.get(config_key, None)
            if conf is not None:
                setattr(neighbor, attr_name, conf)

        # Set session (connection) attributes
        for config_key, attr_name in self._CONFIG_TO_SESSION.items():
            conf = local.get(config_key, None)
            if conf is not None:
                setattr(neighbor.session, attr_name, conf)

        # auto_discovery is now derived from local_address being IP.NoNextHop
        # (which is the default if local-address is not set in config)
        if neighbor.session.auto_discovery:
            neighbor.session.md5_ip = None

        # Derive optional fields (router_id, md5_ip) from required ones
        neighbor.session.infer()

        # Check for missing required session fields
        missing = neighbor.session.missing()
        if missing:
            self.error.set(f'{missing} must be set')

        for family in families:
            neighbor.add_family(family)

        return neighbor

    def _post_families(self, local: dict[str, Any]) -> list[tuple[AFI, SAFI]]:
        families: list[tuple[AFI, SAFI]] = []
        for family in ParseFamily.convert:
            for pair in local.get('family', {}).get(family, []):
                families.append(pair)

        return families or NLRI.known_families()

    def _post_capa_default(self, neighbor: Neighbor, local: dict[str, Any]) -> None:
        capability = local.get('capability', {})
        cap = neighbor.capability

        # Map config keys to typed attributes
        if 'asn4' in capability:
            cap.asn4 = TriState.from_bool(capability['asn4'])
        if 'extended-message' in capability:
            cap.extended_message = TriState.from_bool(capability['extended-message'])
        if 'multi-session' in capability:
            cap.multi_session = TriState.from_bool(capability['multi-session'])
        if 'operational' in capability:
            cap.operational = TriState.from_bool(capability['operational'])
        if 'nexthop' in capability:
            cap.nexthop = TriState.from_bool(capability['nexthop'])
        if 'aigp' in capability:
            cap.aigp = TriState.from_bool(capability['aigp'])
        if 'add-path' in capability:
            cap.add_path = capability['add-path']
        if 'route-refresh' in capability:
            cap.route_refresh = 2 if capability['route-refresh'] else 0  # REFRESH.NORMAL or 0
        if 'software-version' in capability:
            cap.software_version = 'exabgp' if capability['software-version'] else None
        if 'graceful-restart' in capability:
            gr = capability['graceful-restart']
            if gr is False:
                cap.graceful_restart = GracefulRestartConfig.disabled()
            elif isinstance(gr, int):
                # gr == 0 means enabled but use hold-time (inferred later)
                cap.graceful_restart = GracefulRestartConfig.with_time(gr)

    def _post_capa_addpath(self, neighbor: Neighbor, local: dict[str, Any], families: list[tuple[AFI, SAFI]]) -> None:
        if not neighbor.capability.add_path:
            return

        add_path = local.get('add-path', {})
        if not add_path:
            for family in families:
                neighbor.add_addpath(family)
            return

        for afi_name in ParseAddPath.convert:
            for pair in add_path.get(afi_name, []):
                if pair not in families:
                    pair_log = pair

                    def _log_skip(pair_arg: tuple[AFI, SAFI] = pair_log) -> str:
                        return 'skipping add-path family ' + str(pair_arg) + ' as it is not negotiated'

                    log.debug(_log_skip, 'configuration')
                    continue
                neighbor.add_addpath(pair)

    def _post_capa_nexthop(self, neighbor: Neighbor, local: dict[str, Any]) -> None:
        # The default is to auto-detect by the presence of the nexthop block
        # if this is manually set, then we honor it
        nexthop = local.get('nexthop', {})
        if neighbor.capability.nexthop.is_unset() and nexthop:
            neighbor.capability.nexthop = TriState.TRUE

        if not neighbor.capability.nexthop.is_enabled():
            return

        nexthops: list[tuple[AFI, SAFI, AFI]] = []
        for family in nexthop:
            nexthops.extend(nexthop[family])

        if not nexthops:
            return

        for afi, safi, nhafi in nexthops:
            if (afi, safi) not in neighbor.families():
                log.debug(
                    lazymsg('nexthop.skipped afi={afi} safi={safi} reason=not_negotiated', afi=afi, safi=safi),
                    'configuration',
                )
                continue
            if (nhafi, safi) not in neighbor.families():
                log.debug(
                    lazymsg('nexthop.skipped afi={nhafi} safi={safi} reason=not_negotiated', nhafi=nhafi, safi=safi),
                    'configuration',
                )
                continue
            neighbor.add_nexthop(afi, safi, nhafi)

    def _post_capa_rr(self, neighbor: Neighbor) -> None:
        if neighbor.capability.route_refresh:
            if neighbor.adj_rib_out:
                log.debug(lazymsg('neighbor.capability.route_refresh action=enable_adj_rib_out'), 'configuration')

    def _post_routes(self, neighbor: Neighbor, local: dict[str, Any]) -> None:
        # NOTE: this may modify change but does not matter as want to modified

        neighbor.routes = []
        for route in self.scope.pop_routes():
            # remove_self may well have side effects on route
            neighbor.routes.append(neighbor.resolve_self(route))

        # old format
        for section in ('static', 'l2vpn', 'flow'):
            routes = local.get(section, {}).get('routes', [])
            for route in routes:
                route = route.with_action(Action.ANNOUNCE)
                # remove_self may well have side effects on route
                neighbor.routes.append(neighbor.resolve_self(route))

        routes = local.get('routes', [])
        for route in routes:
            route = route.with_action(Action.ANNOUNCE)
            # remove_self may well have side effects on route
            neighbor.routes.append(neighbor.resolve_self(route))

    def _init_neighbor(self, neighbor: Neighbor, local: dict[str, Any]) -> None:
        families = neighbor.families()
        for route in neighbor.routes:
            # remove_self may well have side effects on route
            route = neighbor.resolve_self(route)
            if route.nlri.family().afi_safi() in families:
                # This add the family to neighbor.families()
                neighbor.rib.outgoing.add_to_rib_watchdog(route)

        for message in local.get('operational', {}).get('routes', []):
            if message.family().afi_safi() in families:
                if message.name == 'ASM':
                    neighbor.asm[message.family().afi_safi()] = message
                else:
                    neighbor.messages.append(message)
        self.neighbors[neighbor.name()] = neighbor

    def post(self) -> bool:
        local = self._post_get_scope()
        families = self._post_families(local)
        neighbor = self._post_neighbor(local, families)

        self._post_capa_default(neighbor, local)
        self._post_capa_addpath(neighbor, local, families)
        self._post_capa_nexthop(neighbor, local)
        self._post_routes(neighbor, local)

        neighbor.api = ParseAPI.flatten(local.pop('api', {}))

        neighbor.infer()
        missing = neighbor.missing()
        if missing:
            return self.error.set('incomplete neighbor, missing {}'.format(missing))

        if not neighbor.session.auto_discovery:
            if neighbor.session.local_address.afi != neighbor.session.peer_address.afi:
                return self.error.set('local-address and peer-address must be of the same family')
        if neighbor.session.peer_address is IP.NoNextHop:
            return self.error.set('peer-address must be set')

        # peer_address is always IPRange when parsed from configuration (see parser.peer_ip)
        assert isinstance(neighbor.session.peer_address, IPRange)
        peer_range = neighbor.session.peer_address
        neighbor.range_size = peer_range.mask.size()

        if neighbor.range_size > 1 and not (neighbor.session.passive or getenv().bgp.passive):
            return self.error.set('can only use ip ranges for the peer address with passive neighbors')

        if neighbor.index() in self._neighbors:
            return self.error.set('duplicate peer definition {}'.format(neighbor.session.peer_address.top()))
        self._neighbors.append(neighbor.index())

        md5_error = neighbor.session.validate_md5()
        if md5_error:
            return self.error.set(md5_error)

        # check we are not trying to announce routes without the right MP announcement
        for route in neighbor.routes:
            family = route.nlri.family().afi_safi()
            if family not in families and family != (AFI.ipv4, SAFI.unicast):
                return self.error.set(
                    'Trying to announce a route of type {},{} when we are not announcing the family to our peer'.format(
                        *route.nlri.family().afi_safi()
                    ),
                )

        # create one neighbor object per family for multisession
        if neighbor.capability.multi_session.is_enabled() and len(neighbor.families()) > 1:
            for family in neighbor.families():
                # XXX: FIXME: Ok, it works but it takes LOTS of memory ..
                m_neighbor = deepcopy(neighbor)
                m_neighbor.make_rib()
                m_neighbor.rib.outgoing.families = {family}
                self._init_neighbor(m_neighbor, local)
        else:
            neighbor.make_rib()
            self._init_neighbor(neighbor, local)

        local.clear()
        return True
