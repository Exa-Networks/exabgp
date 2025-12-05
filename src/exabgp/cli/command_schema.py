"""command_schema.py

CLI command schema registry for runtime API commands.

Maps CLI commands (announce, withdraw, show) to their value types and validation
rules. This is separate from the configuration schema (schema.py) which handles
configuration file parsing.

Created by Thomas Mangin on 2025-12-02.
Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from exabgp.configuration.schema import ValueType


@dataclass
class CLIValueSpec:
    """Specification for a CLI command value/argument.

    Describes the expected type, validation, and help text for a CLI value.
    Used to drive auto-completion and validation in the interactive CLI.

    Example:
        CLIValueSpec(
            value_type=ValueType.IP_PREFIX,
            description="Route prefix to announce",
            examples=["10.0.0.0/24", "2001:db8::/32"],
            required=True
        )
    """

    value_type: ValueType
    description: str = ''
    examples: list[str] = field(default_factory=list)
    required: bool = True
    choices: list[str] | None = None  # For enumeration types


@dataclass
class CLICommandSpec:
    """Specification for a CLI command.

    Defines the structure, arguments, and options for a CLI command.
    Used to generate context-aware completion and validation.

    Example:
        CLICommandSpec(
            name="announce route",
            description="Announce a BGP route",
            arguments={"prefix": CLIValueSpec(ValueType.IP_PREFIX, ...)},
            options={"next-hop": CLIValueSpec(ValueType.NEXT_HOP, ...)}
        )
    """

    name: str
    description: str = ''
    arguments: dict[str, CLIValueSpec] = field(default_factory=dict)
    options: dict[str, CLIValueSpec] = field(default_factory=dict)


# CLI Command Schema Registry
# Maps runtime API commands to their value specifications (v6 API format)
CLI_COMMAND_SCHEMA: dict[str, CLICommandSpec] = {
    # Peer announce commands (v6 uses "peer <selector> announce route")
    'peer * announce route': CLICommandSpec(
        name='peer * announce route',
        description='Announce a BGP route to all peers',
        arguments={
            'prefix': CLIValueSpec(
                value_type=ValueType.IP_PREFIX,
                description='IP prefix to announce (CIDR notation)',
                examples=['10.0.0.0/24', '192.0.2.0/24', '2001:db8::/32'],
                required=True,
            )
        },
        options={
            'next-hop': CLIValueSpec(
                value_type=ValueType.NEXT_HOP,
                description='Next-hop IP address or "self"',
                examples=['192.0.2.1', 'self', '2001:db8::1'],
                required=False,
            ),
            'as-path': CLIValueSpec(
                value_type=ValueType.AS_PATH,
                description='AS path as list of AS numbers',
                examples=['[65000]', '[65000 65001]', '[65000 65001 65002]'],
                required=False,
            ),
            'origin': CLIValueSpec(
                value_type=ValueType.ORIGIN,
                description='BGP origin attribute',
                examples=['igp', 'egp', 'incomplete'],
                required=False,
                choices=['igp', 'egp', 'incomplete'],
            ),
            'med': CLIValueSpec(
                value_type=ValueType.MED,
                description='Multi-exit discriminator (metric)',
                examples=['100', '200', '0'],
                required=False,
            ),
            'local-preference': CLIValueSpec(
                value_type=ValueType.LOCAL_PREF,
                description='Local preference value',
                examples=['100', '200', '150'],
                required=False,
            ),
            'community': CLIValueSpec(
                value_type=ValueType.COMMUNITY,
                description='BGP community (AS:value)',
                examples=['65000:100', '65000:200'],
                required=False,
            ),
            'extended-community': CLIValueSpec(
                value_type=ValueType.EXTENDED_COMMUNITY,
                description='Extended community attribute',
                examples=['target:65000:100', 'origin:65000:100'],
                required=False,
            ),
            'large-community': CLIValueSpec(
                value_type=ValueType.LARGE_COMMUNITY,
                description='Large BGP community (AS:value:value)',
                examples=['65000:100:200', '65000:0:1'],
                required=False,
            ),
        },
    ),
    'peer * announce eor': CLICommandSpec(
        name='peer * announce eor',
        description='Announce End-of-RIB marker to all peers',
        arguments={
            'afi': CLIValueSpec(
                value_type=ValueType.ENUMERATION,
                description='Address family identifier',
                examples=['ipv4', 'ipv6', 'l2vpn'],
                required=False,
                choices=['ipv4', 'ipv6', 'l2vpn', 'bgp-ls'],
            ),
            'safi': CLIValueSpec(
                value_type=ValueType.ENUMERATION,
                description='Subsequent address family identifier',
                examples=['unicast', 'multicast', 'mpls-vpn'],
                required=False,
                # Choices depend on AFI, populated dynamically
            ),
        },
    ),
    'peer * announce route-refresh': CLICommandSpec(
        name='peer * announce route-refresh',
        description='Request route refresh from all peers',
        arguments={
            'afi': CLIValueSpec(
                value_type=ValueType.ENUMERATION,
                description='Address family identifier',
                examples=['ipv4', 'ipv6'],
                required=False,
                choices=['ipv4', 'ipv6', 'l2vpn', 'bgp-ls'],
            ),
            'safi': CLIValueSpec(
                value_type=ValueType.ENUMERATION,
                description='Subsequent address family identifier',
                examples=['unicast', 'mpls-vpn'],
                required=False,
            ),
        },
    ),
    # Peer withdraw commands
    'peer * withdraw route': CLICommandSpec(
        name='peer * withdraw route',
        description='Withdraw a previously announced route from all peers',
        arguments={
            'prefix': CLIValueSpec(
                value_type=ValueType.IP_PREFIX,
                description='IP prefix to withdraw (CIDR notation)',
                examples=['10.0.0.0/24', '192.0.2.0/24', '2001:db8::/32'],
                required=True,
            )
        },
        options={
            'next-hop': CLIValueSpec(
                value_type=ValueType.NEXT_HOP,
                description='Next-hop IP address (for NLRI matching)',
                examples=['192.0.2.1', '2001:db8::1'],
                required=False,
            ),
            'path-information': CLIValueSpec(
                value_type=ValueType.INTEGER,
                description='Path identifier for add-path',
                examples=['1', '2', '100'],
                required=False,
            ),
        },
    ),
    # Peer show commands (v6 API)
    'peer show': CLICommandSpec(
        name='peer show',
        description='Display peer information',
        arguments={
            'ip': CLIValueSpec(
                value_type=ValueType.IP_ADDRESS,
                description='Peer IP address (optional filter)',
                examples=['127.0.0.1', '192.168.1.1'],
                required=False,
            )
        },
        options={
            'summary': CLIValueSpec(
                value_type=ValueType.BOOLEAN,
                description='Show brief peer status',
                required=False,
            ),
            'extensive': CLIValueSpec(
                value_type=ValueType.BOOLEAN,
                description='Show detailed peer information',
                required=False,
            ),
            'configuration': CLIValueSpec(
                value_type=ValueType.BOOLEAN,
                description='Show peer configuration',
                required=False,
            ),
        },
    ),
    # RIB show commands (v6 API)
    'rib show in': CLICommandSpec(
        name='rib show in',
        description='Display Adj-RIB-In (received routes)',
        arguments={
            'ip': CLIValueSpec(
                value_type=ValueType.IP_ADDRESS,
                description='Peer IP address (optional filter)',
                examples=['127.0.0.1', '192.168.1.1'],
                required=False,
            ),
        },
        options={
            'extensive': CLIValueSpec(
                value_type=ValueType.BOOLEAN,
                description='Show detailed route information',
                required=False,
            ),
        },
    ),
    'rib show out': CLICommandSpec(
        name='rib show out',
        description='Display Adj-RIB-Out (advertised routes)',
        arguments={
            'ip': CLIValueSpec(
                value_type=ValueType.IP_ADDRESS,
                description='Peer IP address (optional filter)',
                examples=['127.0.0.1', '192.168.1.1'],
                required=False,
            ),
        },
        options={
            'extensive': CLIValueSpec(
                value_type=ValueType.BOOLEAN,
                description='Show detailed route information',
                required=False,
            ),
        },
    ),
    # Peer teardown command (v6 API)
    'peer * teardown': CLICommandSpec(
        name='peer * teardown',
        description='Tear down BGP session with all peers',
        options={
            'notification': CLIValueSpec(
                value_type=ValueType.INTEGER,
                description='BGP notification code (1-6)',
                examples=['6'],
                required=False,
            ),
        },
    ),
}


def get_command_spec(command: str) -> CLICommandSpec | None:
    """Get CLI command specification.

    Args:
        command: Command name (e.g., "peer * announce route", "peer show")

    Returns:
        CLICommandSpec or None if not found
    """
    return CLI_COMMAND_SCHEMA.get(command)


def get_value_spec(command: str, argument: str) -> CLIValueSpec | None:
    """Get value specification for a command argument/option.

    Args:
        command: Command name (e.g., "announce route")
        argument: Argument/option name (e.g., "prefix", "next-hop")

    Returns:
        CLIValueSpec or None if not found
    """
    spec = get_command_spec(command)
    if spec is None:
        return None

    # Check arguments first
    if argument in spec.arguments:
        return spec.arguments[argument]

    # Check options
    if argument in spec.options:
        return spec.options[argument]

    return None


def get_all_commands() -> list[str]:
    """Get list of all registered CLI commands.

    Returns:
        List of command names
    """
    return list(CLI_COMMAND_SCHEMA.keys())
