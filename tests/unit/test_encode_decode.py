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


class TestSRPolicyDecode(unittest.TestCase):
    """Tests for SR-Policy decode (JSON and --command modes)."""

    # From qa/encoding/conf-sr-policy.ci — IPv4 SR-Policy with MPLS preference +
    # binding-sid + one Type-A segment.
    SR_POLICY_PKT_1 = 'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF006902000000524001010040020040050400000064C01728000F00240C060000000000640D06100005DC01008000110009060000000000010106000003E81100800E1600014904C0000201006000000000000000640A000001'
    # IPv4 SR-Policy with SRv6 binding-sid + Type-B segment + policy/candidate names.
    SR_POLICY_PKT_2 = 'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF00A1020000008A4001010040020040050400000064C01760000F005C0C060000000000C814120000FC0000000000000000000000000000018000250009060000000000020D1A1000FC000000000000000000000000000001004100002000100082000A006D792D706F6C696379810008007072696D617279800E1600014904C0000201006000000001000000C80A000002'

    def setUp(self):
        log.silence()

    def _decode_json(self, hex_payload, family='ipv4 sr-policy'):
        from exabgp.application import decode

        args = Namespace(
            payload=hex_payload.replace('\n', ''),
            nlri=False,
            update=False,
            open=False,
            debug=False,
            pdb=False,
            configuration=None,
            family=family,
            path_information=False,
            generic=False,
            json=True,
            command=False,
        )
        captured = io.StringIO()
        with patch.object(sys, 'stdout', captured):
            result = decode.cmdline(args)
        self.assertEqual(result, 0)
        raw = captured.getvalue()
        start = raw.find('{')
        end = raw.rfind('}') + 1
        return json.loads(raw[start:end])

    def _decode_command(self, hex_payload, family='ipv4 sr-policy'):
        from exabgp.application import decode

        args = Namespace(
            payload=hex_payload.replace('\n', ''),
            nlri=False,
            update=False,
            open=False,
            debug=False,
            pdb=False,
            configuration=None,
            family=family,
            path_information=False,
            generic=False,
            json=True,
            command=True,
        )
        captured = io.StringIO()
        with patch.object(sys, 'stdout', captured):
            result = decode.cmdline(args)
        self.assertEqual(result, 0)
        return captured.getvalue().strip()

    def test_sr_policy_json_tunnel_encap_key(self):
        """tunnel-encap must appear as structured key, not generic attribute-0x17-0xC0."""
        data = self._decode_json(self.SR_POLICY_PKT_1)
        attrs = data['neighbor']['message']['update']['attribute']
        self.assertIn('tunnel-encap', attrs, 'tunnel-encap must be a named key')
        self.assertNotIn('attribute-0x17-0xC0', attrs)

    def test_sr_policy_json_nlri_fields(self):
        """SR-Policy NLRI JSON must include distinguisher, color, and endpoint."""
        data = self._decode_json(self.SR_POLICY_PKT_1)
        announce = data['neighbor']['message']['update']['announce']
        self.assertIn('ipv4 sr-policy', announce)
        nlris = list(announce['ipv4 sr-policy'].values())[0]
        self.assertEqual(len(nlris), 1)
        self.assertEqual(nlris[0]['distinguisher'], 0)
        self.assertEqual(nlris[0]['color'], 100)
        self.assertEqual(nlris[0]['endpoint'], '10.0.0.1')

    def test_sr_policy_json_tunnel_content(self):
        """SR-Policy tunnel sub-TLVs must decode to structured JSON."""
        data = self._decode_json(self.SR_POLICY_PKT_1)
        attrs = data['neighbor']['message']['update']['attribute']
        sr = attrs['tunnel-encap']['sr-policy']
        self.assertEqual(sr['preference'], 100)
        self.assertEqual(sr['binding-sid']['type'], 'mpls')
        self.assertEqual(sr['binding-sid']['label'], 24000)
        seg = sr['segment-lists'][0]['segments'][0]
        self.assertEqual(seg['type'], 'A')
        self.assertEqual(seg['label'], 16001)

    def test_sr_policy_command_mpls(self):
        """decode --command must produce a re-injectable SR-Policy announce (MPLS path)."""
        cmd = self._decode_command(self.SR_POLICY_PKT_1)
        self.assertTrue(cmd.startswith('announce ipv4 sr-policy'), repr(cmd))
        self.assertIn('distinguisher 0', cmd)
        self.assertIn('color 100', cmd)
        self.assertIn('endpoint 10.0.0.1', cmd)
        self.assertIn('next-hop 192.0.2.1', cmd)
        self.assertIn('preference 100', cmd)
        self.assertIn('binding-sid mpls 24000', cmd)
        self.assertIn('segment-list weight 1', cmd)
        self.assertIn('segment type-a mpls 16001', cmd)

    def test_sr_policy_command_srv6(self):
        """decode --command must produce a re-injectable announce (SRv6 path + names)."""
        cmd = self._decode_command(self.SR_POLICY_PKT_2)
        self.assertTrue(cmd.startswith('announce ipv4 sr-policy'), repr(cmd))
        self.assertIn('distinguisher 1', cmd)
        self.assertIn('color 200', cmd)
        self.assertIn('endpoint 10.0.0.2', cmd)
        self.assertIn('preference 200', cmd)
        self.assertIn('srv6-binding-sid fc00::1', cmd)
        self.assertIn('segment type-b srv6 fc00::1', cmd)
        self.assertIn('endpoint-behavior 65', cmd)
        self.assertIn('policy-name "my-policy"', cmd)
        self.assertIn('candidate-path-name "primary"', cmd)


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
