"""Unit tests for group command API for UPDATE batching."""

from __future__ import annotations

import pytest
from unittest.mock import Mock

from exabgp.reactor.api.command.group import (
    _GROUP_BUFFERS,
    _is_grouping,
    _start_group,
    _end_group,
    _add_to_group,
    group_start,
    group_end,
    group_inline,
    is_grouping,
)


class TestGroupBufferManagement:
    """Test internal group buffer functions."""

    def setup_method(self):
        """Clear group buffers before each test."""
        _GROUP_BUFFERS.clear()

    def teardown_method(self):
        """Clear group buffers after each test."""
        _GROUP_BUFFERS.clear()

    def test_is_grouping_false_when_empty(self):
        """Test _is_grouping returns False when service not in buffer."""
        assert _is_grouping('test-service') is False

    def test_is_grouping_true_after_start(self):
        """Test _is_grouping returns True after starting group."""
        _start_group('test-service')
        assert _is_grouping('test-service') is True

    def test_is_grouping_false_after_end(self):
        """Test _is_grouping returns False after ending group."""
        _start_group('test-service')
        _end_group('test-service')
        assert _is_grouping('test-service') is False

    def test_start_group_creates_empty_buffer(self):
        """Test _start_group creates empty list for service."""
        _start_group('test-service')
        assert 'test-service' in _GROUP_BUFFERS
        assert _GROUP_BUFFERS['test-service'] == []

    def test_end_group_returns_buffered_commands(self):
        """Test _end_group returns all buffered commands."""
        _start_group('test-service')
        _add_to_group('test-service', ['peer1'], 'announce route 10.0.0.0/24')
        _add_to_group('test-service', ['peer2'], 'announce route 10.0.0.1/24')

        buffered = _end_group('test-service')

        assert len(buffered) == 2
        assert buffered[0] == (['peer1'], 'announce route 10.0.0.0/24')
        assert buffered[1] == (['peer2'], 'announce route 10.0.0.1/24')

    def test_end_group_clears_buffer(self):
        """Test _end_group removes service from buffer."""
        _start_group('test-service')
        _add_to_group('test-service', ['peer1'], 'announce route 10.0.0.0/24')
        _end_group('test-service')

        assert 'test-service' not in _GROUP_BUFFERS

    def test_end_group_nonexistent_returns_empty(self):
        """Test _end_group returns empty list for nonexistent service."""
        buffered = _end_group('nonexistent-service')
        assert buffered == []

    def test_add_to_group_appends_command(self):
        """Test _add_to_group adds command to buffer."""
        _start_group('test-service')
        _add_to_group('test-service', ['peer1'], 'command1')
        _add_to_group('test-service', ['peer2'], 'command2')

        assert len(_GROUP_BUFFERS['test-service']) == 2

    def test_add_to_group_ignores_when_not_grouping(self):
        """Test _add_to_group does nothing when not in group mode."""
        _add_to_group('test-service', ['peer1'], 'command1')

        assert 'test-service' not in _GROUP_BUFFERS

    def test_public_is_grouping_matches_internal(self):
        """Test public is_grouping() matches _is_grouping()."""
        assert is_grouping('test-service') is False

        _start_group('test-service')
        assert is_grouping('test-service') is True

        _end_group('test-service')
        assert is_grouping('test-service') is False

    def test_multiple_services_independent(self):
        """Test multiple services have independent buffers."""
        _start_group('service-a')
        _start_group('service-b')

        _add_to_group('service-a', ['peer1'], 'cmd-a')
        _add_to_group('service-b', ['peer2'], 'cmd-b')

        assert len(_GROUP_BUFFERS['service-a']) == 1
        assert len(_GROUP_BUFFERS['service-b']) == 1
        assert _GROUP_BUFFERS['service-a'][0][1] == 'cmd-a'
        assert _GROUP_BUFFERS['service-b'][0][1] == 'cmd-b'


