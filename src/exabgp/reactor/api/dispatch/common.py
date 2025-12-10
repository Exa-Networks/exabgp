"""dispatch/common.py

Shared types, exceptions, and command metadata for v4/v6 API dispatchers.

Created on 2025-12-05.
Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Union

from exabgp.configuration.core.parser import Tokeniser

if TYPE_CHECKING:
    from exabgp.reactor.api import API
    from exabgp.reactor.loop import Reactor


# Handler signature: (api, reactor, service, peers, command, use_json) -> bool
# - api: API instance
# - reactor: Reactor instance
# - service: service name for responses
# - peers: list of matching peer names (empty for non-neighbor commands)
# - command: remaining command after dispatch prefix stripped
# - use_json: whether to output JSON format
Handler = Callable[['API', 'Reactor', str, list[str], str, bool], bool]

# Dispatch tree types
# A node is either a handler (leaf) or a dict of child nodes
DispatchNode = Union[Handler, 'DispatchTree']
DispatchTree = dict[str, DispatchNode]

# Special key for selector-consuming nodes (peer selectors like *, IP, or [bracket syntax])
SELECTOR_KEY = '__selector__'

# Valid selector keys for filtering peers
SELECTOR_KEYS = frozenset(['local-ip', 'local-as', 'peer-as', 'router-id', 'family-allowed'])


class UnknownCommand(Exception):
    """Raised when a command cannot be dispatched."""

    pass


class NoMatchingPeers(Exception):
    """Raised when neighbor_support=True but no peers match the selector."""

    pass


class InvalidCommand(Exception):
    """Raised when the command syntax is invalid"""

    pass


# Command metadata for help display
# Format: (v6_command, neighbor_support, options)
# - v6_command: The v6 format command string
# - neighbor_support: Whether the command supports peer/neighbor prefix
# - options: Optional list of sub-options for the command
COMMANDS: list[tuple[str, bool, list[str] | None]] = [
    # Daemon control
    ('daemon shutdown', False, None),
    ('daemon reload', False, None),
    ('daemon restart', False, None),
    ('daemon status', False, None),
    # Session management
    ('session ack enable', False, None),
    ('session ack disable', False, None),
    ('session ack silence', False, None),
    ('session sync enable', False, None),
    ('session sync disable', False, None),
    ('session reset', False, None),
    ('session ping', False, None),
    ('session bye', False, None),
    # System commands
    ('system help', False, None),
    ('system version', False, None),
    ('system crash', True, None),
    ('system queue-status', False, None),
    ('system api version', False, ['4', '6']),
    # Comment
    ('#', False, None),
    # RIB operations
    ('rib show in', False, ['extensive']),
    ('rib show out', False, ['extensive']),
    ('rib flush out', True, None),
    ('rib clear in', True, None),
    ('rib clear out', True, None),
    # Peer operations
    ('peer list', False, None),
    ('peer show', False, ['summary', 'extensive', 'configuration']),
    ('peer teardown', True, None),
    ('peer create', False, None),
    ('peer delete', False, None),
    # Announce commands
    ('peer announce route', True, None),
    ('peer announce route-refresh', True, None),
    ('peer announce ipv4', True, None),
    ('peer announce ipv6', True, None),
    ('peer announce flow', True, None),
    ('peer announce eor', True, None),
    ('peer announce watchdog', True, None),
    ('peer announce attribute', True, None),
    ('peer announce attributes', True, None),
    ('peer announce operational', True, None),
    ('peer announce vpls', True, None),
    # Withdraw commands
    ('peer withdraw route', True, None),
    ('peer withdraw ipv4', True, None),
    ('peer withdraw ipv6', True, None),
    ('peer withdraw flow', True, None),
    ('peer withdraw watchdog', True, None),
    ('peer withdraw attribute', True, None),
    ('peer withdraw attributes', True, None),
    ('peer withdraw vpls', True, None),
    # Group commands for batching
    ('group start', False, None),
    ('group end', False, None),
    ('peer group', True, None),
]


def get_commands() -> list[tuple[str, bool, list[str] | None]]:
    """Return the list of available commands with metadata.

    Returns list of (command, neighbor_support, options) tuples.
    """
    return COMMANDS


# =============================================================================
# Tree-based dispatch infrastructure
# =============================================================================


def is_selector_start(token: str) -> bool:
    """Check if a token could be the start of a peer selector.

    Selectors can be:
    - '*' (wildcard for all peers)
    - '[' (bracket syntax for multiple selectors)
    - An IP address (single peer)

    Args:
        token: The token to check

    Returns:
        True if this could start a selector
    """
    if not token:
        return False
    if token in ('*', '['):
        return True
    # Check if it looks like an IP address (contains . or :)
    return '.' in token or ':' in token


def extract_selector(tokeniser: Tokeniser, reactor: 'Reactor', service: str) -> list[str]:
    """Extract peer selector by consuming tokens from the tokeniser.

    This function owns its token consumption - it will consume exactly
    the tokens that make up the selector.

    Supports:
    - * (all peers)
    - Single IP address
    - Extended: IP key value key value... (e.g., 127.0.0.1 local-as 1 peer-as 1)
    - Bracket syntax: [ip key value, ip2]

    Args:
        tokeniser: Tokeniser to consume tokens from
        reactor: Reactor for peer lookup
        service: Service name for peer filtering

    Returns:
        List of matching peer names
    """
    from exabgp.reactor.api.command.limit import match_neighbors

    first_token = tokeniser()

    # Wildcard - all peers
    if first_token == '*':
        return list(reactor.peers(service))

    # Bracket syntax: [ip1 key value, ip2]
    if first_token == '[':
        return _parse_bracket_selector(tokeniser, reactor, service)

    # IP address with optional key-value pairs: IP [key value]...
    definition: list[str] = [f'neighbor {first_token}']

    # Consume any following key-value pairs
    while True:
        peeked = tokeniser.peek()
        if not peeked or peeked not in SELECTOR_KEYS:
            break
        # Consume key
        key = tokeniser()
        # Consume value
        value = tokeniser()
        if value:
            definition.append(f'{key} {value}')
        else:
            break

    return match_neighbors(reactor.peers(service), [definition])


def _parse_bracket_selector(tokeniser: Tokeniser, reactor: 'Reactor', service: str) -> list[str]:
    """Parse bracket selector syntax: [ip1 key value, ip2].

    Called after '[' has been consumed.

    Args:
        tokeniser: Tokeniser positioned after '['
        reactor: Reactor for peer lookup
        service: Service name for peer filtering

    Returns:
        List of matching peer names
    """
    from exabgp.reactor.api.command.limit import match_neighbors

    descriptions: list[list[str]] = []
    current_def: list[str] = []

    while True:
        # Peek to decide what to do
        peeked = tokeniser.peek()

        if not peeked:
            # End of tokens - finalize current definition
            if current_def:
                descriptions.append(current_def)
            break

        if peeked == ']':
            tokeniser()  # Consume the ']'
            if current_def:
                descriptions.append(current_def)
            break

        if peeked == ',':
            tokeniser()  # Consume the ','
            if current_def:
                descriptions.append(current_def)
                current_def = []
            continue

        # Consume the actual content token
        tok = tokeniser()

        # First token in a selector definition is the IP
        if not current_def:
            current_def = [f'neighbor {tok}']
        elif tok in SELECTOR_KEYS:
            # Key-value pair: consume the value too
            value = tokeniser()
            if value:
                current_def.append(f'{tok} {value}')
        else:
            # Unknown token - include it anyway
            current_def.append(tok)

    return match_neighbors(reactor.peers(service), descriptions)


def dispatch(
    tree: DispatchTree,
    tokeniser: Tokeniser,
    reactor: 'Reactor',
    service: str,
) -> tuple[Handler, list[str]]:
    """Walk dispatch tree consuming tokens until a handler is found.

    Uses peek() to check for selector nodes before consuming, allowing
    extract_selector() to own its token consumption.

    Args:
        tree: The dispatch tree (dict of dicts with handlers as leaves)
        tokeniser: Tokeniser with tokens to consume
        reactor: Reactor instance for peer lookup
        service: Service name for peer filtering

    Returns:
        Tuple of (handler, peers)
        - handler: The function to call
        - peers: List of matching peer names (empty for non-peer commands)

    Raises:
        UnknownCommand: If the command cannot be matched to a handler

    Note:
        tokeniser.consumed tracks how many tokens were consumed.
        This is used by remaining_string() to extract the remaining command portion.
    """
    peers: list[str] = []
    node: DispatchNode = tree

    while True:
        # Peek first to check what we're dealing with
        peeked = tokeniser.peek()

        # No more tokens
        if not peeked:
            # Check if current node IS a handler (reached end of command at handler)
            if callable(node):
                return node, peers
            raise UnknownCommand('incomplete command')

        # Current node must be a dict to continue traversal
        if not isinstance(node, dict):
            raise UnknownCommand(f'unexpected token: {peeked}')

        # Check if this is a selector node and the token looks like a selector start
        if SELECTOR_KEY in node and peeked not in node and is_selector_start(peeked):
            # Let extract_selector consume its own tokens
            peers = extract_selector(tokeniser, reactor, service)
            node = node[SELECTOR_KEY]
            # Don't consume again - extract_selector already did
            if callable(node):
                return node, peers
            continue

        # Now consume the token for regular tree traversal
        token = tokeniser()

        # Try to match token in tree
        if token in node:
            node = node[token]
        else:
            raise UnknownCommand(f'unknown command: {token}')

        # Found a handler?
        if callable(node):
            return node, peers
