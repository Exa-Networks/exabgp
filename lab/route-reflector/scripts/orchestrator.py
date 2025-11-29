#!/usr/bin/env python3
"""
Lab Orchestrator - Process Management and Output Multiplexing

Starts all components of the BGP route reflector lab:
  1. ExaBGP route reflector (with filter API process)
  2. Client BGP speakers (2 instances)
  3. Upstream BGP speaker

Multiplexes output from all processes with colored prefixes for easy identification.
Handles graceful shutdown on Ctrl+C.
"""

import subprocess
import sys
import os
import time
import signal
import select
import threading
from typing import List, Dict, Any

# ANSI color codes
RESET = '\033[0m'
BOLD = '\033[1m'
RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
BLUE = '\033[34m'
MAGENTA = '\033[35m'
CYAN = '\033[36m'
WHITE = '\033[37m'


class ProcessManager:
    """Manages multiple subprocesses and multiplexes their output"""

    def __init__(self):
        self.processes: Dict[str, Dict[str, Any]] = {}
        self.running = True
        self.output_lock = threading.Lock()

    def start(self, name: str, command: List[str], prefix: str, color: str = '') -> None:
        """
        Start a subprocess and track it

        Args:
            name: Process identifier
            command: Command and arguments to execute
            prefix: Display prefix for output lines
            color: ANSI color code for this process
        """
        try:
            proc = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,
                universal_newlines=True,
            )
            self.processes[name] = {
                'proc': proc,
                'prefix': prefix,
                'color': color,
                'command': ' '.join(command),
            }
            self._print(f'{BOLD}{CYAN}[ORCHESTRATOR]{RESET} Started {name} (PID {proc.pid})')

        except Exception as e:
            self._print(f'{BOLD}{RED}[ORCHESTRATOR]{RESET} Failed to start {name}: {e}')

    def _print(self, message: str) -> None:
        """Thread-safe print"""
        with self.output_lock:
            print(message)
            sys.stdout.flush()

    def _format_line(self, line: str, prefix: str, color: str) -> str:
        """
        Format output line with colored prefix

        Args:
            line: Raw output line
            prefix: Process prefix (e.g., [CLIENT1])
            color: ANSI color code

        Returns:
            Formatted line with color
        """
        line = line.rstrip()
        if not line:
            return ''

        # Check if line already has a prefix in brackets
        if line.startswith('['):
            # Already has prefix - just add color
            return f'{color}{line}{RESET}'
        else:
            # Add prefix
            return f'{color}{prefix:15s}{RESET} {line}'

    def monitor_output(self) -> None:
        """Monitor and display output from all processes"""
        while self.running:
            # Build list of file descriptors to monitor
            fds = []
            fd_map = {}

            for name, info in self.processes.items():
                proc = info['proc']
                if proc.poll() is not None:
                    # Process exited - collect remaining output
                    if proc.stdout:
                        try:
                            remaining = proc.stdout.read()
                            if remaining:
                                for line in remaining.splitlines():
                                    formatted = self._format_line(line, info['prefix'], info['color'])
                                    if formatted:
                                        self._print(formatted)
                        except Exception:
                            pass
                    if proc.stderr:
                        try:
                            remaining = proc.stderr.read()
                            if remaining:
                                for line in remaining.splitlines():
                                    formatted = self._format_line(line, info['prefix'], info['color'])
                                    if formatted:
                                        self._print(formatted)
                        except Exception:
                            pass
                    continue

                if proc.stdout:
                    fds.append(proc.stdout)
                    fd_map[proc.stdout] = (name, 'stdout')
                if proc.stderr:
                    fds.append(proc.stderr)
                    fd_map[proc.stderr] = (name, 'stderr')

            if not fds:
                break

            # Wait for output (with timeout)
            try:
                ready, _, _ = select.select(fds, [], [], 0.5)
            except select.error:
                break

            for fd in ready:
                if fd not in fd_map:
                    continue

                name, stream_type = fd_map[fd]
                info = self.processes[name]

                try:
                    line = fd.readline()
                    if line:
                        formatted = self._format_line(line, info['prefix'], info['color'])
                        if formatted:
                            self._print(formatted)
                except Exception:
                    pass

            time.sleep(0.01)

    def shutdown(self) -> None:
        """Terminate all processes gracefully"""
        self._print(f'\n{BOLD}{CYAN}[ORCHESTRATOR]{RESET} Shutting down all processes...')
        self.running = False

        # Give processes a moment to finish any pending output
        time.sleep(0.5)

        for name, info in self.processes.items():
            proc = info['proc']
            if proc.poll() is None:
                self._print(f'{BOLD}{CYAN}[ORCHESTRATOR]{RESET} Terminating {name} (PID {proc.pid})...')
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._print(f'{BOLD}{CYAN}[ORCHESTRATOR]{RESET} Killing {name} (PID {proc.pid})...')
                    proc.kill()
                    proc.wait()

        self._print(f'{BOLD}{CYAN}[ORCHESTRATOR]{RESET} All processes terminated')

    def wait_for_exit(self) -> None:
        """Wait for all processes to exit"""
        while any(info['proc'].poll() is None for info in self.processes.values()):
            time.sleep(0.5)


