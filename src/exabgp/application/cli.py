#!/usr/bin/env python3

"""Interactive REPL mode for ExaBGP CLI with readline support"""

from __future__ import annotations

import json
import argparse
import os
import sys
import readline
import atexit
import socket as sock
from typing import Callable

from exabgp.cli.colors import Colors
from exabgp.cli.completer import CommandCompleter
from exabgp.cli.formatter import OutputFormatter
from exabgp.cli.history import HistoryTracker
from exabgp.cli.persistent_connection import PersistentSocketConnection
from exabgp.application.shortcuts import CommandShortcuts
from exabgp.application.pipe import named_pipe
from exabgp.application.unixsocket import unix_socket
from exabgp.environment import ROOT


class InteractiveCLI:
    """Interactive REPL for ExaBGP commands"""

    def __init__(
        self,
        send_command: Callable[[str], str],
        history_file: str | None = None,
        daemon_uuid: str | None = None,
    ):
        """
        Initialize interactive CLI

        Args:
            send_command: Function to send commands to ExaBGP
            history_file: Path to save command history
            daemon_uuid: Optional daemon UUID for connection message
        """
        self.send_command = send_command
        self.formatter = OutputFormatter()
        self.running = True
        self.daemon_uuid = daemon_uuid
        self.output_encoding = 'json'  # API encoding format ('json' or 'text')
        self.display_mode = 'text'  # Display mode ('json' or 'text')
        self.sync_mode = False  # Sync mode: wait for routes on wire before ACK (default: off)

        # Initialize command history tracker (for smart completion ranking)
        self.history_tracker = HistoryTracker()

        # Initialize completer with history tracker
        self.completer = CommandCompleter(send_command, history_tracker=self.history_tracker)

        # Setup history file
        if history_file is None:
            home = os.path.expanduser('~')
            history_file = os.path.join(home, '.exabgp_history')

        self.history_file = history_file
        self._setup_readline()

    def _setup_readline(self) -> None:
        """Configure readline for history and completion"""
        # Set up completion
        readline.set_completer(self.completer.complete)

        # Configure TAB completion behavior
        # Note: macOS uses libedit, Linux uses GNU readline - both supported
        if 'libedit' in readline.__doc__:
            # macOS libedit configuration
            # First, enable emacs mode to ensure arrow keys work properly
            readline.parse_and_bind('bind -e')  # Use emacs key bindings
            # Explicitly bind arrow keys for history navigation
            readline.parse_and_bind('bind ^[[A ed-prev-history')  # Up arrow
            readline.parse_and_bind('bind ^[[B ed-next-history')  # Down arrow
            readline.parse_and_bind('bind ^[[C ed-next-char')  # Right arrow
            readline.parse_and_bind('bind ^[[D ed-prev-char')  # Left arrow
            # Bind completion keys
            readline.parse_and_bind('bind ^I rl_complete')  # TAB key
            readline.parse_and_bind('bind ? rl_complete')  # ? key (help completion)
            # libedit doesn't support show-all-if-ambiguous, so we modify the completer
            # to return all matches at once (handled in complete() method)
        else:
            # GNU readline configuration
            readline.parse_and_bind('tab: complete')
            readline.parse_and_bind('?: complete')  # ? key (help completion)
            # Show all completions immediately (don't require double-TAB)
            readline.parse_and_bind('set show-all-if-ambiguous on')
            # Show completions on first TAB even if there are many matches
            readline.parse_and_bind('set completion-query-items -1')

        # Set up delimiters (what counts as word boundaries)
        readline.set_completer_delims(' \t\n')

        # Load history
        if os.path.exists(self.history_file):
            try:
                readline.read_history_file(self.history_file)
            except OSError:
                pass

        # Set history size
        readline.set_history_length(1000)

        # Save history on exit
        atexit.register(self._save_history)

    def _save_history(self) -> None:
        """Save command history to file"""
        try:
            readline.write_history_file(self.history_file)
        except OSError:
            pass

    def run(self) -> None:
        """Run the interactive REPL"""
        self._print_banner()

        while self.running:
            try:
                # Display prompt and read command
                prompt = self.formatter.format_prompt()
                line = input(prompt).strip()

                # Check if background thread signaled shutdown
                if not self.running:
                    break

                # Skip empty lines
                if not line:
                    continue

                # Handle built-in REPL commands
                if self._handle_builtin(line):
                    continue

                # Send to ExaBGP
                self._execute_command(line)

            except EOFError:
                # Ctrl+D pressed
                sys.stdout.write('\n')  # Newline after ^D
                self._quit()
                break
            except KeyboardInterrupt:
                # Ctrl+C pressed OR signal from background thread
                if not self.running:
                    # Signal from background thread - exit gracefully
                    sys.stdout.write('\n')  # Newline
                    break
                else:
                    # User pressed Ctrl+C - quit normally
                    sys.stdout.write('\n')  # Newline after ^C
                    self._quit()
                    break
            except Exception as exc:
                sys.stdout.write(f'{self.formatter.format_error(f"Unexpected error: {exc}")}\n')

    def _print_banner(self) -> None:
        """Print welcome banner with ASCII art and version"""
        from exabgp.version import version as exabgp_version

        banner = rf"""
╔══════════════════════════════════════════════════════════╗
║ ___________             __________  __________________   ║
║ \_   _____/__  ________ \______   \/  _____/\______   \  ║
║  |    __)_\  \/  /\__  \ |    |  _/   \  ___ |     ___/  ║
║  |        \>    <  / __ \|    |   \    \_\  \|    |      ║
║ /_________/__/\__\(______/________/\________/|____|      ║
║                                                          ║
║  Version: {exabgp_version:<46} ║
╚══════════════════════════════════════════════════════════╝
"""
        if self.formatter.use_color:
            sys.stdout.write(f'{Colors.BOLD}{Colors.CYAN}{banner}{Colors.RESET}')
        else:
            sys.stdout.write(banner)

        # Print connection message if daemon UUID is available
        if self.daemon_uuid:
            conn_msg = f'✓ Connected to ExaBGP daemon (UUID: {self.daemon_uuid})'
            if self.formatter.use_color:
                sys.stdout.write(f'{Colors.GREEN}{conn_msg}{Colors.RESET}\n')
            else:
                sys.stdout.write(f'{conn_msg}\n')
        sys.stdout.write('\n')

        # Print usage instructions
        help_text = """Type 'help' for available commands
Type 'exit' or press Ctrl+D/Ctrl+C to quit
Tab completion and command history enabled

Display Format (optional prefix):
  json <command>  - Display output as JSON
  text <command>  - Display output as text tables
  Example: json show neighbor
"""
        if self.formatter.use_color:
            sys.stdout.write(f'{Colors.DIM}{help_text}{Colors.RESET}\n')
        else:
            sys.stdout.write(f'{help_text}\n')

    def _handle_builtin(self, line: str) -> bool:
        """
        Handle REPL built-in commands

        Args:
            line: Command line

        Returns:
            True if command was handled, False otherwise
        """
        tokens = line.split()
        if not tokens:
            return True

        cmd = tokens[0].lower()

        if cmd in ('exit', 'quit', 'q'):
            self._quit()
            return True

        if cmd == 'clear':
            # Clear screen
            os.system('clear' if os.name != 'nt' else 'cls')
            return True

        if cmd == 'history':
            # Show command history
            self._show_history()
            return True

        if cmd == 'set' and len(tokens) >= 3:
            setting = tokens[1].lower()
            value = tokens[2].lower()

            if setting == 'encoding':
                # Set API output encoding: 'set encoding json' or 'set encoding text'
                if value in ('json', 'text'):
                    self.output_encoding = value
                    sys.stdout.write(f'{self.formatter.format_info(f"API output encoding set to {value}")}\n')
                else:
                    sys.stdout.write(
                        f'{self.formatter.format_error(f"Invalid encoding {value!r}. Use json or text.")}\n'
                    )
                return True

            elif setting == 'display':
                # Set display mode: 'set display json' or 'set display text'
                if value in ('json', 'text'):
                    self.display_mode = value
                    if value == 'text':
                        sys.stdout.write(
                            f'{self.formatter.format_info("Display mode set to text (JSON will be formatted as tables)")}\n'
                        )
                    else:
                        sys.stdout.write(
                            f'{self.formatter.format_info("Display mode set to json (raw JSON display)")}\n'
                        )
                else:
                    sys.stdout.write(
                        f'{self.formatter.format_error(f"Invalid display {value!r}. Use json or text.")}\n'
                    )
                return True

            elif setting == 'sync':
                # Set sync mode: 'set sync on' or 'set sync off'
                if value in ('on', 'off'):
                    new_sync = value == 'on'
                    if new_sync != self.sync_mode:
                        # Send enable-sync or disable-sync to daemon
                        cmd = 'enable-sync' if new_sync else 'disable-sync'
                        result = self.send_command(cmd)
                        if result and result.startswith('Error:'):
                            sys.stdout.write(f'{self.formatter.format_error(result[7:])}\n')
                            return True
                        self.sync_mode = new_sync
                    if new_sync:
                        sys.stdout.write(
                            f'{self.formatter.format_info("Sync mode ON: announce/withdraw will wait for routes to be sent on wire")}\n'
                        )
                    else:
                        sys.stdout.write(
                            f'{self.formatter.format_info("Sync mode OFF: announce/withdraw return immediately (default)")}\n'
                        )
                else:
                    sys.stdout.write(
                        f'{self.formatter.format_error(f"Invalid sync value {value!r}. Use on or off.")}\n'
                    )
                return True

        # Not a builtin
        return False

    def _is_read_command(self, command: str) -> bool:
        """
        Determine if a command is read-only (returns data) or write (modifies state)

        Args:
            command: Command string (may have been partially parsed)

        Returns:
            True if read command, False if write command
        """
        # Read-only commands that support display format override
        read_prefixes = ('show', 'list', 'help', 'version')
        # Write commands that modify state (ignore display prefix)
        write_prefixes = ('announce', 'withdraw', 'flush', 'clear', 'shutdown', 'reload', 'restart')

        # Get first token of command
        tokens = command.split()
        if not tokens:
            return False

        first_token = tokens[0].lower()

        # Check for read commands
        if first_token in read_prefixes:
            return True

        # Check for write commands
        if first_token in write_prefixes:
            return False

        # Builtin CLI commands are read-only
        if first_token in ('exit', 'quit', 'q', 'clear', 'history', 'set'):
            return True

        # Default: treat unknown commands as read (safer - allows user to see output)
        return True

    def _execute_command(self, command: str) -> None:
        """
        Execute a command and display the result

        Args:
            command: Command to execute
        """
        try:
            tokens = command.split()

            # Check for display format prefix (json/text at START)
            display_override = None
            if tokens and tokens[0].lower() in ('json', 'text'):
                display_override = tokens[0].lower()
                # Strip display prefix from command
                command = ' '.join(tokens[1:])
                tokens = command.split()  # Re-tokenize

            # Check if command has explicit encoding override (json/text at end)
            override_encoding = None

            if tokens and tokens[-1].lower() in ('json', 'text'):
                override_encoding = tokens[-1].lower()
                # Strip override keyword from command
                command = ' '.join(tokens[:-1])
                tokens = command.split()  # Re-tokenize after stripping

            # Validate format combination
            if display_override and override_encoding:
                if display_override != override_encoding:
                    # Conflicting formats - block execution
                    error_msg = (
                        f"Error: Conflicting formats - display='{display_override}' "
                        f"but API encoding='{override_encoding}'\n"
                        f'Use matching formats or omit one:\n'
                        f"  '{command} {override_encoding}' (both {override_encoding})\n"
                        f"  '{display_override} {command} {display_override}' (both {display_override})\n"
                        f"  '{display_override} {command}' (display only)"
                    )
                    sys.stdout.write(f'{self.formatter.format_error(error_msg)}\n')
                    return

            # Check if this is a read command (write commands ignore display prefix)
            is_read = self._is_read_command(command)
            if display_override and not is_read:
                # Ignore display prefix for write commands (no output to format)
                display_override = None

            # CLI uses v6 API format natively - no transformation needed
            # Commands are sent directly to daemon in v6 format:
            #   daemon shutdown, peer * announce route, peer show, etc.

            # Determine which encoding to use (override takes precedence)
            encoding_to_use = override_encoding if override_encoding else self.output_encoding

            # Append encoding keyword to command before sending to daemon
            command_with_encoding = f'{command} {encoding_to_use}'

            result = self.send_command(command_with_encoding)

            # Check for socket/timeout errors
            if result and result.startswith('Error: '):
                # Socket write failed or timeout - show error without "Command sent"
                sys.stdout.write(f'{self.formatter.format_error(result[7:])}\n')  # Strip "Error: " prefix
                # Record command failure
                self.history_tracker.record_command(command, success=False)
                return

            # Socket write succeeded - show immediate feedback
            sys.stdout.write(f'{self.formatter.format_success("Command sent")}\n')

            # Format and display daemon response
            result_stripped = result.strip()

            # Check for success with no data FIRST (before formatting which may print "done")
            # Empty response or "done" means command was accepted
            if not result_stripped or result_stripped in ('done', 'done\nerror\n'):
                # Command succeeded but no output - show success confirmation
                sys.stdout.write(f'{self.formatter.format_success("Command accepted")}\n')
                # Record command success
                self.history_tracker.record_command(command, success=True)
                return

            # Check if response ends with API error marker
            is_error = result_stripped.endswith('error')

            if is_error:
                # Split on rightmost 'error' marker to extract error details
                parts = result_stripped.rsplit('error', 1)
                error_content = parts[0].strip() if len(parts) > 1 else ''

                if error_content:
                    # Try to parse as JSON error
                    try:
                        error_data = json.loads(error_content)
                        if isinstance(error_data, dict) and 'error' in error_data:
                            # JSON error format: {"error": "message"}
                            sys.stdout.write(f'{self.formatter.format_error(error_data["error"])}\n')
                        else:
                            # JSON but not error format - show as-is
                            sys.stdout.write(f'{self.formatter.format_error(error_content)}\n')
                    except (json.JSONDecodeError, ValueError):
                        # Not JSON - treat as text error
                        # Format: "error: message" or just "message"
                        if error_content.startswith('error:'):
                            sys.stdout.write(f'{self.formatter.format_error(error_content[6:].strip())}\n')
                        else:
                            sys.stdout.write(f'{self.formatter.format_error(error_content)}\n')
                else:
                    # Just "error" with no details
                    sys.stdout.write(f'{self.formatter.format_error("Command failed")}\n')
                # Record command failure
                self.history_tracker.record_command(command, success=False)
                return

            # Not an error - format normally
            # Determine display mode (display_override takes precedence over session default)
            display_to_use = display_override if display_override else self.display_mode

            # Validate API response format matches display request
            # If user requested JSON display but API returned text, fail loudly
            if display_to_use == 'json' and encoding_to_use == 'text':
                # This should be impossible - tests should catch this
                error_obj = {
                    'error': 'API returned text format when JSON was requested for display',
                    'details': 'This is a bug - please report',
                    'command': command,
                    'api_encoding': encoding_to_use,
                    'display_mode': display_to_use,
                }
                error_json = json.dumps(error_obj, indent=2)
                sys.stdout.write(f'{self.formatter.format_error(error_json)}\n')
                return

            formatted = self.formatter.format_command_output(result, display_mode=display_to_use)

            if formatted:
                # Regular output - display as-is
                sys.stdout.write(f'{formatted}\n')

            # Record command success (got valid response)
            self.history_tracker.record_command(command, success=True)
        except Exception as exc:
            sys.stdout.write(f'{self.formatter.format_error(str(exc))}\n')
            # Record command failure (exception during execution)
            self.history_tracker.record_command(command, success=False)

    def _quit(self) -> None:
        """Exit the REPL"""
        self.running = False
        # Send bye command to server and wait for acknowledgment
        try:
            self.send_command('bye')
        except (Exception, KeyboardInterrupt):
            # Ignore errors during disconnect (including impatient Ctrl+C)
            pass
        sys.stdout.write(f'{self.formatter.format_info("Goodbye!")}\n')

    def _show_history(self) -> None:
        """Display command history"""
        history_len = readline.get_current_history_length()

        if history_len == 0:
            sys.stdout.write(f'{self.formatter.format_info("No commands in history")}\n')
            return

        sys.stdout.write(f'{self.formatter.format_info(f"Command history ({history_len} entries):")}\n')

        # Show last 20 commands
        start = max(1, history_len - 19)
        for i in range(start, history_len + 1):
            item = readline.get_history_item(i)
            if item:
                if self.formatter.use_color:
                    sys.stdout.write(f'{Colors.DIM}{i:4d}{Colors.RESET}  {item}\n')
                else:
                    sys.stdout.write(f'{i:4d}  {item}\n')


