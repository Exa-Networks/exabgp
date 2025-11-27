"""line/reactor.py

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import asyncio
import json

from exabgp.version import version as _version
from exabgp.reactor.api.command.command import Command

from exabgp.logger import log, lazymsg


def register_reactor():
    pass


@Command.register('help', False, json_support=True)
def help_command(self, reactor, service, line, use_json):
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
            if self.callback['options'][command]:
                cmd_info['options'] = list(self.callback['options'][command])

            commands_list.append(cmd_info)

        help_data = {
            'description': 'Available API commands',
            'neighbor_filters': ['local-ip', 'local-as', 'peer-as', 'router-id'],
            'commands': commands_list,
        }

        reactor.processes.write(service, json.dumps(help_data), True)
    else:
        # Text mode output (original implementation)
        lines = []
        encoding = 'text'
        for command in sorted(self.callback[encoding]):
            if self.callback['options'][command]:
                options = ' | '.join(self.callback['options'][command])
                extended = f'{command} [ {options} ]'
            else:
                extended = command
            lines.append(
                '[neighbor <ip> [filters]] ' + command if self.callback['neighbor'][command] else f'{extended} '
            )

        reactor.processes.write(service, '', True)
        reactor.processes.write(service, 'available API commands are listed here:', True)
        reactor.processes.write(service, '=======================================', True)
        reactor.processes.write(service, '', True)
        reactor.processes.write(
            service,
            'filter can be: [local-ip <ip>][local-as <asn>][peer-as <asn>][router-id <router-id>]',
            True,
        )
        reactor.processes.write(service, '', True)
        reactor.processes.write(service, 'command are:', True)
        reactor.processes.write(service, '------------', True)
        reactor.processes.write(service, '', True)
        for line in sorted(lines):
            reactor.processes.write(service, line, True)
        reactor.processes.write(service, '', True)

    reactor.processes.answer_done(service)
    return True


@Command.register('shutdown', False, json_support=True)
def shutdown(self, reactor, service, line, use_json):
    reactor.signal.received = reactor.signal.SHUTDOWN
    if use_json:
        reactor.processes.write(service, json.dumps({'status': 'shutdown in progress'}))
    else:
        reactor.processes.write(service, 'shutdown in progress')
    reactor.processes.answer_done(service)
    return True


@Command.register('reload', False, json_support=True)
def reload(self, reactor, service, line, use_json):
    reactor.signal.received = reactor.signal.RELOAD
    if use_json:
        reactor.processes.write(service, json.dumps({'status': 'reload in progress'}))
    else:
        reactor.processes.write(service, 'reload in progress')
    reactor.processes.answer_done(service)
    return True


@Command.register('restart', False, json_support=True)
def restart(self, reactor, service, line, use_json):
    reactor.signal.received = reactor.signal.RESTART
    if use_json:
        reactor.processes.write(service, json.dumps({'status': 'restart in progress'}))
    else:
        reactor.processes.write(service, 'restart in progress')
    reactor.processes.answer_done(service)
    return True


@Command.register('version', False, json_support=True)
def version(self, reactor, service, line, use_json):
    if use_json:
        reactor.processes.write(service, json.dumps({'version': _version, 'application': 'exabgp'}))
    else:
        reactor.processes.write(service, f'exabgp {_version}')
    reactor.processes.answer_done(service)
    return True


@Command.register('#', False, json_support=True)
def comment(self, reactor, service, line, use_json):
    log.debug(lazymsg('api.comment text={text}', text=line.lstrip().lstrip('#').strip()), 'processes')
    reactor.processes.answer_done(service)
    return True


@Command.register('reset', False, json_support=True)
def reset(self, reactor, service, line, use_json):
    reactor.asynchronous.clear(service)

    if use_json:
        reactor.processes.write(service, json.dumps({'status': 'asynchronous queue cleared'}))
    else:
        reactor.processes.write(service, 'asynchronous queue cleared')

    reactor.processes.answer_done(service)
    return True


@Command.register('crash', json_support=True)
def crash(self, reactor, service, line, use_json):
    async def callback():
        raise ValueError('crash test of the API')
        await asyncio.sleep(0)  # This line is unreachable but matches original structure

    # Send acknowledgment before scheduling the crash
    reactor.processes.answer_done(service)
    reactor.asynchronous.schedule(service, line, callback())
    return True


@Command.register('disable-ack', False, json_support=True)
def disable_ack(self, reactor, service, line, use_json):
    """Disable ACK responses for this connection (sends 'done' for this command, then disables)"""
    reactor.processes.set_ack(service, False)
    reactor.processes.answer_done(service, force=True)
    return True


@Command.register('enable-ack', False, json_support=True)
def enable_ack(self, reactor, service, line, use_json):
    """Re-enable ACK responses for this connection"""
    reactor.processes.set_ack(service, True)
    reactor.processes.answer_done(service)
    return True


@Command.register('silence-ack', False, json_support=True)
def silence_ack(self, reactor, service, line, use_json):
    """Disable ACK responses immediately (no 'done' sent for this command)"""
    reactor.processes.set_ack(service, False)
    return True


@Command.register('ping', False, json_support=True)
def ping(self, reactor, service, line, use_json):
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

    # Determine if this client is the active one
    is_active = True
    if client_uuid and client_start_time is not None:
        import time

        current_time = time.time()
        client_timeout = 15  # seconds - 10s ping interval + 5s grace

        # Check if current active client has timed out (no ping received)
        if reactor.active_client_uuid is not None:
            time_since_last_ping = current_time - reactor.active_client_last_ping
            if time_since_last_ping > client_timeout:
                # Active client timed out - clear it
                reactor.active_client_uuid = None
                reactor.active_client_last_ping = 0.0

        # Now determine active client (first-come-first-served)
        if reactor.active_client_uuid is None:
            # No active client - this one becomes active
            reactor.active_client_uuid = client_uuid
            reactor.active_client_last_ping = current_time
        elif client_uuid == reactor.active_client_uuid:
            # Same client - update last ping time
            reactor.active_client_last_ping = current_time
        else:
            # Different client - not active (first client keeps connection)
            is_active = False

    if output_json:
        response = {'pong': reactor.daemon_uuid, 'active': is_active}
        reactor.processes.write(service, json.dumps(response))
    else:
        reactor.processes.write(service, f'pong {reactor.daemon_uuid} active={str(is_active).lower()}')
    reactor.processes.answer_done(service)
    return True


@Command.register('status', False, json_support=True)
def status(self, reactor, service, line, use_json):
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
            reactor.processes.write(service, line_text, True)

    reactor.processes.answer_done(service)
    return True


@Command.register('bye', False, json_support=True)
def bye(self, reactor, service, line, use_json):
    """Handle client disconnect - clear active client tracking"""
    # Clear active client when CLI disconnects
    reactor.active_client_uuid = None
    reactor.active_client_last_ping = 0.0
    # Send acknowledgment to confirm disconnect
    reactor.processes.answer_done(service)
    return True
