#!/usr/bin/env python3

"""Interactive REPL mode for ExaBGP CLI with readline support"""

from __future__ import annotations

import os
import sys
import readline
import atexit
from typing import List, Optional, Callable, Dict, Any


# ANSI color codes
class Colors:
    """ANSI color codes for terminal output"""

    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

    # Foreground colors
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'

    # Bright colors
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'

    @classmethod
    def supports_color(cls) -> bool:
        """Check if terminal supports ANSI colors"""
        # Check if stdout is a terminal
        if not hasattr(sys.stdout, 'isatty') or not sys.stdout.isatty():
            return False

        # Check TERM environment variable
        term = os.environ.get('TERM', '')
        if term in ('dumb', ''):
            return False

        # Check NO_COLOR environment variable (https://no-color.org/)
        if os.environ.get('NO_COLOR'):
            return False

        return True


class CommandCompleter:
    """Tab completion for ExaBGP commands using readline"""

    def __init__(self, send_command: Callable[[str], str], get_neighbors: Optional[Callable[[], List[str]]] = None):
        """
        Initialize completer

        Args:
            send_command: Function to send commands to ExaBGP
            get_neighbors: Optional function to fetch neighbor IPs for completion
        """
        self.send_command = send_command
        self.get_neighbors = get_neighbors
        self.use_color = Colors.supports_color()

        # Base command list - these are the top-level commands
        self.base_commands = [
            'help',
            'show',
            'announce',
            'withdraw',
            'flush',
            'clear',
            'teardown',
            'shutdown',
            'reload',
            'restart',
            'version',
            'reset',
            'enable-ack',
            'disable-ack',
            'silence-ack',
        ]

        # Command tree for nested completion
        self.command_tree: Dict[str, Any] = {
            'show': {
                'neighbor': ['summary', 'extensive', 'configuration', 'json'],
                'adj-rib': ['in', 'out', 'extensive', 'json'],
            },
            'announce': {
                'route': [],
                'ipv4': [],
                'ipv6': [],
                'vpls': [],
                'attribute': [],
                'attributes': [],
                'flow': [],
                'eor': [],
                'route-refresh': [],
                'operational': [],
                'watchdog': [],
            },
            'withdraw': {
                'route': [],
                'ipv4': [],
                'ipv6': [],
                'vpls': [],
                'attribute': [],
                'attributes': [],
                'flow': [],
                'watchdog': [],
            },
            'flush': {
                'adj-rib': ['out'],
            },
            'clear': {
                'adj-rib': ['in', 'out'],
            },
            'teardown': [],  # Followed by neighbor IP
        }

        # Command shortcuts for completion
        self.shortcuts = {
            'h': 'help',
            's': 'show',
            'a': 'announce',
            'w': 'withdraw',
            'f': 'flush',
            'c': 'clear',
            't': 'teardown',
            'n': 'neighbor',
            'e': 'eor',
            'rr': 'route-refresh',
            'o': 'operational',
        }

        # Cache for neighbor IPs
        self._neighbor_cache: Optional[List[str]] = None

    def complete(self, text: str, state: int) -> Optional[str]:
        """
        Readline completion function

        Args:
            text: Current word being completed
            state: Iteration state (0 for first match, increments for subsequent)

        Returns:
            Next matching completion or None
        """
        # Get the full line buffer to understand context
        line = readline.get_line_buffer()
        begin = readline.get_begidx()

        # Parse the line into tokens
        tokens = line[:begin].split()

        # Generate matches based on context
        if state == 0:
            # First call - generate all matches
            self.matches = self._get_completions(tokens, text)

        # Return the next match
        try:
            return self.matches[state]
        except IndexError:
            return None

    def _get_completions(self, tokens: List[str], text: str) -> List[str]:
        """
        Get list of completions based on current context

        Args:
            tokens: Previously typed tokens
            text: Current partial token

        Returns:
            List of matching completions
        """
        # If no tokens yet, complete base commands
        if not tokens:
            matches = [cmd for cmd in self.base_commands if cmd.startswith(text)]
            # Also include shortcuts
            matches.extend([shortcut for shortcut in self.shortcuts if shortcut.startswith(text)])
            return sorted(matches)

        # Expand shortcuts in tokens
        expanded_tokens = []
        for token in tokens:
            if token in self.shortcuts:
                expanded_tokens.append(self.shortcuts[token])
            else:
                expanded_tokens.append(token)

        # Navigate command tree
        current_level = self.command_tree

        for i, token in enumerate(expanded_tokens):
            if isinstance(current_level, dict):
                if token in current_level:
                    current_level = current_level[token]
                else:
                    # Token not in tree, might be completing this level
                    if i == len(expanded_tokens) - 1 and not text:
                        # Last token, but user pressed TAB after space
                        # No more completions at this level
                        return []
                    # Partial match at this level
                    matches = [cmd for cmd in current_level.keys() if cmd.startswith(token)]
                    return sorted(matches)
            elif isinstance(current_level, list):
                # At a leaf node (list of options)
                matches = [opt for opt in current_level if opt.startswith(text)]
                return sorted(matches)
            else:
                # Unknown structure
                return []

        # After navigating, see what's available at current level
        if isinstance(current_level, dict):
            matches = [cmd for cmd in current_level.keys() if cmd.startswith(text)]

            # Special cases for dynamic completions
            if expanded_tokens and expanded_tokens[0] == 'teardown':
                # Complete with neighbor IPs
                neighbor_ips = self._get_neighbor_ips()
                matches.extend([ip for ip in neighbor_ips if ip.startswith(text)])

            return sorted(matches)
        elif isinstance(current_level, list):
            matches = [opt for opt in current_level if opt.startswith(text)]
            return sorted(matches)

        return []

    def _get_neighbor_ips(self) -> List[str]:
        """
        Get list of neighbor IPs for completion

        Returns:
            List of neighbor IP addresses
        """
        if self._neighbor_cache is not None:
            return self._neighbor_cache

        if self.get_neighbors:
            try:
                self._neighbor_cache = self.get_neighbors()
                return self._neighbor_cache
            except Exception:
                pass

        return []

    def invalidate_cache(self) -> None:
        """Invalidate neighbor IP cache (call after topology changes)"""
        self._neighbor_cache = None


