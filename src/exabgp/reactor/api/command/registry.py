"""registry.py

Command registry introspection and metadata system for auto-completion and documentation.

Created on 2025-11-20.
Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Any, ClassVar

from exabgp.reactor.api.command.command import Command


@dataclass
class CommandMetadata:
    """Structured metadata for a command."""

    name: str
    neighbor_support: bool
    json_support: bool
    options: List[str] | None = None
    description: str = ''
    syntax: str = ''
    parameters: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    shortcuts: List[str] = field(default_factory=list)
    category: str = 'general'

    def __post_init__(self):
        """Generate default syntax if not provided."""
        if not self.syntax:
            self.syntax = self._generate_syntax()

    def _generate_syntax(self) -> str:
        """Generate command syntax from name and options."""
        syntax = self.name
        if self.neighbor_support:
            syntax = f'[neighbor <ip> [filters]] {syntax}'
        if self.options:
            opts = ' '.join(f'[{opt}]' for opt in self.options)
            syntax = f'{syntax} {opts}'
        return syntax


class CommandRegistry:
    """Registry for introspecting and querying available commands."""

    # AFI values for completion
    AFI_NAMES: ClassVar[List[str]] = ['ipv4', 'ipv6', 'l2vpn', 'bgp-ls']

    # SAFI values for completion (from exabgp.protocol.family)
    SAFI_NAMES: ClassVar[List[str]] = [
        'unicast',
        'multicast',
        'nlri-mpls',
        'vpls',
        'evpn',
        'bgp-ls',
        'bgp-ls-vpn',
        'mup',
        'mpls-vpn',
        'mcast-vpn',
        'rtc',
        'flow',
        'flow-vpn',
    ]

    # AFI-specific SAFI values (from AFI.implemented_safi)
    AFI_SAFI_MAP: ClassVar[Dict[str, List[str]]] = {
        'ipv4': ['unicast', 'multicast', 'nlri-mpls', 'mcast-vpn', 'mpls-vpn', 'flow', 'flow-vpn', 'mup'],
        'ipv6': ['unicast', 'mpls-vpn', 'mcast-vpn', 'flow', 'flow-vpn', 'mup'],
        'l2vpn': ['vpls', 'evpn'],
        'bgp-ls': ['bgp-ls', 'bgp-ls-vpn'],
    }

    # Neighbor filter keywords
    # 'id' is the CLI keyword (expands to 'router-id' for API compatibility)
    # 'router-id' removed from autocomplete to avoid clash with 'route' command
    NEIGHBOR_FILTERS: ClassVar[List[str]] = ['local-ip', 'local-as', 'peer-as', 'id', 'family-allowed']

    # Route specification keywords
    ROUTE_KEYWORDS: ClassVar[List[str]] = [
        'next-hop',
        'as-path',
        'community',
        'extended-community',
        'large-community',
        'local-preference',
        'med',
        'origin',
        'aigp',
        'originator-id',
        'cluster-list',
        'label',
        'rd',
        'route-distinguisher',
        'path-information',
        'split',
        'watchdog',
        'withdraw',
    ]

    # Command categories for organization
    CATEGORIES: ClassVar[Dict[str, str]] = {
        'show neighbor': 'show',
        'show adj-rib in': 'show',
        'show adj-rib out': 'show',
        'announce route': 'announce',
        'announce ipv4': 'announce',
        'announce ipv6': 'announce',
        'announce vpls': 'announce',
        'announce flow': 'announce',
        'announce attribute': 'announce',
        'announce attributes': 'announce',
        'announce eor': 'announce',
        'announce route-refresh': 'announce',
        'announce operational': 'announce',
        'announce watchdog': 'announce',
        'withdraw route': 'withdraw',
        'withdraw ipv4': 'withdraw',
        'withdraw ipv6': 'withdraw',
        'withdraw vpls': 'withdraw',
        'withdraw flow': 'withdraw',
        'withdraw attribute': 'withdraw',
        'withdraw attributes': 'withdraw',
        'withdraw watchdog': 'withdraw',
        'flush adj-rib out': 'rib',
        'clear adj-rib in': 'rib',
        'clear adj-rib out': 'rib',
        'teardown': 'control',
        'help': 'control',
        'version': 'control',
        'shutdown': 'control',
        'reload': 'control',
        'restart': 'control',
        'reset': 'control',
        'enable-ack': 'control',
        'disable-ack': 'control',
        'silence-ack': 'control',
    }

    # Option descriptions for auto-completion help
    OPTION_DESCRIPTIONS: ClassVar[Dict[str, str]] = {
        'summary': 'Brief neighbor status',
        'extensive': 'Detailed neighbor information',
        'configuration': 'Show neighbor configuration',
        'json': 'JSON-formatted output',
        'neighbor': 'Target specific neighbor by IP',
        'in': 'Adj-RIB-In (received routes)',
        'out': 'Adj-RIB-Out (advertised routes)',
        'ipv4': 'IPv4 address family',
        'ipv6': 'IPv6 address family',
        'unicast': 'Unicast SAFI',
        'multicast': 'Multicast SAFI',
        'vpn': 'VPN SAFI',
        'flowspec': 'FlowSpec SAFI',
        'route': 'Route prefix/NLRI',
        'next-hop': 'Next-hop IP address',
        'as-path': 'AS path attribute',
        'local-preference': 'Local preference value',
        'med': 'Multi-Exit Discriminator',
        'community': 'BGP community',
        'id': 'Router ID filter (shortcut for router-id)',
        'router-id': 'Router ID filter',
        'local-ip': 'Local IP filter',
        'local-as': 'Local AS number filter',
        'peer-as': 'Peer AS number filter',
        'family-allowed': 'Address family filter',
    }

    def __init__(self):
        """Initialize the command registry."""
        self._metadata_cache: Dict[str, CommandMetadata] = {}

    def get_all_commands(self) -> List[str]:
        """Return list of all registered command names."""
        return list(Command.functions)

    def get_command_metadata(self, command_name: str) -> CommandMetadata | None:
        """Get metadata for a specific command."""
        if command_name in self._metadata_cache:
            return self._metadata_cache[command_name]

        # Check if command exists
        if command_name not in Command.callback['text']:
            return None

        # Build metadata from Command.callback
        metadata = CommandMetadata(
            name=command_name,
            neighbor_support=Command.callback['neighbor'].get(command_name, True),
            json_support=command_name in Command.callback['json'],
            options=Command.callback['options'].get(command_name),
            category=self.CATEGORIES.get(command_name, 'general'),
        )

        self._metadata_cache[command_name] = metadata
        return metadata

    def get_commands_by_category(self, category: str) -> List[CommandMetadata]:
        """Get all commands in a specific category."""
        commands = []
        for cmd_name in self.get_all_commands():
            metadata = self.get_command_metadata(cmd_name)
            if metadata and metadata.category == category:
                commands.append(metadata)
        return commands

    def get_base_commands(self) -> List[str]:
        """Get base commands (first word of each command)."""
        base_commands = set()
        for cmd in self.get_all_commands():
            base = cmd.split()[0]
            base_commands.add(base)
        return sorted(base_commands)

    def get_subcommands(self, prefix: str) -> List[str]:
        """Get all subcommands that start with the given prefix."""
        subcommands = []
        for cmd in self.get_all_commands():
            if cmd.startswith(prefix + ' '):
                # Extract the part after the prefix
                remainder = cmd[len(prefix) + 1 :]
                # Get the first word after the prefix
                next_word = remainder.split()[0] if remainder else None
                if next_word and next_word not in subcommands:
                    subcommands.append(next_word)
        return sorted(subcommands)

    def get_afi_values(self) -> List[str]:
        """Get all valid AFI values for completion."""
        return self.AFI_NAMES.copy()

    def get_safi_values(self, afi: str | None = None) -> List[str]:
        """Get all valid SAFI values, optionally filtered by AFI."""
        if afi and afi in self.AFI_SAFI_MAP:
            return self.AFI_SAFI_MAP[afi].copy()
        return self.SAFI_NAMES.copy()

    def get_neighbor_filters(self) -> List[str]:
        """Get all valid neighbor filter keywords."""
        return self.NEIGHBOR_FILTERS.copy()

    def get_route_keywords(self) -> List[str]:
        """Get all valid route specification keywords."""
        return self.ROUTE_KEYWORDS.copy()

    def build_command_tree(self) -> Dict[str, Any]:
        """Build a hierarchical command tree for auto-completion.

        Returns a nested dictionary where keys are command parts and values are
        either dictionaries (for further nesting) or lists (for terminal options).
        """
        tree: Dict[str, Any] = {}

        for cmd_name in self.get_all_commands():
            metadata = self.get_command_metadata(cmd_name)
            if not metadata:
                continue

            # Split command into parts
            parts = cmd_name.split()

            # Navigate/create tree structure
            current = tree
            for part in parts:
                if part not in current:
                    current[part] = {}
                current = current[part]

            # At the leaf, store options if available
            if metadata.options:
                current['__options__'] = metadata.options
            else:
                current['__options__'] = []

        return tree

    def format_command_help(self, command_name: str) -> str:
        """Format help text for a command."""
        metadata = self.get_command_metadata(command_name)
        if not metadata:
            return f'Unknown command: {command_name}'

        lines = []
        lines.append(f'Command: {metadata.name}')
        lines.append(f'Syntax:  {metadata.syntax}')

        if metadata.description:
            lines.append(f'Description: {metadata.description}')

        if metadata.options:
            lines.append(f'Options: {", ".join(metadata.options)}')

        if metadata.neighbor_support:
            lines.append('Supports neighbor prefix: yes')

        if metadata.json_support:
            lines.append("JSON output: supported (add 'json' to command)")

        if metadata.examples:
            lines.append('Examples:')
            for example in metadata.examples:
                lines.append(f'  {example}')

        return '\n'.join(lines)

    def get_all_metadata(self) -> List[CommandMetadata]:
        """Get metadata for all commands."""
        return [self.get_command_metadata(cmd) for cmd in self.get_all_commands() if self.get_command_metadata(cmd)]

    def get_option_description(self, option: str) -> str | None:
        """Get description for a command option."""
        return self.OPTION_DESCRIPTIONS.get(option)

    def get_command_description(self, command: str) -> str | None:
        """Get description for a command (supports full or partial command paths)."""
        metadata = self.get_command_metadata(command)
        if metadata and metadata.description:
            return metadata.description

        # For base commands without full metadata, provide default descriptions
        base_descriptions = {
            'show': 'Display information about neighbors, routes, or configuration',
            'announce': 'Announce a route to neighbors',
            'withdraw': 'Withdraw a previously announced route',
            'eor': 'Send End-of-RIB marker',
            'route-refresh': 'Request route refresh from neighbor',
            'shutdown': 'Gracefully shutdown neighbor connection',
            'enable': 'Enable neighbor connection',
            'disable': 'Disable neighbor connection',
            'restart': 'Restart neighbor connection',
            'clear': 'Clear routes or reset counters',
            'reload': 'Reload configuration from file',
            'silence-ack': 'Control silence acknowledgments',
            'enable-ack': 'Enable acknowledgment responses',
            'disable-ack': 'Disable acknowledgment responses',
            'help': 'Show available commands and usage',
            'version': 'Display ExaBGP version information',
            'teardown': 'Tear down neighbor session',
            'flush': 'Flush route information',
            'reset': 'Reset connection or state',
            'crash': 'Trigger controlled crash for debugging',
        }
        return base_descriptions.get(command)


# Global registry instance
_registry = None


def get_registry() -> CommandRegistry:
    """Get the global command registry instance."""
    global _registry
    if _registry is None:
        _registry = CommandRegistry()
    return _registry
