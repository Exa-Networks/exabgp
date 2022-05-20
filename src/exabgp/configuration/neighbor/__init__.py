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

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.neighbor import Neighbor

from exabgp.bgp.message import Action

from exabgp.bgp.message.update.nlri.flow import NLRI

from exabgp.configuration.core import Section
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
from exabgp.configuration.neighbor.parser import hostname
from exabgp.configuration.neighbor.parser import domainname
from exabgp.configuration.neighbor.parser import description
from exabgp.configuration.neighbor.parser import inherit
from exabgp.configuration.neighbor.parser import rate_limit

from exabgp.environment import getenv

from exabgp.logger import log


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

    def __init__(self, tokeniser, scope, error):
        Section.__init__(self, tokeniser, scope, error)
        self._neighbors = []
        self.neighbors = {}

    def clear(self):
        self._neighbors = []
        self.neighbors = {}

    def pre(self):
        return self.parse(self.name, 'peer-address')

    def post(self):
        for inherited in self.scope.pop('inherit', []):
            data = self.scope.template('neighbor', inherited)
            self.scope.inherit(data)
        local = self.scope.get()

        neighbor = Neighbor()

        for option in neighbor.defaults:
            conf = local.get(option, None)
            if conf is not None:
                neighbor[option] = conf

        # XXX: use the right class for the data type
        # XXX: we can use the scope.nlri interface ( and rename it ) to set some values

        capability = local.get('capability', {})
        for option in neighbor.Capability.defaults:
            conf = capability.get(option, None)
            if conf is not None:
                neighbor['capability'][option] = conf

        neighbor.api = ParseAPI.flatten(local.pop('api', {}))

        missing = neighbor.missing()
        if missing:
            return self.error.set(missing)
        neighbor.infer()

        families = []
        for family in ParseFamily.convert:
            for pair in local.get('family', {}).get(family, []):
                families.append(pair)

        families = families or NLRI.known_families()

        for family in families:
            neighbor.add_family(family)

        if neighbor['capability']['add-path']:
            add_path = local.get('add-path', {})
            if add_path:
                for family in ParseAddPath.convert:
                    for pair in add_path.get(family, []):
                        if pair not in families:
                            log.debug(
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
        if neighbor['capability']['nexthop'] is None and nexthop:
            neighbor['capability']['nexthop'] = True

        if neighbor['capability']['nexthop']:
            nexthops = []
            for family in nexthop:
                nexthops.extend(nexthop[family])
            if nexthops:
                for afi, safi, nhafi in nexthops:
                    if (afi, safi) not in neighbor.families():
                        log.debug(
                            'skipping nexthop afi,safi ' + str(afi) + '/' + str(safi) + ' as it is not negotiated',
                            'configuration',
                        )
                        continue
                    if (nhafi, safi) not in neighbor.families():
                        log.debug(
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
                route.nlri.action = Action.ANNOUNCE
            neighbor.changes.extend(routes)

        routes = local.get('routes', [])
        for route in routes:
            route.nlri.action = Action.ANNOUNCE
        neighbor.changes.extend(routes)

        messages = local.get('operational', {}).get('routes', [])

        if neighbor['local-address'] is None:
            neighbor.auto_discovery = True
            neighbor['local-address'] = None
            neighbor['md5-ip'] = None

        if not neighbor['router-id']:
            if neighbor['peer-address'].afi == AFI.ipv4 and not neighbor.auto_discovery:
                neighbor['router-id'] = neighbor['local-address']
            else:
                return self.error.set('missing router-id for the peer, it can not be set using the local-ip')

        if neighbor['capability']['route-refresh']:
            if neighbor['adj-rib-out']:
                log.debug('route-refresh requested, enabling adj-rib-out', 'configuration')

        missing = neighbor.missing()
        if missing:
            return self.error.set('incomplete neighbor, missing %s' % missing)

        if not neighbor.auto_discovery and neighbor['local-address'].afi != neighbor['peer-address'].afi:
            return self.error.set('local-address and peer-address must be of the same family')
        neighbor.range_size = neighbor['peer-address'].mask.size()

        if neighbor.range_size > 1 and not (neighbor['passive'] or getenv().bgp.passive):
            return self.error.set('can only use ip ranges for the peer address with passive neighbors')

        if neighbor.index() in self._neighbors:
            return self.error.set('duplicate peer definition %s' % neighbor['peer-address'].top())
        self._neighbors.append(neighbor.index())

        if neighbor['md5-password']:
            try:
                md5 = base64.b64decode(neighbor['md5-password']) if neighbor['md5-base64'] else neighbor['md5-password']
            except TypeError as e:
                return self.error.set(f"Invalid base64 encoding of MD5 password ({e})")
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
        if neighbor['capability']['multi-session'] and len(neighbor.families()) > 1:
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
