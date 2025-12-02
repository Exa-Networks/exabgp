"""line/reactor.py

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

from exabgp.version import version as _version
from exabgp.reactor.api.command.command import Command

from exabgp.logger import log, lazymsg

if TYPE_CHECKING:
    from exabgp.reactor.loop import Reactor


def register_reactor() -> None:
    pass


@Command.register('help', False, json_support=True)
def help_command(self: Command, reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
    if use_json:
        # Build JSON structure with command metadata
        commands_list = []
        encoding = 'json'

        for command in sorted(self.callback[encoding]):
            cmd_info = {
                'command': command,
                'neighbor_support': self.callback['neighbor'][command],
                'json_support': True,  # We're listing commands from json callback
            }

            # Add options if available
            opts = self.callback['options'][command]
            if isinstance(opts, (list, tuple, set)):
                cmd_info['options'] = list(opts)

            commands_list.append(cmd_info)

        help_data = {
            'description': 'Available API commands',
            'neighbor_filters': ['local-ip', 'local-as', 'peer-as', 'router-id'],
            'commands': commands_list,
        }

        reactor.processes.write(service, json.dumps(help_data))
    else:
        # Text mode output (original implementation)
        lines = []
        encoding = 'text'
        for command in sorted(self.callback[encoding]):
            opts = self.callback['options'][command]
            if isinstance(opts, (list, tuple, set)):
                options = ' | '.join(str(o) for o in opts)
                extended = f'{command} [ {options} ]'
            else:
                extended = command
            lines.append(
                '[neighbor <ip> [filters]] ' + command if self.callback['neighbor'][command] else f'{extended} '
            )

        reactor.processes.write(service, '')
        reactor.processes.write(service, 'available API commands are listed here:')
        reactor.processes.write(service, '=======================================')
        reactor.processes.write(service, '')
        reactor.processes.write(
            service,
            'filter can be: [local-ip <ip>][local-as <asn>][peer-as <asn>][router-id <router-id>]',
        )
        reactor.processes.write(service, '')
        reactor.processes.write(service, 'command are:')
        reactor.processes.write(service, '------------')
        reactor.processes.write(service, '')
        for line in sorted(lines):
            reactor.processes.write(service, line)
        reactor.processes.write(service, '')

    reactor.processes.answer_done(service)
    return True


@Command.register('shutdown', False, json_support=True)
def shutdown(self: Command, reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
    reactor.signal.received = reactor.signal.SHUTDOWN
    if use_json:
        reactor.processes.write(service, json.dumps({'status': 'shutdown in progress'}))
    else:
        reactor.processes.write(service, 'shutdown in progress')
    reactor.processes.answer_done(service)
    return True


@Command.register('reload', False, json_support=True)
def reload(self: Command, reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
    reactor.signal.received = reactor.signal.RELOAD
    if use_json:
        reactor.processes.write(service, json.dumps({'status': 'reload in progress'}))
    else:
        reactor.processes.write(service, 'reload in progress')
    reactor.processes.answer_done(service)
    return True


@Command.register('restart', False, json_support=True)
def restart(self: Command, reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
    reactor.signal.received = reactor.signal.RESTART
    if use_json:
        reactor.processes.write(service, json.dumps({'status': 'restart in progress'}))
    else:
        reactor.processes.write(service, 'restart in progress')
    reactor.processes.answer_done(service)
    return True


@Command.register('version', False, json_support=True)
def version(self: Command, reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
    if use_json:
        reactor.processes.write(service, json.dumps({'version': _version, 'application': 'exabgp'}))
    else:
        reactor.processes.write(service, f'exabgp {_version}')
    reactor.processes.answer_done(service)
    return True


@Command.register('#', False, json_support=True)
def comment(self: Command, reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
    log.debug(lazymsg('api.comment text={text}', text=line.lstrip().lstrip('#').strip()), 'processes')
    reactor.processes.answer_done(service)
    return True


@Command.register('reset', False, json_support=True)
def reset(self: Command, reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
    reactor.asynchronous.clear(service)

    if use_json:
        reactor.processes.write(service, json.dumps({'status': 'asynchronous queue cleared'}))
    else:
        reactor.processes.write(service, 'asynchronous queue cleared')

    reactor.processes.answer_done(service)
    return True


@Command.register('queue-status', False, json_support=True)
def queue_status(self: Command, reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
    """Display write queue status for all API processes.

    Returns queue size (items and bytes) for each process.
    Useful for monitoring backpressure and diagnosing slow API clients.
    """
    stats = reactor.processes.get_queue_stats()

    if use_json:
        reactor.processes.write(service, json.dumps(stats))
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

    reactor.processes.answer_done(service)
    return True


@Command.register('crash', json_support=True)
def crash(self: Command, reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
    async def callback() -> None:
        raise ValueError('crash test of the API')
        await asyncio.sleep(0)  # This line is unreachable but matches original structure

    # Send acknowledgment before scheduling the crash
    reactor.processes.answer_done(service)
    reactor.asynchronous.schedule(service, line, callback())
    return True


@Command.register('disable-ack', False, json_support=True)
def disable_ack(self: Command, reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
    """Disable ACK responses for this connection (sends 'done' for this command, then disables)"""
    reactor.processes.set_ack(service, False)
    reactor.processes.answer_done(service, force=True)
    return True


@Command.register('enable-ack', False, json_support=True)
def enable_ack(self: Command, reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
    """Re-enable ACK responses for this connection"""
    reactor.processes.set_ack(service, True)
    reactor.processes.answer_done(service)
    return True


@Command.register('silence-ack', False, json_support=True)
def silence_ack(self: Command, reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
    """Disable ACK responses immediately (no 'done' sent for this command)"""
    reactor.processes.set_ack(service, False)
    return True


@Command.register('enable-sync', False, json_support=True)
def enable_sync(self: Command, reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
    """Enable sync mode - wait for routes to be flushed to wire before ACK.

    When sync mode is enabled, announce/withdraw commands will wait until
    the routes have been sent on the wire to the BGP peer before returning
    the ACK response. This allows API processes to know when routes have
    actually been transmitted.
    """
    reactor.processes.set_sync(service, True)
    reactor.processes.answer_done(service)
    return True


@Command.register('disable-sync', False, json_support=True)
def disable_sync(self: Command, reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
    """Disable sync mode - ACK immediately after RIB update (default).

    When sync mode is disabled (default), announce/withdraw commands return
    ACK immediately after the route is added to the RIB, without waiting
    for it to be sent on the wire.
    """
    reactor.processes.set_sync(service, False)
    reactor.processes.answer_done(service)
    return True


@Command.register('ping', False, json_support=True)
def ping(self: Command, reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
    """Lightweight health check - responds with 'pong <UUID>' and active status

    Defaults to JSON output unless 'text' keyword is explicitly used.
    """
    # Parse client UUID and start time if provided
    # Format: "ping <client_uuid> <client_start_time>"
    parts = line.strip().split()
    client_uuid = None
    client_start_time = None

    # Check if 'text' keyword is explicitly used in the command line
    # Default to JSON unless text is explicitly requested
    if 'text' in [p.lower() for p in parts]:
        output_json = False
    else:
        output_json = True

    if len(parts) >= 3:
        client_uuid = parts[1]
        try:
            client_start_time = float(parts[2])
        except ValueError:
            pass

    # Multi-client support: all clients are active
    is_active = True
    if client_uuid and client_start_time is not None:
        import time

        current_time = time.time()
        client_timeout = 15  # seconds - 10s ping interval + 5s grace

        # Clean up stale clients (no ping received within timeout)
        stale_uuids = [
            uuid for uuid, last_ping in reactor.active_clients.items() if current_time - last_ping > client_timeout
        ]
        for uuid in stale_uuids:
            del reactor.active_clients[uuid]

        # Update this client's ping time (all clients are active in multi-client mode)
        reactor.active_clients[client_uuid] = current_time

    if output_json:
        response = {'pong': reactor.daemon_uuid, 'active': is_active}
        reactor.processes.write(service, json.dumps(response))
    else:
        reactor.processes.write(service, f'pong {reactor.daemon_uuid} active={str(is_active).lower()}')
    reactor.processes.answer_done(service)
    return True


@Command.register('bye', False, json_support=True)
def bye(self: Command, reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
    """Handle client disconnect - cleanup client tracking

    Format: "bye <client_uuid>"
    Called by socket server when a client disconnects.
    """
    # Parse client UUID if provided
    parts = line.strip().split()
    client_uuid = parts[1] if len(parts) >= 2 else None

    # Remove client from active clients tracking
    if client_uuid and client_uuid in reactor.active_clients:
        del reactor.active_clients[client_uuid]

    reactor.processes.answer_done(service)
    return True


@Command.register('status', False, json_support=True)
def status(self: Command, reactor: Reactor, service: str, line: str, use_json: bool) -> bool:
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
        reactor.processes.write(service, json.dumps(status_info))
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

    reactor.processes.answer_done(service)
    return True


