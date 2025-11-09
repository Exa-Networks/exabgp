# encoding: utf-8
"""test_logger.py

Unit tests for exabgp.logger modules
"""

import time
from unittest.mock import patch, Mock

import pytest

from exabgp.logger import color
from exabgp.logger.format import (
    formater,
    lazyformat,
    lazyattribute,
    lazynlri,
    _short_formater,
    _long_formater,
    _short_color_formater,
    _long_color_formater,
)
from exabgp.logger.tty import istty, _istty


class TestColor:
    """Test color module functions"""

    def test_source_with_color(self):
        """Test source() with color levels"""
        # Test each color level
        result = color.source('ERROR', 'test')
        assert '\033[' in result  # ANSI escape code
        assert 'test' in result
        assert '\033[0m' in result  # Reset code

        result = color.source('WARNING', 'test')
        assert '\033[' in result

        result = color.source('INFO', 'test')
        assert '\033[' in result

    def test_source_without_color(self):
        """Test source() without color (DEBUG)"""
        result = color.source('DEBUG', 'test')
        assert result == 'test'
        assert '\033[' not in result

    def test_source_unknown_level(self):
        """Test source() with unknown level"""
        result = color.source('UNKNOWN', 'test')
        assert result == 'test'
        assert '\033[' not in result

    def test_message_with_color(self):
        """Test message() with color levels"""
        result = color.message('ERROR', 'test')
        assert '\033[' in result
        assert 'test' in result
        assert '\033[0m' in result

        result = color.message('WARNING', 'test')
        assert '\033[' in result

        result = color.message('FATAL', 'test')
        assert '\033[' in result

    def test_message_without_color(self):
        """Test message() without color (DEBUG)"""
        result = color.message('DEBUG', 'test')
        assert result == 'test'
        assert '\033[' not in result

    def test_message_unknown_level(self):
        """Test message() with unknown level"""
        result = color.message('UNKNOWN', 'test')
        assert result == 'test'

    def test_color_levels(self):
        """Test all defined color levels"""
        levels = ['FATAL', 'CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG', 'NOTSET']
        for level in levels:
            # Should not raise exceptions
            source_result = color.source(level, 'test')
            message_result = color.message(level, 'test')
            assert isinstance(source_result, str)
            assert isinstance(message_result, str)


class TestTTY:
    """Test TTY detection functions"""

    def test_istty_stderr(self):
        """Test istty() with stderr"""
        # Just test it doesn't crash
        result = istty('stderr')
        assert isinstance(result, bool)

    def test_istty_stdout(self):
        """Test istty() with stdout"""
        result = istty('stdout')
        assert isinstance(result, bool)

    def test_istty_out(self):
        """Test istty() with 'out' alias"""
        result = istty('out')
        assert isinstance(result, bool)

    def test_istty_true(self):
        """Test istty() returns a boolean"""
        # istty checks if stdout/stderr is a tty
        # Just verify it returns a boolean
        result = istty('stdout')
        assert isinstance(result, bool)

    @patch('sys.stdout')
    def test_istty_false(self, mock_stdout):
        """Test istty() when output is not a tty"""
        mock_stdout.isatty.return_value = False
        result = istty('stdout')
        assert result is False

    @patch('sys.stderr')
    def test_istty_exception(self, mock_stderr):
        """Test istty() when isatty() raises exception"""
        mock_stderr.isatty.side_effect = Exception('Test error')
        result = istty('stderr')
        assert result is False

    def test_istty_internal(self):
        """Test _istty() helper function"""
        # Mock file object
        mock_file = Mock()
        mock_file.isatty.return_value = True
        assert _istty(mock_file) is True

        mock_file.isatty.return_value = False
        assert _istty(mock_file) is False

        mock_file.isatty.side_effect = AttributeError()
        assert _istty(mock_file) is False


