"""test_reactor_health.py

Unit tests for daemon health monitoring commands:
- ping
- status
"""

from __future__ import annotations

import json
import time
import uuid


class MockReactor:
    """Mock Reactor for testing commands"""

    def __init__(self):
        self.daemon_uuid = str(uuid.uuid4())
        self.daemon_start_time = time.time() - 3600  # Started 1 hour ago
        self._peers = {}
        self.processes = MockProcesses()


class MockProcesses:
    """Mock Processes for testing command output"""

    def __init__(self):
        self.written_data = []

    def write(self, service, data, force=False):
        self.written_data.append(data)

    def answer_done_sync(self, service, force=False):
        self.written_data.append('done')


class TestPingCommand:
    """Test ping command"""

    def test_ping_text_format(self):
        """Test ping command returns 'pong <UUID> active=true' in text format when 'text' keyword used"""
        from exabgp.reactor.api.command.reactor import ping

        reactor = MockReactor()
        service = 'test-service'

        # Execute command in text mode with explicit 'text' keyword
        # New signature: ping(self, reactor, service, peers, command, use_json)
        result = ping(None, reactor, service, [], 'text', use_json=False)

        assert result is True
        assert len(reactor.processes.written_data) >= 1
        output = reactor.processes.written_data[0]
        assert output.startswith('pong ')
        assert reactor.daemon_uuid in output
        assert 'active=true' in output

    def test_ping_json_format(self):
        """Test ping command returns JSON with active status"""
        from exabgp.reactor.api.command.reactor import ping

        reactor = MockReactor()
        service = 'test-service'

        # Execute command in JSON mode
        # New signature: ping(self, reactor, service, peers, command, use_json)
        result = ping(None, reactor, service, [], '', use_json=True)

        assert result is True
        assert len(reactor.processes.written_data) >= 1
        output = reactor.processes.written_data[0]

        # Parse JSON output
        data = json.loads(output)
        assert 'pong' in data
        assert data['pong'] == reactor.daemon_uuid
        assert 'active' in data
        assert data['active'] is True


class TestStatusCommand:
    """Test status command"""

    def test_status_text_format(self):
        """Test status command returns formatted text"""
        from exabgp.reactor.api.command.reactor import status

        reactor = MockReactor()
        service = 'test-service'

        # Execute command in text mode
        # New signature: status(self, reactor, service, peers, command, use_json)
        result = status(None, reactor, service, [], '', use_json=False)

        assert result is True
        assert len(reactor.processes.written_data) > 0

        # Check for expected fields in output
        output_text = ''.join(str(line) for line in reactor.processes.written_data if line != 'done')
        assert 'UUID' in output_text or reactor.daemon_uuid in output_text
        assert 'PID' in output_text
        assert 'Uptime' in output_text or 'uptime' in output_text.lower()

    def test_status_json_format(self):
        """Test status command returns JSON"""
        from exabgp.reactor.api.command.reactor import status

        reactor = MockReactor()
        service = 'test-service'

        # Execute command in JSON mode
        # New signature: status(self, reactor, service, peers, command, use_json)
        result = status(None, reactor, service, [], '', use_json=True)

        assert result is True
        assert len(reactor.processes.written_data) >= 1
        output = reactor.processes.written_data[0]

        # Parse JSON output
        data = json.loads(output)
        assert 'uuid' in data
        assert data['uuid'] == reactor.daemon_uuid
        assert 'pid' in data
        assert 'uptime' in data
        assert 'start_time' in data
        assert 'version' in data
        assert 'peers' in data

    def test_status_includes_uptime(self):
        """Test status includes uptime calculation"""
        from exabgp.reactor.api.command.reactor import status

        reactor = MockReactor()
        service = 'test-service'

        # Execute command in JSON mode for easy parsing
        # New signature: status(self, reactor, service, peers, command, use_json)
        result = status(None, reactor, service, [], '', use_json=True)

        assert result is True
        output = reactor.processes.written_data[0]
        data = json.loads(output)

        # Uptime should be roughly 3600 seconds (1 hour) based on mock
        assert data['uptime'] >= 3600
        assert data['uptime'] < 3700  # Allow some execution time


class TestCommandIntegration:
    """Integration tests for health monitoring commands"""

    def test_ping_and_status_consistent_uuid(self):
        """Test that ping and status return same UUID"""
        from exabgp.reactor.api.command.reactor import ping, status

        reactor = MockReactor()
        service = 'test-service'

        # Get UUID from ping (JSON mode)
        # New signature: ping(self, reactor, service, peers, command, use_json)
        ping(None, reactor, service, [], '', use_json=True)
        ping_output = reactor.processes.written_data[0]
        ping_data = json.loads(ping_output)
        ping_uuid = ping_data['pong']

        # Get UUID from status
        reactor.processes.written_data = []
        status(None, reactor, service, [], '', use_json=True)
        status_output = reactor.processes.written_data[0]
        status_data = json.loads(status_output)

        # UUIDs should match
        assert ping_uuid == status_data['uuid']

    def test_every_client_is_active(self):
        """The daemon keeps no list of CLI clients: one at a time is the socket helper's job.

        It used to record each client's uuid and last ping, first to let only one CLI in and
        then, once any number could be, for nothing, since nothing read the list.
        """
        from exabgp.reactor.api.command.reactor import ping

        reactor = MockReactor()
        for command in ('client-1 1000.0 text', 'client-2 2000.0 text', 'client-1 1000.0 text'):
            reactor.processes.written_data = []
            ping(None, reactor, 'test-service', [], command, use_json=False)
            assert reactor.processes.written_data == [f'pong {reactor.daemon_uuid} active=true', 'done']

    def test_a_ping_with_an_unreadable_start_time_is_answered(self):
        from exabgp.reactor.api.command.reactor import ping

        reactor = MockReactor()
        ping(None, reactor, 'test-service', [], 'client-1 later text', use_json=False)
        assert reactor.processes.written_data == [f'pong {reactor.daemon_uuid} active=true', 'done']

    def test_bye_is_acknowledged(self):
        """The CLI sends bye when it quits, and waits for the done."""
        from exabgp.reactor.api.command.reactor import bye

        reactor = MockReactor()
        assert bye(None, reactor, 'test-service', [], 'client-1', use_json=False) is True
        assert reactor.processes.written_data == ['done']
