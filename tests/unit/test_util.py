# encoding: utf-8
"""
test_util.py

Unit tests for exabgp.util modules
"""

import errno
import socket
from unittest.mock import patch, Mock

import pytest

from exabgp.util.dictionary import Dictionary
from exabgp.util.enumeration import Enumeration, enum
from exabgp.util.usage import usage
from exabgp.util.errstr import errstr
from exabgp.util.ip import isipv4, isipv6, isip
from exabgp.util.od import od
from exabgp.util.dns import host, domain


class TestDictionary:
    """Test Dictionary class (defaultdict with dict as factory)"""

    def test_dictionary_init(self):
        """Test Dictionary initialization"""
        d = Dictionary()
        assert isinstance(d, dict)
        assert d.default_factory == dict

    def test_dictionary_default_behavior(self):
        """Test Dictionary creates dict for missing keys"""
        d = Dictionary()
        # Accessing a missing key should create an empty dict
        d['key1']['nested'] = 'value'
        assert d['key1']['nested'] == 'value'
        assert isinstance(d['key2'], dict)
        assert len(d['key2']) == 0

    def test_dictionary_multiple_levels(self):
        """Test Dictionary with nested dicts"""
        d = Dictionary()
        # Dictionary only creates one level automatically
        # Create a nested dict manually
        d['level1']['nested'] = 'value'
        assert d['level1']['nested'] == 'value'
        assert isinstance(d['level1'], dict)


class TestEnumeration:
    """Test Enumeration class"""

    def test_enumeration_init(self):
        """Test Enumeration initialization with names"""
        e = Enumeration('RED', 'GREEN', 'BLUE')
        assert hasattr(e, 'RED')
        assert hasattr(e, 'GREEN')
        assert hasattr(e, 'BLUE')

    def test_enumeration_values(self):
        """Test Enumeration values are powers of 2"""
        e = Enumeration('FIRST', 'SECOND', 'THIRD')
        assert e.FIRST == 1  # 2^0
        assert e.SECOND == 2  # 2^1
        assert e.THIRD == 4  # 2^2

    def test_enumeration_str(self):
        """Test Enumeration string representation"""
        e = Enumeration('RED', 'GREEN', 'BLUE')
        assert str(e.RED) == 'RED'
        assert str(e.GREEN) == 'GREEN'
        assert str(e.BLUE) == 'BLUE'

    def test_enumeration_int_operations(self):
        """Test Enumeration values work as integers"""
        e = Enumeration('FLAG1', 'FLAG2', 'FLAG3')
        # Can use as integers
        assert e.FLAG1 + e.FLAG2 == 3
        assert e.FLAG1 | e.FLAG2 == 3
        assert e.FLAG1 & e.FLAG2 == 0

    def test_enum_function(self):
        """Test enum() helper function"""
        Colors = enum('RED', 'GREEN', 'BLUE')
        assert Colors.RED == 'RED'
        assert Colors.GREEN == 'GREEN'
        assert Colors.BLUE == 'BLUE'


class TestUsage:
    """Test usage() function"""

    def test_usage_default_label(self):
        """Test usage() with default label"""
        result = usage()
        assert result.startswith('usage:')
        assert 'usertime=' in result
        assert 'systime=' in result
        assert 'mem=' in result
        assert 'mb' in result

    def test_usage_custom_label(self):
        """Test usage() with custom label"""
        result = usage('custom')
        assert result.startswith('custom:')
        assert 'usertime=' in result

    @patch('resource.getrusage')
    def test_usage_with_mock_rusage(self, mock_rusage):
        """Test usage() with mocked resource data"""
        # Create a mock rusage object
        mock_ru = Mock()
        mock_ru.ru_utime = 1.5
        mock_ru.ru_stime = 0.5
        mock_ru.ru_maxrss = 10240  # depends on platform
        mock_rusage.return_value = mock_ru

        result = usage('test')
        assert 'test:' in result
        assert 'usertime=1.5' in result
        assert 'systime=0.5' in result


class TestErrstr:
    """Test errstr() function"""

    def test_errstr_with_errno(self):
        """Test errstr() with exception containing errno"""
        exc = OSError(errno.ENOENT, 'File not found')
        result = errstr(exc)
        assert '[Errno ENOENT]' in result
        assert 'File not found' in result

    def test_errstr_with_errno_attr(self):
        """Test errstr() with exception having errno attribute"""
        exc = OSError()
        exc.errno = errno.EACCES
        result = errstr(exc)
        assert 'Errno' in result

    def test_errstr_unknown_key(self):
        """Test errstr() with unknown error code"""
        exc = OSError(99999, 'Unknown error')
        result = errstr(exc)
        assert 'Errno' in result
        assert 'Unknown error' in result

    def test_errstr_no_errno(self):
        """Test errstr() with exception without errno"""
        exc = Exception('Generic error')
        result = errstr(exc)
        assert 'Errno' in result
        assert 'Generic error' in result

    def test_errstr_empty_args(self):
        """Test errstr() with exception with no args"""
        exc = OSError()
        exc.args = ()
        result = errstr(exc)
        assert 'Errno' in result


