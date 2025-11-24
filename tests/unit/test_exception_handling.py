"""Unit tests for exception handling and exception hierarchies."""

from __future__ import annotations

import pytest

# ProcessError hierarchy
from exabgp.reactor.api.processes import (
    ProcessError,
    ProcessStartError,
    ProcessCommunicationError,
    ProcessWriteError,
    ProcessReadError,
    ProcessRespawnError,
)

# CLIError hierarchy
from exabgp.application.error import (
    CLIError,
    CLIConnectionError,
    CLISocketError,
    CLIPipeError,
    CLITimeoutError,
)

# ParsingError hierarchy
from exabgp.configuration.core.error import (
    Error,
    ParsingError,
    AFISAFIParsingError,
    IPAddressParsingError,
)


class TestProcessErrorHierarchy:
    """Test ProcessError exception hierarchy."""

    def test_process_error_is_exception(self):
        assert issubclass(ProcessError, Exception)

    def test_process_start_error_hierarchy(self):
        assert issubclass(ProcessStartError, ProcessError)
        assert issubclass(ProcessStartError, Exception)

    def test_process_communication_error_hierarchy(self):
        assert issubclass(ProcessCommunicationError, ProcessError)
        assert issubclass(ProcessCommunicationError, Exception)

    def test_process_write_error_hierarchy(self):
        assert issubclass(ProcessWriteError, ProcessCommunicationError)
        assert issubclass(ProcessWriteError, ProcessError)
        assert issubclass(ProcessWriteError, Exception)

    def test_process_read_error_hierarchy(self):
        assert issubclass(ProcessReadError, ProcessCommunicationError)
        assert issubclass(ProcessReadError, ProcessError)
        assert issubclass(ProcessReadError, Exception)

    def test_process_respawn_error_hierarchy(self):
        assert issubclass(ProcessRespawnError, ProcessError)
        assert issubclass(ProcessRespawnError, Exception)

    def test_catch_process_error_catches_subclasses(self):
        """Verify catching ProcessError catches all subclasses."""
        subclasses = [
            ProcessStartError,
            ProcessCommunicationError,
            ProcessWriteError,
            ProcessReadError,
            ProcessRespawnError,
        ]
        for exc_class in subclasses:
            with pytest.raises(ProcessError):
                raise exc_class('test')

    def test_catch_communication_error_catches_read_write(self):
        """Verify catching ProcessCommunicationError catches Read/Write errors."""
        with pytest.raises(ProcessCommunicationError):
            raise ProcessWriteError('broken pipe')
        with pytest.raises(ProcessCommunicationError):
            raise ProcessReadError('read failed')


class TestCLIErrorHierarchy:
    """Test CLIError exception hierarchy."""

    def test_cli_error_is_exception(self):
        assert issubclass(CLIError, Exception)

    def test_cli_connection_error_hierarchy(self):
        assert issubclass(CLIConnectionError, CLIError)
        assert issubclass(CLIConnectionError, Exception)

    def test_cli_socket_error_hierarchy(self):
        assert issubclass(CLISocketError, CLIConnectionError)
        assert issubclass(CLISocketError, CLIError)
        assert issubclass(CLISocketError, Exception)

    def test_cli_pipe_error_hierarchy(self):
        assert issubclass(CLIPipeError, CLIConnectionError)
        assert issubclass(CLIPipeError, CLIError)
        assert issubclass(CLIPipeError, Exception)

    def test_cli_timeout_error_hierarchy(self):
        assert issubclass(CLITimeoutError, CLIError)
        assert issubclass(CLITimeoutError, Exception)

    def test_catch_cli_error_catches_subclasses(self):
        """Verify catching CLIError catches all subclasses."""
        subclasses = [
            CLIConnectionError,
            CLISocketError,
            CLIPipeError,
            CLITimeoutError,
        ]
        for exc_class in subclasses:
            with pytest.raises(CLIError):
                raise exc_class('test')

    def test_catch_connection_error_catches_socket_pipe(self):
        """Verify catching CLIConnectionError catches Socket/Pipe errors."""
        with pytest.raises(CLIConnectionError):
            raise CLISocketError('socket failed')
        with pytest.raises(CLIConnectionError):
            raise CLIPipeError('pipe failed')


class TestParsingErrorHierarchy:
    """Test ParsingError exception hierarchy."""

    def test_parsing_error_inherits_from_error(self):
        assert issubclass(ParsingError, Error)
        assert issubclass(ParsingError, Exception)

    def test_afi_safi_parsing_error_hierarchy(self):
        assert issubclass(AFISAFIParsingError, ParsingError)
        assert issubclass(AFISAFIParsingError, Error)
        assert issubclass(AFISAFIParsingError, Exception)

    def test_ip_address_parsing_error_hierarchy(self):
        assert issubclass(IPAddressParsingError, ParsingError)
        assert issubclass(IPAddressParsingError, Error)
        assert issubclass(IPAddressParsingError, Exception)

    def test_catch_parsing_error_catches_subclasses(self):
        """Verify catching ParsingError catches all subclasses."""
        subclasses = [
            AFISAFIParsingError,
            IPAddressParsingError,
        ]
        for exc_class in subclasses:
            with pytest.raises(ParsingError):
                raise exc_class()

    def test_catch_error_catches_parsing_errors(self):
        """Verify catching Error catches all ParsingError subclasses."""
        with pytest.raises(Error):
            raise AFISAFIParsingError()
        with pytest.raises(Error):
            raise IPAddressParsingError()


class TestExceptionMessages:
    """Test exception messages and attributes."""

    def test_process_error_with_message(self):
        exc = ProcessStartError('failed to spawn process')
        assert str(exc) == 'failed to spawn process'

    def test_cli_error_with_message(self):
        exc = CLISocketError('connection refused')
        assert str(exc) == 'connection refused'

    def test_parsing_error_message_attribute(self):
        exc = AFISAFIParsingError()
        exc.message = 'invalid AFI value'
        assert exc.message == 'invalid AFI value'
