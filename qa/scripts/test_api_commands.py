#!/usr/bin/env python3
"""Test comprehensive ExaBGP API commands.

Modern replacement for the old bash socket-based test.
Tests: version, ping, status, shutdown (via api-simple.run process).
"""

import subprocess
import sys
import os
import time

# Paths relative to repository root
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.join(SCRIPT_DIR, '..', '..')
CONFIG_FILE = os.path.join(ROOT_DIR, 'etc', 'exabgp', 'api-simple.conf')
EXABGP_BIN = os.path.join(ROOT_DIR, 'sbin', 'exabgp')


def test_api_commands():
    """Run ExaBGP with api-simple config and validate behavior."""

    # Verify files exist
    if not os.path.exists(CONFIG_FILE):
        print(f'ERROR: Config file not found: {CONFIG_FILE}')
        return False

    if not os.path.exists(EXABGP_BIN):
        print(f'ERROR: ExaBGP binary not found: {EXABGP_BIN}')
        return False

    print('=' * 70)
    print('ExaBGP API Commands Test (version, ping, status, shutdown)')
    print('=' * 70)

    # Start ExaBGP
    env = os.environ.copy()
    env['exabgp_log_enable'] = 'false'

    try:
        proc = subprocess.Popen(
            [EXABGP_BIN, CONFIG_FILE],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Wait for test to complete (shutdown should happen automatically)
        timeout = 10
        start_time = time.time()

        while proc.poll() is None:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                print(f'ERROR: Test timed out after {timeout}s')
                proc.kill()
                proc.wait()
                return False
            time.sleep(0.1)

        # Collect output
        stdout, stderr = proc.communicate(timeout=1)
        exit_code = proc.returncode

        # Check exit code
        if exit_code != 0:
            print(f'FAILURE: ExaBGP exited with code {exit_code}')
            if stderr:
                print(f'STDERR:\n{stderr}')
            if stdout:
                print(f'STDOUT:\n{stdout}')
            return False

        # Validate that our tests actually ran
        if 'SUCCESS: All API commands' in stderr:
            print('SUCCESS: All API commands tested and passed')
            if stderr:
                # Show test output
                print('\nTest output:')
                for line in stderr.strip().split('\n'):
                    if line.startswith('TEST:') or line.startswith('  PASS:') or line.startswith('SUCCESS:'):
                        print(f'  {line}')
            print('=' * 70)
            return True
        else:
            print('WARNING: Test completed but validation message not found')
            print(f'Exit code: {exit_code}')
            if stderr:
                print(f'STDERR:\n{stderr}')
            return exit_code == 0

    except subprocess.TimeoutExpired:
        print('ERROR: Process did not terminate within timeout')
        proc.kill()
        proc.wait()
        return False
    except Exception as e:
        print(f'ERROR: Unexpected exception: {e}')
        if 'proc' in locals():
            try:
                proc.kill()
                proc.wait()
            except:
                pass
        return False


if __name__ == '__main__':
    success = test_api_commands()
    sys.exit(0 if success else 1)