def cmdline_interactive(pipename: str, socketname: str, use_pipe_transport: bool, cmdarg: argparse.Namespace) -> int:
    """
    Entry point for interactive CLI mode

    Args:
        pipename: Name of the named pipe
        socketname: Name of the Unix socket
        use_pipe_transport: If True, use pipe; otherwise use socket
        cmdarg: Command-line arguments

    Returns:
        Exit code (0 for success)
    """
    # Initialize connection variable for cleanup
    connection = None

    # Determine transport method
    if use_pipe_transport:
        # Use named pipe transport
        pipes = named_pipe(ROOT, pipename)
        if len(pipes) != 1:
            sys.stderr.write(f"Could not find ExaBGP's named pipe ({pipename})\n")
            sys.stderr.write('Available pipes:\n - ')
            sys.stderr.write('\n - '.join(pipes))
            sys.stderr.write('\n')
            sys.stderr.flush()
            return 1

        pipe_path = pipes[0]

        def send_command_pipe(command: str) -> str:
            """Send command via named pipe and return response"""
            try:
                # Expand shortcuts
                expanded = CommandShortcuts.expand_shortcuts(command)

                # Open pipe and send command
                with open(pipe_path, 'w') as writer:
                    writer.write(expanded + '\n')
                    writer.flush()

                # Read response (simplified - real implementation needs proper response handling)
                # For now, return acknowledgment
                return 'Command sent'
            except OSError as exc:
                return f'Error: {exc}'

        send_func = send_command_pipe
        daemon_uuid = None
    else:
        # Use Unix socket transport
        sockets = unix_socket(ROOT, socketname)
        if len(sockets) != 1:
            sys.stderr.write(f"Could not find ExaBGP's Unix socket ({socketname}.sock)\n")
            sys.stderr.write('Available sockets:\n - ')
            sys.stderr.write('\n - '.join(sockets))
            sys.stderr.write('\n')
            sys.stderr.flush()
            return 1

        socket_path = sockets[0]

        # Create persistent connection with health monitoring
        try:
            connection = PersistentSocketConnection(socket_path)
        except sock.error as exc:
            # Socket connection errors
            sys.stderr.write('\n')
            sys.stderr.write('╔════════════════════════════════════════════════════════╗\n')
            sys.stderr.write('║  ERROR: Could not connect to ExaBGP daemon             ║\n')
            sys.stderr.write('╠════════════════════════════════════════════════════════╣\n')
            sys.stderr.write(f'║  {str(exc):<54} ║\n')
            sys.stderr.write('╚════════════════════════════════════════════════════════╝\n')
            sys.stderr.write('\n')
            sys.stderr.flush()
            return 1
        except SystemExit:
            # Raised by _initial_ping() with user-friendly error already shown
            raise
        except Exception as exc:
            sys.stderr.write('\n')
            sys.stderr.write('╔════════════════════════════════════════════════════════╗\n')
            sys.stderr.write('║  ERROR: Unexpected error connecting to ExaBGP          ║\n')
            sys.stderr.write('╠════════════════════════════════════════════════════════╣\n')
            sys.stderr.write(f'║  {str(exc):<54} ║\n')
            sys.stderr.write('╚════════════════════════════════════════════════════════╝\n')
            sys.stderr.write('\n')
            sys.stderr.flush()
            return 1

        def send_command_persistent(command: str) -> str:
            """Send command via persistent connection"""
            expanded = CommandShortcuts.expand_shortcuts(command)
            return connection.send_command(expanded)

        send_func = send_command_persistent
        daemon_uuid = connection.daemon_uuid

    # Create and run interactive CLI
    try:
        cli = InteractiveCLI(send_func, daemon_uuid=daemon_uuid)
        cli.run()
        return 0
    except Exception as exc:
        sys.stderr.write(f'CLI error: {exc}\n')
        sys.stderr.flush()
        return 1
    finally:
        # Clean up persistent connection if it exists
        if connection is not None:
            try:
                connection.close()
            except (Exception, KeyboardInterrupt):
                # Ignore all errors during cleanup (including Ctrl+C)
                pass
