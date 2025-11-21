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

        # Active CLI client tracking
        self.active_client_uuid = None
        self.active_client_last_ping = 0.0


class MockProcesses:
    """Mock Processes for testing command output"""

    def __init__(self):
        self.written_data = []

    def write(self, service, data, force=False):
        self.written_data.append(data)

    def answer_done(self, service, force=False):
        self.written_data.append('done')


class TestPingCommand:
    """Test ping command"""

    def test_ping_text_format(self):
        """Test ping command returns 'pong <UUID> active=true' in text format when 'text' keyword used"""
        from exabgp.reactor.api.command.reactor import ping

        reactor = MockReactor()
        service = 'test-service'

        # Execute command in text mode with explicit 'text' keyword
        result = ping(None, reactor, service, 'ping text', use_json=False)

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
        result = ping(None, reactor, service, 'ping', use_json=True)

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
        result = status(None, reactor, service, 'status', use_json=False)

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
        result = status(None, reactor, service, 'status', use_json=True)

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
        result = status(None, reactor, service, 'status', use_json=True)

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
        ping(None, reactor, service, 'ping', use_json=True)
        ping_output = reactor.processes.written_data[0]
        ping_data = json.loads(ping_output)
        ping_uuid = ping_data['pong']

        # Get UUID from status
        reactor.processes.written_data = []
        status(None, reactor, service, 'status', use_json=True)
        status_output = reactor.processes.written_data[0]
        status_data = json.loads(status_output)

        # UUIDs should match
        assert ping_uuid == status_data['uuid']

    def test_ping_client_replacement(self):
        """Test that first client stays active when second client connects"""
        from exabgp.reactor.api.command.reactor import ping

        reactor = MockReactor()
        service = 'test-service'

        # Client 1 connects first (using text mode for easier assertion)
        ping(None, reactor, service, 'ping client-1 1000.0 text', use_json=False)
        client1_output = reactor.processes.written_data[0]
        assert 'active=true' in client1_output
        assert reactor.active_client_uuid == 'client-1'

        # Client 2 tries to connect - should get active=false (first client keeps connection)
        reactor.processes.written_data = []
        ping(None, reactor, service, 'ping client-2 2000.0 text', use_json=False)
        client2_output = reactor.processes.written_data[0]
        assert 'active=false' in client2_output

        # Client 1 still active
        reactor.processes.written_data = []
        ping(None, reactor, service, 'ping client-1 1000.0 text', use_json=False)
        client1_still_active = reactor.processes.written_data[0]
        assert 'active=true' in client1_still_active

        # Client 2 still gets rejected
        reactor.processes.written_data = []
        ping(None, reactor, service, 'ping client-2 2000.0 text', use_json=False)
        client2_still_rejected = reactor.processes.written_data[0]
        assert 'active=false' in client2_still_rejected

    def test_ping_client_timeout_replacement(self):
        """Test that new client can become active if current client times out"""
        from exabgp.reactor.api.command.reactor import ping

        reactor = MockReactor()
        service = 'test-service'

        # Client 1 connects first (using text mode for easier assertion)
        ping(None, reactor, service, 'ping client-1 1000.0 text', use_json=False)
        assert 'active=true' in reactor.processes.written_data[0]
        assert reactor.active_client_uuid == 'client-1'

        # Simulate 20 seconds passing (client-1 timed out - no ping for >15s)
        reactor.active_client_last_ping = time.time() - 20

        # Client 2 tries to connect - should succeed since active client timed out
        reactor.processes.written_data = []
        ping(None, reactor, service, 'ping client-2 2000.0 text', use_json=False)
        output = reactor.processes.written_data[0]
        assert 'active=true' in output
        assert reactor.active_client_uuid == 'client-2'