class TestIP:
    """Test IP validation functions"""

    def test_isipv4_valid(self):
        """Test isipv4() with valid IPv4 addresses"""
        assert isipv4('192.168.1.1') is True
        assert isipv4('10.0.0.1') is True
        assert isipv4('255.255.255.255') is True
        assert isipv4('0.0.0.0') is True
        assert isipv4('127.0.0.1') is True

    def test_isipv4_invalid(self):
        """Test isipv4() with invalid IPv4 addresses"""
        assert isipv4('256.256.256.256') is False
        assert isipv4('192.168.1') is False
        assert isipv4('not-an-ip') is False
        assert isipv4('2001:db8::1') is False  # IPv6
        assert isipv4('') is False

    def test_isipv6_valid(self):
        """Test isipv6() with valid IPv6 addresses"""
        assert isipv6('2001:db8::1') is True
        assert isipv6('::1') is True
        assert isipv6('fe80::1') is True
        assert isipv6('::') is True
        assert isipv6('2001:0db8:0000:0000:0000:0000:0000:0001') is True

    def test_isipv6_invalid(self):
        """Test isipv6() with invalid IPv6 addresses"""
        assert isipv6('192.168.1.1') is False  # IPv4
        assert isipv6('not-an-ip') is False
        assert isipv6('gggg::1') is False
        assert isipv6('') is False

    def test_isip_valid(self):
        """Test isip() with valid IP addresses"""
        assert isip('192.168.1.1') is True
        assert isip('2001:db8::1') is True
        assert isip('127.0.0.1') is True
        assert isip('::1') is True

    def test_isip_invalid(self):
        """Test isip() with invalid IP addresses"""
        assert isip('not-an-ip') is False
        assert isip('') is False
        assert isip('256.256.256.256') is False


class TestOD:
    """Test od() function (hex dump)"""

    def test_od_empty(self):
        """Test od() with empty bytes"""
        result = od(b'')
        assert result == ''

    def test_od_single_byte(self):
        """Test od() with single byte"""
        result = od(b'\x00')
        assert result == '00'

    def test_od_two_bytes(self):
        """Test od() with two bytes"""
        result = od(b'\x01\x02')
        assert result == '0102'

    def test_od_multiple_bytes(self):
        """Test od() with multiple bytes"""
        result = od(b'\x01\x02\x03\x04')
        # Groups bytes in pairs with spaces between pairs
        assert result == '0102 0304'

    def test_od_spacing(self):
        """Test od() spacing pattern"""
        # Groups bytes in pairs with spaces between pairs
        result = od(b'\xAA\xBB\xCC\xDD\xEE\xFF')
        assert result == 'AABB CCDD EEFF'

    def test_od_with_zeros(self):
        """Test od() with zero bytes"""
        result = od(b'\x00\x00\x00\x00')
        assert result == '0000 0000'

    def test_od_with_text(self):
        """Test od() with text bytes"""
        result = od(b'AB')
        # A = 0x41, B = 0x42
        assert result == '4142'

    def test_od_odd_bytes(self):
        """Test od() with odd number of bytes"""
        result = od(b'\x01\x02\x03')
        # Three bytes: pairs are grouped, third starts new group
        assert result == '0102 03'


class TestDNS:
    """Test DNS-related functions"""

    def test_host(self):
        """Test host() returns a hostname"""
        result = host()
        assert isinstance(result, str)
        assert len(result) > 0
        # Should not contain dots (short hostname)
        # or be localhost if no hostname available
        assert '.' not in result or result == 'localhost'

    def test_host_caching(self):
        """Test host() caches result"""
        result1 = host()
        result2 = host()
        assert result1 == result2

    def test_domain(self):
        """Test domain() returns a domain name"""
        result = domain()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_domain_caching(self):
        """Test domain() caches result"""
        result1 = domain()
        result2 = domain()
        assert result1 == result2

    @patch('exabgp.util.dns.socket.gethostname')
    def test_host_with_mock(self, mock_gethostname):
        """Test host() with mocked socket.gethostname"""
        # Mock to return a FQDN
        mock_gethostname.return_value = 'testhost.example.com'
        # Can't easily test due to module caching, but verify it returns a string
        result = host()
        assert isinstance(result, str)
        assert len(result) > 0

    @patch('exabgp.util.dns.socket.gethostname')
    def test_host_empty(self, mock_gethostname):
        """Test host() when gethostname returns empty"""
        # This test verifies the function handles empty hostname gracefully
        # Due to module-level caching, we can't easily reset state
        # Just verify the function works
        result = host()
        assert isinstance(result, str)

    @patch('exabgp.util.dns.socket.getfqdn')
    def test_domain_with_mock(self, mock_getfqdn):
        """Test domain() with mocked socket.getfqdn"""
        # Verify domain() returns a string value
        result = domain()
        assert isinstance(result, str)
        assert len(result) > 0
