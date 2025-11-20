#!/usr/bin/env python3

"""Interactive REPL mode for ExaBGP CLI with readline support"""

from __future__ import annotations

import json
import os
import re
import sys
import readline
import atexit
import ctypes
from dataclasses import dataclass
from typing import List, Optional, Callable, Dict, Tuple

from exabgp.application.shortcuts import CommandShortcuts
from exabgp.application.pipe import named_pipe
from exabgp.application.unixsocket import unix_socket
from exabgp.environment import ROOT
from exabgp.reactor.api.command.registry import CommandRegistry


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


@dataclass
class CompletionItem:
    """Metadata for a single completion item"""

    value: str  # The actual completion text
    description: Optional[str] = None  # Human-readable description
    item_type: str = 'option'  # Type: 'option', 'neighbor', 'command', 'keyword'


class CommandCompleter:
    """Tab completion for ExaBGP commands using readline with dynamic command discovery"""

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

        # Initialize command registry
        self.registry = CommandRegistry()

        # Build command tree dynamically from registry
        self.command_tree = self.registry.build_command_tree()

        # Get base commands from registry (exclude internal/non-interactive commands)
        all_commands = self.registry.get_base_commands()
        # Filter out "#" (comment command - useful in scripts/API but not interactive CLI)
        self.base_commands = [cmd for cmd in all_commands if cmd != '#']

        # Cache for neighbor IPs
        self._neighbor_cache: Optional[List[str]] = None
        self._cache_timeout = 300  # Refresh cache every 5 minutes (avoid repeated socket calls)
        self._cache_timestamp = 0
        self._cache_in_progress = False  # Prevent concurrent queries

        # Track state for single-TAB display on macOS libedit
        self.matches: List[str] = []
        self.match_metadata: Dict[str, CompletionItem] = {}  # Map completion value to metadata
        self.is_libedit = 'libedit' in readline.__doc__
        self.last_line = ''
        self.last_matches: List[str] = []

        # Try to get access to readline's rl_replace_line for line editing
        self._rl_replace_line = self._get_rl_replace_line()
        self._rl_forced_update_display = self._get_rl_forced_update_display()

    def _get_rl_replace_line(self) -> Optional[Callable]:
        """Try to get rl_replace_line function from readline library via ctypes"""
        try:
            # Try to load the readline library
            if sys.platform == 'darwin':
                # macOS uses libedit by default
                lib = ctypes.CDLL('/usr/lib/libedit.dylib')
                # libedit calls it rl_replace_line
                rl_replace_line = lib.rl_replace_line
            else:
                # Linux typically uses GNU readline
                lib = ctypes.CDLL('libreadline.so')
                rl_replace_line = lib.rl_replace_line

            # Set argument and return types
            rl_replace_line.argtypes = [ctypes.c_char_p, ctypes.c_int]
            rl_replace_line.restype = None
            return rl_replace_line
        except (OSError, AttributeError):
            return None

    def _get_rl_forced_update_display(self) -> Optional[Callable]:
        """Try to get rl_forced_update_display function from readline library via ctypes"""
        try:
            if sys.platform == 'darwin':
                lib = ctypes.CDLL('/usr/lib/libedit.dylib')
            else:
                lib = ctypes.CDLL('libreadline.so')

            rl_forced_update_display = lib.rl_forced_update_display
            rl_forced_update_display.argtypes = []
            rl_forced_update_display.restype = ctypes.c_int
            return rl_forced_update_display
        except (OSError, AttributeError):
            return None

    def complete(self, text: str, state: int) -> Optional[str]:
        """
        Readline completion function with auto-expansion of unambiguous tokens

        Args:
            text: Current word being completed
            state: Iteration state (0 for first match, increments for subsequent)

        Returns:
            Next matching completion or None (with space suffix if unambiguous)
        """
        # Get the full line buffer to understand context
        line = readline.get_line_buffer()
        begin = readline.get_begidx()
        end = readline.get_endidx()

        # Parse the line into tokens
        tokens = line[:begin].split()

        # Generate matches based on context
        if state == 0:
            # First call - try to auto-expand any unambiguous tokens
            expanded_prefix, expansions_made = self._try_auto_expand_tokens(tokens)

            if expansions_made and self._rl_replace_line:
                # We have expansions and can modify the line directly
                suffix = line[end:]  # Everything after the current word

                # Get completions for current word in expanded context
                current_matches = self._get_completions(expanded_prefix, text)

                # Build the full replacement
                prefix_str = ' '.join(expanded_prefix) + (' ' if expanded_prefix else '')

                if len(current_matches) == 1:
                    # Single match - replace entire line with expanded version
                    new_line = prefix_str + current_matches[0] + ' ' + suffix
                    self._rl_replace_line(new_line.encode('utf-8'), 0)
                    if self._rl_forced_update_display:
                        self._rl_forced_update_display()
                    # Return empty list to signal completion is done
                    self.matches = []
                    return None
                elif len(current_matches) > 1:
                    # Multiple matches - replace prefix but let user complete current word
                    new_line = prefix_str + text + suffix
                    self._rl_replace_line(new_line.encode('utf-8'), 0)
                    if self._rl_forced_update_display:
                        self._rl_forced_update_display()
                    # Now return completions for the current word
                    self.matches = current_matches
                else:
                    # No matches after expansion - just expand the prefix
                    new_line = prefix_str + text + suffix
                    self._rl_replace_line(new_line.encode('utf-8'), 0)
                    if self._rl_forced_update_display:
                        self._rl_forced_update_display()
                    self.matches = []
                    return None

            # No expansion or can't modify line - generate matches for current token
            if not expansions_made or not self._rl_replace_line:
                self.matches = self._get_completions(tokens, text)

            # macOS libedit: Display all matches on first TAB press
            if self.is_libedit and len(self.matches) > 1:
                # Check if this is a new completion (avoid repeating on subsequent TABs)
                current_line = readline.get_line_buffer()
                if current_line != self.last_line or self.matches != self.last_matches:
                    # Display matches
                    self._display_matches_and_redraw(self.matches, line)
                    self.last_line = current_line
                    self.last_matches = self.matches.copy()

        # Return the next match
        try:
            match = self.matches[state]
            # Add space suffix for unambiguous completion (single match only)
            if len(self.matches) == 1 and state == 0 and not match.startswith('\b'):
                return match + ' '
            return match
        except IndexError:
            return None

    def _try_auto_expand_tokens(self, tokens: List[str]) -> Tuple[List[str], bool]:
        """
        Auto-expand unambiguous partial tokens

        Args:
            tokens: List of tokens to potentially expand

        Returns:
            Tuple of (expanded_tokens, expansions_made)
        """
        if not tokens:
            return ([], False)

        # Build expanded tokens by checking each token for unambiguous completion
        expanded_tokens = []
        current_context = []  # Tokens we've processed so far
        expansions_made = False

        for token in tokens:
            # Get completions for this token in the current context
            completions = self._get_completions(current_context, token)

            # If exactly one completion and it's different from the token, expand it
            if len(completions) == 1 and completions[0] != token:
                expanded_tokens.append(completions[0])
                current_context.append(completions[0])
                expansions_made = True
            else:
                # Multiple completions or exact match - keep as is
                expanded_tokens.append(token)
                current_context.append(token)

        return (expanded_tokens, expansions_made)

    def _display_matches_and_redraw(self, matches: List[str], current_line: str) -> None:
        """Display completion matches with descriptions (one per line) and redraw the prompt"""
        if not matches:
            return

        # Print newline before matches
        sys.stdout.write('\n')

        # Calculate column width for value (longest match + padding)
        max_len = max(len(m) for m in matches)
        value_width = min(max_len + 2, 25)  # Cap at 25 chars to leave room for descriptions

        # Print all matches one per line with descriptions
        for match in matches:
            metadata = self.match_metadata.get(match)
            value_str = match.ljust(value_width)

            # Get description (always present due to _add_completion_metadata)
            desc_str = metadata.description if metadata and metadata.description else ''

            # Color formatting if enabled
            if self.use_color and metadata:
                if metadata.item_type == 'neighbor':
                    # Cyan for neighbors
                    sys.stdout.write(f'{Colors.CYAN}{value_str}{Colors.RESET}')
                elif metadata.item_type == 'command':
                    # Yellow for commands
                    sys.stdout.write(f'{Colors.YELLOW}{value_str}{Colors.RESET}')
                else:
                    # Green for options/keywords
                    sys.stdout.write(f'{Colors.GREEN}{value_str}{Colors.RESET}')

                if desc_str:
                    sys.stdout.write(f'{Colors.DIM}{desc_str}{Colors.RESET}\n')
                else:
                    sys.stdout.write('\n')
            else:
                # No color
                if desc_str:
                    sys.stdout.write(f'{value_str}{desc_str}\n')
                else:
                    sys.stdout.write(f'{match}\n')

        # Redraw the prompt and current input
        formatter = OutputFormatter()
        prompt = formatter.format_prompt()

        sys.stdout.write(prompt + current_line)
        sys.stdout.flush()

    def _add_completion_metadata(
        self, value: str, description: Optional[str] = None, item_type: str = 'option'
    ) -> None:
        """Add metadata for a completion item"""
        self.match_metadata[value] = CompletionItem(value=value, description=description, item_type=item_type)

    def _get_completions(self, tokens: List[str], text: str) -> List[str]:
        """
        Get list of completions based on current context

        Args:
            tokens: Previously typed tokens
            text: Current partial token

        Returns:
            List of matching completions
        """
        # Clear previous metadata
        self.match_metadata.clear()

        # If no tokens yet, complete base commands
        if not tokens:
            matches = sorted([cmd for cmd in self.base_commands if cmd.startswith(text)])
            # Add metadata for base commands with descriptions
            for match in matches:
                desc = self.registry.get_command_description(match)
                self._add_completion_metadata(match, desc, 'command')
            return matches

        # Expand shortcuts in tokens using CommandShortcuts
        expanded_tokens = CommandShortcuts.expand_token_list(tokens.copy())

        # Check if completing neighbor-targeted command
        if self._is_neighbor_command(expanded_tokens):
            return self._complete_neighbor_command(expanded_tokens, text)

        # Check for specific command patterns
        if len(expanded_tokens) >= 2:
            # Special case: 'show neighbor' can filter by IP even though neighbor=False
            if expanded_tokens[0] == 'show' and expanded_tokens[1] == 'neighbor':
                # After 'show neighbor', suggest options AND neighbor IPs
                neighbor_data = self._get_neighbor_data()

                # Get command tree options (summary, extensive, configuration)
                metadata = self.registry.get_command_metadata('show neighbor')
                options = list(metadata.options) if metadata and metadata.options else []

                # Add 'json' if command supports it
                if metadata and metadata.json_support and 'json' not in options:
                    options.append('json')

                # Add options with descriptions
                matches = []
                for opt in options:
                    if opt.startswith(text):
                        matches.append(opt)
                        desc = self.registry.get_option_description(opt)
                        self._add_completion_metadata(opt, desc, 'option')

                # Add neighbor IPs with descriptions
                for ip, info in neighbor_data.items():
                    if ip.startswith(text):
                        matches.append(ip)
                        self._add_completion_metadata(ip, info, 'neighbor')

                return sorted(matches)

            # AFI/SAFI completion for eor and route-refresh
            if expanded_tokens[-1] in ('eor', 'route-refresh'):
                return self._complete_afi_safi(expanded_tokens, text)

            # Route specification hints
            if expanded_tokens[-1] in ('route', 'ipv4', 'ipv6'):
                return self._complete_route_spec(expanded_tokens, text)

            # Neighbor filter completion
            if 'neighbor' in expanded_tokens and self._is_ip_address(expanded_tokens[-1]):
                return self._complete_neighbor_filters(text)

        # Navigate command tree
        current_level = self.command_tree

        for i, token in enumerate(expanded_tokens):
            if isinstance(current_level, dict):
                if token in current_level:
                    current_level = current_level[token]
                elif '__options__' in current_level:
                    # At a command with options
                    options = current_level['__options__']
                    if isinstance(options, list):
                        matches = []
                        for opt in options:
                            if opt.startswith(text):
                                matches.append(opt)
                                desc = self.registry.get_option_description(opt)
                                self._add_completion_metadata(opt, desc, 'option')
                        return sorted(matches)
                else:
                    # Token not in tree, try partial match
                    matches = [cmd for cmd in current_level.keys() if cmd.startswith(token) and cmd != '__options__']
                    if matches and i == len(expanded_tokens) - 1:
                        # Last token being completed - these are subcommands
                        # Build full command path for description lookup
                        cmd_prefix = ' '.join(expanded_tokens[:i]) + ' ' if i > 0 else ''
                        for match in matches:
                            full_cmd = cmd_prefix + match
                            desc = self.registry.get_command_description(full_cmd.strip())
                            self._add_completion_metadata(match, desc, 'command')
                        return sorted(matches)
                    return []
            elif isinstance(current_level, list):
                # At a leaf node (list of options)
                matches = []
                for opt in current_level:
                    if opt.startswith(text):
                        matches.append(opt)
                        desc = self.registry.get_option_description(opt)
                        self._add_completion_metadata(opt, desc, 'option')
                return sorted(matches)

        # After navigating, see what's available at current level
        if isinstance(current_level, dict):
            matches = [cmd for cmd in current_level.keys() if cmd.startswith(text) and cmd != '__options__']

            # Add metadata for commands with descriptions
            # Build full command path for description lookup
            cmd_prefix = ' '.join(expanded_tokens) + ' ' if expanded_tokens else ''
            for match in matches:
                full_cmd = (cmd_prefix + match).strip()
                desc = self.registry.get_command_description(full_cmd)
                self._add_completion_metadata(match, desc, 'command')

            # Add options if available
            if '__options__' in current_level:
                options = current_level['__options__']
                if isinstance(options, list):
                    for opt in options:
                        if opt.startswith(text):
                            matches.append(opt)
                            desc = self.registry.get_option_description(opt)
                            self._add_completion_metadata(opt, desc, 'option')

            return sorted(matches)
        elif isinstance(current_level, list):
            matches = []
            for opt in current_level:
                if opt.startswith(text):
                    matches.append(opt)
                    desc = self.registry.get_option_description(opt)
                    self._add_completion_metadata(opt, desc, 'option')
            return sorted(matches)

        return []

    def _is_neighbor_command(self, tokens: List[str]) -> bool:
        """Check if command targets a specific neighbor using registry metadata"""
        if not tokens:
            return False

        # Try progressively longer command prefixes to find a match
        # This handles multi-word commands like "flush adj-rib out"
        for length in range(len(tokens), 0, -1):
            potential_cmd = ' '.join(tokens[:length])
            metadata = self.registry.get_command_metadata(potential_cmd)
            if metadata and metadata.neighbor_support:
                return True

        # Fallback: check if first token suggests neighbor targeting
        return tokens[0] in ('neighbor', 'teardown')

    def _complete_neighbor_command(self, tokens: List[str], text: str) -> List[str]:
        """Complete neighbor-targeted commands"""
        # Check if we should complete neighbor IP
        last_token = tokens[-1] if tokens else ''

        # Check if we're at the end of a complete command (ready for neighbor spec)
        # This handles both simple commands (teardown) and multi-word commands (flush adj-rib out)
        command_str = ' '.join(tokens)
        metadata = self.registry.get_command_metadata(command_str)

        if metadata and metadata.neighbor_support:
            # We're at the end of a recognized neighbor-targeted command
            matches = []
            if 'neighbor'.startswith(text):
                matches.append('neighbor')
                desc = self.registry.get_option_description('neighbor')
                self._add_completion_metadata('neighbor', desc, 'keyword')

            # Add neighbor IPs with descriptions
            neighbor_data = self._get_neighbor_data()
            for ip, info in neighbor_data.items():
                if ip.startswith(text):
                    matches.append(ip)
                    self._add_completion_metadata(ip, info, 'neighbor')

            return sorted(matches)

        # If last token is 'neighbor', complete with IPs
        if last_token == 'neighbor':
            neighbor_data = self._get_neighbor_data()
            matches = []
            for ip, info in neighbor_data.items():
                if ip.startswith(text):
                    matches.append(ip)
                    self._add_completion_metadata(ip, info, 'neighbor')
            return sorted(matches)

        # If last token is an IP, suggest filters
        if self._is_ip_address(last_token):
            return self._complete_neighbor_filters(text)

        return []

    def _complete_neighbor_filters(self, text: str) -> List[str]:
        """Complete neighbor filter keywords"""
        filters = self.registry.get_neighbor_filters()
        matches = sorted([f for f in filters if f.startswith(text)])
        # Add descriptions for filter keywords
        for match in matches:
            desc = self.registry.get_option_description(match)
            self._add_completion_metadata(match, desc, 'keyword')
        return matches

    def _complete_afi_safi(self, tokens: List[str], text: str) -> List[str]:
        """Complete AFI/SAFI values for eor and route-refresh"""
        # Get AFI values first, then SAFI
        afi_values = self.registry.get_afi_values()

        # Check if we've already typed an AFI
        potential_afi = tokens[-2] if len(tokens) >= 2 and tokens[-2] in afi_values else None

        if potential_afi:
            # Complete SAFI for the given AFI
            safi_values = self.registry.get_safi_values(potential_afi)
            matches = sorted([s for s in safi_values if s.startswith(text)])
            # Add descriptions for SAFI values
            for match in matches:
                desc = f'SAFI for {potential_afi}'
                self._add_completion_metadata(match, desc, 'keyword')
            return matches
        else:
            # Complete AFI
            matches = sorted([a for a in afi_values if a.startswith(text)])
            # Add descriptions for AFI values
            for match in matches:
                desc = 'Address Family Identifier'
                self._add_completion_metadata(match, desc, 'keyword')
            return matches

    def _complete_route_spec(self, tokens: List[str], text: str) -> List[str]:
        """Complete route specification keywords"""
        keywords = self.registry.get_route_keywords()
        matches = sorted([k for k in keywords if k.startswith(text)])
        # Add descriptions for route keywords
        for match in matches:
            desc = 'Route specification parameter'
            self._add_completion_metadata(match, desc, 'keyword')
        return matches

    def _is_ip_address(self, token: str) -> bool:
        """Check if token looks like an IP address"""
        # Simple check for IPv4 or IPv6
        ipv4_pattern = r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'
        ipv6_pattern = r'^[0-9a-fA-F:]+$'
        return bool(re.match(ipv4_pattern, token) or (': ' in token or re.match(ipv6_pattern, token)))

    def _get_neighbor_ips(self) -> List[str]:
        """
        Get list of neighbor IPs for completion (with caching)

        Returns:
            List of neighbor IP addresses
        """
        import time

        # Check if cache is still valid
        current_time = time.time()
        if self._neighbor_cache is not None and (current_time - self._cache_timestamp) < self._cache_timeout:
            return self._neighbor_cache

        # Prevent concurrent queries (avoid socket connection issues)
        if self._cache_in_progress:
            return self._neighbor_cache if self._neighbor_cache is not None else []

        self._cache_in_progress = True

        try:
            # Try to fetch neighbor IPs from ExaBGP
            neighbor_ips = []

            # Use provided get_neighbors callback if available
            if self.get_neighbors:
                try:
                    neighbor_ips = self.get_neighbors()
                except Exception:
                    pass
            else:
                # Try to query ExaBGP via 'show neighbor json'
                try:
                    response = self.send_command('show neighbor json')
                    if response and response != 'Command sent' and not response.startswith('Error:'):
                        # Parse JSON response
                        # Clean up response - remove 'done' marker if present
                        json_text = response
                        if 'done' in json_text:
                            # Split by 'done' and take first part
                            json_text = json_text.split('done')[0].strip()

                        neighbors = json.loads(json_text)
                        if isinstance(neighbors, list):
                            for neighbor in neighbors:
                                if isinstance(neighbor, dict):
                                    # Try different possible locations for peer address
                                    peer_addr = None

                                    # Format 1: peer-address at top level
                                    if 'peer-address' in neighbor:
                                        peer_addr = neighbor['peer-address']
                                    # Format 2: remote-addr at top level
                                    elif 'remote-addr' in neighbor:
                                        peer_addr = neighbor['remote-addr']
                                    # Format 3: nested in 'peer' object (ExaBGP 5.x format)
                                    elif 'peer' in neighbor and isinstance(neighbor['peer'], dict):
                                        peer_obj = neighbor['peer']
                                        if 'address' in peer_obj:
                                            peer_addr = peer_obj['address']
                                        elif 'ip' in peer_obj:
                                            peer_addr = peer_obj['ip']

                                    if peer_addr:
                                        neighbor_ips.append(str(peer_addr))
                except Exception:
                    # Silently fail - neighbor completion is optional
                    pass

            # Update cache
            self._neighbor_cache = neighbor_ips
            self._cache_timestamp = current_time

            return neighbor_ips
        finally:
            self._cache_in_progress = False

    def _get_neighbor_data(self) -> Dict[str, str]:
        """
        Get neighbor IPs with descriptions (AS, state) for completion

        Returns:
            Dict mapping neighbor IP to description string
        """
        neighbor_data: Dict[str, str] = {}

        # Try to fetch detailed neighbor information
        try:
            response = self.send_command('show neighbor json')
            if response and response != 'Command sent' and not response.startswith('Error:'):
                # Parse JSON response
                json_text = response
                if 'done' in json_text:
                    json_text = json_text.split('done')[0].strip()

                neighbors = json.loads(json_text)
                if isinstance(neighbors, list):
                    for neighbor in neighbors:
                        if isinstance(neighbor, dict):
                            # Extract peer address
                            peer_addr = None
                            if 'peer-address' in neighbor:
                                peer_addr = neighbor['peer-address']
                            elif 'remote-addr' in neighbor:
                                peer_addr = neighbor['remote-addr']
                            elif 'peer' in neighbor and isinstance(neighbor['peer'], dict):
                                peer_obj = neighbor['peer']
                                peer_addr = peer_obj.get('address') or peer_obj.get('ip')

                            if peer_addr:
                                # Build description from neighbor info
                                peer_as = neighbor.get('peer-as', 'unknown')
                                state = neighbor.get('state', 'unknown')

                                # Format: (neighbor, AS65000, ESTABLISHED)
                                desc = f'(neighbor, AS{peer_as}, {state})'
                                neighbor_data[str(peer_addr)] = desc
        except Exception:
            # Silently fail - just return IPs without descriptions
            pass

        # If no data from JSON, fall back to IPs only
        if not neighbor_data:
            for ip in self._get_neighbor_ips():
                neighbor_data[ip] = '(neighbor)'

        return neighbor_data

    def invalidate_cache(self) -> None:
        """Invalidate neighbor IP cache (call after topology changes)"""
        self._neighbor_cache = None
        self._cache_timestamp = 0


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
        """Format command output with colors and pretty-print JSON"""
        if not output:
            return output

        # Strip common response markers
        output_stripped = output.strip()

        # Remove 'done' marker if present (ExaBGP API response suffix)
        if output_stripped.endswith('done'):
            output_stripped = output_stripped[:-4].strip()

        # Try to parse and pretty-print as JSON
        if output_stripped.startswith('{') or output_stripped.startswith('['):
            try:
                # Parse JSON
                parsed = json.loads(output_stripped)
                # Pretty-print with 2-space indent
                pretty_json = json.dumps(parsed, indent=2, ensure_ascii=False)

                # Apply color if enabled
                if self.use_color:
                    # Colorize the JSON output
                    colored_lines = []
                    for line in pretty_json.split('\n'):
                        colored_lines.append(f'{Colors.CYAN}{line}{Colors.RESET}')
                    return '\n'.join(colored_lines)
                else:
                    return pretty_json
            except (json.JSONDecodeError, ValueError):
                # Not valid JSON, fall through to regular formatting
                pass

        # Not JSON or parsing failed - use regular formatting
        if not self.use_color:
            return output

        lines = output.split('\n')
        formatted = []

        for line in lines:
            # Colorize JSON-like output (for partial/invalid JSON)
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

        # Configure TAB completion behavior
        # Note: macOS uses libedit, Linux uses GNU readline - both supported
        if 'libedit' in readline.__doc__:
            # macOS libedit configuration
            readline.parse_and_bind('bind ^I rl_complete')  # TAB key
            # libedit doesn't support show-all-if-ambiguous, so we modify the completer
            # to return all matches at once (handled in complete() method)
        else:
            # GNU readline configuration
            readline.parse_and_bind('tab: complete')
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
                self._quit()
                break
            except Exception as exc:
                print(self.formatter.format_error(f'Unexpected error: {exc}'))

    def _print_banner(self) -> None:
        """Print welcome banner"""
        banner = """
╔══════════════════════════════════════════════════════════╗
║          ExaBGP Interactive CLI                          ║
╚══════════════════════════════════════════════════════════╝

Type 'help' for available commands
Type 'exit' or press Ctrl+D/Ctrl+C to quit
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


def cmdline_interactive(pipename: str, socketname: str, use_pipe_transport: bool, cmdarg) -> int:
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
    import socket as sock

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
            except Exception as exc:
                return f'Error: {exc}'

        send_func = send_command_pipe
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

        def send_command_socket(command: str) -> str:
            """Send command via Unix socket and return response"""
            s = None
            try:
                # Expand shortcuts
                expanded = CommandShortcuts.expand_shortcuts(command)

                # Connect to socket
                s = sock.socket(sock.AF_UNIX, sock.SOCK_STREAM)
                s.settimeout(5.0)

                # Build full socket path
                full_socket_path = socket_path if socket_path.endswith('.sock') else socket_path + 'exabgp.sock'
                s.connect(full_socket_path)

                # Send command
                s.sendall((expanded + '\n').encode('utf-8'))

                # Receive response
                response_parts = []
                while True:
                    try:
                        data = s.recv(4096)
                        if not data:
                            break
                        response_parts.append(data.decode('utf-8'))

                        # Check for done marker
                        response = ''.join(response_parts)
                        if 'done' in response or 'error' in response:
                            break
                    except sock.timeout:
                        break
                    except Exception:
                        break

                return ''.join(response_parts).strip()
            except Exception as exc:
                return f'Error: {exc}'
            finally:
                if s:
                    try:
                        s.close()
                    except Exception:
                        pass

        send_func = send_command_socket

    # Create and run interactive CLI
    try:
        cli = InteractiveCLI(send_func)
        cli.run()
        return 0
    except Exception as exc:
        sys.stderr.write(f'CLI error: {exc}\n')
        sys.stderr.flush()
        return 1
