"""neighbor/__init__.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# import sys
from __future__ import annotations

import base64
from copy import deepcopy
from typing import Any
from typing import Dict
from typing import List
from typing import Tuple

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.neighbor import Neighbor
from exabgp.bgp.neighbor.capability import GracefulRestartConfig
from exabgp.util.enumeration import TriState

from exabgp.bgp.message import Action

from exabgp.bgp.message.update.nlri.flow import NLRI

from exabgp.configuration.core import Section
from exabgp.configuration.core import Parser
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Error

from exabgp.configuration.neighbor.api import ParseAPI
from exabgp.configuration.neighbor.family import ParseFamily
from exabgp.configuration.neighbor.family import ParseAddPath

from exabgp.configuration.parser import boolean
from exabgp.configuration.parser import auto_boolean
from exabgp.configuration.parser import ip
from exabgp.configuration.parser import peer_ip

# from exabgp.configuration.parser import asn
from exabgp.configuration.parser import auto_asn
from exabgp.configuration.parser import port
from exabgp.configuration.neighbor.parser import ttl
from exabgp.configuration.neighbor.parser import md5
from exabgp.configuration.neighbor.parser import hold_time
from exabgp.configuration.neighbor.parser import router_id
from exabgp.configuration.neighbor.parser import local_address
from exabgp.configuration.neighbor.parser import source_interface
from exabgp.configuration.neighbor.parser import hostname
from exabgp.configuration.neighbor.parser import domainname
from exabgp.configuration.neighbor.parser import description
from exabgp.configuration.neighbor.parser import inherit
from exabgp.configuration.neighbor.parser import rate_limit

from exabgp.environment import getenv

from exabgp.logger import log, lazymsg

# MD5 password length constraint (RFC 2385)
MAX_MD5_PASSWORD_LENGTH = 80  # Maximum length for TCP MD5 signature password


class ParseNeighbor(Section):
    TTL_SECURITY = 255

    syntax = ''

    known = {
        'inherit': inherit,
        'description': description,
        'host-name': hostname,
        'domain-name': domainname,
        'router-id': router_id,
        'hold-time': hold_time,
        'rate-limit': rate_limit,
        'local-address': local_address,
        'source-interface': source_interface,
        'peer-address': peer_ip,
        'local-as': auto_asn,
        'peer-as': auto_asn,
        'passive': boolean,
        'listen': port,
        'connect': port,
        'outgoing-ttl': ttl,
        'incoming-ttl': ttl,
        'md5-password': md5,
        'md5-base64': auto_boolean,
        'md5-ip': ip,
        'group-updates': boolean,
        'auto-flush': boolean,
        'adj-rib-out': boolean,
        'adj-rib-in': boolean,
        'manual-eor': boolean,
    }

    action = {
        'inherit': 'extend-command',
        'description': 'set-command',
        'host-name': 'set-command',
        'domain-name': 'set-command',
        'router-id': 'set-command',
        'hold-time': 'set-command',
        'rate-limit': 'set-command',
        'local-address': 'set-command',
        'source-interface': 'set-command',
        'peer-address': 'set-command',
        'local-as': 'set-command',
        'peer-as': 'set-command',
        'passive': 'set-command',
        'listen': 'set-command',
        'connect': 'set-command',
        'outgoing-ttl': 'set-command',
        'incoming-ttl': 'set-command',
        'md5-password': 'set-command',
        'md5-base64': 'set-command',
        'md5-ip': 'set-command',
        'group-updates': 'set-command',
        'auto-flush': 'set-command',
        'adj-rib-out': 'set-command',
        'adj-rib-in': 'set-command',
        'manual-eor': 'set-command',
        'route': 'append-name',
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
        self._neighbors: List[str] = []
        self.neighbors: Dict[str, Neighbor] = {}

    def clear(self) -> None:
        self._neighbors = []
        self.neighbors = {}

    def pre(self) -> bool:
        return self.parse(self.name, 'peer-address')

    def _post_get_scope(self) -> Dict[str, Any]:
        for inherited in self.scope.pop('inherit', []):
            data = self.scope.template('neighbor', inherited)
            self.scope.inherit(data)
        return self.scope.get()  # type: ignore[no-any-return]

    # Map config keys (with dashes) to Neighbor attributes (with underscores)
    _CONFIG_TO_ATTR: Dict[str, str] = {
        'description': 'description',
        'router-id': 'router_id',
        'local-address': 'local_address',
        'source-interface': 'source_interface',
        'peer-address': 'peer_address',
        'local-as': 'local_as',
        'peer-as': 'peer_as',
        'passive': 'passive',
        'listen': 'listen',
        'connect': 'connect',
        'hold-time': 'hold_time',
        'rate-limit': 'rate_limit',
        'host-name': 'host_name',
        'domain-name': 'domain_name',
        'group-updates': 'group_updates',
        'auto-flush': 'auto_flush',
        'adj-rib-in': 'adj_rib_in',
        'adj-rib-out': 'adj_rib_out',
        'manual-eor': 'manual_eor',
        'md5-password': 'md5_password',
        'md5-base64': 'md5_base64',
        'md5-ip': 'md5_ip',
        'outgoing-ttl': 'outgoing_ttl',
        'incoming-ttl': 'incoming_ttl',
    }

    def _post_neighbor(self, local: Dict[str, Any], families: List[Tuple[AFI, SAFI]]) -> Neighbor:
        neighbor = Neighbor()

        for config_key, attr_name in self._CONFIG_TO_ATTR.items():
            conf = local.get(config_key, None)
            if conf is not None:
                setattr(neighbor, attr_name, conf)

        if neighbor.local_address is None:
            neighbor.auto_discovery = True
            neighbor.local_address = None
            neighbor.md5_ip = None

        if not neighbor.router_id:
            if neighbor.peer_address.afi == AFI.ipv4 and not neighbor.auto_discovery:
                neighbor.router_id = neighbor.local_address

        for family in families:
            neighbor.add_family(family)

        return neighbor

    def _post_families(self, local: Dict[str, Any]) -> List[Tuple[AFI, SAFI]]:
        families: List[Tuple[AFI, SAFI]] = []
        for family in ParseFamily.convert:
            for pair in local.get('family', {}).get(family, []):
                families.append(pair)

        return families or NLRI.known_families()

    def _post_capa_default(self, neighbor: Neighbor, local: Dict[str, Any]) -> None:
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

    def _post_capa_addpath(self, neighbor: Neighbor, local: Dict[str, Any], families: List[Tuple[AFI, SAFI]]) -> None:
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

    def _post_capa_nexthop(self, neighbor: Neighbor, local: Dict[str, Any]) -> None:
        # The default is to auto-detect by the presence of the nexthop block
        # if this is manually set, then we honor it
        nexthop = local.get('nexthop', {})
        if neighbor.capability.nexthop.is_unset() and nexthop:
            neighbor.capability.nexthop = TriState.TRUE

        if not neighbor.capability.nexthop.is_enabled():
            return

        nexthops: List[Tuple[AFI, SAFI, AFI]] = []
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

    def _post_routes(self, neighbor: Neighbor, local: Dict[str, Any]) -> None:
        # NOTE: this may modify change but does not matter as want to modified

        neighbor.changes = []
        for change in self.scope.pop_routes():
            # remove_self may well have side effects on change
            neighbor.changes.append(neighbor.remove_self(change))

        # old format
        for section in ('static', 'l2vpn', 'flow'):
            routes = local.get(section, {}).get('routes', [])
            for route in routes:
                route.nlri.action = Action.ANNOUNCE
                # remove_self may well have side effects on change
                neighbor.changes.append(neighbor.remove_self(route))

        routes = local.get('routes', [])
        for route in routes:
            route.nlri.action = Action.ANNOUNCE
            # remove_self may well have side effects on change
            neighbor.changes.append(neighbor.remove_self(route))

    def _init_neighbor(self, neighbor: Neighbor, local: Dict[str, Any]) -> None:
        families = neighbor.families()
        for change in neighbor.changes:
            # remove_self may well have side effects on change
            change = neighbor.remove_self(change)
            if change.nlri.family().afi_safi() in families and neighbor.rib is not None:
                # This add the family to neighbor.families()
                neighbor.rib.outgoing.add_to_rib_watchdog(change)

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

        missing = neighbor.missing()
        if missing:
            return self.error.set('incomplete neighbor, missing {}'.format(missing))
        neighbor.infer()

        if not neighbor.auto_discovery and neighbor.local_address.afi != neighbor.peer_address.afi:
            return self.error.set('local-address and peer-address must be of the same family')
        neighbor.range_size = neighbor.peer_address.mask.size()

        if neighbor.range_size > 1 and not (neighbor.passive or getenv().bgp.passive):
            return self.error.set('can only use ip ranges for the peer address with passive neighbors')

        if neighbor.index() in self._neighbors:
            return self.error.set('duplicate peer definition {}'.format(neighbor.peer_address.top()))
        self._neighbors.append(neighbor.index())

        if neighbor.md5_password:
            try:
                md5 = base64.b64decode(neighbor.md5_password) if neighbor.md5_base64 else neighbor.md5_password
            except TypeError as e:
                return self.error.set(f'Invalid base64 encoding of MD5 password ({e})')
            else:
                if len(md5) > MAX_MD5_PASSWORD_LENGTH:
                    return self.error.set(f'MD5 password must be no larger than {MAX_MD5_PASSWORD_LENGTH} characters')

        # check we are not trying to announce routes without the right MP announcement
        for change in neighbor.changes:
            family = change.nlri.family().afi_safi()
            if family not in families and family != (AFI.ipv4, SAFI.unicast):
                return self.error.set(
                    'Trying to announce a route of type {},{} when we are not announcing the family to our peer'.format(
                        *change.nlri.family().afi_safi()
                    ),
                )

        # create one neighbor object per family for multisession
        if neighbor.capability.multi_session.is_enabled() and len(neighbor.families()) > 1:
            for family in neighbor.families():
                # XXX: FIXME: Ok, it works but it takes LOTS of memory ..
                m_neighbor = deepcopy(neighbor)
                m_neighbor.make_rib()
                if m_neighbor.rib is not None:
                    m_neighbor.rib.outgoing.families = {family}
                self._init_neighbor(m_neighbor, local)
        else:
            neighbor.make_rib()
            self._init_neighbor(neighbor, local)

        local.clear()
        return True
