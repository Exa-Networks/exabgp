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
from exabgp.protocol.ip import IP

from exabgp.reactor.api.command.announce import (
    parse_sync_mode,
    register_flush_callbacks,
    unsendable,
)
from exabgp.util.intvalue import json_number

if TYPE_CHECKING:
    from exabgp.reactor.api import API
    from exabgp.reactor.loop import Reactor
    from exabgp.rib.route import Route


def register_group() -> None:
    pass


# A group is only closed by the client sending "group end", so a client which never
# does would otherwise let the buffer grow until the daemon runs out of memory.
MAX_GROUP_COMMANDS = 100000
MAX_GROUP_BYTES = 100 * 1024 * 1024

# Per-service group buffers: service -> list of (peers, command) tuples
_GROUP_BUFFERS: dict[str, list[tuple[list[str], str]]] = {}
# Per-service byte count of the buffered commands
_GROUP_BYTES: dict[str, int] = {}


def _is_grouping(service: str) -> bool:
    """Check if service is currently in a group block."""
    return service in _GROUP_BUFFERS


def _start_group(service: str) -> None:
    """Start buffering commands for service."""
    _GROUP_BUFFERS[service] = []
    _GROUP_BYTES[service] = 0


def _end_group(service: str) -> list[tuple[list[str], str]]:
    """End grouping and return buffered commands."""
    counted = _GROUP_BYTES.pop(service, 0)
    buffered = _GROUP_BUFFERS.pop(service, [])
    # the cap is only worth anything if the count follows what the buffer holds
    assert counted == sum(len(command) for _, command in buffered), 'the group byte count has to follow its buffer'
    return buffered


def clear_group(service: str) -> None:
    """Drop any group state held for a service.

    Called when the process behind the service is gone: it will never send the
    "group end" which would otherwise release the buffer.
    """
    _GROUP_BYTES.pop(service, None)
    _GROUP_BUFFERS.pop(service, None)


def _add_to_group(service: str, peers: list[str], command: str) -> bool:
    """Add command to group buffer.

    Returns:
        True if the command was buffered, False if the group is over its limits
        (in which case the group state has been dropped).
    """
    if service not in _GROUP_BUFFERS:
        return False

    assert service in _GROUP_BYTES, 'a buffered group always has a byte count'

    if len(_GROUP_BUFFERS[service]) >= MAX_GROUP_COMMANDS:
        log.error(
            lazymsg('api.group.overflow service={s} commands={n}', s=service, n=len(_GROUP_BUFFERS[service])), 'api'
        )
        clear_group(service)
        return False

    if _GROUP_BYTES[service] + len(command) > MAX_GROUP_BYTES:
        log.error(lazymsg('api.group.overflow service={s} bytes={n}', s=service, n=_GROUP_BYTES[service]), 'api')
        clear_group(service)
        return False

    _GROUP_BUFFERS[service].append((peers, command))
    _GROUP_BYTES[service] += len(command)
    return True