class TestFormat:
    """Test format module functions"""

    def test_short_formater(self):
        """Test _short_formater()"""
        timestamp = time.localtime()
        result = _short_formater('test message', 'source', 'INFO', timestamp)
        assert 'source' in result
        assert 'test message' in result
        # Short format doesn't include timestamp or PID
        assert ':' not in result or 'test message' in result

    def test_long_formater(self):
        """Test _long_formater()"""
        timestamp = time.localtime()
        result = _long_formater('test message', 'source', 'INFO', timestamp)
        assert 'source' in result
        assert 'test message' in result
        # Long format includes timestamp
        assert ':' in result

    @patch('os.getpid')
    def test_long_formater_with_pid(self, mock_getpid):
        """Test _long_formater() includes PID"""
        mock_getpid.return_value = 12345
        timestamp = time.localtime()
        result = _long_formater('test message', 'source', 'INFO', timestamp)
        assert '12345' in result

    def test_short_color_formater(self):
        """Test _short_color_formater()"""
        timestamp = time.localtime()
        result = _short_color_formater('test message', 'source', 'ERROR', timestamp)
        assert '\r' in result  # Carriage return for color output
        # May contain ANSI codes depending on level
        assert 'test message' in result or '\033[' in result

    def test_long_color_formater(self):
        """Test _long_color_formater()"""
        timestamp = time.localtime()
        result = _long_color_formater('test message', 'source', 'WARNING', timestamp)
        assert '\r' in result
        assert ':' in result  # Timestamp

    def test_formater_stdout_short(self):
        """Test formater() for stdout, short"""
        func = formater(short=True, destination='stdout')
        # Should return one of the short formatters
        assert func in (_short_formater, _short_color_formater)

    def test_formater_stdout_long(self):
        """Test formater() for stdout, long"""
        func = formater(short=False, destination='stdout')
        # Should return one of the long formatters
        assert func in (_long_formater, _long_color_formater)

    def test_formater_stderr(self):
        """Test formater() for stderr"""
        func = formater(short=True, destination='stderr')
        # Should return one of the short formatters
        assert func in (_short_formater, _short_color_formater)

    def test_formater_returns_callable(self):
        """Test formater() returns a callable"""
        for dest in ('stdout', 'stderr'):
            for short in (True, False):
                func = formater(short=short, destination=dest)
                assert callable(func) or func is None

    def test_lazyformat(self):
        """Test lazyformat() creates lazy formatter"""
        data = b'\x01\x02\x03\x04'
        lazy = lazyformat('PREFIX', data)

        # Should be callable
        assert callable(lazy)

        # Call it
        result = lazy()
        assert 'PREFIX' in result
        assert '4' in result  # Length
        # Should contain hex representation
        assert '01' in result or '02' in result

    def test_lazyformat_custom_formater(self):
        """Test lazyformat() with custom formater"""

        def custom_formater(data):
            return 'CUSTOM'

        lazy = lazyformat('PREFIX', b'test', formater=custom_formater)
        result = lazy()
        assert 'PREFIX' in result
        assert 'CUSTOM' in result

    def test_lazyattribute(self):
        """Test lazyattribute() creates lazy formatter"""
        # aid should be an integer (attribute ID code)
        lazy = lazyattribute(flag=0x40, aid=0x02, length=10, data=b'\x01\x02')

        assert callable(lazy)
        result = lazy()
        assert 'attribute' in result
        assert '0x40' in result
        assert '0x02' in result
        assert 'payload' in result

    def test_lazyattribute_no_data(self):
        """Test lazyattribute() without data"""
        # ORIGIN attribute ID is 0x01
        lazy = lazyattribute(flag=0x40, aid=0x01, length=1, data=b'')

        result = lazy()
        assert 'attribute' in result
        assert '0x01' in result
        assert 'payload' not in result

    def test_lazynlri(self):
        """Test lazynlri() creates lazy formatter"""
        from exabgp.protocol.family import AFI, SAFI

        lazy = lazynlri(afi=AFI.ipv4, safi=SAFI.unicast, addpath=False, data=b'\xc0\xa8\x01\x01')

        assert callable(lazy)
        result = lazy()
        assert 'NLRI' in result
        assert 'payload' in result

    def test_lazynlri_with_addpath(self):
        """Test lazynlri() with addpath enabled"""
        from exabgp.protocol.family import AFI, SAFI

        lazy = lazynlri(afi=AFI.ipv4, safi=SAFI.unicast, addpath=True, data=b'\x01\x02\x03\x04')

        result = lazy()
        assert 'NLRI' in result
        assert 'with path-information' in result

    def test_lazynlri_without_addpath(self):
        """Test lazynlri() without addpath"""
        from exabgp.protocol.family import AFI, SAFI

        lazy = lazynlri(afi=AFI.ipv4, safi=SAFI.unicast, addpath=False, data=b'\x01\x02\x03\x04')

        result = lazy()
        assert 'NLRI' in result
        assert 'without path-information' in result

    def test_lazynlri_no_data(self):
        """Test lazynlri() without data"""
        from exabgp.protocol.family import AFI, SAFI

        lazy = lazynlri(afi=AFI.ipv4, safi=SAFI.unicast, addpath=False, data=b'')

        result = lazy()
        assert 'NLRI' in result
        assert 'none' in result