def print_banner():
    """Print lab startup banner"""
    print()
    print('=' * 70)
    print(f'{BOLD}{WHITE}BGP Route Reflector Lab - AS-PATH Based Filtering{RESET}')
    print('=' * 70)
    print()
    print(f'{BOLD}Topology:{RESET}')
    print('  Upstream (AS 65001) → ExaBGP (AS 65000) → Clients (AS 65002, 65003)')
    print()
    print(f'{BOLD}Filter Rules:{RESET}')
    print('  Google routes (AS 15169)    → Client1')
    print('  Microsoft routes (AS 8075)  → Client2')
    print('  Other routes                → Dropped')
    print()
    print('=' * 70)
    print()


def main():
    """Main orchestrator entry point"""
    # Get paths relative to script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    lab_root = os.path.abspath(os.path.join(script_dir, '..'))
    repo_root = os.path.abspath(os.path.join(lab_root, '..', '..'))

    config_file = os.path.join(lab_root, 'config', 'exabgp-rr.conf')
    exabgp_bin = os.path.join(repo_root, 'sbin', 'exabgp')
    client_script = os.path.join(script_dir, 'client_speaker.py')
    upstream_script = os.path.join(script_dir, 'upstream_speaker.py')

    # Verify files exist
    for path, desc in [(config_file, 'ExaBGP config'), (exabgp_bin, 'ExaBGP binary'),
                       (client_script, 'Client script'), (upstream_script, 'Upstream script')]:
        if not os.path.exists(path):
            print(f'ERROR: {desc} not found: {path}')
            return 1

    print_banner()

    pm = ProcessManager()

    # Signal handler for graceful shutdown
    def signal_handler(sig, frame):
        print(f'\n{BOLD}{CYAN}[ORCHESTRATOR]{RESET} Received interrupt signal')
        pm.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Start ExaBGP route reflector
        pm.start(
            'exabgp',
            [exabgp_bin, config_file],
            '[EXABGP]',
            BLUE
        )

        # Wait for ExaBGP to initialize and start listening
        print(f'{BOLD}{CYAN}[ORCHESTRATOR]{RESET} Waiting 3s for ExaBGP to initialize...')
        time.sleep(3)

        # Start client BGP speakers (both connect to port 1790)
        pm.start(
            'client1',
            ['python3', client_script, '--name', 'CLIENT1', '--port', '1790', '--asn', '65002'],
            '[CLIENT1]',
            GREEN
        )

        pm.start(
            'client2',
            ['python3', client_script, '--name', 'CLIENT2', '--port', '1790', '--asn', '65003'],
            '[CLIENT2]',
            MAGENTA
        )

        # Wait for clients to connect
        print(f'{BOLD}{CYAN}[ORCHESTRATOR]{RESET} Waiting 2s for clients to connect...')
        time.sleep(2)

        # Start upstream BGP speaker
        pm.start(
            'upstream',
            ['python3', upstream_script],
            '[UPSTREAM]',
            YELLOW
        )

        print()
        print('=' * 70)
        print(f'{BOLD}{WHITE}All processes started - Monitoring output{RESET}')
        print(f'{BOLD}{CYAN}Press Ctrl+C to shutdown{RESET}')
        print('=' * 70)
        print()
        print(f'{BOLD}Legend:{RESET}')
        print(f'  {BLUE}EXABGP{RESET}    - Route reflector messages')
        print(f'  {WHITE}FILTER{RESET}    - AS-PATH filter decisions')
        print(f'  {YELLOW}UPSTREAM{RESET}  - Routes announced (Google/MS/Other)')
        print(f'  {GREEN}CLIENT1{RESET}   - Routes received (Google only)')
        print(f'  {MAGENTA}CLIENT2{RESET}   - Routes received (Microsoft only)')
        print()
        print('=' * 70)
        print()

        # Monitor output from all processes
        pm.monitor_output()

    except Exception as e:
        print(f'{BOLD}{RED}[ORCHESTRATOR]{RESET} Error: {e}')
        import traceback
        traceback.print_exc()
    finally:
        pm.shutdown()

    return 0


if __name__ == '__main__':
    sys.exit(main())
