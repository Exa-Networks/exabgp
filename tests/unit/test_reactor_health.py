"""test_reactor_health.py

Unit tests for daemon health monitoring commands:
- ping
- status
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Iterator

import pytest

from exabgp.configuration.configuration import Configuration
from exabgp.reactor.api.processes import Processes
from exabgp.reactor.loop import Reactor


class PipedHelper:
    """The Popen of the API client, as far as answering it goes: its stdin is a pipe."""

    def __init__(self) -> None:
        self._reader, writer = os.pipe()
        os.set_blocking(self._reader, False)
        self.stdin = os.fdopen(writer, 'wb')

    def lines(self) -> list[str]:
        """Every line written to the client since the last call."""
        try:
            return os.read(self._reader, 65536).decode('ascii').splitlines()
        except BlockingIOError:
            return []

    def close(self) -> None:
        os.close(self._reader)
        self.stdin.close()


@pytest.fixture
def client() -> Iterator[PipedHelper]:
    piped = PipedHelper()
    yield piped
    piped.close()


def daemon(client: PipedHelper) -> Reactor:
    """A real Reactor, started an hour ago, whose API client 'test-service' is `client`."""
    reactor = Reactor(Configuration([''], text=True))
    reactor.daemon_start_time = time.time() - 3600
    reactor.processes = Processes()
    reactor.processes._process['test-service'] = client  # type: ignore[assignment]
    reactor.processes._ack['test-service'] = True
    reactor.processes._ackjson['test-service'] = False
    return reactor


class TestPingCommand:
    """Test ping command"""

    def test_ping_text_format(self, client: PipedHelper) -> None:
        """Test ping command returns 'pong <UUID> active=true' in text format when 'text' keyword used"""
        from exabgp.reactor.api.command.reactor import ping

        reactor = daemon(client)
        service = 'test-service'

        # Execute command in text mode with explicit 'text' keyword
        # New signature: ping(self, reactor, service, peers, command, use_json)
        result = ping(reactor.api, reactor, service, [], 'text', use_json=False)
        written = client.lines()

        assert result is True
        assert len(written) >= 1
        output = written[0]
        assert output.startswith('pong ')
        assert reactor.daemon_uuid in output
        assert 'active=true' in output

    def test_ping_json_format(self, client: PipedHelper) -> None:
        """Test ping command returns JSON with active status"""
        from exabgp.reactor.api.command.reactor import ping

        reactor = daemon(client)
        service = 'test-service'

        # Execute command in JSON mode
        # New signature: ping(self, reactor, service, peers, command, use_json)
        result = ping(reactor.api, reactor, service, [], '', use_json=True)
        written = client.lines()

        assert result is True
        assert len(written) >= 1
        output = written[0]

        # Parse JSON output
        data = json.loads(output)
        assert 'pong' in data
        assert data['pong'] == reactor.daemon_uuid
        assert 'active' in data
        assert data['active'] is True


class TestStatusCommand:
    """Test status command"""

    def test_status_text_format(self, client: PipedHelper) -> None:
        """Test status command returns formatted text"""
        from exabgp.reactor.api.command.reactor import status

        reactor = daemon(client)
        service = 'test-service'

        # Execute command in text mode
        # New signature: status(self, reactor, service, peers, command, use_json)
        result = status(reactor.api, reactor, service, [], '', use_json=False)
        written = client.lines()

        assert result is True
        assert len(written) > 0

        # Check for expected fields in output
        output_text = ''.join(str(line) for line in written if line != 'done')
        assert 'UUID' in output_text or reactor.daemon_uuid in output_text
        assert 'PID' in output_text
        assert 'Uptime' in output_text or 'uptime' in output_text.lower()

    def test_status_json_format(self, client: PipedHelper) -> None:
        """Test status command returns JSON"""
        from exabgp.reactor.api.command.reactor import status

        reactor = daemon(client)
        service = 'test-service'

        # Execute command in JSON mode
        # New signature: status(self, reactor, service, peers, command, use_json)
        result = status(reactor.api, reactor, service, [], '', use_json=True)
        written = client.lines()

        assert result is True
        assert len(written) >= 1
        output = written[0]

        # Parse JSON output
        data = json.loads(output)
        assert 'uuid' in data
        assert data['uuid'] == reactor.daemon_uuid
        assert 'pid' in data
        assert 'uptime' in data
        assert 'start_time' in data
        assert 'version' in data
        assert 'peers' in data

    def test_status_includes_uptime(self, client: PipedHelper) -> None:
        """Test status includes uptime calculation"""
        from exabgp.reactor.api.command.reactor import status

        reactor = daemon(client)
        service = 'test-service'

        # Execute command in JSON mode for easy parsing
        # New signature: status(self, reactor, service, peers, command, use_json)
        result = status(reactor.api, reactor, service, [], '', use_json=True)
        written = client.lines()

        assert result is True
        output = written[0]
        data = json.loads(output)

        # Uptime should be roughly 3600 seconds (1 hour) based on mock
        assert data['uptime'] >= 3600
        assert data['uptime'] < 3700  # Allow some execution time


class TestCommandIntegration:
    """Integration tests for health monitoring commands"""

    def test_ping_and_status_consistent_uuid(self, client: PipedHelper) -> None:
        """Test that ping and status return same UUID"""
        from exabgp.reactor.api.command.reactor import ping, status

        reactor = daemon(client)
        service = 'test-service'

        # Get UUID from ping (JSON mode)
        # New signature: ping(self, reactor, service, peers, command, use_json)
        ping(reactor.api, reactor, service, [], '', use_json=True)
        written = client.lines()
        ping_output = written[0]
        ping_data = json.loads(ping_output)
        ping_uuid = ping_data['pong']

        # Get UUID from status
        status(reactor.api, reactor, service, [], '', use_json=True)
        written = client.lines()
        status_output = written[0]
        status_data = json.loads(status_output)

        # UUIDs should match
        assert ping_uuid == status_data['uuid']

    def test_every_client_is_active(self, client: PipedHelper) -> None:
        """The daemon keeps no list of CLI clients: one at a time is the socket helper's job.

        It used to record each client's uuid and last ping, first to let only one CLI in and
        then, once any number could be, for nothing, since nothing read the list.
        """
        from exabgp.reactor.api.command.reactor import ping

        reactor = daemon(client)
        for command in ('client-1 1000.0 text', 'client-2 2000.0 text', 'client-1 1000.0 text'):
            ping(reactor.api, reactor, 'test-service', [], command, use_json=False)
            written = client.lines()
            assert written == [f'pong {reactor.daemon_uuid} active=true', 'done']

    def test_a_ping_with_an_unreadable_start_time_is_answered(self, client: PipedHelper) -> None:
        from exabgp.reactor.api.command.reactor import ping

        reactor = daemon(client)
        ping(reactor.api, reactor, 'test-service', [], 'client-1 later text', use_json=False)
        written = client.lines()
        assert written == [f'pong {reactor.daemon_uuid} active=true', 'done']

    def test_bye_is_acknowledged(self, client: PipedHelper) -> None:
        """The CLI sends bye when it quits, and waits for the done."""
        from exabgp.reactor.api.command.reactor import bye

        reactor = daemon(client)
        assert bye(reactor.api, reactor, 'test-service', [], 'client-1', use_json=False) is True
        written = client.lines()
        assert written == ['done']