def group_start(self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool) -> bool:
    """Start a group block - begin buffering commands.

    Usage: group start
    """
    if _is_grouping(service):
        error_msg = 'already in group block (nested groups not allowed)'
        if use_json:
            reactor.processes.write(service, json.dumps({'error': error_msg}, default=json_number))
        else:
            reactor.processes.write(service, f'error: {error_msg}')
        reactor.processes.answer_error_sync(service)
        return False

    _start_group(service)
    log.debug(lazymsg('api.group.start service={s}', s=service), 'api')

    if use_json:
        reactor.processes.write(service, json.dumps({'status': 'group started'}, default=json_number))
    else:
        reactor.processes.write(service, 'group started')
    reactor.processes.answer_done_sync(service)
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
            reactor.processes.write(service, json.dumps({'error': error_msg}, default=json_number))
        else:
            reactor.processes.write(service, f'error: {error_msg}')
        reactor.processes.answer_error_sync(service)
        return False

    buffered = _end_group(service)
    log.debug(lazymsg('api.group.end service={s} commands={n}', s=service, n=len(buffered)), 'api')

    if not buffered:
        # Empty group - no-op
        if use_json:
            reactor.processes.write(service, json.dumps({'status': 'group ended', 'commands': 0}, default=json_number))
        else:
            reactor.processes.write(service, 'group ended (0 commands)')
        reactor.processes.answer_done_sync(service)
        return True

    # Schedule async processing of all buffered commands
    async def callback() -> None:
        try:
            await _process_group(self, reactor, service, buffered, use_json)
        except Exception as e:
            error_msg = f'group processing failed: {type(e).__name__}: {str(e)}'
            log.error(lazymsg('api.group.error error={e}', e=error_msg), 'api')
            await reactor.processes.answer_error(service, error_msg)

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
            reactor.processes.write(service, json.dumps({'error': error_msg}, default=json_number))
        else:
            reactor.processes.write(service, f'error: {error_msg}')
        reactor.processes.answer_error_sync(service)
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
            await reactor.processes.answer_error(service, error_msg)

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
    # how many routes each action applied, the peers they went to, and what could not be applied
    applied = {'announce': 0, 'withdraw': 0}
    touched: set[str] = set()
    errors: list[str] = []

    # Shared attributes from 'attributes ...' command (first in group)
    shared: Route | None = None

    # Determine sync mode from first command (or service default)
    first_cmd = buffered[0][1] if buffered else ''
    _, sync_mode = parse_sync_mode(first_cmd, reactor, service)

    for cmd_peers, cmd in buffered:
        words = cmd.split(None, 1)
        if not words:
            continue

        action = words[0].lower()
        # Strip sync/async/json/text from remaining command
        remaining, _ = parse_sync_mode(words[1] if len(words) > 1 else '', reactor, service)

        if action in ('attribute', 'attributes'):
            # Parse shared attributes - use full command including 'attributes'
            routes = _parse_routes(api, cmd, action='announce')
            if routes:
                shared = routes[0]
                log.debug(lazymsg('api.group.shared_attributes attrs={a}', a=shared.attributes), 'api')
            else:
                errors.append(f'could not parse attributes: {cmd}')
        elif action in applied:
            await _apply(api, reactor, service, cmd_peers, cmd, remaining, action, shared, applied, touched, errors)
        else:
            errors.append(f'unknown action in group: {action}')

    # Wait for every peer given a route to have sent it (if sync mode)
    flush_events = register_flush_callbacks(list(touched), reactor, sync_mode)
    if flush_events:
        await asyncio.gather(*[e.wait() for e in flush_events])

    await _answer_group(reactor, service, use_json, applied, errors)


async def _apply(
    api: 'API',
    reactor: 'Reactor',
    service: str,
    peers: list[str],
    cmd: str,
    remaining: str,
    action: str,
    shared: 'Route | None',
    applied: dict[str, int],
    touched: set[str],
    errors: list[str],
) -> None:
    """Apply the routes of one `announce ...` or `withdraw ...` of a group to the RIB of `peers`."""
    routes = _parse_routes(api, remaining, action=action)
    if not routes:
        errors.append(f'could not parse: {cmd}')
        return

    for route in routes:
        # the attributes a group shares, for announcements and withdrawals alike
        if shared:
            route = route.with_merged_attributes(shared.attributes)
            # and its next-hop, to a route which gave none of its own
            if route.nexthop is IP.NoNextHop and shared.nexthop is not IP.NoNextHop:
                route = route.with_nexthop(shared.nexthop)

        if action == 'announce':
            # Validate route before announcing (early feedback)
            error = unsendable(reactor, peers, route)
            if error:
                errors.append(f'invalid route: {error}')
                continue
            reactor.configuration.announce_route(peers, route, service)
        else:
            reactor.configuration.withdraw_route(peers, route)
        touched.update(peers)
        applied[action] += 1
        await asyncio.sleep(0)


async def _answer_group(
    reactor: 'Reactor', service: str, use_json: bool, applied: dict[str, int], errors: list[str]
) -> None:
    """Say what a group applied, and end with done, or with error when a command could not be applied.

    The routes which could be applied are, whatever the others did: the errors say which were not.
    """
    if use_json:
        response = {
            'status': 'group processed',
            'announced': applied['announce'],
            'withdrawn': applied['withdraw'],
        }
        if errors:
            response['errors'] = errors
        reactor.processes.write(service, json.dumps(response, default=json_number))
    else:
        msg = f'group processed: {applied["announce"]} announced, {applied["withdraw"]} withdrawn'
        if errors:
            msg += f', {len(errors)} errors'
        reactor.processes.write(service, msg)

    if errors:
        await reactor.processes.answer_error(service)
    else:
        await reactor.processes.answer_done(service)


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
    if not _add_to_group(service, peers, command):
        error_msg = 'group buffer limit reached, group discarded'
        if use_json:
            reactor.processes.write(service, json.dumps({'error': error_msg}, default=json_number))
        else:
            reactor.processes.write(service, f'error: {error_msg}')
        reactor.processes.answer_error_sync(service)
        return False

    log.debug(lazymsg('api.group.add service={s} command={c}', s=service, c=command[:50]), 'api')
    reactor.processes.answer_done_sync(service)
    return True


def is_grouping(service: str) -> bool:
    """Check if service is currently in a group block.

    Used by dispatch to redirect announce/withdraw to group buffer.
    """
    return _is_grouping(service)
