"""command/group.py

Group command for batching multiple announcements into single UPDATE messages.

Enables:
- Exact wire-format reproduction for multi-NLRI UPDATEs
- Atomic updates (all-or-nothing)
- Reduced UPDATE count for bulk operations

Syntax:
    Single-line: group announce ... ; announce ...
    Multi-line:  group start
                 announce ...
                 announce ...
                 group end

Created on 2025-12-10.
Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

from exabgp.logger import log, lazymsg

from exabgp.reactor.api.command.announce import (
    parse_sync_mode,
    register_flush_callbacks,
    validate_announce,
)

if TYPE_CHECKING:
    from exabgp.reactor.api import API
    from exabgp.reactor.loop import Reactor
    from exabgp.rib.route import Route


def register_group() -> None:
    pass


# Per-service group buffers: service -> list of (peers, command) tuples
_GROUP_BUFFERS: dict[str, list[tuple[list[str], str]]] = {}


def _is_grouping(service: str) -> bool:
    """Check if service is currently in a group block."""
    return service in _GROUP_BUFFERS


def _start_group(service: str) -> None:
    """Start buffering commands for service."""
    _GROUP_BUFFERS[service] = []


def _end_group(service: str) -> list[tuple[list[str], str]]:
    """End grouping and return buffered commands."""
    return _GROUP_BUFFERS.pop(service, [])


def _add_to_group(service: str, peers: list[str], command: str) -> None:
    """Add command to group buffer."""
    if service in _GROUP_BUFFERS:
        _GROUP_BUFFERS[service].append((peers, command))


def group_start(self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool) -> bool:
    """Start a group block - begin buffering commands.

    Usage: group start
    """
    if _is_grouping(service):
        error_msg = 'already in group block (nested groups not allowed)'
        if use_json:
            reactor.processes.write(service, json.dumps({'error': error_msg}))
        else:
            reactor.processes.write(service, f'error: {error_msg}')
        reactor.processes.answer_error(service)
        return False

    _start_group(service)
    log.debug(lazymsg('api.group.start service={s}', s=service), 'api')

    if use_json:
        reactor.processes.write(service, json.dumps({'status': 'group started'}))
    else:
        reactor.processes.write(service, 'group started')
    reactor.processes.answer_done(service)
    return True


def group_end(self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool) -> bool:
    """End a group block - process all buffered commands.

    Usage: group end

    All buffered announce/withdraw commands are processed together,
    allowing RIB-level batching to combine them into minimal UPDATEs.
    """
    if not _is_grouping(service):
        error_msg = 'not in group block'
        if use_json:
            reactor.processes.write(service, json.dumps({'error': error_msg}))
        else:
            reactor.processes.write(service, f'error: {error_msg}')
        reactor.processes.answer_error(service)
        return False

    buffered = _end_group(service)
    log.debug(lazymsg('api.group.end service={s} commands={n}', s=service, n=len(buffered)), 'api')

    if not buffered:
        # Empty group - no-op
        if use_json:
            reactor.processes.write(service, json.dumps({'status': 'group ended', 'commands': 0}))
        else:
            reactor.processes.write(service, 'group ended (0 commands)')
        reactor.processes.answer_done(service)
        return True

    # Schedule async processing of all buffered commands
    async def callback() -> None:
        try:
            await _process_group(self, reactor, service, buffered, use_json)
        except Exception as e:
            error_msg = f'group processing failed: {type(e).__name__}: {str(e)}'
            log.error(lazymsg('api.group.error error={e}', e=error_msg), 'api')
            await reactor.processes.answer_error_async(service, error_msg)

    reactor.asynchronous.schedule(service, 'group end', callback())
    return True


def group_inline(self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool) -> bool:
    """Process single-line group command.

    Usage: group announce ... ; announce ... ; withdraw ...

    Commands are separated by semicolons and processed together,
    allowing RIB-level batching to combine them into minimal UPDATEs.
    """
    # Parse semicolon-separated commands
    # command is everything after "group " token
    parts = [p.strip() for p in command.split(';') if p.strip()]

    if not parts:
        error_msg = 'empty group'
        if use_json:
            reactor.processes.write(service, json.dumps({'error': error_msg}))
        else:
            reactor.processes.write(service, f'error: {error_msg}')
        reactor.processes.answer_error(service)
        return False

    log.debug(lazymsg('api.group.inline service={s} commands={n}', s=service, n=len(parts)), 'api')

    # Build buffered list with peer targeting
    # Each command in the inline group inherits the original peers
    buffered: list[tuple[list[str], str]] = [(peers, cmd) for cmd in parts]

    # Schedule async processing
    async def callback() -> None:
        try:
            await _process_group(self, reactor, service, buffered, use_json)
        except Exception as e:
            error_msg = f'group processing failed: {type(e).__name__}: {str(e)}'
            log.error(lazymsg('api.group.error error={e}', e=error_msg), 'api')
            await reactor.processes.answer_error_async(service, error_msg)

    reactor.asynchronous.schedule(service, 'group inline', callback())
    return True


async def _process_group(
    api: 'API',
    reactor: 'Reactor',
    service: str,
    buffered: list[tuple[list[str], str]],
    use_json: bool,
) -> None:
    """Process a group of buffered commands.

    Parses all commands, injects routes into RIB, then waits for flush.
    RIB-level batching will automatically combine routes with same attributes.

    Special handling for 'group attributes ... ; withdraw ...' syntax:
    - First command starting with 'attributes' sets shared attributes
    - Subsequent withdraw commands get those shared attributes merged in
    """

    # Collect all peers that will receive routes (for flush callbacks)
    all_peers: set[str] = set()
    routes_added = 0
    routes_withdrawn = 0
    errors: list[str] = []

    # Shared attributes from 'attributes ...' command (first in group)
    shared_attributes_route: Route | None = None

    # Determine sync mode from first command (or service default)
    first_cmd = buffered[0][1] if buffered else ''
    _, sync_mode = parse_sync_mode(first_cmd, reactor, service)

    # Process each buffered command
    for cmd_peers, cmd in buffered:
        # Determine action from command prefix
        words = cmd.split(None, 1)
        if not words:
            continue

        action_word = words[0].lower()
        remaining = words[1] if len(words) > 1 else ''

        # Strip sync/async/json/text from remaining command
        remaining, _ = parse_sync_mode(remaining, reactor, service)

        if action_word in ('attribute', 'attributes'):
            # Parse shared attributes - use full command including 'attributes'
            routes = _parse_routes(api, cmd, action='announce')
            if routes:
                shared_attributes_route = routes[0]
                log.debug(lazymsg('api.group.shared_attributes attrs={a}', a=shared_attributes_route.attributes), 'api')
            else:
                errors.append(f'could not parse attributes: {cmd}')

        elif action_word == 'announce':
            # Parse the announcement
            routes = _parse_routes(api, remaining, action='announce')
            if not routes:
                errors.append(f'could not parse: {cmd}')
                continue

            for route in routes:
                # Merge shared attributes if available
                if shared_attributes_route:
                    route = route.with_merged_attributes(shared_attributes_route.attributes)

                # Validate route before announcing (early feedback)
                error = validate_announce(route)
                if error:
                    errors.append(f'invalid route: {error}')
                    continue

                reactor.configuration.announce_route(cmd_peers, route)
                all_peers.update(cmd_peers)
                routes_added += 1
                await asyncio.sleep(0)

        elif action_word == 'withdraw':
            # Parse the withdrawal - pass action='withdraw' for proper handling
            routes = _parse_routes(api, remaining, action='withdraw')
            if not routes:
                errors.append(f'could not parse: {cmd}')
                continue

            for route in routes:
                # Merge shared attributes if available (for withdrawals with attributes)
                if shared_attributes_route:
                    route = route.with_merged_attributes(shared_attributes_route.attributes)

                reactor.configuration.withdraw_route(cmd_peers, route)
                all_peers.update(cmd_peers)
                routes_withdrawn += 1
                await asyncio.sleep(0)

        else:
            errors.append(f'unknown action in group: {action_word}')

    # Register flush callbacks for all affected peers
    flush_events = register_flush_callbacks(list(all_peers), reactor, sync_mode)

    # Wait for flush if sync mode
    if flush_events:
        await asyncio.gather(*[e.wait() for e in flush_events])

    # Build response
    if use_json:
        response = {
            'status': 'group processed',
            'announced': routes_added,
            'withdrawn': routes_withdrawn,
        }
        if errors:
            response['errors'] = errors
        reactor.processes.write(service, json.dumps(response))
    else:
        msg = f'group processed: {routes_added} announced, {routes_withdrawn} withdrawn'
        if errors:
            msg += f', {len(errors)} errors'
        reactor.processes.write(service, msg)

    await reactor.processes.answer_done_async(service)


def _parse_routes(api: 'API', command: str, action: str = 'announce') -> list['Route']:
    """Parse routes from command string.

    Handles various route formats:
    - route 10.0.0.0/24 next-hop 1.2.3.4
    - ipv4 unicast route 10.0.0.0/24 next-hop 1.2.3.4
    - ipv4 mcast-vpn shared-join ...
    - flow match ...
    - vpls ...

    Args:
        api: API instance for parsing
        command: Command string to parse
        action: 'announce' or 'withdraw' - affects how routes are parsed
    """
    if not command:
        return []

    words = command.split(None, 1)
    if not words:
        return []

    route_type = words[0].lower()

    try:
        if route_type == 'route':
            return api.api_route(command, action=action)
        elif route_type == 'ipv4':
            return api.api_announce_v4(command, action=action)
        elif route_type == 'ipv6':
            return api.api_announce_v6(command, action=action)
        elif route_type == 'flow':
            return api.api_flow(command, action=action)
        elif route_type == 'vpls':
            return api.api_vpls(command, action=action)
        elif route_type in ('attribute', 'attributes'):
            return api.api_attributes(command, [], action=action)
        else:
            # Unknown type, try as generic route
            return api.api_route(command, action=action)
    except Exception:
        return []


def group_add_command(
    self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool
) -> bool:
    """Add a command to the current group buffer (called during multi-line grouping).

    This is used internally when a service is in grouping mode and sends
    announce/withdraw commands.
    """
    _add_to_group(service, peers, command)
    log.debug(lazymsg('api.group.add service={s} command={c}', s=service, c=command[:50]), 'api')
    reactor.processes.answer_done(service)
    return True


def is_grouping(service: str) -> bool:
    """Check if service is currently in a group block.

    Used by dispatch to redirect announce/withdraw to group buffer.
    """
    return _is_grouping(service)
