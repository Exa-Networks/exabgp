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
from typing import Any, Callable

from exabgp.application.shortcuts import CommandShortcuts
from exabgp.cli.colors import Colors
from exabgp.cli.command_schema import get_command_spec
from exabgp.cli.formatter import OutputFormatter
from exabgp.cli.fuzzy import FuzzyMatcher
from exabgp.cli.schema_bridge import ValueTypeCompletionEngine, ValidationState
from exabgp.reactor.api.command.registry import CommandRegistry


@dataclass
class CompletionItem:
    """Metadata for a single completion item"""

    value: str  # The actual completion text
    description: str | None = None  # Human-readable description
    item_type: str = 'option'  # Type: 'option', 'neighbor', 'command', 'keyword'
    syntax_hint: str | None = None  # Syntax hint (e.g., '<ip>', 'IGP|EGP|INCOMPLETE')
    example: str | None = None  # Example value (e.g., '192.0.2.1')


class CommandCompleter:
    """Tab completion for ExaBGP commands using readline with dynamic command discovery"""

    def __init__(
        self,
        send_command: Callable[[str], str],
        get_neighbors: Callable[[], list[str]] | None = None,
        history_tracker: Any | None = None,
    ):
        """
        Initialize completer

        Args:
            send_command: Function to send commands to ExaBGP
            get_neighbors: Optional function to fetch neighbor IPs for completion
            history_tracker: Optional HistoryTracker for smart completion ranking
        """
        self.send_command = send_command
        self.get_neighbors = get_neighbors
        self.history_tracker = history_tracker
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
        # Add noun-first top-level commands
        self.base_commands.extend(['daemon', 'session', 'system', 'rib'])

        # Cache for neighbor IPs
        self._neighbor_cache: list[str] | None = None
        self._cache_timeout = 300  # Refresh cache every 5 minutes (avoid repeated socket calls)
        self._cache_timestamp: float = 0
        self._cache_in_progress = False  # Prevent concurrent queries

        # Track state for single-TAB display on macOS libedit
        self.matches: list[str] = []
        self.match_metadata: dict[str, CompletionItem] = {}  # Map completion value to metadata
        self.is_libedit = 'libedit' in readline.__doc__
        self.last_line = ''
        self.last_matches: list[str] = []

        # Try to get access to readline's rl_replace_line for line editing
        self._rl_replace_line = self._get_rl_replace_line()
        self._rl_forced_update_display = self._get_rl_forced_update_display()

        # Initialize new completion engines
        # Create frequency provider dict-like wrapper for fuzzy matcher
        class FrequencyProvider:
            """Dict-like wrapper for history tracker"""

            def __init__(self, tracker):
                self.tracker = tracker

            def get(self, command: str, default: int = 0) -> int:
                if self.tracker:
                    # Convert total bonus (0-100) to frequency count (0-10) for scoring
                    return self.tracker.get_total_bonus(command) // 10
                return default

        freq_provider = FrequencyProvider(self.history_tracker) if self.history_tracker else {}
        self.fuzzy_matcher = FuzzyMatcher(frequency_provider=freq_provider)
        self.schema_engine = ValueTypeCompletionEngine()

    def _get_rl_replace_line(self) -> Callable | None:
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

    def _get_rl_forced_update_display(self) -> Callable | None:
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

    def _is_help_mode(self, line: str, text: str) -> bool:
        """Detect if user is requesting help (line ends with '?').

        Args:
            line: Full line buffer
            text: Current word being completed

        Returns:
            True if help mode requested
        """
        # Check if line ends with '?' (user typed '?' to trigger help)
        # The '?' won't be in the line buffer since it's bound to rl_complete,
        # so we check if text is '?' or line ends with ' ?'
        return text == '?' or line.rstrip().endswith('?')

    def complete(self, text: str, state: int) -> str | None:
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

            # Check if user is requesting help
            show_help = self._is_help_mode(line, text)

            # Remove '?' from text if present for completion matching
            if text == '?':
                text = ''

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
                        # Display matches with descriptions (and help if requested)
                        self._display_matches_and_redraw(self.matches, line, show_help=show_help)
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

    def _try_auto_expand_tokens(self, tokens: list[str]) -> tuple[list[str], bool]:
        """
        Auto-expand unambiguous partial tokens

        IMPORTANT: Uses ONLY exact prefix matching, not fuzzy matching.
        Fuzzy matches are not suitable for auto-expansion because they
        can be ambiguous or unexpected.

        Args:
            tokens: List of tokens to potentially expand

        Returns:
            Tuple of (expanded_tokens, expansions_made)
        """
        if not tokens:
            return ([], False)

        # Build expanded tokens by checking each token for unambiguous completion
        expanded_tokens = []
        current_context: list[str] = []  # Tokens we've processed so far
        expansions_made = False

        for token in tokens:
            # Get completions for this token in the current context
            # IMPORTANT: _get_completions will try fuzzy if no exact matches,
            # but we only want to auto-expand on exact prefix matches.
            # So we need to check if there's exactly one exact prefix match.
            completions = self._get_completions(current_context, token)

            # Filter to only exact prefix matches
            exact_matches = [c for c in completions if c.lower().startswith(token.lower())]

            # If exactly one exact match and it's different from the token, expand it
            if len(exact_matches) == 1 and exact_matches[0] != token:
                expanded_tokens.append(exact_matches[0])
                current_context.append(exact_matches[0])
                expansions_made = True
            else:
                # Multiple completions or exact match - keep as is
                expanded_tokens.append(token)
                current_context.append(token)

        return (expanded_tokens, expansions_made)

    def _display_matches_and_redraw(self, matches: list[str], current_line: str, show_help: bool = False) -> None:
        """Display completion matches with descriptions (one per line) and redraw the prompt.

        Args:
            matches: List of completion matches
            current_line: Current input line
            show_help: If True, show extended syntax hints and examples
        """
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

                # Show extended help if requested
                if show_help and metadata and hasattr(metadata, 'syntax_hint'):
                    if metadata.syntax_hint:
                        sys.stdout.write(f'           {Colors.DIM}Syntax: {Colors.RESET}')
                        sys.stdout.write(f'{Colors.CYAN}{metadata.syntax_hint}{Colors.RESET}\n')
                if show_help and metadata and hasattr(metadata, 'example'):
                    if metadata.example:
                        sys.stdout.write(f'           {Colors.DIM}Example: {Colors.RESET}')
                        sys.stdout.write(f'{Colors.CYAN}{metadata.example}{Colors.RESET}\n')
            else:
                # No color
                if desc_str:
                    sys.stdout.write(f'{value_str}{desc_str}\n')
                else:
                    sys.stdout.write(f'{match}\n')

                # Show extended help if requested (no color)
                if show_help and metadata:
                    if hasattr(metadata, 'syntax_hint') and metadata.syntax_hint:
                        sys.stdout.write(f'           Syntax: {metadata.syntax_hint}\n')
                    if hasattr(metadata, 'example') and metadata.example:
                        sys.stdout.write(f'           Example: {metadata.example}\n')

        # Redraw the prompt and current input
        formatter = OutputFormatter()
        prompt = formatter.format_prompt()

        sys.stdout.write(prompt + current_line)
        sys.stdout.flush()

    def _add_completion_metadata(
        self,
        value: str,
        description: str | None = None,
        item_type: str = 'option',
        syntax_hint: str | None = None,
        example: str | None = None,
    ) -> None:
        """Add metadata for a completion item.

        Args:
            value: Completion value
            description: Human-readable description
            item_type: Type of completion (option/neighbor/command/keyword)
            syntax_hint: Syntax hint (e.g., '<ip>', 'IGP|EGP|INCOMPLETE')
            example: Example value (e.g., '192.0.2.1')
        """
        self.match_metadata[value] = CompletionItem(
            value=value,
            description=description,
            item_type=item_type,
            syntax_hint=syntax_hint,
            example=example,
        )

    def _filter_candidates(self, candidates: list[str], text: str, use_fuzzy: bool = True) -> list[str]:
        """Filter candidates using exact prefix or fuzzy matching.

        Args:
            candidates: List of candidate strings to filter
            text: Partial text to match against
            use_fuzzy: If True, use fuzzy matching when no exact matches found

        Returns:
            List of matching candidates, sorted by relevance

        Strategy:
            1. Try exact prefix matches first (highest priority)
            2. If no exact matches and fuzzy enabled, try fuzzy matching
            3. Sort results by score (exact prefix matches automatically score highest)
        """
        if not text:
            # Empty query returns all candidates (alphabetical)
            return sorted(candidates)

        # Phase 1: Try exact prefix matches
        exact_matches = [c for c in candidates if c.lower().startswith(text.lower())]

        if exact_matches:
            # Return exact matches sorted alphabetically
            return sorted(exact_matches)

        # Phase 2: Fuzzy matching (if enabled and no exact matches)
        if use_fuzzy:
            # Check environment variable for fuzzy matching control
            import os

            fuzzy_enabled = os.environ.get('exabgp_cli_fuzzy_matching', 'true').lower()
            if fuzzy_enabled in ('false', '0', 'no'):
                return []

            # Use fuzzy matcher
            matches = self.fuzzy_matcher.get_matches(text, candidates, limit=10)
            return [m.candidate for m in matches]

        # No matches
        return []

    def _get_completions(self, tokens: list[str], text: str) -> list[str]:
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
            # Collect all candidates
            display_formats = ['json', 'text']
            all_candidates = display_formats + self.base_commands

            # Use fuzzy filtering
            matches = self._filter_candidates(all_candidates, text)

            # Add metadata for matches
            for match in matches:
                if match == 'json':
                    self._add_completion_metadata('json', 'Display output as JSON', 'option')
                elif match == 'text':
                    self._add_completion_metadata('text', 'Display output as text tables', 'option')
                else:
                    desc = self.registry.get_command_description(match)
                    self._add_completion_metadata(match, desc, 'command')

            return matches  # Already sorted by _filter_candidates

        # Check if first token is display format prefix - if so, strip it for completion
        # Example: "json show" → complete as if tokens = ["show"]
        if tokens and tokens[0].lower() in ('json', 'text'):
            # Strip display prefix and complete normally
            if len(tokens) == 1:
                # Just "json " or "text " - suggest all base commands with fuzzy matching
                matches = self._filter_candidates(self.base_commands, text)
                for match in matches:
                    desc = self.registry.get_command_description(match)
                    self._add_completion_metadata(match, desc, 'command')
                return matches
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

        # Handle noun-first command completions
        if len(expanded_tokens) >= 1:
            first_token = expanded_tokens[0]

            # Daemon commands: daemon <shutdown|reload|restart|status>
            if first_token == 'daemon':
                if len(expanded_tokens) == 1:
                    candidates = ['shutdown', 'reload', 'restart', 'status']
                    matches = self._filter_candidates(candidates, text)
                    for match in matches:
                        desc = {
                            'shutdown': 'Shutdown ExaBGP daemon',
                            'reload': 'Reload configuration',
                            'restart': 'Restart daemon',
                            'status': 'Show daemon status',
                        }.get(match, '')
                        self._add_completion_metadata(match, desc, 'command')
                    return matches

            # Session commands: session <ack|sync|reset|ping|bye>
            elif first_token == 'session':
                if len(expanded_tokens) == 1:
                    candidates = ['ack', 'sync', 'reset', 'ping', 'bye']
                    matches = self._filter_candidates(candidates, text)
                    for match in matches:
                        desc = {
                            'ack': 'Manage acknowledgment responses',
                            'sync': 'Manage sync mode',
                            'reset': 'Reset async queue',
                            'ping': 'Health check',
                            'bye': 'Disconnect',
                        }.get(match, '')
                        self._add_completion_metadata(match, desc, 'command')
                    return matches
                elif len(expanded_tokens) == 2:
                    # session ack <enable|disable|silence>
                    if expanded_tokens[1] == 'ack':
                        candidates = ['enable', 'disable', 'silence']
                        matches = self._filter_candidates(candidates, text)
                        for match in matches:
                            desc = {
                                'enable': 'Enable ACK responses',
                                'disable': 'Disable ACK responses',
                                'silence': 'Silence ACK permanently',
                            }.get(match, '')
                            self._add_completion_metadata(match, desc, 'option')
                        return matches
                    # session sync <enable|disable>
                    elif expanded_tokens[1] == 'sync':
                        candidates = ['enable', 'disable']
                        matches = self._filter_candidates(candidates, text)
                        for match in matches:
                            desc = {
                                'enable': 'Enable sync mode',
                                'disable': 'Disable sync mode',
                            }.get(match, '')
                            self._add_completion_metadata(match, desc, 'option')
                        return matches

            # RIB commands: rib <show|flush|clear>
            elif first_token == 'rib':
                if len(expanded_tokens) == 1:
                    candidates = ['show', 'flush', 'clear']
                    matches = self._filter_candidates(candidates, text)
                    for match in matches:
                        desc = {
                            'show': 'Show RIB entries',
                            'flush': 'Flush RIB entries',
                            'clear': 'Clear RIB entries',
                        }.get(match, '')
                        self._add_completion_metadata(match, desc, 'command')
                    return matches
                elif len(expanded_tokens) == 2:
                    # rib show <in|out>
                    if expanded_tokens[1] == 'show':
                        candidates = ['in', 'out']
                        matches = self._filter_candidates(candidates, text)
                        for match in matches:
                            desc = {'in': 'Adj-RIB-In (received)', 'out': 'Adj-RIB-Out (advertised)'}.get(match, '')
                            self._add_completion_metadata(match, desc, 'option')
                        return matches
                    # rib flush <out>
                    elif expanded_tokens[1] == 'flush':
                        candidates = ['out']
                        matches = self._filter_candidates(candidates, text)
                        self._add_completion_metadata('out', 'Flush outbound RIB', 'option')
                        return matches
                    # rib clear <in|out>
                    elif expanded_tokens[1] == 'clear':
                        candidates = ['in', 'out']
                        matches = self._filter_candidates(candidates, text)
                        for match in matches:
                            desc = {'in': 'Clear inbound RIB', 'out': 'Clear outbound RIB'}.get(match, '')
                            self._add_completion_metadata(match, desc, 'option')
                        return matches

            # System commands: system <help|version|crash>
            elif first_token == 'system':
                if len(expanded_tokens) == 1:
                    candidates = ['help', 'version', 'crash']
                    matches = self._filter_candidates(candidates, text)
                    for match in matches:
                        desc = {
                            'help': 'Show available commands',
                            'version': 'Show ExaBGP version',
                            'crash': 'Crash daemon (debug only)',
                        }.get(match, '')
                        self._add_completion_metadata(match, desc, 'command')
                    return matches

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
                candidates = ['in', 'out']
                matches = self._filter_candidates(candidates, text)
                for match in matches:
                    if match == 'in':
                        self._add_completion_metadata('in', 'Adj-RIB-In (received routes)', 'option')
                    elif match == 'out':
                        self._add_completion_metadata('out', 'Adj-RIB-Out (advertised routes)', 'option')
                return matches

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
            # Builtin CLI command: 'set encoding' / 'set display' / 'set sync'
            if expanded_tokens[0] == 'set':
                if len(expanded_tokens) == 1:
                    # After 'set', suggest 'encoding', 'display', or 'sync'
                    candidates = ['encoding', 'display', 'sync']
                    matches = self._filter_candidates(candidates, text)
                    for match in matches:
                        if match == 'encoding':
                            self._add_completion_metadata('encoding', 'Set API output encoding', 'option')
                        elif match == 'display':
                            self._add_completion_metadata('display', 'Set display format', 'option')
                        elif match == 'sync':
                            self._add_completion_metadata('sync', 'Set sync mode for announce/withdraw', 'option')
                    return matches
                elif len(expanded_tokens) == 2:
                    setting = expanded_tokens[1]
                    if setting in ('encoding', 'display'):
                        # After 'set encoding' or 'set display', suggest 'json' or 'text'
                        candidates = ['json', 'text']
                        matches = self._filter_candidates(candidates, text)
                        for match in matches:
                            if match == 'json':
                                desc = 'JSON encoding' if setting == 'encoding' else 'Show raw JSON'
                                self._add_completion_metadata('json', desc, 'option')
                            elif match == 'text':
                                desc = 'Text encoding' if setting == 'encoding' else 'Format as tables'
                                self._add_completion_metadata('text', desc, 'option')
                        return matches
                    elif setting == 'sync':
                        # After 'set sync', suggest 'on' or 'off'
                        candidates = ['on', 'off']
                        matches = self._filter_candidates(candidates, text)
                        for match in matches:
                            if match == 'on':
                                self._add_completion_metadata('on', 'Wait for routes on wire before ACK', 'option')
                            elif match == 'off':
                                self._add_completion_metadata('off', 'Return ACK immediately (default)', 'option')
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

                # Filter options with fuzzy matching
                option_matches = self._filter_candidates(options, text)
                for opt in option_matches:
                    desc = self.registry.get_option_description(opt)
                    self._add_completion_metadata(opt, desc, 'option')

                # Only add neighbor IPs if one isn't already specified
                # Example: "show neighbor" → suggest IPs, but "show neighbor 127.0.0.1" → don't suggest IPs again
                ip_already_specified = len(expanded_tokens) >= 3 and self._is_ip_address(expanded_tokens[2])

                if not ip_already_specified:
                    # Filter neighbor IPs with fuzzy matching
                    neighbor_ips = list(neighbor_data.keys())
                    ip_matches = self._filter_candidates(neighbor_ips, text)
                    for ip in ip_matches:
                        info = neighbor_data[ip]
                        self._add_completion_metadata(ip, info, 'neighbor')

                # Combine options and IPs (both already sorted by _filter_candidates)
                all_matches = option_matches + ip_matches if not ip_already_specified else option_matches
                return all_matches

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

    def _is_neighbor_command(self, tokens: list[str]) -> bool:
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

    def _complete_neighbor_command(self, tokens: list[str], text: str) -> list[str]:
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

    def _complete_neighbor_filters(self, text: str) -> list[str]:
        """Complete neighbor filter keywords"""
        filters = self.registry.get_neighbor_filters()
        matches = sorted([f for f in filters if f.startswith(text)])
        # Add descriptions for filter keywords
        for match in matches:
            desc = self.registry.get_option_description(match)
            self._add_completion_metadata(match, desc, 'keyword')
        return matches

    def _complete_afi_safi(self, tokens: list[str], text: str) -> list[str]:
        """Complete AFI/SAFI values for eor and route refresh with schema support.

        Uses schema validation to provide accurate choices for enumeration types.
        """
        # Get AFI values first, then SAFI
        afi_values = self.registry.get_afi_values()

        # Check if we've already typed an AFI
        potential_afi = tokens[-2] if len(tokens) >= 2 and tokens[-2] in afi_values else None

        if potential_afi:
            # Complete SAFI for the given AFI - use fuzzy matching
            safi_values = self.registry.get_safi_values(potential_afi)
            matches = self._filter_candidates(safi_values, text)

            # Add descriptions for SAFI values
            for match in matches:
                # Try to get better description from schema
                desc = f'SAFI for {potential_afi}'

                # Check if this is part of announce eor/route-refresh
                if 'eor' in tokens or 'refresh' in tokens:
                    cmd_name = 'announce eor' if 'eor' in tokens else 'announce route-refresh'
                    cmd_spec = get_command_spec(cmd_name)
                    if cmd_spec and 'safi' in cmd_spec.arguments:
                        safi_spec = cmd_spec.arguments['safi']
                        if safi_spec.description:
                            desc = safi_spec.description

                self._add_completion_metadata(match, desc, 'keyword')
            return matches
        else:
            # Complete AFI - use fuzzy matching
            matches = self._filter_candidates(afi_values, text)

            # Add descriptions for AFI values
            for match in matches:
                # Try to get better description from schema
                desc = 'Address Family Identifier'

                # Check if this is part of announce eor/route-refresh
                if 'eor' in tokens or 'refresh' in tokens:
                    cmd_name = 'announce eor' if 'eor' in tokens else 'announce route-refresh'
                    cmd_spec = get_command_spec(cmd_name)
                    if cmd_spec and 'afi' in cmd_spec.arguments:
                        afi_spec = cmd_spec.arguments['afi']
                        if afi_spec.description:
                            desc = afi_spec.description
                            # Add examples if available
                            if afi_spec.examples and match in afi_spec.examples:
                                desc += f' (e.g., {match})'

                self._add_completion_metadata(match, desc, 'keyword')
            return matches

    def _complete_route_spec(self, tokens: list[str], text: str) -> list[str]:
        """Complete route specification keywords with schema-based validation.

        Validates the route prefix if present and provides attribute suggestions
        based on the command schema.
        """
        # Get route keywords from registry (legacy approach)
        keywords = self.registry.get_route_keywords()

        # Try to get command spec for enhanced metadata
        command_name = None
        if 'announce' in tokens and 'route' in tokens:
            command_name = 'announce route'
        elif 'withdraw' in tokens and 'route' in tokens:
            command_name = 'withdraw route'

        # If we have a command spec, use it to provide better descriptions
        if command_name:
            cmd_spec = get_command_spec(command_name)
            if cmd_spec:
                # Find the route prefix (token after 'route')
                try:
                    route_idx = tokens.index('route')
                    if route_idx < len(tokens) - 1:
                        prefix = tokens[route_idx + 1]

                        # Validate the prefix using schema engine
                        from exabgp.configuration.schema import ValueType

                        result = self.schema_engine.validate_value(ValueType.IP_PREFIX, prefix, allow_partial=False)

                        # If prefix is invalid, show error (but continue with completion)
                        if result.state == ValidationState.INVALID:
                            # Still provide completions, but user will see error if they try to execute
                            pass
                except (ValueError, IndexError):
                    pass

                # Use fuzzy filtering for keywords
                matches = self._filter_candidates(keywords, text)

                # Add descriptions from schema where available
                for match in matches:
                    if match in cmd_spec.options:
                        value_spec = cmd_spec.options[match]
                        desc = value_spec.description

                        # Get syntax hint from schema engine
                        syntax_hint = self.schema_engine.get_syntax_help(
                            value_spec.value_type, include_description=False
                        )

                        # Get example (prefer from spec, fallback to schema engine)
                        example = None
                        if value_spec.examples:
                            example = value_spec.examples[0]
                        else:
                            example = self.schema_engine.get_example_value(value_spec.value_type)

                        self._add_completion_metadata(match, desc, 'keyword', syntax_hint=syntax_hint, example=example)
                    else:
                        # Fallback to generic description
                        desc = 'Route specification parameter'
                        self._add_completion_metadata(match, desc, 'keyword')

                return matches

        # Fallback: no schema available, use legacy approach with fuzzy matching
        matches = self._filter_candidates(keywords, text)
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

    def _get_neighbor_ips(self) -> list[str]:
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

    def _get_neighbor_data(self) -> dict[str, str]:
        """
        Get neighbor IPs with descriptions (AS, state) for completion

        Returns:
            Dict mapping neighbor IP to description string
        """
        neighbor_data: dict[str, str] = {}

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
