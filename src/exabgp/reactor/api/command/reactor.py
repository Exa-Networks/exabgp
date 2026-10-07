"""command/reactor.py

Reactor control commands (shutdown, reload, help, etc.)

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from exabgp.version import version as _version

from exabgp.logger import log, lazymsg
from exabgp.util.intvalue import json_number

if TYPE_CHECKING:
    from exabgp.reactor.api import API
    from exabgp.reactor.loop import Reactor


def register_reactor() -> None:
    pass


def help_command(self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool) -> bool:
    from exabgp.reactor.api.dispatch import get_commands

    commands = get_commands()

    if use_json:
        # Build JSON structure with command metadata
        commands_list = []

        for cmd_name, neighbor_support, options in sorted(commands, key=lambda x: x[0]):
            cmd_info = {
                'command': cmd_name,
                'neighbor_support': neighbor_support,
                'json_support': True,
            }
            if options:
                cmd_info['options'] = options
            commands_list.append(cmd_info)

        help_data = {
            'description': 'Available API commands (v6 format)',
            'peer_filters': ['local-ip', 'local-as', 'peer-as', 'router-id'],
            'commands': commands_list,
        }

        reactor.processes.write(service, json.dumps(help_data, default=json_number))
    else:
        # Text mode output
        lines = []

        for cmd_name, neighbor_support, options in sorted(commands, key=lambda x: x[0]):
            if options:
                opts_str = ' | '.join(str(o) for o in options)
                extended = f'{cmd_name} [ {opts_str} ]'
            else:
                extended = cmd_name
            lines.append('[peer <ip> [filters]] ' + extended if neighbor_support else f'{extended} ')

        reactor.processes.write(service, '')
        reactor.processes.write(service, 'available API commands (v6 format):')
        reactor.processes.write(service, '====================================')
        reactor.processes.write(service, '')
        reactor.processes.write(
            service,
            'filter can be: [local-ip <ip>][local-as <asn>][peer-as <asn>][router-id <router-id>]',
        )
        reactor.processes.write(service, '')
        reactor.processes.write(service, 'commands:')
        reactor.processes.write(service, '---------')
        reactor.processes.write(service, '')
        for line_text in sorted(lines):
            reactor.processes.write(service, line_text)
        reactor.processes.write(service, '')

    reactor.processes.answer_done_sync(service)
    return True


def shutdown(self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool) -> bool:
    reactor.signal.request(reactor.signal.SHUTDOWN)
    if use_json:
        reactor.processes.write(service, json.dumps({'status': 'shutdown in progress'}, default=json_number))
    else:
        reactor.processes.write(service, 'shutdown in progress')
    reactor.processes.answer_done_sync(service)
    return True


def reload(self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool) -> bool:
    if not reactor.signal.request(reactor.signal.RELOAD):
        reactor.processes.answer_error_sync(service, 'shutdown in progress')
        return False
    if use_json:
        reactor.processes.write(service, json.dumps({'status': 'reload in progress'}, default=json_number))
    else:
        reactor.processes.write(service, 'reload in progress')
    reactor.processes.answer_done_sync(service)
    return True


def restart(self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool) -> bool:
    if not reactor.signal.request(reactor.signal.RESTART):
        reactor.processes.answer_error_sync(service, 'shutdown in progress')
        return False
    if use_json:
        reactor.processes.write(service, json.dumps({'status': 'restart in progress'}, default=json_number))
    else:
        reactor.processes.write(service, 'restart in progress')
    reactor.processes.answer_done_sync(service)
    return True


def version(self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool) -> bool:
    if use_json:
        reactor.processes.write(
            service, json.dumps({'version': _version, 'application': 'exabgp'}, default=json_number)
        )
    else:
        reactor.processes.write(service, f'exabgp {_version}')
    reactor.processes.answer_done_sync(service)
    return True


def comment(self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool) -> bool:
    log.debug(lazymsg('api.comment text={text}', text=command.lstrip().lstrip('#').strip()), 'processes')
    reactor.processes.answer_done_sync(service)
    return True


def reset(self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool) -> bool:
    reactor.asynchronous.clear(service)

    if use_json:
        reactor.processes.write(service, json.dumps({'status': 'asynchronous queue cleared'}, default=json_number))
    else:
        reactor.processes.write(service, 'asynchronous queue cleared')

    reactor.processes.answer_done_sync(service)
    return True


def queue_status(self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool) -> bool:
    """Display write queue status for all API processes.

    Returns queue size (items and bytes) for each process.
    Useful for monitoring backpressure and diagnosing slow API clients.
    """
    stats = reactor.processes.get_queue_stats()

    if use_json:
        reactor.processes.write(service, json.dumps(stats, default=json_number))
    else:
        # Text format: process: N items (M bytes)
        if not stats:
            reactor.processes.write(service, 'no queued messages')
        else:
            lines = []
            for process_name, process_stats in sorted(stats.items()):
                items = process_stats['items']
                bytes_count = process_stats['bytes']
                lines.append(f'{process_name}: {items} items ({bytes_count} bytes)')
            reactor.processes.write(service, '\n'.join(lines))

    reactor.processes.answer_done_sync(service)
    return True


def crash(self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool) -> bool:
    """Raise inside a scheduled coroutine, to test what the reactor does when one does.

    The reactor answers `error` for a coroutine which raised, and that is the answer: one
    `done` before it would be read as the answer, and the `error` as the next command's.
    """

    async def callback() -> None:
        raise ValueError('crash test of the API')

    reactor.asynchronous.schedule(service, command, callback())
    return True


def disable_ack(self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool) -> bool:
    """Disable ACK responses for this connection (sends 'done' for this command, then disables)"""
    reactor.processes.set_ack(service, False)
    reactor.processes.answer_done_sync(service, force=True)
    return True


def enable_ack(self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool) -> bool:
    """Re-enable ACK responses for this connection"""
    reactor.processes.set_ack(service, True)
    reactor.processes.answer_done_sync(service)
    return True


def silence_ack(self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool) -> bool:
    """Disable ACK responses immediately (no 'done' sent for this command)"""
    reactor.processes.set_ack(service, False)
    return True


def enable_sync(self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool) -> bool:
    """Enable sync mode - wait for routes to be flushed to wire before ACK.

    When sync mode is enabled, announce/withdraw commands will wait until
    the routes have been sent on the wire to the BGP peer before returning
    the ACK response. This allows API processes to know when routes have
    actually been transmitted.
    """
    reactor.processes.set_sync(service, True)
    reactor.processes.answer_done_sync(service)
    return True


def disable_sync(self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool) -> bool:
    """Disable sync mode - ACK immediately after RIB update (default).

    When sync mode is disabled (default), announce/withdraw commands return
    ACK immediately after the route is added to the RIB, without waiting
    for it to be sent on the wire.
    """
    reactor.processes.set_sync(service, False)
    reactor.processes.answer_done_sync(service)
    return True


def ping(self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool) -> bool:
    """Lightweight health check - responds with 'pong <UUID>' and active status

    Defaults to JSON output unless 'text' keyword is explicitly used.

    The CLI sends "ping <client_uuid> <client_start_time>". Both are accepted and unused:
    the daemon once let one CLI in at a time by them, and keeps no list of clients now,
    since one at a time is the socket helper's job. So every client is active.
    """
    parts = command.strip().split()

    # Check if 'text' keyword is explicitly used in the command line
    # Default to JSON unless text is explicitly requested
    if 'text' in [p.lower() for p in parts]:
        output_json = False
    else:
        output_json = True

    is_active = True

    if output_json:
        response = {'pong': reactor.daemon_uuid, 'active': is_active}
        reactor.processes.write(service, json.dumps(response, default=json_number))
    else:
        reactor.processes.write(service, f'pong {reactor.daemon_uuid} active={str(is_active).lower()}')
    reactor.processes.answer_done_sync(service)
    return True


def bye(self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool) -> bool:
    """Acknowledge a client leaving: the CLI sends "bye" when it quits, and waits for done.

    It once released the daemon's one CLI slot, and there is no slot to release any more.
    """
    reactor.processes.answer_done_sync(service)
    return True


def api_version_cmd(
    self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool
) -> bool:
    """Display or set the API version of the helpers.

    Usage:
        api version       - Show the setting, and this helper's version
        api version auto  - Detect each helper's version from its commands (default)
        api version 4     - Hold every helper to API 4 (legacy, text or json)
        api version 6     - Hold every helper to API 6 (json only)

    Note: a change applies to helpers started afterwards.
    """
    from exabgp.environment import getenv
    from exabgp.environment.parsing import api_version as parse_api_version

    parts = command.strip().split()
    if not parts:
        return _show_api_version(reactor, service, use_json)

    try:
        new_version = parse_api_version(parts[0])
    except TypeError as exc:
        _write(reactor, service, use_json, {'error': str(exc)}, f'error: {exc}')
        reactor.processes.answer_error_sync(service)
        return False

    getenv().api.version = new_version
    name = _api_version_name(new_version)
    _write(
        reactor,
        service,
        use_json,
        {'status': 'API version set', 'version': name, 'note': 'effective for helpers started afterwards'},
        f'API version set to {name} (effective for helpers started afterwards)',
    )
    reactor.processes.answer_done_sync(service)
    return True


def _api_version_name(version: int) -> str:
    return 'auto' if version == 0 else str(version)


def _write(reactor: 'Reactor', service: str, use_json: bool, data: dict[str, Any], text: str) -> None:
    if use_json:
        reactor.processes.write(service, json.dumps(data, default=json_number))
    else:
        reactor.processes.write(service, text)


def _show_api_version(reactor: 'Reactor', service: str, use_json: bool) -> bool:
    """The setting, and the version this helper speaks (auto until its commands tell)."""
    from exabgp.environment import getenv

    setting = _api_version_name(getenv().api.version)
    current = _api_version_name(reactor.processes.api_version(service))
    _write(
        reactor,
        service,
        use_json,
        {'api_version': setting, 'helper_api_version': current},
        f'API version: {setting} (this helper: {current})',
    )
    reactor.processes.answer_done_sync(service)
    return True


def status(self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool) -> bool:
    """Display daemon status information (UUID, uptime, version, peers)"""
    import os
    import time

    uptime = int(time.time() - reactor.daemon_start_time)
    hours = uptime // 3600
    minutes = (uptime % 3600) // 60
    seconds = uptime % 60

    peers_dict = {}
    for name, peer in reactor._peers.items():
        state = peer.fsm.name()
        peers_dict[name] = state

    if use_json:
        status_info = {
            'version': _version,
            'uuid': reactor.daemon_uuid,
            'pid': os.getpid(),
            'uptime': uptime,
            'start_time': reactor.daemon_start_time,
            'peers': peers_dict,
        }
        reactor.processes.write(service, json.dumps(status_info, default=json_number))
    else:
        lines = [
            'ExaBGP Daemon Status',
            '====================',
            f'Version: {_version}',
            f'UUID: {reactor.daemon_uuid}',
            f'PID: {os.getpid()}',
            f'Uptime: {hours}h {minutes}m {seconds}s',
            f'Peers: {len(peers_dict)}',
        ]

        if peers_dict:
            for name, state in peers_dict.items():
                lines.append(f'  - {name}: {state}')

        for line_text in lines:
            reactor.processes.write(service, line_text)

    reactor.processes.answer_done_sync(service)
    return True
