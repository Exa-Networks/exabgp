# encoding: utf-8
"""
neighbor/__init__.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# import sys
import base64
from copy import deepcopy

from exabgp.util.dns import host, domain

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.neighbor import Neighbor

from exabgp.bgp.message import OUT

# from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.holdtime import HoldTime

from exabgp.bgp.message.update.nlri.flow import NLRI

from exabgp.configuration.core import Section
from exabgp.configuration.neighbor.api import ParseAPI
from exabgp.configuration.neighbor.family import ParseFamily
from exabgp.configuration.neighbor.nexthop import ParseNextHop
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
from exabgp.configuration.neighbor.parser import hostname
from exabgp.configuration.neighbor.parser import domainname
from exabgp.configuration.neighbor.parser import description
from exabgp.configuration.neighbor.parser import inherit
from exabgp.configuration.neighbor.parser import rate_limit


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

    def __init__(self, tokeniser, scope, error, logger):
        Section.__init__(self, tokeniser, scope, error, logger)
        self._neighbors = []
        self.neighbors = {}

    def clear(self):
        self._neighbors = []
        self.neighbors = {}

    def pre(self):
        return self.parse(self.name, 'peer-address')

    def post(self):
        for inherit in self.scope.pop('inherit', []):
            data = self.scope.template('neighbor', inherit)
            self.scope.inherit(data)
        local = self.scope.get()

        neighbor = Neighbor()

        # XXX: use the right class for the data type
        # XXX: we can use the scope.nlri interface ( and rename it ) to set some values
        neighbor.router_id = local.get('router-id', None)
        neighbor.peer_address = local.get('peer-address', None)
        neighbor.local_address = local.get('local-address', None)
        neighbor.local_as = local.get('local-as', None)
        neighbor.peer_as = local.get('peer-as', None)
        neighbor.passive = local.get('passive', None)
        neighbor.listen = local.get('listen', 0)
        neighbor.connect = local.get('connect', 0)
        neighbor.hold_time = local.get('hold-time', HoldTime(180))
        neighbor.rate_limit = local.get('rate-limit', 0)
        neighbor.host_name = local.get('host-name', host())
        neighbor.domain_name = local.get('domain-name', domain())
        neighbor.md5_password = local.get('md5-password', None)
        neighbor.md5_base64 = local.get('md5-base64', None)
        neighbor.md5_ip = local.get('md5-ip', neighbor.local_address)
        neighbor.description = local.get('description', '')
        neighbor.flush = local.get('auto-flush', True)
        neighbor.adj_rib_out = local.get('adj-rib-out', True)
        neighbor.adj_rib_in = local.get('adj-rib-in', True)
        neighbor.aigp = local.get('aigp', None)
        neighbor.ttl_out = local.get('outgoing-ttl', None)
        neighbor.ttl_in = local.get('incoming-ttl', None)
        neighbor.group_updates = local.get('group-updates', True)
        neighbor.manual_eor = local.get('manual-eor', False)

        if neighbor.local_address is None:
            return self.error.set('incomplete neighbor, missing local-address')
        if neighbor.local_as is None:
            return self.error.set('incomplete neighbor, missing local-as')
        if neighbor.peer_as is None:
            return self.error.set('incomplete neighbor, missing peer-as')

        if neighbor.passive is None:
            neighbor.passive = False

        capability = local.get('capability', {})
        neighbor.nexthop = capability.get('nexthop', None)
        neighbor.add_path = capability.get('add-path', 0)
        neighbor.asn4 = capability.get('asn4', True)
        neighbor.extended_message = capability.get('extended-message', True)
        neighbor.multisession = capability.get('multi-session', False)
        neighbor.operational = capability.get('operational', False)
        neighbor.route_refresh = capability.get('route-refresh', 0)

        if capability.get('graceful-restart', False) is not False:
            neighbor.graceful_restart = capability.get('graceful-restart', 0) or int(neighbor.hold_time)

        neighbor.api = ParseAPI.flatten(local.pop('api', {}))

        families = []
        for family in ParseFamily.convert:
            for pair in local.get('family', {}).get(family, []):
                families.append(pair)

        families = families or NLRI.known_families()

        for family in families:
            neighbor.add_family(family)

        if neighbor.add_path:
            add_path = local.get('add-path', {})
            if add_path:
                for family in ParseAddPath.convert:
                    for pair in add_path.get(family, []):
                        if pair not in families:
                            self.logger.debug(
                                'skipping add-path family ' + str(pair) + ' as it is not negotiated', 'configuration'
                            )
                            continue
                        neighbor.add_addpath(pair)
            else:
                for family in families:
                    neighbor.add_addpath(family)

        # The default is to auto-detect by the presence of the nexthop block
        # if this is manually set, then we honor it
        nexthop = local.get('nexthop', {})
        if neighbor.nexthop is None and nexthop:
            neighbor.nexthop = True

        if neighbor.nexthop:
            nexthops = []
            for family in nexthop:
                nexthops.extend(nexthop[family])
            if nexthops:
                for afi, safi, nhafi in nexthops:
                    if (afi, safi) not in neighbor.families():
                        self.logger.debug(
                            'skipping nexthop afi,safi ' + str(afi) + '/' + str(safi) + ' as it is not negotiated',
                            'configuration',
                        )
                        continue
                    if (nhafi, safi) not in neighbor.families():
                        self.logger.debug(
                            'skipping nexthop afi ' + str(nhafi) + '/' + str(safi) + ' as it is not negotiated',
                            'configuration',
                        )
                        continue
                    neighbor.add_nexthop(afi, safi, nhafi)

        neighbor.changes = []
        neighbor.changes.extend(self.scope.pop_routes())

        # old format
        for section in ('static', 'l2vpn', 'flow'):
            routes = local.get(section, {}).get('routes', [])
            for route in routes:
                route.nlri.action = OUT.ANNOUNCE
            neighbor.changes.extend(routes)

        routes = local.get('routes', [])
        for route in routes:
            route.nlri.action = OUT.ANNOUNCE
        neighbor.changes.extend(routes)

        messages = local.get('operational', {}).get('routes', [])

        if neighbor.local_address is None:
            neighbor.auto_discovery = True
            neighbor.local_address = None
            neighbor.md5_ip = None

        if not neighbor.router_id:
            if neighbor.peer_address.afi == AFI.ipv4 and not neighbor.auto_discovery:
                neighbor.router_id = neighbor.local_address
            else:
                return self.error.set('missing router-id for the peer, it can not be set using the local-ip')

        if neighbor.route_refresh:
            if neighbor.adj_rib_out:
                self.logger.debug('route-refresh requested, enabling adj-rib-out', 'configuration')

        missing = neighbor.missing()
        if missing:
            return self.error.set('incomplete neighbor, missing %s' % missing)

        if not neighbor.auto_discovery and neighbor.local_address.afi != neighbor.peer_address.afi:
            return self.error.set('local-address and peer-address must be of the same family')
        neighbor.range_size = neighbor.peer_address.mask.size()

        if neighbor.range_size > 1 and not neighbor.passive:
            return self.error.set('can only use ip ranges for the peer address with passive neighbors')

        if neighbor.index() in self._neighbors:
            return self.error.set('duplicate peer definition %s' % neighbor.peer_address.top())
        self._neighbors.append(neighbor.index())

        if neighbor.md5_password:
            try:
                md5 = base64.b64decode(neighbor.md5_password) if neighbor.md5_base64 else neighbor.md5_password
            except TypeError as e:
                return self.error.set("Invalid base64 encoding of MD5 password.")
            else:
                if len(md5) > 80:
                    return self.error.set('MD5 password must be no larger than 80 characters')

        # check we are not trying to announce routes without the right MP announcement
        for change in neighbor.changes:
            family = change.nlri.family()
            if family not in families and family != (AFI.ipv4, SAFI.unicast):
                return self.error.set(
                    'Trying to announce a route of type %s,%s when we are not announcing the family to our peer'
                    % change.nlri.family()
                )

        def _init_neighbor(neighbor):
            families = neighbor.families()
            for change in neighbor.changes:
                if change.nlri.family() in families:
                    # This add the family to neighbor.families()
                    neighbor.rib.outgoing.add_to_rib_watchdog(change)
            for message in messages:
                if message.family() in families:
                    if message.name == 'ASM':
                        neighbor.asm[message.family()] = message
                    else:
                        neighbor.messages.append(message)
            self.neighbors[neighbor.name()] = neighbor

        # create one neighbor object per family for multisession
        if neighbor.multisession and len(neighbor.families()) > 1:
            for family in neighbor.families():
                # XXX: FIXME: Ok, it works but it takes LOTS of memory ..
                m_neighbor = deepcopy(neighbor)
                m_neighbor.make_rib()
                m_neighbor.rib.outgoing.families = [family]
                _init_neighbor(m_neighbor)
        else:
            neighbor.make_rib()
            _init_neighbor(neighbor)

        local.clear()
        return True
