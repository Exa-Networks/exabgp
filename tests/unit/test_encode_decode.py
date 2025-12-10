#!/usr/bin/env python3
# encoding: utf-8
"""test_encode_decode.py

Tests for the encode and decode CLI commands.

Created on 2025-11-27.
Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import io
import json
import sys
import unittest
from argparse import Namespace
from unittest.mock import patch

from exabgp.environment import getenv
from exabgp.logger import log

# Initialize logging
log.init(getenv())


class TestEncodeCommand(unittest.TestCase):
    """Tests for the encode CLI command."""

    def setUp(self):
        # Silence logging during tests
        log.silence()
        # Clear RIB cache to prevent pollution from other tests
        from exabgp.rib import RIB

        RIB._cache.clear()

    def test_encode_basic_ipv4_route(self):
        """Test encoding a basic IPv4 route."""
        from exabgp.application import encode

        args = Namespace(
            route='route 10.0.0.0/24 next-hop 192.168.1.1',
            family='ipv4 unicast',
            local_as=65533,
            peer_as=65533,
            path_information=False,
            nlri_only=False,
            no_header=False,
            configuration=None,
            debug=False,
            pdb=False,
        )

        # Capture stdout
        captured = io.StringIO()
        with patch.object(sys, 'stdout', captured):
            with patch.object(sys, 'exit'):
                encode.cmdline(args)

        output = captured.getvalue().strip()

        # Should produce hex output starting with BGP marker
        self.assertTrue(
            output.startswith('FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF'), f'Expected BGP marker, got: {output[:40]}'
        )
        # Should be valid hex
        self.assertTrue(all(c in '0123456789ABCDEF' for c in output), 'Output should be hex')
        # BGP UPDATE type is 02 at position 37 (after 16-byte marker + 2-byte length = 36 hex chars)
        self.assertEqual(output[36:38], '02', 'Should have UPDATE type marker at correct position')

    def test_encode_nlri_only(self):
        """Test encoding with NLRI-only flag."""
        from exabgp.application import encode

        args = Namespace(
            route='route 10.0.0.0/24 next-hop 192.168.1.1',
            family='ipv4 unicast',
            local_as=65533,
            peer_as=65533,
            path_information=False,
            nlri_only=True,
            no_header=False,
            configuration=None,
            debug=False,
            pdb=False,
        )

        captured = io.StringIO()
        with patch.object(sys, 'stdout', captured):
            with patch.object(sys, 'exit'):
                encode.cmdline(args)

        output = captured.getvalue().strip()

        # NLRI-only should NOT start with BGP marker
        self.assertFalse(output.startswith('FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF'), 'NLRI-only should not have BGP marker')
        # For /24, NLRI is: 18 (prefix len) + 3 bytes = 4 bytes = 8 hex chars
        self.assertEqual(len(output), 8, f'NLRI for /24 should be 8 hex chars, got {len(output)}')
        # First byte is prefix length (24 = 0x18)
        self.assertEqual(output[:2], '18', 'First byte should be prefix length 24 (0x18)')

    def test_encode_no_header(self):
        """Test encoding without BGP header."""
        from exabgp.application import encode

        args = Namespace(
            route='route 10.0.0.0/24 next-hop 192.168.1.1',
            family='ipv4 unicast',
            local_as=65533,
            peer_as=65533,
            path_information=False,
            nlri_only=False,
            no_header=True,
            configuration=None,
            debug=False,
            pdb=False,
        )

        captured = io.StringIO()
        with patch.object(sys, 'stdout', captured):
            with patch.object(sys, 'exit'):
                encode.cmdline(args)

        output = captured.getvalue().strip()

        # Without header, should NOT start with BGP marker
        self.assertFalse(output.startswith('FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF'), 'no-header should not have BGP marker')
        # Should start with withdrawn routes length (0000)
        self.assertTrue(output.startswith('0000'), f'Should start with withdrawn routes length, got: {output[:4]}')

    def test_encode_ipv6_route(self):
        """Test encoding an IPv6 route."""
        from exabgp.application import encode

        args = Namespace(
            route='route 2001:db8::/32 next-hop 2001:db8::1',
            family='ipv6 unicast',
            local_as=65533,
            peer_as=65533,
            path_information=False,
            nlri_only=False,
            no_header=False,
            configuration=None,
            debug=False,
            pdb=False,
        )

        captured = io.StringIO()
        with patch.object(sys, 'stdout', captured):
            with patch.object(sys, 'exit'):
                encode.cmdline(args)

        output = captured.getvalue().strip()

        # Should produce valid hex
        self.assertTrue(all(c in '0123456789ABCDEF' for c in output), 'Output should be hex')
        # Should contain MP_REACH_NLRI attribute (type 0x0E = 14)
        # The attribute appears as 800E (optional transitive + type 14)
        self.assertIn('800E', output, 'Should contain MP_REACH_NLRI attribute')

    def test_encode_with_as_path(self):
        """Test encoding a route with AS path."""
        from exabgp.application import encode

        args = Namespace(
            route='route 10.0.0.0/24 next-hop 192.168.1.1 as-path [65000 65001]',
            family='ipv4 unicast',
            local_as=65533,
            peer_as=65533,
            path_information=False,
            nlri_only=False,
            no_header=False,
            configuration=None,
            debug=False,
            pdb=False,
        )

        captured = io.StringIO()
        with patch.object(sys, 'stdout', captured):
            with patch.object(sys, 'exit'):
                encode.cmdline(args)

        output = captured.getvalue().strip()

        # Should be longer than basic route (has AS path)
        self.assertGreater(len(output), 80, 'Route with AS path should be longer')
        # AS 65000 = 0xFDE8, AS 65001 = 0xFDE9
        self.assertIn('FDE8', output, 'Should contain AS 65000')
        self.assertIn('FDE9', output, 'Should contain AS 65001')


class TestDecodeCommand(unittest.TestCase):
    """Tests for the decode CLI command."""

    def setUp(self):
        log.silence()

    def test_decode_basic_update(self):
        """Test decoding a basic UPDATE message."""
        from exabgp.application import decode

        # A simple UPDATE with 10.0.0.0/24 next-hop 192.168.1.1
        hex_payload = 'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF0030020000001540010100400200400304C0A8010140050400000064180A0000'

        args = Namespace(
            payload=hex_payload,
            nlri=False,
            update=False,
            open=False,
            debug=False,
            pdb=False,
            configuration=None,
            family=None,
            path_information=False,
            generic=False,
            json=True,
            command=False,
        )

        captured = io.StringIO()
        with patch.object(sys, 'stdout', captured):
            result = decode.cmdline(args)

        output = captured.getvalue()

        # Should succeed
        self.assertEqual(result, 0, 'Decode should succeed')
        # Output should be JSON
        self.assertIn('{', output, 'Output should contain JSON')
        # Should contain the route
        self.assertIn('10.0.0.0/24', output, 'Should contain the decoded route')
        # Should contain next-hop
        self.assertIn('192.168.1.1', output, 'Should contain next-hop')

    def test_decode_stdin_single_line(self):
        """Test decoding from stdin with single line."""
        from exabgp.application import decode

        hex_payload = 'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF0030020000001540010100400200400304C0A8010140050400000064180A0000'

        args = Namespace(
            payload=None,  # No payload means read from stdin
            nlri=False,
            update=False,
            open=False,
            debug=False,
            pdb=False,
            configuration=None,
            family=None,
            path_information=False,
            generic=False,
            json=True,
            command=False,
        )

        # Mock stdin
        mock_stdin = io.StringIO(hex_payload + '\n')

        captured = io.StringIO()
        with patch.object(sys, 'stdin', mock_stdin):
            with patch.object(sys, 'stdout', captured):
                with patch.object(sys.stdin, 'isatty', return_value=False):
                    result = decode.cmdline(args)

        output = captured.getvalue()

        self.assertEqual(result, 0, 'Decode should succeed')
        self.assertIn('10.0.0.0/24', output, 'Should contain the decoded route')

    def test_decode_stdin_multiple_lines(self):
        """Test decoding multiple payloads from stdin."""
        from exabgp.application import decode

        # Two different routes
        hex1 = 'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF0030020000001540010100400200400304C0A8010140050400000064180A0000'
        hex2 = 'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF0030020000001540010100400200400304C0A8010240050400000064180A0100'

        args = Namespace(
            payload=None,
            nlri=False,
            update=False,
            open=False,
            debug=False,
            pdb=False,
            configuration=None,
            family=None,
            path_information=False,
            generic=False,
            json=True,
            command=False,
        )

        mock_stdin = io.StringIO(hex1 + '\n' + hex2 + '\n')

        captured = io.StringIO()
        with patch.object(sys, 'stdin', mock_stdin):
            with patch.object(sys, 'stdout', captured):
                with patch.object(sys.stdin, 'isatty', return_value=False):
                    result = decode.cmdline(args)

        output = captured.getvalue()

        self.assertEqual(result, 0, 'Decode should succeed')
        # Should have two JSON outputs
        self.assertIn('10.0.0.0/24', output, 'Should contain first route')
        self.assertIn('10.1.0.0/24', output, 'Should contain second route')

    def test_decode_with_colons(self):
        """Test decoding hex with colons (common format)."""
        from exabgp.application import decode

        # Same payload but with colons
        hex_payload = 'FF:FF:FF:FF:FF:FF:FF:FF:FF:FF:FF:FF:FF:FF:FF:FF:00:30:02:00:00:00:15:40:01:01:00:40:02:00:40:03:04:C0:A8:01:01:40:05:04:00:00:00:64:18:0A:00:00'

        args = Namespace(
            payload=hex_payload,
            nlri=False,
            update=False,
            open=False,
            debug=False,
            pdb=False,
            configuration=None,
            family=None,
            path_information=False,
            generic=False,
            json=True,
            command=False,
        )

        captured = io.StringIO()
        with patch.object(sys, 'stdout', captured):
            result = decode.cmdline(args)

        output = captured.getvalue()

        self.assertEqual(result, 0, 'Decode should succeed with colons')
        self.assertIn('10.0.0.0/24', output, 'Should decode correctly')

    def test_decode_invalid_hex(self):
        """Test decoding invalid hex."""
        from exabgp.application import decode

        args = Namespace(
            payload='not-valid-hex-GHIJ',
            nlri=False,
            update=False,
            open=False,
            debug=False,
            pdb=False,
            configuration=None,
            family=None,
            path_information=False,
            generic=False,
            json=True,
            command=False,
        )

        captured = io.StringIO()
        with patch.object(sys, 'stdout', captured):
            result = decode.cmdline(args)

        output = captured.getvalue()

        self.assertEqual(result, 1, 'Decode should fail for invalid hex')
        self.assertIn('invalid', output.lower(), 'Should report invalid input')


class TestEncodeDecodeRoundTrip(unittest.TestCase):
    """Tests for encode/decode round-trip verification."""

    def setUp(self):
        log.silence()
        # Clear RIB cache to prevent pollution from other tests
        from exabgp.rib import RIB

        RIB._cache.clear()

    def test_roundtrip_basic_ipv4(self):
        """Test that encode output can be decoded back."""
        from exabgp.application import decode, encode

        # First encode
        encode_args = Namespace(
            route='route 10.0.0.0/24 next-hop 192.168.1.1',
            family='ipv4 unicast',
            local_as=65533,
            peer_as=65533,
            path_information=False,
            nlri_only=False,
            no_header=False,
            configuration=None,
            debug=False,
            pdb=False,
        )

        encoded = io.StringIO()
        with patch.object(sys, 'stdout', encoded):
            with patch.object(sys, 'exit'):
                encode.cmdline(encode_args)

        hex_output = encoded.getvalue().strip()

        # Then decode
        decode_args = Namespace(
            payload=hex_output,
            nlri=False,
            update=False,
            open=False,
            debug=False,
            pdb=False,
            configuration=None,
            family=None,
            path_information=False,
            generic=False,
            json=True,
            command=False,
        )

        decoded = io.StringIO()
        with patch.object(sys, 'stdout', decoded):
            result = decode.cmdline(decode_args)

        output = decoded.getvalue()

        self.assertEqual(result, 0, 'Round-trip decode should succeed')
        self.assertIn('10.0.0.0/24', output, 'Should recover original route')
        self.assertIn('192.168.1.1', output, 'Should recover next-hop')

    def test_roundtrip_ipv6(self):
        """Test round-trip for IPv6 route."""
        from exabgp.application import decode, encode

        encode_args = Namespace(
            route='route 2001:db8::/32 next-hop 2001:db8::1',
            family='ipv6 unicast',
            local_as=65533,
            peer_as=65533,
            path_information=False,
            nlri_only=False,
            no_header=False,
            configuration=None,
            debug=False,
            pdb=False,
        )

        encoded = io.StringIO()
        with patch.object(sys, 'stdout', encoded):
            with patch.object(sys, 'exit'):
                encode.cmdline(encode_args)

        hex_output = encoded.getvalue().strip()

        decode_args = Namespace(
            payload=hex_output,
            nlri=False,
            update=False,
            open=False,
            debug=False,
            pdb=False,
            configuration=None,
            family='ipv6 unicast',
            path_information=False,
            generic=False,
            json=True,
            command=False,
        )

        decoded = io.StringIO()
        with patch.object(sys, 'stdout', decoded):
            result = decode.cmdline(decode_args)

        output = decoded.getvalue()

        self.assertEqual(result, 0, 'Round-trip decode should succeed')
        self.assertIn('2001:db8::/32', output, 'Should recover IPv6 route')

    def test_roundtrip_with_attributes(self):
        """Test round-trip preserves attributes."""
        from exabgp.application import decode, encode

        encode_args = Namespace(
            route='route 10.0.0.0/24 next-hop 192.168.1.1 origin igp local-preference 200',
            family='ipv4 unicast',
            local_as=65533,
            peer_as=65533,
            path_information=False,
            nlri_only=False,
            no_header=False,
            configuration=None,
            debug=False,
            pdb=False,
        )

        encoded = io.StringIO()
        with patch.object(sys, 'stdout', encoded):
            with patch.object(sys, 'exit'):
                encode.cmdline(encode_args)

        hex_output = encoded.getvalue().strip()

        decode_args = Namespace(
            payload=hex_output,
            nlri=False,
            update=False,
            open=False,
            debug=False,
            pdb=False,
            configuration=None,
            family=None,
            path_information=False,
            generic=False,
            json=True,
            command=False,
        )

        decoded = io.StringIO()
        with patch.object(sys, 'stdout', decoded):
            result = decode.cmdline(decode_args)

        output = decoded.getvalue()

        self.assertEqual(result, 0, 'Round-trip decode should succeed')
        # Parse JSON to check attributes
        json_start = output.find('{')
        json_end = output.rfind('}') + 1
        data = json.loads(output[json_start:json_end])

        attrs = data['neighbor']['message']['update']['attribute']
        self.assertEqual(attrs['origin'], 'igp', 'Should preserve origin')
        self.assertEqual(attrs['local-preference'], 200, 'Should preserve local-preference')


class TestIsBgpFunction(unittest.TestCase):
    """Tests for the is_bgp helper function."""

    def test_valid_hex(self):
        """Test valid hex strings."""
        from exabgp.application.decode import is_bgp

        self.assertTrue(is_bgp('AABBCCDD'))
        self.assertTrue(is_bgp('aabbccdd'))
        self.assertTrue(is_bgp('0123456789abcdef'))
        self.assertTrue(is_bgp('AA:BB:CC:DD'))
        # Note: spaces are NOT valid in is_bgp - only colons
        # Spaces are stripped before is_bgp is called in cmdline

    def test_invalid_hex(self):
        """Test invalid hex strings."""
        from exabgp.application.decode import is_bgp

        self.assertFalse(is_bgp('GHIJ'))
        self.assertFalse(is_bgp('hello'))
        self.assertFalse(is_bgp('12345G'))


if __name__ == '__main__':
    unittest.main()
