"""configuration.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, Any, cast

from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.protocol.family import AFI, SAFI

if TYPE_CHECKING:
    from exabgp.bgp.message.operational import OperationalFamily
    from exabgp.rib.change import Change

from exabgp.configuration.announce import AnnounceIPv4, AnnounceIPv6, AnnounceL2VPN, SectionAnnounce
from exabgp.configuration.announce.flow import AnnounceFlow  # noqa: F401,E261,E501

# for registration
from exabgp.configuration.announce.ip import AnnounceIP  # noqa: F401,E261,E501
from exabgp.configuration.announce.label import AnnounceLabel  # noqa: F401,E261,E501
from exabgp.configuration.announce.mup import AnnounceMup  # noqa: F401,E261,E501
from exabgp.configuration.announce.mvpn import AnnounceMVPN  # noqa: F401,E261,E501
from exabgp.configuration.announce.path import AnnouncePath  # noqa: F401,E261,E501
from exabgp.configuration.announce.vpls import AnnounceVPLS  # noqa: F401,E261,E501
from exabgp.configuration.announce.vpn import AnnounceVPN  # noqa: F401,E261,E501
from exabgp.configuration.capability import ParseCapability
from exabgp.configuration.core import Error, Parser, Scope, Section, Tokeniser
from exabgp.configuration.flow import ParseFlow, ParseFlowMatch, ParseFlowRoute, ParseFlowScope, ParseFlowThen
from exabgp.configuration.l2vpn import ParseL2VPN, ParseVPLS
from exabgp.configuration.neighbor import ParseNeighbor
from exabgp.configuration.neighbor.api import ParseAPI, ParseReceive, ParseSend
from exabgp.configuration.neighbor.family import ParseAddPath, ParseFamily
from exabgp.configuration.neighbor.nexthop import ParseNextHop
from exabgp.configuration.operational import ParseOperational
from exabgp.configuration.process import ParseProcess
from exabgp.configuration.static import ParseStatic, ParseStaticRoute
from exabgp.configuration.template import ParseTemplate
from exabgp.configuration.template.neighbor import ParseTemplateNeighbor
from exabgp.environment import getenv
from exabgp.logger import lazymsg, log


# Mapping for config keywords that don't match parser section names
# Format: (parent_section_name, keyword) -> target_section_name
# Only needed for exceptions where keyword != parser.name
_KEYWORD_TO_SECTION: dict[tuple[str, str], str] = {
    ('template', 'neighbor'): 'template-neighbor',
    ('neighbor', 'l2vpn'): 'L2VPN',
    ('template-neighbor', 'l2vpn'): 'L2VPN',
    ('flow', 'route'): 'flow/route',
    ('flow/route', 'match'): 'flow/match',
    ('flow/route', 'then'): 'flow/then',
    ('flow/route', 'scope'): 'flow/scope',
    ('L2VPN', 'vpls'): 'l2vpn/vpls',
    ('api', 'send'): 'api/send',
    ('api', 'receive'): 'api/receive',
    ('static', 'route'): 'static/route',
}


class _Configuration:
    def __init__(self) -> None:
        self.processes: dict[str, Any] = {}
        self.neighbors: dict[str, Any] = {}

    def inject_change(self, peers: list[str], change: 'Change') -> bool:
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
                        lazymsg(
                            'route.family.unconfigured family={family} neighbor={neighbor}',
                            family=change.nlri.short(),
                            neighbor=neighbor_name,
                        ),
                        'configuration',
                    )
        return result

    def inject_eor(self, peers: list[str], family: object) -> bool:
        result = False
        for neighbor in self.neighbors:
            if neighbor in peers:
                result = True
                self.neighbors[neighbor].eor.append(family)
        return result

    def inject_operational(self, peers: list[str], operational: 'OperationalFamily') -> bool:
        result = True
        for neighbor in self.neighbors:
            if neighbor in peers:
                family = operational.family()
                if family in self.neighbors[neighbor].families():
                    if operational.name == 'ASM':
                        self.neighbors[neighbor].asm[family] = operational
                    self.neighbors[neighbor].messages.append(operational)
                else:
                    neighbor_err: str = neighbor
                    family_err = family

                    def _log_err(neighbor: str = neighbor_err, family: tuple[AFI, SAFI] = family_err) -> str:
                        return f'the route family {family} is not configured on neighbor {neighbor}'

                    log.error(_log_err, 'configuration')
                    result = False
        return result

    def inject_refresh(self, peers: list[str], refreshes: list[RouteRefresh]) -> bool:
        result = True
        for neighbor in self.neighbors:
            if neighbor in peers:
                for refresh in refreshes:
                    family = (refresh.afi, refresh.safi)
                    if family in self.neighbors[neighbor].families():
                        self.neighbors[neighbor].refresh.append(RouteRefresh(refresh.afi, refresh.safi))
                    else:
                        family_err = family
                        neighbor_err: str = neighbor

                        def _log_refresh_err(
                            family: tuple[AFI, SAFI] = family_err, neighbor: str = neighbor_err
                        ) -> str:
                            return f'the route family {family} is not configured on neighbor {neighbor}'

                        log.error(_log_refresh_err, 'configuration')
                        result = False
        return result


class Configuration(_Configuration):
    def __init__(self, configurations: list[str], text: bool = False) -> None:
        _Configuration.__init__(self)
        self.api_encoder: str = getenv().api.encoder

        self._configurations: list[str] = configurations
        self._text: bool = text

        self.error: Error = Error()
        self.scope: Scope = Scope()

        self.parser: Parser = Parser(self.scope, self.error)

        params = (self.parser, self.scope, self.error)
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

        # Build parser registry: section_name -> parser instance
        self._parsers: dict[str, Section] = {
            p.name: p
            for p in [
                self.process,
                self.template,
                self.template_neighbor,
                self.neighbor,
                self.family,
                self.addpath,
                self.nexthop,
                self.capability,
                self.api,
                self.api_send,
                self.api_receive,
                self.static,
                self.static_route,
                self.announce,
                self.announce_ipv4,
                self.announce_ipv6,
                self.announce_l2vpn,
                self.flow,
                self.flow_route,
                self.flow_match,
                self.flow_then,
                self.flow_scope,
                self.l2vpn,
                self.vpls,
                self.operational,
            ]
        }

        # Build structure from schemas
        self._structure = self._build_structure()

        self._neighbors: dict[str, Any] = {}
        self._previous_neighbors: dict[str, Any] = {}

    def _build_structure(self) -> dict[str, dict[str, Any]]:
        """Build the configuration structure from parser schemas.

        Returns a dict mapping section names to their configuration:
        - 'class': parser instance
        - 'commands': valid commands (from known.keys() or explicit list)
        - 'sections': mapping of keywords to child section names
        """
        # Special command lists for parsers that don't use known.keys()
        _SPECIAL_COMMANDS: dict[str, list[str]] = {
            'ipv4': ['unicast', 'multicast', 'nlri-mpls', 'mpls-vpn', 'mcast-vpn', 'flow', 'flow-vpn', 'mup'],
            'ipv6': ['unicast', 'multicast', 'nlri-mpls', 'mpls-vpn', 'mcast-vpn', 'flow', 'flow-vpn', 'mup'],
            'l2vpn': ['vpls'],
            'static': ['route', 'attributes'],
        }

        # Build sections dict from schema Container children
        def get_sections(parser: Section) -> dict[str, str]:
            sections: dict[str, str] = {}
            for keyword in parser.get_subsection_keywords():
                # Look up target section name from override mapping or use keyword as-is
                target = _KEYWORD_TO_SECTION.get((parser.name, keyword), keyword)
                sections[keyword] = target
            return sections

        # Build structure entry for a parser
        def build_entry(parser: Section) -> dict[str, Any]:
            # Get commands from special list, known dict, or schema
            if parser.name in _SPECIAL_COMMANDS:
                commands = _SPECIAL_COMMANDS[parser.name]
            else:
                # Combine commands from known dict and schema Leaf children
                commands = list(parser.known.keys())
                if parser.schema:
                    from exabgp.configuration.schema import Leaf, LeafList

                    for name, child in parser.schema.children.items():
                        if isinstance(child, (Leaf, LeafList)) and name not in commands:
                            commands.append(name)
            return {
                'class': parser,
                'commands': commands,
                'sections': get_sections(parser),
            }

        # Start with root entry (special case - no parser)
        structure: dict[str, dict[str, Any]] = {
            'root': {
                'class': self.section,
                'commands': [],
                'sections': {
                    'process': 'process',
                    'neighbor': 'neighbor',
                    'template': 'template',
                },
            },
        }

        # Add entries for all registered parsers
        for name, parser in self._parsers.items():
            structure[name] = build_entry(parser)

        # Special case: l2vpn/vpls uses l2vpn.known (commands from parent)
        structure['l2vpn/vpls']['commands'] = list(self.l2vpn.known.keys())

        return structure

    @property
    def tokeniser(self) -> Tokeniser:
        """Convenience accessor for parser.tokeniser"""
        return self.parser.tokeniser

    def _clear(self) -> None:
        self.processes = {}
        self._previous_neighbors = self.neighbors
        self.neighbors = {}
        self._neighbors = {}

    # clear the parser data (ie: free memory)
    def _cleanup(self) -> None:
        self.error.clear()
        self.parser.clear()
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

    def _rollback_reload(self) -> None:
        self.neighbors = self._previous_neighbors
        self.processes = self.process.processes
        self._neighbors = {}
        self._previous_neighbors = {}

    def _commit_reload(self) -> None:
        self.neighbors = self.neighbor.neighbors
        # Process change detection is handled in Processes.start() which compares
        # old vs new config and only restarts processes that actually changed.
        self.processes = self.process.processes
        self._neighbors = {}

        # Add the changes prior to the reload to the neighbor to correct handling of deleted routes
        for neighbor in self.neighbors:
            if neighbor in self._previous_neighbors:
                self.neighbors[neighbor].previous = self._previous_neighbors[neighbor]

        self._previous_neighbors = {}
        self._cleanup()

    def reload(self) -> bool:
        try:
            return self._reload()
        except KeyboardInterrupt:
            return self.error.set('configuration reload aborted by ^C or SIGINT')
        except Error as exc:
            if getenv().debug.configuration:
                raise
            return self.error.set(
                f'problem parsing configuration file line {self.parser.index_line}\nerror message: {exc}',
            )
        except Exception as exc:
            if getenv().debug.configuration:
                raise
            return self.error.set(
                f'problem parsing configuration file line {self.parser.index_line}\nerror message: {exc}',
            )

    def _reload(self) -> bool:
        # taking the first configuration available (FIFO buffer)
        fname = self._configurations.pop(0)
        self._configurations.append(fname)

        # clearing the current configuration to be able to re-parse it
        self._clear()

        if self._text:
            if not self.parser.set_text(fname):
                return False
        else:
            # resolve any potential symlink, and check it is a file
            target = os.path.realpath(fname)
            if not os.path.isfile(target):
                return False
            if not self.parser.set_file(target):
                return False

        # XXX: Should it be in neighbor ?
        self.process.add_api()

        if self.parse_section('root') is not True:
            self._rollback_reload()
            line_str = ' '.join(self.parser.line)
            return self.error.set(
                f'\nsyntax error in section {self.scope.location()}\nline {self.parser.number}: {line_str}\n\n{self.error!s}',
            )

        self._commit_reload()
        self._link()

        check = self.validate()
        if check:
            return check

        return True

    def validate(self) -> bool:
        for neighbor in self.neighbors.values():
            has_procs = 'processes' in neighbor.api and neighbor.api['processes']
            has_match = 'processes-match' in neighbor.api and neighbor.api['processes-match']
            if has_procs and has_match:
                return self.error.set(
                    "\n\nprocesses and processes-match are mutually exclusive, verify neighbor '{}' configuration.\n\n".format(
                        neighbor.session.peer_address
                    ),
                )

            for notification in neighbor.api:
                errors = []
                for api in neighbor.api[notification]:
                    if notification == 'processes':
                        if not self.processes[api].get('run', False):
                            return self.error.set(
                                f"\n\nan api called '{api}' is used by neighbor '{neighbor.session.peer_address}' but not defined\n\n",
                            )
                    elif notification == 'processes-match':
                        if not any(v.get('run', False) for k, v in self.processes.items() if re.match(api, k)):
                            errors.append(
                                f"\n\nAny process match regex '{api}' for neighbor '{neighbor.session.peer_address}'.\n\n",
                            )

                # matching mode is an "or", we test all rules and check
                # if any of rule had a match
                if len(errors) > 0 and len(errors) == len(neighbor.api[notification]):
                    return self.error.set(
                        ' '.join(errors),
                    )
        return True

    def _link(self) -> None:
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
                        key = f'{way}-{name}'
                        if api[key]:
                            self.processes[process].setdefault(key, []).append(neighbor.session.router_id)
                    for name in ('open', 'update', 'notification', 'keepalive', 'refresh', 'operational'):
                        key = f'{way}-{name}'
                        if api[key]:
                            self.processes[process].setdefault(key, []).append(neighbor.session.router_id)

    def partial(self, section: str, text: str, action: str = 'announce') -> bool:
        self._cleanup()  # this perform a big cleanup (may be able to be smarter)
        self._clear()
        self.parser.set_api(text if text.endswith(';') or text.endswith('}') else text + ' ;')
        self.parser.set_action(action)

        if self.parse_section(section) is not True:
            self._rollback_reload()
            line_str = ' '.join(self.parser.line)
            error_msg = (
                f'\n'
                f'syntax error in api command {self.scope.location()}\n'
                f'line {self.parser.number}: {line_str}\n'
                f'\n{self.error}'
            )
            log.debug(lazymsg('configuration.parse.error message={error_msg}', error_msg=error_msg), 'configuration')
            return False
        return True

    def _enter(self, name: str) -> bool | str:
        location = self.parser.tokeniser()
        log.debug(
            lazymsg(
                'configuration.enter location={location} params={params}',
                location=location,
                params=self.parser.params(),
            ),
            'configuration',
        )

        if location not in self._structure[name]['sections']:
            return self.error.set(f'section {location} is invalid in {name}, {self.scope.location()}')

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

        log.debug(
            lazymsg('configuration.leave section={left} params={params}', left=left, params=self.parser.params()),
            'configuration',
        )
        return True

    def _run(self, name: str) -> bool:
        command = self.parser.tokeniser()
        log.debug(
            lazymsg(
                'configuration.run command={command} params={params}', command=command, params=self.parser.params()
            ),
            'configuration',
        )

        if not self.run(name, command):
            return False
        return True

    def dispatch(self, name: str) -> bool | str:
        while True:
            self.parser()

            if self.parser.end == ';':
                if self._run(name):
                    continue
                return False

            if self.parser.end == '{':
                if self._enter(name):
                    continue
                return False

            if self.parser.end == '}':
                return True

            if not self.parser.end:  # finished
                return True

            return self.error.set('invalid syntax line %d' % self.parser.index_line)
        return False

    def parse_section(self, name: str) -> bool | str:
        if name not in self._structure:
            return self.error.set('option {} is not allowed here'.format(name))

        if not self.dispatch(name):
            return False

        instance = self._structure[name].get('class', None)
        if instance is not None:
            instance.post()
        return True

    def run(self, name: str, command: str) -> bool | str:
        # restore 'anounce attribute' to provide backward 3.4 compatibility
        if name == 'static' and command == 'attribute':
            command = 'attributes'
        if command not in self._structure[name]['commands']:
            return self.error.set('invalid keyword "{}"'.format(command))

        return cast(bool | str, self._structure[name]['class'].parse(name, command))