class OutputFormatter:
    """Format and colorize output"""

    def __init__(self, use_color: bool = True):
        self.use_color = use_color and Colors.supports_color()

    def format_prompt(self, hostname: str = 'exabgp') -> str:
        """Format the interactive prompt"""
        if self.use_color:
            return f'{Colors.BOLD}{Colors.GREEN}{hostname}{Colors.RESET}{Colors.BOLD}>{Colors.RESET} '
        return f'{hostname}> '

    def format_error(self, message: str) -> str:
        """Format error message"""
        if self.use_color:
            return f'{Colors.BOLD}{Colors.RED}Error:{Colors.RESET} {message}'
        return f'Error: {message}'

    def format_warning(self, message: str) -> str:
        """Format warning message"""
        if self.use_color:
            return f'{Colors.BOLD}{Colors.YELLOW}Warning:{Colors.RESET} {message}'
        return f'Warning: {message}'

    def format_success(self, message: str) -> str:
        """Format success message"""
        if self.use_color:
            return f'{Colors.BOLD}{Colors.GREEN}✓{Colors.RESET} {message}'
        return f'✓ {message}'

    def format_info(self, message: str) -> str:
        """Format info message"""
        if self.use_color:
            return f'{Colors.BOLD}{Colors.CYAN}Info:{Colors.RESET} {message}'
        return f'Info: {message}'

    def format_command_output(self, output: str) -> str:
        """Format command output with colors"""
        if not self.use_color or not output:
            return output

        lines = output.split('\n')
        formatted = []

        for line in lines:
            # Colorize JSON-like output
            if line.strip().startswith('{') or line.strip().startswith('['):
                formatted.append(f'{Colors.CYAN}{line}{Colors.RESET}')
            # Colorize IP addresses
            elif any(c in line for c in ['.', ':']):
                # Simple IP highlighting (can be improved)
                formatted.append(line)
            else:
                formatted.append(line)

        return '\n'.join(formatted)

    def format_table(self, headers: List[str], rows: List[List[str]]) -> str:
        """Format data as a table"""
        if not headers or not rows:
            return ''

        # Calculate column widths
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = max(col_widths[i], len(str(cell)))

        # Build table
        lines = []

        # Header
        if self.use_color:
            header_line = ' │ '.join(f'{Colors.BOLD}{h.ljust(w)}{Colors.RESET}' for h, w in zip(headers, col_widths))
        else:
            header_line = ' | '.join(h.ljust(w) for h, w in zip(headers, col_widths))

        lines.append(header_line)

        # Separator
        sep_char = '─' if self.use_color else '-'
        lines.append(
            '─┼─'.join(sep_char * w for w in col_widths) if self.use_color else '-+-'.join('-' * w for w in col_widths)
        )

        # Rows
        for row in rows:
            line = ' │ ' if self.use_color else ' | '
            line = line.join(str(cell).ljust(w) for cell, w in zip(row, col_widths))
            lines.append(line)

        return '\n'.join(lines)


