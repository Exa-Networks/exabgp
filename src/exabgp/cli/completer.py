"""command_completer.py

Tab completion for ExaBGP CLI commands using readline.

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import ctypes
import json
import re
import readline
import sys
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from exabgp.application.shortcuts import CommandShortcuts
from exabgp.cli.colors import Colors
from exabgp.cli.formatter import OutputFormatter
from exabgp.reactor.api.command.registry import CommandRegistry


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
        # Filter out commands not useful in interactive CLI:
        # - "#" (comment command - useful in scripts/API but not interactive)
        # - "show" (no subcommands after filtering neighbor/adj-rib - use new syntax)
        self.base_commands = [cmd for cmd in all_commands if cmd not in ('#', 'show')]
        # Add builtin CLI commands (not in registry)
        self.base_commands.extend(['exit', 'quit', 'q', 'clear', 'history', 'set'])
        # Add CLI-first keywords for discoverability:
        # - 'neighbor' for "neighbor <IP> show/announce/withdraw" syntax
        # - 'adj-rib' for "adj-rib <in|out> show" syntax
        self.base_commands.extend(['neighbor', 'adj-rib'])

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
        try:
            # Get the full line buffer to understand context
            line = readline.get_line_buffer()
            begin = readline.get_begidx()
            end = readline.get_endidx()

            # Parse the line into tokens
            # Note: "?" key is bound to rl_complete (same as TAB) so it triggers
            # completion without appearing in the line buffer
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

                # macOS libedit: Display all matches on first TAB/? press
                # (GNU readline has built-in display via show-all-if-ambiguous)
                if self.is_libedit and len(self.matches) > 1:
                    # Check if this is a new completion (avoid repeating on subsequent TABs)
                    current_line = readline.get_line_buffer()
                    if current_line != self.last_line or self.matches != self.last_matches:
                        # Display matches with descriptions
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
        except Exception:
            # If any exception occurs during completion (e.g., socket errors, JSON parsing),
            # silently fail and return no completions. This prevents readline from breaking.
            # Completion is a nice-to-have feature - don't let it crash the CLI.
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

        # If no tokens yet, complete base commands + display format prefix
        if not tokens:
            matches = []

            # Add display format prefixes (json/text) first
            if 'json'.startswith(text):
                matches.append('json')
                self._add_completion_metadata('json', 'Display output as JSON', 'option')
            if 'text'.startswith(text):
                matches.append('text')
                self._add_completion_metadata('text', 'Display output as text tables', 'option')

            # Add base commands
            for cmd in self.base_commands:
                if cmd.startswith(text):
                    matches.append(cmd)
                    desc = self.registry.get_command_description(cmd)
                    self._add_completion_metadata(cmd, desc, 'command')

            return sorted(matches)

        # Check if first token is display format prefix - if so, strip it for completion
        # Example: "json show" → complete as if tokens = ["show"]
        if tokens and tokens[0].lower() in ('json', 'text'):
            # Strip display prefix and complete normally
            if len(tokens) == 1:
                # Just "json " or "text " - suggest all base commands
                matches = []
                for cmd in self.base_commands:
                    if cmd.startswith(text):
                        matches.append(cmd)
                        desc = self.registry.get_command_description(cmd)
                        self._add_completion_metadata(cmd, desc, 'command')
                return sorted(matches)
            else:
                # "json show ..." - strip prefix and continue with rest
                tokens = tokens[1:]

        # Expand shortcuts in tokens using CommandShortcuts
        expanded_tokens = CommandShortcuts.expand_token_list(tokens.copy())

        # Handle "neighbor <ip> <command>" prefix transformations
        if len(expanded_tokens) >= 2 and expanded_tokens[0] == 'neighbor' and self._is_ip_address(expanded_tokens[1]):
            ip = expanded_tokens[1]

            # For "show", transform to "show neighbor <ip>" before completion
            if len(expanded_tokens) >= 3 and expanded_tokens[2] == 'show':
                # Transform: "neighbor 127.0.0.1 show ..." → "show neighbor 127.0.0.1 ..."
                rest = expanded_tokens[3:] if len(expanded_tokens) > 3 else []
                expanded_tokens = ['show', 'neighbor', ip] + rest

            # For "announce" and "withdraw", strip "neighbor <ip>" to complete at root level
            elif len(expanded_tokens) >= 3 and expanded_tokens[2] in ('announce', 'withdraw'):
                # Strip "neighbor <ip>" and continue completion from that command
                expanded_tokens = expanded_tokens[2:]

        # Handle "adj-rib" completions (CLI-first syntax)
        # Supports both: "adj-rib <in|out> show" and "neighbor <ip> adj-rib <in|out> show"
        adj_rib_idx = -1
        neighbor_ip = None

        # Check for "neighbor <ip> adj-rib" pattern
        if (
            len(expanded_tokens) >= 3
            and expanded_tokens[0] == 'neighbor'
            and self._is_ip_address(expanded_tokens[1])
            and expanded_tokens[2] == 'adj-rib'
        ):
            adj_rib_idx = 2
            neighbor_ip = expanded_tokens[1]
        # Check for "adj-rib" pattern
        elif len(expanded_tokens) >= 1 and expanded_tokens[0] == 'adj-rib':
            adj_rib_idx = 0

        if adj_rib_idx >= 0:
            tokens_after_adjrib = expanded_tokens[adj_rib_idx + 1 :]

            # If exactly "adj-rib" or "neighbor <ip> adj-rib", suggest "in" and "out"
            if len(tokens_after_adjrib) == 0:
                matches = []
                if 'in'.startswith(text):
                    matches.append('in')
                    self._add_completion_metadata('in', 'Adj-RIB-In (received routes)', 'option')
                if 'out'.startswith(text):
                    matches.append('out')
                    self._add_completion_metadata('out', 'Adj-RIB-Out (advertised routes)', 'option')
                return sorted(matches)

            # If "adj-rib <in|out>" or "neighbor <ip> adj-rib <in|out>", suggest "show"
            if len(tokens_after_adjrib) == 1 and tokens_after_adjrib[0] in ('in', 'out'):
                if 'show'.startswith(text):
                    self._add_completion_metadata('show', 'Show adj-rib information', 'command')
                    return ['show']
                return []

            # For "adj-rib <in|out> show" or "neighbor <ip> adj-rib <in|out> show", transform to API syntax
            if (
                len(tokens_after_adjrib) >= 2
                and tokens_after_adjrib[0] in ('in', 'out')
                and tokens_after_adjrib[1] == 'show'
            ):
                direction = tokens_after_adjrib[0]
                rest = tokens_after_adjrib[2:] if len(tokens_after_adjrib) > 2 else []

                # Transform based on whether neighbor IP is present:
                # "adj-rib in show ..." → "show adj-rib in ..."
                # "neighbor <ip> adj-rib in show ..." → "show adj-rib in <ip> ..."
                if neighbor_ip:
                    expanded_tokens = ['show', 'adj-rib', direction, neighbor_ip] + rest
                else:
                    expanded_tokens = ['show', 'adj-rib', direction] + rest

        # Check if we have "announce route <ip-prefix>" or "withdraw route <ip-prefix>"
        # In this case, suggest route attributes (next-hop, as-path, etc.)
        # This must come BEFORE _is_neighbor_command check (which would return base commands)
        if len(expanded_tokens) >= 3 and 'route' in expanded_tokens:
            try:
                route_idx = expanded_tokens.index('route')
                # Check if token after 'route' looks like IP/prefix
                if route_idx < len(expanded_tokens) - 1:
                    potential_prefix = expanded_tokens[route_idx + 1]
                    if self._is_ip_or_prefix(potential_prefix):
                        # We have "route <ip-prefix>", suggest route attributes
                        return self._complete_route_spec(expanded_tokens, text)
            except ValueError:
                pass

        # Special case: "announce route" - suggest "refresh" or "neighbor" keyword only
        # This must come BEFORE _is_neighbor_command check
        # Note: Do NOT suggest neighbor IPs here - they are for filtering and must come BEFORE "announce"
        # Correct syntax: "neighbor <IP> announce route <route-prefix> ..." NOT "announce route <neighbor-IP> ..."
        if len(expanded_tokens) >= 2 and expanded_tokens[-1] == 'route' and 'announce' in expanded_tokens:
            matches = []

            # Suggest "refresh" for "announce route refresh"
            if 'refresh'.startswith(text):
                matches.append('refresh')
                self._add_completion_metadata('refresh', 'Send route refresh request', 'command')

            # Suggest "neighbor" keyword for "neighbor <IP> announce route ..." filtering
            if 'neighbor'.startswith(text):
                matches.append('neighbor')
                desc = self.registry.get_option_description('neighbor')
                self._add_completion_metadata('neighbor', desc if desc else 'Target specific neighbor by IP', 'keyword')

            return sorted(matches)

        # Check if completing neighbor-targeted command
        if self._is_neighbor_command(expanded_tokens):
            return self._complete_neighbor_command(expanded_tokens, text)

        # Check for specific command patterns
        if len(expanded_tokens) >= 1:
            # Builtin CLI command: 'set encoding' / 'set display'
            if expanded_tokens[0] == 'set':
                if len(expanded_tokens) == 1:
                    # After 'set', suggest 'encoding' or 'display'
                    matches = []
                    if 'encoding'.startswith(text):
                        matches.append('encoding')
                        self._add_completion_metadata('encoding', 'Set API output encoding', 'option')
                    if 'display'.startswith(text):
                        matches.append('display')
                        self._add_completion_metadata('display', 'Set display format', 'option')
                    return matches
                elif len(expanded_tokens) == 2:
                    setting = expanded_tokens[1]
                    if setting in ('encoding', 'display'):
                        # After 'set encoding' or 'set display', suggest 'json' or 'text'
                        matches = []
                        if 'json'.startswith(text):
                            matches.append('json')
                            desc = 'JSON encoding' if setting == 'encoding' else 'Show raw JSON'
                            self._add_completion_metadata('json', desc, 'option')
                        if 'text'.startswith(text):
                            matches.append('text')
                            desc = 'Text encoding' if setting == 'encoding' else 'Format as tables'
                            self._add_completion_metadata('text', desc, 'option')
                        return matches
                # 'set' with other tokens - no more completions
                return []

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

                # Only add neighbor IPs if one isn't already specified
                # Example: "show neighbor" → suggest IPs, but "show neighbor 127.0.0.1" → don't suggest IPs again
                ip_already_specified = len(expanded_tokens) >= 3 and self._is_ip_address(expanded_tokens[2])

                if not ip_already_specified:
                    # Add neighbor IPs with descriptions
                    for ip, info in neighbor_data.items():
                        if ip.startswith(text):
                            matches.append(ip)
                            self._add_completion_metadata(ip, info, 'neighbor')

                return sorted(matches)

            # AFI/SAFI completion for eor and route refresh
            if expanded_tokens[-1] in ('eor', 'refresh'):
                # Check if this is "announce route refresh" or similar
                if len(expanded_tokens) >= 2 and expanded_tokens[-2] == 'route':
                    return self._complete_afi_safi(expanded_tokens, text)
                elif expanded_tokens[-1] == 'eor':
                    return self._complete_afi_safi(expanded_tokens, text)

            # Route specification hints - but NOT for withdraw route
            # (user needs to type IP/prefix first before any attributes)
            if expanded_tokens[-1] in ('route', 'ipv4', 'ipv6'):
                # Check if this is "withdraw route" or "neighbor X withdraw route"
                if expanded_tokens[-1] == 'route':
                    # Look backwards for "withdraw" command (but not "announce" - handled above)
                    if 'withdraw' in expanded_tokens:
                        # Don't auto-complete after withdraw route commands
                        # User must type IP/prefix first
                        return []
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

                    # Filter out legacy hyphenated commands
                    if 'announce' in expanded_tokens[:i]:
                        matches = [m for m in matches if m != 'route-refresh']

                    # Filter out 'neighbor' and 'adj-rib' after 'show' - use new syntax instead
                    if i == 1 and expanded_tokens[0] == 'show':
                        matches = [m for m in matches if m not in ('neighbor', 'adj-rib')]

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

            # Filter out legacy hyphenated commands (e.g., "route-refresh" when "route" exists)
            # This keeps CLI clean and user-friendly
            filtered_matches = []
            for match in matches:
                # Skip if this is a hyphenated command and we have "announce route" in context
                if '-' in match and 'announce' in expanded_tokens:
                    # Check if this is "route-refresh" - skip it
                    if match == 'route-refresh':
                        continue
                # Filter out 'neighbor' and 'adj-rib' after 'show' - use new syntax instead
                if match in ('neighbor', 'adj-rib') and len(expanded_tokens) == 1 and expanded_tokens[0] == 'show':
                    continue
                filtered_matches.append(match)
            matches = filtered_matches

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

        # If last token is an IP, suggest: announce, withdraw, show, adj-rib
        # "show" will be rewritten to "show neighbor <ip>" before sending to API
        # "adj-rib" allows "neighbor <ip> adj-rib <in|out> show" syntax
        if self._is_ip_address(last_token):
            matches = []

            # Commands valid after "neighbor <ip>"
            allowed_commands = ['announce', 'withdraw', 'show', 'adj-rib']

            for cmd in allowed_commands:
                if cmd.startswith(text):
                    matches.append(cmd)
                    desc = self.registry.get_command_description(cmd)
                    self._add_completion_metadata(cmd, desc if desc else '', 'command')

            return sorted(matches)

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
        """Complete AFI/SAFI values for eor and route refresh"""
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

    def _is_ip_or_prefix(self, token: str) -> bool:
        """Check if token looks like an IP address or CIDR prefix"""
        # Check for IPv4/prefix (e.g., 1.2.3.4 or 10.0.0.0/24)
        ipv4_pattern = r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(/\d{1,2})?$'
        # Check for IPv6/prefix (e.g., 2001:db8::1 or 2001:db8::/32)
        ipv6_pattern = r'^[0-9a-fA-F:]+(/\d{1,3})?$'
        return bool(re.match(ipv4_pattern, token) or ((':' in token) and re.match(ipv6_pattern, token)))

    def _get_neighbor_ips(self) -> List[str]:
        """
        Get list of neighbor IPs for completion (with caching)

        Returns:
            List of neighbor IP addresses
        """
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
                except (json.JSONDecodeError, ValueError, OSError):
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
        except (json.JSONDecodeError, ValueError, OSError):
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