class TestGroupStartHandler:
    """Test group_start command handler."""

    def setup_method(self):
        """Clear group buffers before each test."""
        _GROUP_BUFFERS.clear()

    def teardown_method(self):
        """Clear group buffers after each test."""
        _GROUP_BUFFERS.clear()

    @pytest.fixture
    def mock_reactor(self):
        """Create mock reactor for testing."""
        reactor = Mock()
        reactor.processes = Mock()
        reactor.processes.write = Mock()
        reactor.processes.answer_done = Mock()
        reactor.processes.answer_error = Mock()
        return reactor

    def test_group_start_success(self, mock_reactor):
        """Test successful group start."""
        result = group_start(None, mock_reactor, 'test-service', [], '', False)

        assert result is True
        assert _is_grouping('test-service') is True
        mock_reactor.processes.write.assert_called_once()
        mock_reactor.processes.answer_done.assert_called_once_with('test-service')

    def test_group_start_text_response(self, mock_reactor):
        """Test group start text response."""
        group_start(None, mock_reactor, 'test-service', [], '', False)

        call_args = mock_reactor.processes.write.call_args[0]
        assert call_args[0] == 'test-service'
        assert 'group started' in call_args[1]

    def test_group_start_json_response(self, mock_reactor):
        """Test group start JSON response."""
        group_start(None, mock_reactor, 'test-service', [], '', True)

        call_args = mock_reactor.processes.write.call_args[0]
        assert call_args[0] == 'test-service'
        assert '"status"' in call_args[1]
        assert 'group started' in call_args[1]

    def test_group_start_nested_error(self, mock_reactor):
        """Test group start fails when already in group."""
        _start_group('test-service')

        result = group_start(None, mock_reactor, 'test-service', [], '', False)

        assert result is False
        mock_reactor.processes.answer_error.assert_called_once_with('test-service')

    def test_group_start_nested_error_message(self, mock_reactor):
        """Test nested group error message contains explanation."""
        _start_group('test-service')

        group_start(None, mock_reactor, 'test-service', [], '', False)

        call_args = mock_reactor.processes.write.call_args[0]
        assert 'already in group' in call_args[1].lower() or 'nested' in call_args[1].lower()


class TestGroupEndHandler:
    """Test group_end command handler."""

    def setup_method(self):
        """Clear group buffers before each test."""
        _GROUP_BUFFERS.clear()

    def teardown_method(self):
        """Clear group buffers after each test."""
        _GROUP_BUFFERS.clear()

    @pytest.fixture
    def mock_reactor(self):
        """Create mock reactor for testing."""
        reactor = Mock()
        reactor.processes = Mock()
        reactor.processes.write = Mock()
        reactor.processes.answer_done = Mock()
        reactor.processes.answer_error = Mock()
        reactor.asynchronous = Mock()
        reactor.asynchronous.schedule = Mock()
        return reactor

    def test_group_end_not_in_group_error(self, mock_reactor):
        """Test group end fails when not in group."""
        result = group_end(None, mock_reactor, 'test-service', [], '', False)

        assert result is False
        mock_reactor.processes.answer_error.assert_called_once_with('test-service')

    def test_group_end_not_in_group_error_message(self, mock_reactor):
        """Test not in group error message."""
        group_end(None, mock_reactor, 'test-service', [], '', False)

        call_args = mock_reactor.processes.write.call_args[0]
        assert 'not in group' in call_args[1].lower()

    def test_group_end_empty_group_success(self, mock_reactor):
        """Test group end succeeds with empty group."""
        _start_group('test-service')

        result = group_end(None, mock_reactor, 'test-service', [], '', False)

        assert result is True
        mock_reactor.processes.answer_done.assert_called_once_with('test-service')

    def test_group_end_empty_group_clears_buffer(self, mock_reactor):
        """Test group end clears buffer."""
        _start_group('test-service')
        group_end(None, mock_reactor, 'test-service', [], '', False)

        assert not _is_grouping('test-service')

    def test_group_end_with_commands_schedules_async(self, mock_reactor):
        """Test group end with buffered commands schedules async processing."""
        _start_group('test-service')
        _add_to_group('test-service', ['peer1'], 'announce route 10.0.0.0/24 next-hop 1.2.3.4')

        result = group_end(None, mock_reactor, 'test-service', [], '', False)

        assert result is True
        mock_reactor.asynchronous.schedule.assert_called_once()
        call_args = mock_reactor.asynchronous.schedule.call_args[0]
        assert call_args[0] == 'test-service'
        assert call_args[1] == 'group end'


