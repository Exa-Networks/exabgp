# encoding: utf-8
"""
configuration.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import os
import re

from exabgp.logger import log

from exabgp.configuration.core import Error
from exabgp.configuration.core import Scope
from exabgp.configuration.core import Tokeniser
from exabgp.configuration.core import Section

from exabgp.configuration.process import ParseProcess
from exabgp.configuration.template import ParseTemplate
from exabgp.configuration.template.neighbor import ParseTemplateNeighbor
from exabgp.configuration.neighbor import ParseNeighbor
from exabgp.configuration.neighbor.api import ParseAPI
from exabgp.configuration.neighbor.api import ParseSend
from exabgp.configuration.neighbor.api import ParseReceive
from exabgp.configuration.neighbor.family import ParseFamily
from exabgp.configuration.neighbor.family import ParseAddPath
from exabgp.configuration.neighbor.nexthop import ParseNextHop
from exabgp.configuration.capability import ParseCapability
from exabgp.configuration.announce import SectionAnnounce
from exabgp.configuration.announce import AnnounceIPv4
from exabgp.configuration.announce import AnnounceIPv6
from exabgp.configuration.announce import AnnounceL2VPN
from exabgp.configuration.static import ParseStatic
from exabgp.configuration.static import ParseStaticRoute
from exabgp.configuration.flow import ParseFlow
from exabgp.configuration.flow import ParseFlowRoute
from exabgp.configuration.flow import ParseFlowThen
from exabgp.configuration.flow import ParseFlowMatch
from exabgp.configuration.flow import ParseFlowScope
from exabgp.configuration.l2vpn import ParseL2VPN
from exabgp.configuration.l2vpn import ParseVPLS
from exabgp.configuration.operational import ParseOperational

from exabgp.environment import getenv

# for registration
from exabgp.configuration.announce.ip import AnnounceIP  # noqa: F401,E261,E501
from exabgp.configuration.announce.path import AnnouncePath  # noqa: F401,E261,E501
from exabgp.configuration.announce.label import AnnounceLabel  # noqa: F401,E261,E501
from exabgp.configuration.announce.vpn import AnnounceVPN  # noqa: F401,E261,E501
from exabgp.configuration.announce.mvpn import AnnounceMVPN  # noqa: F401,E261,E501
from exabgp.configuration.announce.flow import AnnounceFlow  # noqa: F401,E261,E501
from exabgp.configuration.announce.vpls import AnnounceVPLS  # noqa: F401,E261,E501
from exabgp.configuration.announce.mup import AnnounceMup  # noqa: F401,E261,E501


class _Configuration(object):
    def __init__(self):
        self.processes = {}
        self.neighbors = {}

    def inject_change(self, peers, change):
        result = False
        for neighbor_name in self.neighbors:
            if neighbor_name in peers:
                neighbor = self.neighbors[neighbor_name]
                if change.nlri.family().afi_safi() in neighbor.families():
                    # remove_self may well have side effects on change
                    neighbor.rib.outgoing.add_to_rib(neighbor.remove_self(change))
                    result = True
                else:
                    log.error(
                        'the route family (%s) is not configured on neighbor %s' % (change.nlri.short(), neighbor_name),
                        'configuration',
                    )
        return result

    def inject_eor(self, peers, family):
        result = False
        for neighbor in self.neighbors:
            if neighbor in peers:
                result = True
                self.neighbors[neighbor].eor.append(family)
        return result

    def inject_operational(self, peers, operational):
        result = True
        for neighbor in self.neighbors:
            if neighbor in peers:
                if operational.family().afi_safi() in self.neighbors[neighbor].families():
                    if operational.name == 'ASM':
                        self.neighbors[neighbor].asm[operational.family().afi_safi()] = operational
                    self.neighbors[neighbor].messages.append(operational)
                else:
                    log.error('the route family is not configured on neighbor', 'configuration')
                    result = False
        return result

    def inject_refresh(self, peers, refreshes):
        result = True
        for neighbor in self.neighbors:
            if neighbor in peers:
                for refresh in refreshes:
                    family = (refresh.afi, refresh.safi)
                    if family in self.neighbors[neighbor].families():
                        self.neighbors[neighbor].refresh.append(refresh.__class__(refresh.afi, refresh.safi))
                    else:
                        result = False
        return result


class Configuration(_Configuration):
    def __init__(self, configurations, text=False):
        _Configuration.__init__(self)
        self.api_encoder = getenv().api.encoder

        self._configurations = configurations
        self._text = text

        self.error = Error()
        self.scope = Scope()

        self.tokeniser = Tokeniser(self.scope, self.error)

        params = (self.tokeniser, self.scope, self.error)
        self.section = Section(*params)
        self.process = ParseProcess(*params)
        self.template = ParseTemplate(*params)
        self.template_neighbor = ParseTemplateNeighbor(*params)
        self.neighbor = ParseNeighbor(*params)
        self.family = ParseFamily(*params)
        self.addpath = ParseAddPath(*params)
        self.nexthop = ParseNextHop(*params)
        self.capability = ParseCapability(*params)
        self.api = ParseAPI(*params)
        self.api_send = ParseSend(*params)
        self.api_receive = ParseReceive(*params)
        self.static = ParseStatic(*params)
        self.static_route = ParseStaticRoute(*params)
        self.announce = SectionAnnounce(*params)
        self.announce_ipv4 = AnnounceIPv4(*params)
        self.announce_ipv6 = AnnounceIPv6(*params)
        self.announce_l2vpn = AnnounceL2VPN(*params)
        self.flow = ParseFlow(*params)
        self.flow_route = ParseFlowRoute(*params)
        self.flow_match = ParseFlowMatch(*params)
        self.flow_then = ParseFlowThen(*params)
        self.flow_scope = ParseFlowScope(*params)
        self.l2vpn = ParseL2VPN(*params)
        self.vpls = ParseVPLS(*params)
        self.operational = ParseOperational(*params)

        # We should check if name are unique when running Section.__init__

        self._structure = {
            'root': {
                'class': self.section,
                'commands': [],
                'sections': {
                    'process': self.process.name,
                    'neighbor': self.neighbor.name,
                    'template': self.template.name,
                },
            },
            self.process.name: {
                'class': self.process,
                'commands': self.process.known.keys(),
                'sections': {},
            },
            self.template.name: {
                'class': self.template,
                'commands': self.template.known.keys(),
                'sections': {
                    'neighbor': self.template_neighbor.name,
                },
            },
            self.template_neighbor.name: {
                'class': self.template_neighbor,
                'commands': self.template_neighbor.known.keys(),
                'sections': {
                    'family': self.family.name,
                    'capability': self.capability.name,
                    'add-path': self.addpath.name,
                    'nexthop': self.nexthop.name,
                    'api': self.api.name,
                    'static': self.static.name,
                    'flow': self.flow.name,
                    'l2vpn': self.l2vpn.name,
                    'operational': self.operational.name,
                    'announce': self.announce.name,
                },
            },
            self.neighbor.name: {
                'class': self.neighbor,
                'commands': self.neighbor.known.keys(),
                'sections': {
                    'family': self.family.name,
                    'capability': self.capability.name,
                    'add-path': self.addpath.name,
                    'nexthop': self.nexthop.name,
                    'api': self.api.name,
                    'static': self.static.name,
                    'flow': self.flow.name,
                    'l2vpn': self.l2vpn.name,
                    'operational': self.operational.name,
                    'announce': self.announce.name,
                },
            },
            self.family.name: {
                'class': self.family,
                'commands': self.family.known.keys(),
                'sections': {},
            },
            self.capability.name: {
                'class': self.capability,
                'commands': self.capability.known.keys(),
                'sections': {},
            },
            self.nexthop.name: {
                'class': self.nexthop,
                'commands': self.nexthop.known.keys(),
                'sections': {},
            },
            self.addpath.name: {
                'class': self.addpath,
                'commands': self.addpath.known.keys(),
                'sections': {},
            },
            self.api.name: {
                'class': self.api,
                'commands': self.api.known.keys(),
                'sections': {
                    'send': self.api_send.name,
                    'receive': self.api_receive.name,
                },
            },
            self.api_send.name: {
                'class': self.api_send,
                'commands': self.api_send.known.keys(),
                'sections': {},
            },
            self.api_receive.name: {
                'class': self.api_receive,
                'commands': self.api_receive.known.keys(),
                'sections': {},
            },
            self.announce.name: {
                'class': self.announce,
                'commands': self.announce.known.keys(),
                'sections': {
                    'ipv4': self.announce_ipv4.name,
                    'ipv6': self.announce_ipv6.name,
                    'l2vpn': self.announce_l2vpn.name,
                },
            },
            self.announce_ipv4.name: {
                'class': self.announce_ipv4,
                'commands': ['unicast', 'multicast', 'nlri-mpls', 'mpls-vpn', 'mcast-vpn', 'flow', 'flow-vpn', 'mup'],
                'sections': {},
            },
            self.announce_ipv6.name: {
                'class': self.announce_ipv6,
                'commands': ['unicast', 'multicast', 'nlri-mpls', 'mpls-vpn', 'mcast-vpn', 'flow', 'flow-vpn', 'mup'],
                'sections': {},
            },
            self.announce_l2vpn.name: {
                'class': self.announce_l2vpn,
                'commands': [
                    'vpls',
                ],
                'sections': {},
            },
            self.static.name: {
                'class': self.static,
                'commands': ['route', 'attributes'],
                'sections': {
                    'route': self.static_route.name,
                },
            },
            self.static_route.name: {
                'class': self.static_route,
                'commands': self.static_route.known.keys(),
                'sections': {},
            },
            self.flow.name: {
                'class': self.flow,
                'commands': self.flow.known.keys(),
                'sections': {
                    'route': self.flow_route.name,
                },
            },
            self.flow_route.name: {
                'class': self.flow_route,
                'commands': self.flow_route.known.keys(),
                'sections': {
                    'match': self.flow_match.name,
                    'then': self.flow_then.name,
                    'scope': self.flow_scope.name,
                },
            },
            self.flow_match.name: {
                'class': self.flow_match,
                'commands': self.flow_match.known.keys(),
                'sections': {},
            },
            self.flow_then.name: {
                'class': self.flow_then,
                'commands': self.flow_then.known.keys(),
                'sections': {},
            },
            self.flow_scope.name: {'class': self.flow_scope, 'commands': self.flow_scope.known.keys(), 'sections': {}},
            self.l2vpn.name: {
                'class': self.l2vpn,
                'commands': self.l2vpn.known.keys(),
                'sections': {
                    'vpls': self.vpls.name,
                },
            },
            self.vpls.name: {
                'class': self.vpls,
                'commands': self.l2vpn.known.keys(),
                'sections': {},
            },
            self.operational.name: {
                'class': self.operational,
                'commands': self.operational.known.keys(),
                'sections': {},
            },
        }

        self._neighbors = {}
        self._previous_neighbors = {}

    def _clear(self):
        self.processes = {}
        self._previous_neighbors = self.neighbors
        self.neighbors = {}
        self._neighbors = {}

    # clear the parser data (ie: free memory)
    def _cleanup(self):
        self.error.clear()
        self.tokeniser.clear()
        self.scope.clear()

        self.process.clear()
        self.template.clear()
        self.template_neighbor.clear()
        self.neighbor.clear()
        self.family.clear()
        self.capability.clear()
        self.api.clear()
        self.api_send.clear()
        self.api_receive.clear()
        self.announce_ipv6.clear()
        self.announce_ipv4.clear()
        self.announce_l2vpn.clear()
        self.announce.clear()
        self.static.clear()
        self.static_route.clear()
        self.flow.clear()
        self.flow_route.clear()
        self.flow_match.clear()
        self.flow_then.clear()
        self.flow_scope.clear()
        self.l2vpn.clear()
        self.vpls.clear()
        self.operational.clear()

    def _rollback_reload(self):
        self.neighbors = self._previous_neighbors
        self.processes = self.process.processes
        self._neighbors = {}
        self._previous_neighbors = {}

    def _commit_reload(self):
        self.neighbors = self.neighbor.neighbors
        # XXX: Yes, we do not detect changes in processes and restart anything ..
        # XXX: This is a bug ..
        self.processes = self.process.processes
        self._neighbors = {}

        # Add the changes prior to the reload to the neighbor to correct handling of deleted routes
        for neighbor in self.neighbors:
            if neighbor in self._previous_neighbors:
                self.neighbors[neighbor].previous = self._previous_neighbors[neighbor]

        self._previous_neighbors = {}
        self._cleanup()

    def reload(self):
        try:
            return self._reload()
        except KeyboardInterrupt:
            return self.error.set('configuration reload aborted by ^C or SIGINT')
        except Error as exc:
            if getenv().debug.configuration:
                raise
            return self.error.set(
                'problem parsing configuration file line %d\nerror message: %s' % (self.tokeniser.index_line, exc)
            )
        except Exception as exc:
            if getenv().debug.configuration:
                raise
            return self.error.set(
                'problem parsing configuration file line %d\nerror message: %s' % (self.tokeniser.index_line, exc)
            )

    def _reload(self):
        # taking the first configuration available (FIFO buffer)
        fname = self._configurations.pop(0)
        self._configurations.append(fname)

        # clearing the current configuration to be able to re-parse it
        self._clear()

        if self._text:
            if not self.tokeniser.set_text(fname):
                return False
        else:
            # resolve any potential symlink, and check it is a file
            target = os.path.realpath(fname)
            if not os.path.isfile(target):
                return False
            if not self.tokeniser.set_file(target):
                return False

        # XXX: Should it be in neighbor ?
        self.process.add_api()

        if self.parse_section('root') is not True:
            self._rollback_reload()

            return self.error.set(
                '\n'
                'syntax error in section %s\n'
                'line %d: %s\n'
                '\n%s' % (self.scope.location(), self.tokeniser.number, ' '.join(self.tokeniser.line), str(self.error))
            )

        self._commit_reload()
        self._link()

        check = self.validate()
        if check is not None:
            return check

        return True

    def validate(self):
        for neighbor in self.neighbors.values():
            has_procs = 'processes' in neighbor.api and neighbor.api['processes']
            has_match = 'processes-match' in neighbor.api and neighbor.api['processes-match']
            if has_procs and has_match:
                return self.error.set(
                    "\n\nprocesses and processes-match are mutually exclusive, verify neighbor '%s' configuration.\n\n"
                    % neighbor['peer-address'],
                )

            for notification in neighbor.api:
                errors = []
                for api in neighbor.api[notification]:
                    if notification == 'processes':
                        if not self.processes[api].get('run', False):
                            return self.error.set(
                                "\n\nan api called '%s' is used by neighbor '%s' but not defined\n\n"
                                % (api, neighbor['peer-address']),
                            )
                    elif notification == 'processes-match':
                        if not any(v.get('run', False) for k, v in self.processes.items() if re.match(api, k)):
                            errors.append(
                                "\n\nAny process match regex '%s' for neighbor '%s'.\n\n"
                                % (api, neighbor['peer-address']),
                            )

                # matching mode is an "or", we test all rules and check
                # if any of rule had a match
                if len(errors) > 0 and len(errors) == len(neighbor.api[notification]):
                    return self.error.set(
                        ' '.join(errors),
                    )

    def _link(self):
        for neighbor in self.neighbors.values():
            api = neighbor.api
            processes = []
            if api.get('processes', []):
                processes = api['processes']
            elif api.get('processes-match', []):
                processes = [k for k in self.processes.keys() for pm in api['processes-match'] if re.match(pm, k)]

            for process in processes:
                self.processes.setdefault(process, {})['neighbor-changes'] = api['neighbor-changes']
                self.processes.setdefault(process, {})['negotiated'] = api['negotiated']
                self.processes.setdefault(process, {})['fsm'] = api['fsm']
                self.processes.setdefault(process, {})['signal'] = api['signal']
                for way in ('send', 'receive'):
                    for name in ('parsed', 'packets', 'consolidate'):
                        key = '%s-%s' % (way, name)
                        if api[key]:
                            self.processes[process].setdefault(key, []).append(neighbor['router-id'])
                    for name in ('open', 'update', 'notification', 'keepalive', 'refresh', 'operational'):
                        key = '%s-%s' % (way, name)
                        if api[key]:
                            self.processes[process].setdefault(key, []).append(neighbor['router-id'])

    def partial(self, section, text, action='announce'):
        self._cleanup()  # this perform a big cleanup (may be able to be smarter)
        self._clear()
        self.tokeniser.set_api(text if text.endswith(';') or text.endswith('}') else text + ' ;')
        self.tokeniser.set_action(action)

        if self.parse_section(section) is not True:
            self._rollback_reload()
            log.debug(
                '\n'
                'syntax error in api command %s\n'
                'line %d: %s\n'
                '\n%s' % (self.scope.location(), self.tokeniser.number, ' '.join(self.tokeniser.line), str(self.error)),
                'configuration',
            )
            return False
        return True

    def _enter(self, name):
        location = self.tokeniser.iterate()
        log.debug('> %-16s | %s' % (location, self.tokeniser.params()), 'configuration')

        if location not in self._structure[name]['sections']:
            return self.error.set('section %s is invalid in %s, %s' % (location, name, self.scope.location()))

        self.scope.enter(location)
        self.scope.to_context()

        class_name = self._structure[name]['sections'][location]
        instance = self._structure[class_name].get('class', None)
        if not instance:
            raise RuntimeError('This should not be happening, debug time !')

        if not instance.pre():
            return False

        if not self.dispatch(self._structure[name]['sections'][location]):
            return False

        if not instance.post():
            return False

        left = self.scope.leave()
        if not left:
            return self.error.set('closing too many parenthesis')
        self.scope.to_context()

        log.debug('< %-16s | %s' % (left, self.tokeniser.params()), 'configuration')
        return True

    def _run(self, name):
        command = self.tokeniser.iterate()
        log.debug('. %-16s | %s' % (command, self.tokeniser.params()), 'configuration')

        if not self.run(name, command):
            return False
        return True

    def dispatch(self, name):
        while True:
            self.tokeniser()

            if self.tokeniser.end == ';':
                if self._run(name):
                    continue
                return False

            if self.tokeniser.end == '{':
                if self._enter(name):
                    continue
                return False

            if self.tokeniser.end == '}':
                return True

            if not self.tokeniser.end:  # finished
                return True

            return self.error.set('invalid syntax line %d' % self.tokeniser.index_line)
        return False

    def parse_section(self, name):
        if name not in self._structure:
            return self.error.set('option %s is not allowed here' % name)

        if not self.dispatch(name):
            return False

        instance = self._structure[name].get('class', None)
        instance.post()
        return True

    def run(self, name, command):
        # restore 'anounce attribute' to provide backward 3.4 compatibility
        if name == 'static' and command == 'attribute':
            command = 'attributes'
        if command not in self._structure[name]['commands']:
            return self.error.set('invalid keyword "%s"' % command)

        return self._structure[name]['class'].parse(name, command)