class InteractiveCLI:
    """Interactive REPL for ExaBGP commands"""

    def __init__(self, send_command: Callable[[str], str], history_file: Optional[str] = None):
        """
        Initialize interactive CLI

        Args:
            send_command: Function to send commands to ExaBGP
            history_file: Path to save command history
        """
        self.send_command = send_command
        self.formatter = OutputFormatter()
        self.completer = CommandCompleter(send_command)
        self.running = True

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
        readline.parse_and_bind('tab: complete')

        # Set up delimiters (what counts as word boundaries)
        readline.set_completer_delims(' \t\n')

        # Load history
        if os.path.exists(self.history_file):
            try:
                readline.read_history_file(self.history_file)
            except Exception:
                pass

        # Set history size
        readline.set_history_length(1000)

        # Save history on exit
        atexit.register(self._save_history)

    def _save_history(self) -> None:
        """Save command history to file"""
        try:
            readline.write_history_file(self.history_file)
        except Exception:
            pass

    def run(self) -> None:
        """Run the interactive REPL"""
        self._print_banner()

        while self.running:
            try:
                # Display prompt and read command
                prompt = self.formatter.format_prompt()
                line = input(prompt).strip()

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
                print()  # Newline after ^D
                self._quit()
                break
            except KeyboardInterrupt:
                # Ctrl+C pressed
                print()  # Newline after ^C
                continue
            except Exception as exc:
                print(self.formatter.format_error(f'Unexpected error: {exc}'))

    def _print_banner(self) -> None:
        """Print welcome banner"""
        banner = """
╔══════════════════════════════════════════════════════════╗
║          ExaBGP Interactive CLI                          ║
╚══════════════════════════════════════════════════════════╝

Type 'help' for available commands
Type 'exit' or press Ctrl+D to quit
Tab completion and command history enabled
"""
        if self.formatter.use_color:
            print(f'{Colors.BOLD}{Colors.CYAN}{banner}{Colors.RESET}')
        else:
            print(banner)

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

        # Not a builtin
        return False

    def _execute_command(self, command: str) -> None:
        """
        Execute a command and display the result

        Args:
            command: Command to execute
        """
        try:
            result = self.send_command(command)

            # Format and display output
            if result:
                formatted = self.formatter.format_command_output(result)
                print(formatted)
        except Exception as exc:
            print(self.formatter.format_error(str(exc)))

    def _quit(self) -> None:
        """Exit the REPL"""
        self.running = False
        print(self.formatter.format_info('Goodbye!'))

    def _show_history(self) -> None:
        """Display command history"""
        history_len = readline.get_current_history_length()

        if history_len == 0:
            print(self.formatter.format_info('No commands in history'))
            return

        print(self.formatter.format_info(f'Command history ({history_len} entries):'))

        # Show last 20 commands
        start = max(1, history_len - 19)
        for i in range(start, history_len + 1):
            item = readline.get_history_item(i)
            if item:
                if self.formatter.use_color:
                    print(f'{Colors.DIM}{i:4d}{Colors.RESET}  {item}')
                else:
                    print(f'{i:4d}  {item}')