class TestGroupInlineHandler:
    """Test group_inline command handler (single-line group)."""

    def setup_method(self):
        """Clear group buffers before each test."""
        _GROUP_BUFFERS.clear()

    def teardown_method(self):
        """Clear group buffers after each test."""
        _GROUP_BUFFERS.clear()

    @pytest.fixture
    def mock_reactor(self):
        """Create mock reactor for testing."""
        reactor = Mock()
        reactor.processes = Mock()
        reactor.processes.write = Mock()
        reactor.processes.answer_done = Mock()
        reactor.processes.answer_error = Mock()
        reactor.asynchronous = Mock()
        reactor.asynchronous.schedule = Mock()
        return reactor

    def test_group_inline_empty_error(self, mock_reactor):
        """Test group inline fails with empty command."""
        result = group_inline(None, mock_reactor, 'test-service', [], '', False)

        assert result is False
        mock_reactor.processes.answer_error.assert_called_once_with('test-service')

    def test_group_inline_empty_error_message(self, mock_reactor):
        """Test empty group error message."""
        group_inline(None, mock_reactor, 'test-service', [], '', False)

        call_args = mock_reactor.processes.write.call_args[0]
        assert 'empty group' in call_args[1].lower()

    def test_group_inline_single_command(self, mock_reactor):
        """Test group inline with single command."""
        result = group_inline(
            None, mock_reactor, 'test-service', ['peer1'], 'announce route 10.0.0.0/24 next-hop 1.2.3.4', False
        )

        assert result is True
        mock_reactor.asynchronous.schedule.assert_called_once()

    def test_group_inline_multiple_commands(self, mock_reactor):
        """Test group inline with multiple semicolon-separated commands."""
        result = group_inline(
            None,
            mock_reactor,
            'test-service',
            ['peer1'],
            'announce route 10.0.0.0/24 next-hop 1.2.3.4 ; announce route 10.0.0.1/24 next-hop 1.2.3.4',
            False,
        )

        assert result is True
        mock_reactor.asynchronous.schedule.assert_called_once()

    def test_group_inline_strips_whitespace(self, mock_reactor):
        """Test group inline strips whitespace around commands."""
        result = group_inline(
            None,
            mock_reactor,
            'test-service',
            ['peer1'],
            '  announce route 10.0.0.0/24 next-hop 1.2.3.4  ;  announce route 10.0.0.1/24 next-hop 1.2.3.4  ',
            False,
        )

        assert result is True

    def test_group_inline_ignores_empty_parts(self, mock_reactor):
        """Test group inline ignores empty command parts."""
        result = group_inline(
            None,
            mock_reactor,
            'test-service',
            ['peer1'],
            'announce route 10.0.0.0/24 next-hop 1.2.3.4 ; ; ; announce route 10.0.0.1/24 next-hop 1.2.3.4',
            False,
        )

        assert result is True

    def test_group_inline_preserves_peers(self, mock_reactor):
        """Test group inline passes peers to callback."""
        peers = ['peer1', 'peer2']
        group_inline(None, mock_reactor, 'test-service', peers, 'announce route 10.0.0.0/24 next-hop 1.2.3.4', False)

        # The peers are captured in the closure passed to schedule
        mock_reactor.asynchronous.schedule.assert_called_once()


class TestGroupBufferIsolation:
    """Test that group buffers are properly isolated between services."""

    def setup_method(self):
        """Clear group buffers before each test."""
        _GROUP_BUFFERS.clear()

    def teardown_method(self):
        """Clear group buffers after each test."""
        _GROUP_BUFFERS.clear()

    @pytest.fixture
    def mock_reactor(self):
        """Create mock reactor for testing."""
        reactor = Mock()
        reactor.processes = Mock()
        reactor.processes.write = Mock()
        reactor.processes.answer_done = Mock()
        reactor.processes.answer_error = Mock()
        reactor.asynchronous = Mock()
        reactor.asynchronous.schedule = Mock()
        return reactor

    def test_different_services_independent(self, mock_reactor):
        """Test that different services have independent group state."""
        # Start group for service A
        group_start(None, mock_reactor, 'service-a', [], '', False)
        assert is_grouping('service-a') is True
        assert is_grouping('service-b') is False

        # Start group for service B
        group_start(None, mock_reactor, 'service-b', [], '', False)
        assert is_grouping('service-a') is True
        assert is_grouping('service-b') is True

        # End group for service A
        group_end(None, mock_reactor, 'service-a', [], '', False)
        assert is_grouping('service-a') is False
        assert is_grouping('service-b') is True

    def test_service_buffer_contents_isolated(self, mock_reactor):
        """Test that buffer contents are isolated between services."""
        _start_group('service-a')
        _start_group('service-b')

        _add_to_group('service-a', ['peer-a'], 'cmd-a-1')
        _add_to_group('service-a', ['peer-a'], 'cmd-a-2')
        _add_to_group('service-b', ['peer-b'], 'cmd-b-1')

        buffer_a = _end_group('service-a')
        buffer_b = _end_group('service-b')

        assert len(buffer_a) == 2
        assert len(buffer_b) == 1
        assert buffer_a[0][1] == 'cmd-a-1'
        assert buffer_b[0][1] == 'cmd-b-1'
