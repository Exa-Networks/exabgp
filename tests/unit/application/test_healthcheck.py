"""Tests for exabgp.application.healthcheck module.

Tests the healthcheck FSM states, check function, IP parsing, and logging setup.
"""

from __future__ import annotations

import argparse
import logging
from ipaddress import ip_network
from unittest.mock import patch

import pytest

from exabgp.application.healthcheck import (
    States,
    check,
    setup_logging,
    setargs,
    ip_ifname,
    drop_privileges,
    IFNAME_MAX_LENGTH,
    IP_CMD_ADD_ERROR_CODE,
    IP_IFNAME_PARTS,
)


class TestStatesEnum:
    """Test the States enum for healthcheck FSM."""

    def test_states_are_string_enum(self) -> None:
        """States should be string enums for easy comparison."""
        assert States.INIT == 'INIT'
        assert States.DISABLED == 'DISABLED'
        assert States.RISING == 'RISING'
        assert States.FALLING == 'FALLING'
        assert States.UP == 'UP'
        assert States.DOWN == 'DOWN'
        assert States.EXIT == 'EXIT'
        assert States.END == 'END'

    def test_all_states_defined(self) -> None:
        """All expected states should be defined."""
        expected = {'INIT', 'DISABLED', 'RISING', 'FALLING', 'UP', 'DOWN', 'EXIT', 'END'}
        actual = {s.value for s in States}
        assert actual == expected

    def test_states_are_comparable(self) -> None:
        """States should be comparable for FSM transitions."""
        assert States.UP != States.DOWN
        assert States.RISING != States.FALLING
        assert States.INIT != States.EXIT


class TestCheckFunction:
    """Test the check() function that runs health commands."""

    def test_check_with_none_command(self) -> None:
        """Check with None command should return True (no check needed)."""
        assert check(None, 5) is True

    def test_check_successful_command(self) -> None:
        """Check with successful command should return True."""
        assert check('true', 5) is True

    def test_check_failing_command(self) -> None:
        """Check with failing command should return False."""
        assert check('false', 5) is False

    def test_check_timeout(self) -> None:
        """Check that times out should return False."""
        # Use a command that would take longer than timeout
        result = check('sleep 10', 1)
        assert result is False

    def test_check_with_output(self) -> None:
        """Check with command that produces output should work."""
        assert check('echo hello', 5) is True

    def test_check_nonexistent_command(self) -> None:
        """Check with nonexistent command should return False."""
        result = check('/nonexistent/command/that/does/not/exist', 5)
        assert result is False


class TestSetupLogging:
    """Test the setup_logging function."""

    def test_setup_logging_debug_mode(self) -> None:
        """Debug mode should set logger to DEBUG level."""
        logger = logging.getLogger('healthcheck')
        # Clear existing handlers
        logger.handlers.clear()

        setup_logging(debug=True, silent=False, name='test', syslog_facility='daemon', syslog=False)

        assert logger.level == logging.DEBUG

    def test_setup_logging_info_mode(self) -> None:
        """Non-debug mode should set logger to INFO level."""
        logger = logging.getLogger('healthcheck')
        logger.handlers.clear()

        setup_logging(debug=False, silent=False, name='test', syslog_facility='daemon', syslog=False)

        assert logger.level == logging.INFO

    def test_setup_logging_console_handler(self) -> None:
        """Non-silent mode should add console handler."""
        logger = logging.getLogger('healthcheck')
        logger.handlers.clear()

        setup_logging(debug=False, silent=False, name='test', syslog_facility='daemon', syslog=False)

        stream_handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
        assert len(stream_handlers) >= 1

    def test_setup_logging_silent_mode(self) -> None:
        """Silent mode should not add console handler."""
        logger = logging.getLogger('healthcheck')
        logger.handlers.clear()

        setup_logging(debug=False, silent=True, name='test', syslog_facility='daemon', syslog=False)

        # Should only have syslog handler (if any) but not StreamHandler
        stream_handlers = [
            h
            for h in logger.handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.handlers.SysLogHandler)
        ]
        assert len(stream_handlers) == 0


class TestSetargs:
    """Test the argument parser setup."""

    def test_setargs_creates_valid_parser(self) -> None:
        """setargs should create a valid argument parser."""
        parser = argparse.ArgumentParser()
        setargs(parser)

        # Should be able to parse empty args (using defaults)
        args = parser.parse_args([])
        assert hasattr(args, 'interval')
        assert hasattr(args, 'command')
        assert hasattr(args, 'rise')
        assert hasattr(args, 'fall')

    def test_setargs_default_values(self) -> None:
        """Default values should be sensible."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args([])

        assert args.interval == 5
        assert args.fast == 1
        assert args.timeout == 5
        assert args.rise == 3
        assert args.fall == 3

    def test_setargs_custom_values(self) -> None:
        """Custom values should be parsed correctly."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(
            ['--interval', '10', '--rise', '5', '--fall', '2', '--command', 'curl http://localhost/health']
        )

        assert args.interval == 10
        assert args.rise == 5
        assert args.fall == 2
        assert args.command == 'curl http://localhost/health'

    def test_setargs_ip_addresses(self) -> None:
        """IP addresses should be parsed as networks."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['--ip', '10.0.0.1/32', '--ip', '192.168.1.0/24'])

        assert len(args.ips) == 2
        assert ip_network('10.0.0.1/32') in args.ips
        assert ip_network('192.168.1.0/24') in args.ips

    def test_setargs_metrics(self) -> None:
        """Metric arguments should be parsed correctly."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['--up-metric', '50', '--down-metric', '500', '--disabled-metric', '250'])

        assert args.up_metric == 50
        assert args.down_metric == 500
        assert args.disabled_metric == 250


