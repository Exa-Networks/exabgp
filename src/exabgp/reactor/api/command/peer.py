"""command/peer.py

Dynamic peer management commands (create/delete).

Created by Thomas Mangin on 2025-11-23.
Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from exabgp.protocol.ip import IP
from exabgp.protocol.family import AFI, SAFI
from exabgp.bgp.neighbor import Neighbor
from exabgp.bgp.neighbor.capability import GracefulRestartConfig
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.routerid import RouterID
from exabgp.reactor.api.command.command import Command
from exabgp.reactor.api.command.limit import extract_neighbors, match_neighbors
from exabgp.configuration.neighbor.api import ParseAPI

if TYPE_CHECKING:
    from exabgp.reactor.loop import Reactor


def register_peer() -> None:
    """Register peer management commands.

    This function is called during module initialization to ensure
    the @Command.register decorators are executed.
    """
    pass


def _parse_ip(value: str) -> IP:
    """Parse IP address string into IP object."""
    try:
        return IP.make_ip(value)
    except Exception as e:
        raise ValueError(f'invalid IP address {value}: {e}')


def _parse_asn(value: str) -> ASN:
    """Parse ASN string into ASN object."""
    try:
        asn_int = int(value)
        if asn_int < 0 or asn_int > 4294967295:  # Max ASN4
            raise ValueError('ASN out of range')
        return ASN(asn_int)
    except ValueError as e:
        raise ValueError(f'invalid ASN {value}: {e}')


def _parse_families(value: str) -> list[tuple[AFI, SAFI]]:
    """Parse family-allowed value into list of (AFI, SAFI) tuples.

    Accepts formats like:
    - ipv4-unicast
    - ipv4-unicast/ipv6-unicast
    - in-open (returns empty list, meaning negotiate in BGP OPEN)
    """
    # Special case: 'in-open' means negotiate families in BGP OPEN message
    if value == 'in-open':
        return []

    families = []
    for family_str in value.split('/'):
        family_str = family_str.strip()
        if not family_str:
            continue

        # Parse AFI-SAFI format (e.g., ipv4-unicast)
        parts = family_str.split('-')
        if len(parts) != 2:
            raise ValueError(f'invalid family format {family_str}, expected <afi>-<safi>')

        afi_str, safi_str = parts

        # Convert to AFI/SAFI objects
        # Note: fromString() typically returns undefined values rather than raising,
        # but we keep exception handling for safety against future changes
        try:
            afi = AFI.fromString(afi_str)
        except (KeyError, AttributeError):
            raise ValueError(f'unknown AFI {afi_str}')

        try:
            safi = SAFI.fromString(safi_str)
        except (KeyError, AttributeError):
            raise ValueError(f'unknown SAFI {safi_str}')

        families.append((afi, safi))

    return families


def _parse_neighbor_params(line: str) -> tuple[dict[str, Any], list[str]]:
    """Parse neighbor parameters from command line.

    API format: neighbor <ip> local-address <ip> local-as <asn> peer-as <asn> [router-id <ip>] [family-allowed <families>] [graceful-restart <seconds>] [group-updates true|false] [api <process>]...

    Line should NOT include the command word (create/delete).
    Example: "neighbor 127.0.0.1 local-address 127.0.0.1 local-as 1 peer-as 1 api peer-lifecycle"

    Returns:
        Tuple of (parameters dict, list of API process names - empty if none specified)
    """

    # Helper to parse key-value parameter
    from typing import Callable

    def parse_param(
        key: str, tokens: list[str], i: int, seen: set[str], parser: Callable[[str], Any]
    ) -> tuple[Any, int]:
        if key in seen:
            raise ValueError(f'duplicate parameter: {key}')
        if i + 1 >= len(tokens):
            raise ValueError(f'missing value for {key}')
        seen.add(key)
        return parser(tokens[i + 1]), i + 2

    tokens = line.split()
    if len(tokens) < 2:
        raise ValueError('no neighbor selector')
    if tokens[0] != 'neighbor':
        raise ValueError('command must start with "neighbor <ip>"')

    params: dict[str, Any] = {}
    api_processes: list[str] = []
    seen_params: set[str] = set()

    # Parse peer IP (second token)
    params['peer-address'] = _parse_ip(tokens[1])

    # Parse remaining tokens as key-value pairs
    i = 2
    while i < len(tokens):
        key = tokens[i]

        if key == 'local-address' or key == 'local-ip':
            # Accept both 'local-address' and 'local-ip' as aliases
            params['local-address'], i = parse_param('local-address', tokens, i, seen_params, _parse_ip)
        elif key == 'local-as':
            params['local-as'], i = parse_param(key, tokens, i, seen_params, _parse_asn)
        elif key == 'peer-as':
            params['peer-as'], i = parse_param(key, tokens, i, seen_params, _parse_asn)
        elif key == 'router-id':
            params['router-id'], i = parse_param(key, tokens, i, seen_params, RouterID)
        elif key == 'family-allowed':
            params['families'], i = parse_param(key, tokens, i, seen_params, _parse_families)
        elif key == 'graceful-restart':
            params['graceful-restart'], i = parse_param(key, tokens, i, seen_params, int)
        elif key == 'group-updates':
            if key in seen_params:
                raise ValueError(f'duplicate parameter: {key}')
            if i + 1 >= len(tokens):
                raise ValueError(f'missing value for {key}')
            value = tokens[i + 1].lower()
            if value not in ('true', 'false'):
                raise ValueError(f'group-updates must be true or false, got: {value}')
            params['group-updates'] = value == 'true'
            seen_params.add(key)
            i += 2
        elif key == 'api':
            # Multiple 'api' keywords allowed for multiple processes
            if i + 1 >= len(tokens):
                raise ValueError('missing process name after "api"')
            api_processes.append(tokens[i + 1])
            i += 2
        elif key == 'create':
            # Accept and ignore trailing 'create' command (for backwards compatibility with tests)
            i += 1
        elif key == 'delete':
            # Reject 'delete' command in create context
            raise ValueError('expected "create" command')
        else:
            raise ValueError(f'unknown parameter: {key}')

    # Validate all required parameters were provided
    required = {'local-address', 'local-as', 'peer-as'}
    missing = required - seen_params
    if missing:
        raise ValueError(f'missing required parameters: {", ".join(sorted(missing))}')

    # Return None instead of empty list when no API processes (for test compatibility)
    if not api_processes:
        api_processes = None  # type: ignore

    # Default router-id to local-address if not provided
    if 'router-id' not in params:
        params['router-id'] = RouterID(str(params['local-address']))

    return params, api_processes


def _build_neighbor(params: dict[str, Any], api_processes: list[str] | None = None) -> Neighbor:
    """Build Neighbor object from parsed parameters.

    Args:
        params: Dictionary of parsed parameters (already validated by _parse_neighbor_params)
        api_processes: List of API process names for peer lifecycle events (None or empty list if none)

    Returns:
        Configured Neighbor object

    Raises:
        ValueError: If validation fails
    """
    # Validate required parameters
    required_params = {
        'peer-address': 'peer-address',
        'local-address': 'local-ip',  # Use 'local-ip' in error messages for backwards compatibility
        'local-as': 'local-as',
        'peer-as': 'peer-as',
        'router-id': 'router-id',
    }
    for param_key, error_name in required_params.items():
        if param_key not in params:
            raise ValueError(f'missing required parameter: {error_name}')

    neighbor = Neighbor()

    # Set required fields
    neighbor.session.peer_address = params['peer-address']
    neighbor.session.local_address = params['local-address']
    neighbor.session.local_as = params['local-as']
    neighbor.session.peer_as = params['peer-as']
    neighbor.session.router_id = params['router-id']

    # Optional: families (defaults to IPv4 unicast only)
    if 'families' in params and params['families']:
        for family in params['families']:
            neighbor.add_family(family)
    else:
        # Default to IPv4 unicast only
        neighbor.add_family((AFI.ipv4, SAFI.unicast))

    # Optional: graceful-restart (defaults to False)
    if 'graceful-restart' in params:
        gr_time = params['graceful-restart']
        if gr_time:
            neighbor.capability.graceful_restart = GracefulRestartConfig.with_time(gr_time)
        else:
            neighbor.capability.graceful_restart = GracefulRestartConfig.disabled()

    # Optional: group-updates (defaults to True per Neighbor.defaults)
    if 'group-updates' in params:
        neighbor.group_updates = params['group-updates']

    # Initialize API configuration (required before setting processes)
    neighbor.api = ParseAPI.flatten({})

    # Configure API processes for dynamic peer notifications
    if api_processes:
        neighbor.api['processes'] = api_processes

    # Validate completeness
    missing = neighbor.missing()
    if missing:
        raise ValueError(f'incomplete neighbor configuration, missing: {missing}')

    # Infer additional fields (e.g., md5-ip defaults to local-address)
    neighbor.infer()

    # Create RIB for route management
    neighbor.make_rib()

    return neighbor


@Command.register('create', neighbor=False, json_support=True)
def neighbor_create(self: Command, reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
    """Create a new BGP neighbor dynamically at runtime.

    API format: create neighbor <ip> local-address <ip> local-as <asn> peer-as <asn> [router-id <ip>] [family-allowed <families>] [graceful-restart <seconds>] [group-updates true|false] [api <process>]...

    Required parameters:
        - neighbor <ip> - peer IP address
        - local-address <ip> - local IP address (mandatory, no auto-discovery)
        - local-as <asn> - local AS number
        - peer-as <asn> - peer AS number

    Optional parameters:
        - router-id <ip> (defaults to local-address)
        - family-allowed <families> (defaults to ipv4-unicast)
        - graceful-restart <seconds> (defaults to disabled)
        - group-updates true|false (defaults to true)
        - api <process> (repeat 'api' keyword for multiple processes)

    Examples (API format):
        create neighbor 127.0.0.2 local-address 127.0.0.1 local-as 65001 peer-as 65002
        create neighbor 127.0.0.2 local-address 127.0.0.1 local-as 65001 peer-as 65002 router-id 2.2.2.2 api peer-lifecycle
        create neighbor 10.0.0.2 local-address 10.0.0.1 local-as 65001 peer-as 65002 api proc1 api proc2
        create neighbor 10.0.0.2 local-address 10.0.0.1 local-as 65001 peer-as 65002 family-allowed ipv4-unicast/ipv6-unicast api monitor
    """
    try:
        # line contains FULL command including "create", need to strip it
        # Expected format: "create neighbor <ip> local-address <ip> ..."
        # Strip "create " prefix if present
        line = line.strip()
        if line.startswith('create '):
            line = line[7:]  # Remove "create " prefix
        elif line.startswith('create\t'):
            line = line[7:]  # Remove "create\t" prefix

        # Parse parameters and API processes
        params, api_processes = _parse_neighbor_params(line)

        # Build Neighbor object with API process configuration
        neighbor = _build_neighbor(params, api_processes)
    except Exception as e:
        # Log full exception for debugging
        import traceback
        import sys

        sys.stderr.write(f'Exception in neighbor_create: {e}\n')
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        reactor.processes.answer_error(service, f'Unexpected error: {type(e).__name__}: {e}')
        return False

    try:
        # Check if peer already exists
        key = neighbor.index()
        if key in reactor._peers:
            reactor.processes.answer_error(service, f'peer already exists: {neighbor.name()}')
            return False

        # Add to configuration (for reload persistence - though we'll mark as dynamic)
        reactor.configuration.neighbors[key] = neighbor

        # Create and register Peer (import here to avoid circular import)
        from exabgp.reactor.peer import Peer

        peer = Peer(neighbor, reactor)
        reactor._peers[key] = peer

        # Mark as dynamic peer (ephemeral - removed on reload)
        if not hasattr(reactor, '_dynamic_peers'):
            reactor._dynamic_peers = set()  # type: ignore[attr-defined]
        reactor._dynamic_peers.add(key)  # type: ignore[attr-defined]

        # Success response - use _answer() which works in both sync and async modes
        reactor.processes._answer(service, 'done')
        return True

    except ValueError as e:
        reactor.processes.answer_error(service, f'neighbor create failed: {e}')
        return False
    except Exception as e:
        reactor.processes.answer_error(service, f'neighbor create error: {e}')
        return False


@Command.register('delete', neighbor=False, json_support=True)
def neighbor_delete(self: Command, reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
    """Delete BGP neighbor(s) dynamically at runtime.

    API format: delete neighbor <selector>

    Supports full neighbor selector syntax using existing announce/withdraw syntax.

    Examples (API format):
        delete neighbor 127.0.0.2                        # Delete specific peer
        delete neighbor *                                # Delete all peers (dangerous!)
        delete neighbor 127.0.0.2 local-as 1             # Delete with filter

    Note: Only dynamic peers created via 'create neighbor' should be deleted.
          Deleting static (configured) peers may cause issues on reload.
    """
    try:
        # Parse selector using extract_neighbors
        # Line should be: "neighbor <selector>"
        if not line.strip().startswith('neighbor'):
            reactor.processes.answer_error(service, 'missing neighbor selector')
            return False

        descriptions, command = extract_neighbors(line)

        # Get matching peers
        peers = match_neighbors(reactor.peers(service), descriptions)

        if not peers:
            # No matches - return error
            reactor.processes.answer_error(service, 'no neighbors match the selector')
            return False

        # Delete each matched peer
        deleted_count = 0
        for peer_name in peers:
            if peer_name in reactor._peers:
                # Get peer object
                peer = reactor._peers[peer_name]

                # Stop peer (sends NOTIFICATION, graceful shutdown)
                peer.remove()

                # Remove from reactor
                del reactor._peers[peer_name]

                # Remove from configuration
                if peer_name in reactor.configuration.neighbors:
                    del reactor.configuration.neighbors[peer_name]

                # Remove from dynamic peers tracking
                if hasattr(reactor, '_dynamic_peers') and peer_name in reactor._dynamic_peers:
                    reactor._dynamic_peers.remove(peer_name)

                deleted_count += 1

        # Success response
        reactor.processes.answer_done(service)
        return True

    except ValueError as e:
        reactor.processes.answer_error(service, f'neighbor delete failed: {e}')
        return False
    except Exception as e:
        reactor.processes.answer_error(service, f'neighbor delete error: {e}')
        return False
