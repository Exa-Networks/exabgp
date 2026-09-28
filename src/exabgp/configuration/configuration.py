"""configuration.py

The configuration exabgp runs with: read from its files by the grammar (configuration/grammar),
and changed by the API commands.

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, Any

from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.configuration.cli_process import cli_processes
from exabgp.environment import getenv
from exabgp.logger import lazymsg, log
from exabgp.protocol.family import Family, FamilyTuple

if TYPE_CHECKING:
    from exabgp.bgp.message.operational import OperationalFamily
    from exabgp.configuration.settings import ConfigurationSettings
    from exabgp.rib.route import Route


class _Configuration:
    def __init__(self) -> None:
        self.processes: dict[str, Any] = {}
        self.neighbors: dict[str, Any] = {}
        # Global route store: index -> Route (shared across neighbors)
        self._routes: dict[bytes, 'Route'] = {}

    def store_route(self, route: 'Route') -> bytes:
        """Store route in global store, incrementing refcount.

        Args:
            route: Route to store

        Returns:
            Route index (bytes)
        """
        index = route.index()
        if index in self._routes:
            # Route already exists, just increment refcount
            self._routes[index].ref_inc()
        else:
            # New route, add to store with refcount 1
            route.ref_inc()
            self._routes[index] = route
        return index

    def release_route(self, index: bytes) -> bool:
        """Release route reference, removing if refcount reaches zero.

        Args:
            index: Route index to release

        Returns:
            True if route was found and released, False otherwise
        """
        route = self._routes.get(index)
        if route is None:
            return False
        if route.ref_dec() <= 0:
            del self._routes[index]
        return True

    def get_route(self, index: bytes) -> 'Route | None':
        """Get route by index (O(1) lookup).

        Args:
            index: Route index

        Returns:
            Route if found, None otherwise
        """
        return self._routes.get(index)

    def announce_route(self, peers: list[str], route: 'Route', owner: str = '') -> bool:
        """Announce route to matching peers.

        Args:
            peers: List of peer names to announce to
            route: Route to announce
            owner: the API helper announcing it, whose death withdraws it

        Returns:
            True if route was announced to at least one peer
        """
        result = False
        for neighbor_name in self.neighbors:
            if neighbor_name in peers:
                neighbor = self.neighbors[neighbor_name]
                if route.nlri.family().afi_safi() in neighbor.families():
                    # resolve_self creates a copy with resolved nexthop
                    neighbor.rib.outgoing.add_to_rib(neighbor.resolve_self(route), owner=owner)
                    result = True
                else:
                    log.error(
                        lazymsg(
                            'route.family.unconfigured family={family} neighbor={neighbor}',
                            family=route.nlri.short(),
                            neighbor=neighbor_name,
                        ),
                        'configuration',
                    )
        return result

    def withdraw_route(self, peers: list[str], route: 'Route') -> bool:
        """Withdraw route from matching peers.

        Args:
            peers: List of peer names to withdraw from
            route: Route to withdraw

        Returns:
            True if route was withdrawn from at least one peer
        """
        result = False
        for neighbor_name in self.neighbors:
            if neighbor_name in peers:
                neighbor = self.neighbors[neighbor_name]
                if route.nlri.family().afi_safi() in neighbor.families():
                    # resolve_self creates a copy with resolved nexthop
                    neighbor.rib.outgoing.del_from_rib(neighbor.resolve_self(route))
                    result = True
                else:
                    log.error(
                        lazymsg(
                            'route.family.unconfigured family={family} neighbor={neighbor}',
                            family=route.nlri.short(),
                            neighbor=neighbor_name,
                        ),
                        'configuration',
                    )
        return result

    def announce_route_indexed(self, peers: list[str], route: 'Route', owner: str = '') -> tuple[bytes, bool]:
        """Announce route and store in global index for API access.

        Args:
            peers: List of peer names to announce to
            route: Route to announce
            owner: the API helper announcing it, whose death withdraws it

        Returns:
            Tuple of (route_index, success) where success is True if
            route was announced to at least one peer
        """
        # Store in global store for index-based lookup
        index = self.store_route(route)
        # Announce to peers
        success = self.announce_route(peers, route, owner)
        return index, success

    def withdraw_route_by_index(self, peers: list[str], index: bytes) -> bool:
        """Withdraw route by its index.

        Args:
            peers: List of peer names to withdraw from
            index: Route index (from announce_route_indexed or route.index())

        Returns:
            True if route was found and withdrawn from at least one peer
        """
        route = self.get_route(index)
        if route is None:
            return False

        # del_from_rib handles withdraws - no need to set action on route
        result = False
        for neighbor_name in self.neighbors:
            if neighbor_name in peers:
                neighbor = self.neighbors[neighbor_name]
                if route.nlri.family().afi_safi() in neighbor.families():
                    neighbor.rib.outgoing.del_from_rib(neighbor.resolve_self(route))
                    result = True

        # Release from global store
        if result:
            self.release_route(index)

        return result

    def inject_eor(self, peers: list[str], family: Family) -> bool:
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

                    def _log_err(neighbor: str = neighbor_err, family: FamilyTuple = family_err) -> str:
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
                        self.neighbors[neighbor].refresh.append(
                            RouteRefresh.make_route_refresh(refresh.afi, refresh.safi)
                        )
                    else:
                        family_err = family
                        neighbor_err: str = neighbor

                        def _log_refresh_err(family: FamilyTuple = family_err, neighbor: str = neighbor_err) -> str:
                            return f'the route family {family} is not configured on neighbor {neighbor}'

                        log.error(_log_refresh_err, 'configuration')
                        result = False
        return result


class ConfigurationError:
    """The last error of a reload or of an API command, as `str()` gives it."""

    def __init__(self) -> None:
        self.message = ''

    def set(self, message: str) -> bool:
        self.message = message
        return False

    def clear(self) -> None:
        self.message = ''

    def __str__(self) -> str:
        return self.message


class Configuration(_Configuration):
    def __init__(self, configurations: list[str], text: bool = False) -> None:
        _Configuration.__init__(self)
        self.api_encoder: str = getenv().api.encoder

        self._configurations: list[str] = configurations
        self._text: bool = text

        self.error = ConfigurationError()
        # the routes an API command read, until the API takes them
        self._command_routes: list['Route'] = []
        # how many sections the last API command left open: its routes are then not used
        self.open_sections = 0
        self._previous_neighbors: dict[str, Any] = {}

    @classmethod
    def from_settings(cls, settings: 'ConfigurationSettings') -> 'Configuration':
        """Create Configuration from validated settings, without reading a file.

        Raises:
            ValueError: If settings validation fails.
        """
        from exabgp.bgp.neighbor.neighbor import Neighbor
        from exabgp.configuration.settings import ProcessSettings

        error = settings.validate()
        if error:
            raise ValueError(error)

        config = cls(configurations=[])
        # the reactor takes each process as a dict keyed by configuration keyword
        config.processes = {
            name: process.to_dict() if isinstance(process, ProcessSettings) else process
            for name, process in settings.processes.items()
        }
        for neighbor_settings in settings.neighbors:
            neighbor = Neighbor.from_settings(neighbor_settings)
            config.neighbors[neighbor.name()] = neighbor
        return config

    def reload(self) -> bool:
        """Read the configuration again."""
        try:
            return self._reload()
        except KeyboardInterrupt:
            return self.error.set('configuration reload aborted by ^C or SIGINT')
        except Exception as exc:
            if getenv().debug.configuration:
                raise
            return self.error.set(f'problem parsing configuration file\nerror message: {exc}')

    def _reload(self) -> bool:
        from exabgp.configuration.grammar.install import install
        from exabgp.configuration.grammar.read import read_file, read_text

        # created by from_settings(): nothing to read, the neighbors are there
        if not self._configurations and self.neighbors:
            return True

        # taking the first configuration available (FIFO buffer)
        fname = self._configurations.pop(0)
        self._configurations.append(fname)

        self.error.clear()
        self._previous_neighbors = self.neighbors
        try:
            settings = read_text(fname) if self._text else read_file(os.path.realpath(fname))
        except (ValueError, OSError) as exc:
            self._previous_neighbors = {}
            return self.error.set(str(exc))

        self.processes = cli_processes()
        self.processes.update({name: process.to_dict() for name, process in settings.processes.items()})
        self.neighbors = install(settings.neighbors)
        # the neighbor before the reload, for the routes which are gone
        for name, neighbor in self.neighbors.items():
            if name in self._previous_neighbors:
                neighbor.previous = self._previous_neighbors[name]
        self._previous_neighbors = {}

        self._link()
        # legacy: what validate() reports is ignored, an api naming a missing process is accepted
        self.validate()
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
        """Read an API command as a statement of `section`; its routes are taken with pop_routes()."""
        from exabgp.configuration.grammar.read import read_command

        self.error.clear()
        self._command_routes = []
        self.open_sections = 0
        try:
            routes, self.open_sections = read_command(section, text, action == 'announce')
        except ValueError as exc:
            log.debug(lazymsg('configuration.parse.error message={error}', error=str(exc)), 'configuration')
            return self.error.set(str(exc))
        self._command_routes = routes
        return True

    def pop_routes(self) -> list['Route']:
        """The routes of the last API command, given once."""
        routes, self._command_routes = self._command_routes, []
        return routes

    def parse_route_text(self, route_text: str, action: str = 'announce') -> list['Route']:
        """Parse route text into Route objects, the neighbors left as they are.

        Returns:
            List of parsed Route objects, empty list if parsing failed.

        Example:
            config = create_minimal_configuration(families='ipv4 unicast')
            routes = config.parse_route_text('route 10.0.0.0/24 next-hop 1.2.3.4')
            for route in routes:
                neighbor.rib.outgoing.add_to_rib(neighbor.resolve_self(route))
        """
        if not self.partial('static', route_text, action):
            return []
        return self.pop_routes()

    def to_dict(self) -> dict[str, Any]:
        """Export parsed configuration as a serializable dict.

        Returns a dictionary containing:
        - neighbors: dict mapping peer addresses to neighbor configuration
        - processes: dict of configured processes

        The returned dict can be serialized to JSON using ConfigEncoder.
        """
        return {
            'neighbors': {name: self._neighbor_to_dict(neighbor) for name, neighbor in self.neighbors.items()},
            'processes': self.processes,
        }

    def _neighbor_to_dict(self, neighbor: Any) -> dict[str, Any]:
        """Convert Neighbor object to serializable dict.

        Args:
            neighbor: Neighbor instance to convert

        Returns:
            Dictionary with all neighbor configuration fields
        """
        return {
            'description': neighbor.description,
            'hold_time': neighbor.hold_time,
            'rate_limit': neighbor.rate_limit,
            'host_name': neighbor.host_name,
            'domain_name': neighbor.domain_name,
            'group_updates': neighbor.group_updates,
            'auto_flush': neighbor.auto_flush,
            'adj_rib_in': neighbor.adj_rib_in,
            'adj_rib_out': neighbor.adj_rib_out,
            'manual_eor': neighbor.manual_eor,
            'shutdown': neighbor.shutdown,
            'session': neighbor.session,
            'capability': neighbor.capability,
            'api': neighbor.api,
            'families': [(afi, safi) for afi, safi in neighbor.families()],
            'nexthops': [(afi, safi, nhafi) for afi, safi, nhafi in neighbor.nexthops()],
            'addpaths': [(afi, safi) for afi, safi in neighbor.addpaths()],
            'routes': [route for route in neighbor.routes],
        }