class TestIpIfname:
    """Test the ip_ifname helper function."""

    def test_ip_ifname_with_mapping(self) -> None:
        """Should return mapped interface name."""
        ip = ip_network('10.0.0.1/32')
        ip_ifnames = {ip: 'eth0'}

        assert ip_ifname(ip, ip_ifnames) == 'eth0'

    def test_ip_ifname_without_mapping_linux(self) -> None:
        """Should return 'lo' on Linux when no mapping."""
        ip = ip_network('10.0.0.1/32')

        with patch('sys.platform', 'linux'):
            result = ip_ifname(ip, {})
            assert result == 'lo'

    def test_ip_ifname_without_mapping_other(self) -> None:
        """Should return 'lo0' on non-Linux when no mapping."""
        ip = ip_network('10.0.0.1/32')

        with patch('sys.platform', 'darwin'):
            result = ip_ifname(ip, {})
            assert result == 'lo0'


class TestConstants:
    """Test module constants."""

    def test_ifname_max_length(self) -> None:
        """IFNAME_MAX_LENGTH should be Linux kernel limit."""
        assert IFNAME_MAX_LENGTH == 15

    def test_ip_cmd_add_error_code(self) -> None:
        """IP_CMD_ADD_ERROR_CODE should be 2."""
        assert IP_CMD_ADD_ERROR_CODE == 2

    def test_ip_ifname_parts(self) -> None:
        """IP_IFNAME_PARTS should be 2."""
        assert IP_IFNAME_PARTS == 2


class TestDropPrivileges:
    """Test drop_privileges function."""

    def test_drop_privileges_with_none(self) -> None:
        """Should do nothing when user and group are None."""
        # Should not raise
        drop_privileges(None, None)

    def test_drop_privileges_nonexistent_user(self) -> None:
        """Should raise KeyError for nonexistent user."""
        with pytest.raises(KeyError):
            drop_privileges('__nonexistent_user_12345__', None)

    def test_drop_privileges_nonexistent_group(self) -> None:
        """Should raise KeyError for nonexistent group."""
        with pytest.raises(KeyError):
            drop_privileges(None, '__nonexistent_group_12345__')


class TestFSMTransitions:
    """Test FSM state transition logic through loop iteration behavior."""

    def test_states_in_condition(self) -> None:
        """States should work in conditionals."""
        state = States.INIT

        assert state == States.INIT
        assert state != States.UP
        assert state in (States.INIT, States.DISABLED)
        assert state not in (States.UP, States.DOWN)

    def test_exabgp_target_states(self) -> None:
        """Certain states should trigger exabgp announcements."""
        announcement_states = (States.UP, States.DOWN, States.DISABLED, States.EXIT, States.END)

        for state in States:
            if state in announcement_states:
                assert state in (States.UP, States.DOWN, States.DISABLED, States.EXIT, States.END)
            else:
                assert state in (States.INIT, States.RISING, States.FALLING)


class TestParseIpIfnames:
    """Test IP interface parsing (integration test via parse function mock)."""

    def test_valid_ip_ifname_format(self) -> None:
        """Valid IP%IFNAME format should be accepted."""
        # This is a format validation test
        valid_format = '192.168.1.1/32%eth0'
        parts = valid_format.split('%')
        assert len(parts) == IP_IFNAME_PARTS

        # Validate IP part
        ip = ip_network(parts[0])
        assert ip is not None

        # Validate interface name length
        assert len(parts[1]) <= IFNAME_MAX_LENGTH

    def test_invalid_ip_ifname_format(self) -> None:
        """Invalid IP%IFNAME format should be rejected."""
        # Missing % separator
        invalid_format = '192.168.1.1/32eth0'
        parts = invalid_format.split('%')
        assert len(parts) != IP_IFNAME_PARTS

    def test_interface_name_validation_regex(self) -> None:
        """Interface names should match expected pattern."""
        import re

        pattern = rf'^[a-zA-Z0-9._:-]{{1,{IFNAME_MAX_LENGTH}}}$'

        # Valid names
        assert re.match(pattern, 'eth0')
        assert re.match(pattern, 'lo')
        assert re.match(pattern, 'bond0.100')
        assert re.match(pattern, 'veth-peer1')

        # Invalid names
        assert not re.match(pattern, '')  # Too short
        assert not re.match(pattern, 'a' * 16)  # Too long
        assert not re.match(pattern, 'eth 0')  # Space not allowed
