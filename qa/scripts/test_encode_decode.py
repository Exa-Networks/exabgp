#!/usr/bin/env python3
"""Test ExaBGP encode and decode CLI commands.

This test validates:
- encode command produces valid BGP UPDATE hex
- decode command can parse the encoded output
- Round-trip encode|decode preserves route information
- stdin support for decode command
- Various address families and attributes
"""

import json
import os
import subprocess
import sys

# Paths relative to repository root
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.join(SCRIPT_DIR, '..', '..')
EXABGP_BIN = os.path.join(ROOT_DIR, 'sbin', 'exabgp')


def run_exabgp(args, stdin_input=None):
    """Run exabgp with given arguments and return (exit_code, stdout, stderr)."""
    env = os.environ.copy()
    env['exabgp_log_enable'] = 'false'

    proc = subprocess.Popen(
        [EXABGP_BIN] + args,
        env=env,
        stdin=subprocess.PIPE if stdin_input else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    stdout, stderr = proc.communicate(input=stdin_input, timeout=30)
    return proc.returncode, stdout, stderr


def test_encode_basic_ipv4():
    """Test encoding a basic IPv4 route."""
    print('TEST: encode basic IPv4 route')

    exit_code, stdout, stderr = run_exabgp(['encode', 'route 10.0.0.0/24 next-hop 192.168.1.1'])

    if exit_code != 0:
        print(f'  FAIL: exit code {exit_code}')
        print(f'  stderr: {stderr}')
        return False

    output = stdout.strip()

    # Verify it starts with BGP marker
    if not output.startswith('FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF'):
        print(f'  FAIL: missing BGP marker, got: {output[:40]}')
        return False

    # Verify it's valid hex
    if not all(c in '0123456789ABCDEF' for c in output):
        print('  FAIL: invalid hex characters')
        return False

    print(f'  PASS: produced {len(output) // 2} bytes of hex')
    return True


def test_encode_ipv6():
    """Test encoding an IPv6 route."""
    print('TEST: encode IPv6 route')

    exit_code, stdout, stderr = run_exabgp(['encode', '-f', 'ipv6 unicast', 'route 2001:db8::/32 next-hop 2001:db8::1'])

    if exit_code != 0:
        print(f'  FAIL: exit code {exit_code}')
        return False

    output = stdout.strip()

    # Should contain MP_REACH_NLRI (0x800E)
    if '800E' not in output:
        print('  FAIL: missing MP_REACH_NLRI attribute')
        return False

    print(f'  PASS: produced {len(output) // 2} bytes with MP_REACH_NLRI')
    return True


def test_encode_nlri_only():
    """Test encoding with NLRI-only flag."""
    print('TEST: encode NLRI-only')

    exit_code, stdout, stderr = run_exabgp(['encode', '-n', 'route 10.0.0.0/24 next-hop 192.168.1.1'])

    if exit_code != 0:
        print(f'  FAIL: exit code {exit_code}')
        return False

    output = stdout.strip()

    # Should NOT have BGP marker
    if output.startswith('FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF'):
        print('  FAIL: NLRI-only should not have BGP marker')
        return False

    # For /24, NLRI is 4 bytes = 8 hex chars
    if len(output) != 8:
        print(f'  FAIL: expected 8 hex chars, got {len(output)}')
        return False

    print(f'  PASS: NLRI-only is {len(output) // 2} bytes')
    return True


def test_decode_basic():
    """Test decoding a basic UPDATE."""
    print('TEST: decode basic UPDATE')

    hex_payload = 'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF0030020000001540010100400200400304C0A8010140050400000064180A0000'

    exit_code, stdout, stderr = run_exabgp(['decode', hex_payload])

    if exit_code != 0:
        print(f'  FAIL: exit code {exit_code}')
        return False

    # Parse JSON output
    try:
        data = json.loads(stdout.strip())
    except json.JSONDecodeError as e:
        print(f'  FAIL: invalid JSON: {e}')
        return False

    # Check route is present
    try:
        announce = data['neighbor']['message']['update']['announce']
        ipv4 = announce['ipv4 unicast']
        nexthop = list(ipv4.keys())[0]
        nlri = ipv4[nexthop][0]['nlri']

        if nlri != '10.0.0.0/24':
            print(f'  FAIL: expected 10.0.0.0/24, got {nlri}')
            return False

        if nexthop != '192.168.1.1':
            print(f'  FAIL: expected next-hop 192.168.1.1, got {nexthop}')
            return False

    except (KeyError, IndexError) as e:
        print(f'  FAIL: missing expected fields: {e}')
        return False

    print('  PASS: decoded 10.0.0.0/24 next-hop 192.168.1.1')
    return True


def test_decode_stdin():
    """Test decoding from stdin."""
    print('TEST: decode from stdin')

    hex_payload = 'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF0030020000001540010100400200400304C0A8010140050400000064180A0000\n'

    exit_code, stdout, stderr = run_exabgp(['decode'], stdin_input=hex_payload)

    if exit_code != 0:
        print(f'  FAIL: exit code {exit_code}')
        return False

    if '10.0.0.0/24' not in stdout:
        print('  FAIL: route not found in output')
        return False

    print('  PASS: decoded from stdin')
    return True


def test_decode_stdin_multiple():
    """Test decoding multiple payloads from stdin."""
    print('TEST: decode multiple from stdin')

    hex1 = 'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF0030020000001540010100400200400304C0A8010140050400000064180A0000'
    hex2 = 'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF0030020000001540010100400200400304C0A8010240050400000064180A0100'

    stdin_input = hex1 + '\n' + hex2 + '\n'

    exit_code, stdout, stderr = run_exabgp(['decode'], stdin_input=stdin_input)

    if exit_code != 0:
        print(f'  FAIL: exit code {exit_code}')
        return False

    lines = [line for line in stdout.strip().split('\n') if line.strip()]
    if len(lines) != 2:
        print(f'  FAIL: expected 2 JSON lines, got {len(lines)}')
        return False

    if '10.0.0.0/24' not in stdout:
        print('  FAIL: first route not found')
        return False

    if '10.1.0.0/24' not in stdout:
        print('  FAIL: second route not found')
        return False

    print('  PASS: decoded 2 routes from stdin')
    return True


def test_roundtrip_ipv4():
    """Test encode|decode round-trip for IPv4."""
    print('TEST: round-trip IPv4')

    # Encode
    exit_code, encoded, stderr = run_exabgp(['encode', 'route 172.16.0.0/16 next-hop 10.0.0.1'])

    if exit_code != 0:
        print(f'  FAIL: encode failed with {exit_code}')
        return False

    # Decode
    exit_code, decoded, stderr = run_exabgp(['decode', encoded.strip()])

    if exit_code != 0:
        print(f'  FAIL: decode failed with {exit_code}')
        return False

    # Verify route preserved
    if '172.16.0.0/16' not in decoded:
        print('  FAIL: route not preserved')
        return False

    if '10.0.0.1' not in decoded:
        print('  FAIL: next-hop not preserved')
        return False

    print('  PASS: round-trip preserved route and next-hop')
    return True


def test_roundtrip_ipv6():
    """Test encode|decode round-trip for IPv6."""
    print('TEST: round-trip IPv6')

    # Encode
    exit_code, encoded, stderr = run_exabgp(
        ['encode', '-f', 'ipv6 unicast', 'route 2001:db8:1234::/48 next-hop 2001:db8::1']
    )

    if exit_code != 0:
        print(f'  FAIL: encode failed with {exit_code}')
        return False

    # Decode with family hint
    exit_code, decoded, stderr = run_exabgp(['decode', '-f', 'ipv6 unicast', encoded.strip()])

    if exit_code != 0:
        print(f'  FAIL: decode failed with {exit_code}')
        return False

    if '2001:db8:1234::/48' not in decoded:
        print('  FAIL: IPv6 route not preserved')
        return False

    print('  PASS: round-trip preserved IPv6 route')
    return True


def test_roundtrip_with_attributes():
    """Test round-trip preserves BGP attributes."""
    print('TEST: round-trip with attributes')

    # Encode with attributes
    route = 'route 192.168.100.0/24 next-hop 10.0.0.1 origin igp local-preference 200 community [65000:100]'
    exit_code, encoded, stderr = run_exabgp(['encode', route])

    if exit_code != 0:
        print(f'  FAIL: encode failed with {exit_code}')
        return False

    # Decode
    exit_code, decoded, stderr = run_exabgp(['decode', encoded.strip()])

    if exit_code != 0:
        print(f'  FAIL: decode failed with {exit_code}')
        return False

    # Parse and verify attributes
    try:
        data = json.loads(decoded.strip())
        attrs = data['neighbor']['message']['update']['attribute']

        if attrs.get('origin') != 'igp':
            print('  FAIL: origin not preserved')
            return False

        if attrs.get('local-preference') != 200:
            print('  FAIL: local-preference not preserved')
            return False

    except (json.JSONDecodeError, KeyError) as e:
        print(f'  FAIL: could not verify attributes: {e}')
        return False

    print('  PASS: attributes preserved')
    return True


def test_pipe_encode_to_decode():
    """Test piping encode output directly to decode via shell."""
    print('TEST: pipe encode | decode')

    env = os.environ.copy()
    env['exabgp_log_enable'] = 'false'

    # Use shell to pipe
    cmd = f'{EXABGP_BIN} encode "route 10.20.30.0/24 next-hop 1.2.3.4" | {EXABGP_BIN} decode'

    proc = subprocess.Popen(cmd, shell=True, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    stdout, stderr = proc.communicate(timeout=30)

    if proc.returncode != 0:
        print(f'  FAIL: pipe failed with {proc.returncode}')
        return False

    if '10.20.30.0/24' not in stdout:
        print('  FAIL: route not in output')
        return False

    if '1.2.3.4' not in stdout:
        print('  FAIL: next-hop not in output')
        return False

    print('  PASS: shell pipe works')
    return True


def main():
    """Run all tests and report results."""
    if not os.path.exists(EXABGP_BIN):
        print(f'ERROR: ExaBGP binary not found: {EXABGP_BIN}')
        return False

    print('Testing ExaBGP encode/decode commands...\n')

    tests = [
        test_encode_basic_ipv4,
        test_encode_ipv6,
        test_encode_nlri_only,
        test_decode_basic,
        test_decode_stdin,
        test_decode_stdin_multiple,
        test_roundtrip_ipv4,
        test_roundtrip_ipv6,
        test_roundtrip_with_attributes,
        test_pipe_encode_to_decode,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f'  EXCEPTION: {e}')
            failed += 1

    print(f'\n{"=" * 40}')
    print(f'RESULTS: {passed} passed, {failed} failed')
    print(f'{"=" * 40}')

    if failed == 0:
        print('SUCCESS: All encode/decode tests passed')
        return True
    else:
        print('FAILURE: Some tests failed')
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
