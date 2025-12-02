"""example.py

Generate documented configuration example from schema definitions.

This module provides functions to generate a complete, documented ExaBGP
configuration example by walking the schema definitions. The output includes
full metadata comments (description, type, default, range, examples) for all
configuration options.

Usage:
    from exabgp.configuration.example import generate_full_example
    print(generate_full_example())

Created by Thomas Mangin on 2025-12-02.
Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.configuration.schema import (
    Container,
    Leaf,
    LeafList,
    RouteBuilder,
    TypeSelectorBuilder,
    ValueType,
)


# Options that require system-specific setup - comment out for portability
# These are kept as documentation but won't break when running the example
COMMENTED_OPTIONS: set[str] = {
    'source-interface',  # Interface doesn't exist
    'md5-password',  # Requires TCP MD5 setup
    'md5-ip',  # Requires MD5 password
    'md5-base64',  # Requires MD5 password
    'outgoing-ttl',  # GTSM requires specific network setup
    'incoming-ttl',  # GTSM requires specific network setup
}

# Options with non-portable default values - override for testing
PORTABLE_OVERRIDES: dict[str, str] = {
    'listen': '1790',  # Port 179 requires root privileges
    'connect': '1790',  # Port 179 requires root privileges
}

# Example values for each ValueType - used when leaf.example is not set
VALUE_TYPE_EXAMPLES: dict[ValueType, str] = {
    # Network types - use loopback (127.0.0.1) so examples can actually run
    ValueType.IP_ADDRESS: '127.0.0.1',
    ValueType.IP_PREFIX: '10.0.0.0/24',
    ValueType.IP_RANGE: '10.0.0.0/24',
    ValueType.ASN: '65000',
    ValueType.PORT: '1790',  # Avoid privileged port 179
    # BGP-specific types
    ValueType.COMMUNITY: '65000:100',
    ValueType.EXTENDED_COMMUNITY: 'target:65000:100',
    ValueType.LARGE_COMMUNITY: '65000:1:1',
    ValueType.RD: '65000:1',
    ValueType.RT: '65000:1',
    ValueType.NEXT_HOP: 'self',
    # Basic types
    ValueType.BOOLEAN: 'enable',
    ValueType.STRING: '"example"',
    ValueType.INTEGER: '100',
    ValueType.ENUMERATION: '<value>',
    ValueType.HEX_STRING: '0x1234',
    # Special types
    ValueType.LABEL: '100',
    ValueType.ORIGIN: 'igp',
    ValueType.MED: '100',
    ValueType.LOCAL_PREF: '100',
    ValueType.ATOMIC_AGGREGATE: '',  # Flag, no value
    ValueType.AGGREGATOR: '( 65000:192.0.2.1 )',
    ValueType.AS_PATH: '[ 65001 65002 ]',
    ValueType.BANDWIDTH: '1000000',
}


def _format_type_info(leaf: Leaf | LeafList) -> str:
    """Format type info string for a leaf."""
    type_name = leaf.type.name
    if leaf.type == ValueType.ENUMERATION and leaf.choices:
        return f'{type_name} ({", ".join(leaf.choices)})'
    return type_name


def generate_leaf_comment(name: str, leaf: Leaf | LeafList, indent: str) -> list[str]:
    """Generate comment lines for a leaf with full metadata.

    Args:
        name: Configuration key name
        leaf: Leaf or LeafList schema element
        indent: Indentation string

    Returns:
        List of comment lines with metadata
    """
    lines: list[str] = []

    # Main description
    if leaf.description:
        lines.append(f'{indent}# {name}: {leaf.description}')
    else:
        lines.append(f'{indent}# {name}')

    # Type information
    lines.append(f'{indent}# Type: {_format_type_info(leaf)}')

    # Mandatory
    if isinstance(leaf, Leaf) and leaf.mandatory:
        lines.append(f'{indent}# Mandatory: yes')

    # Default value
    if isinstance(leaf, Leaf) and leaf.default is not None:
        lines.append(f'{indent}# Default: {leaf.default}')

    # Range (for integers)
    if isinstance(leaf, Leaf):
        if leaf.min_value is not None or leaf.max_value is not None:
            min_val = leaf.min_value if leaf.min_value is not None else 0
            max_val = leaf.max_value if leaf.max_value is not None else 'max'
            lines.append(f'{indent}# Range: {min_val}-{max_val}')

    # Choices
    if leaf.choices:
        lines.append(f'{indent}# Choices: {", ".join(leaf.choices)}')

    return lines


def get_example_value(name: str, leaf: Leaf | LeafList) -> str:
    """Get example value for a leaf.

    Priority:
    1. leaf.example if set
    2. First choice if choices available
    3. VALUE_TYPE_EXAMPLES mapping
    4. '<value>' fallback

    Args:
        name: Configuration key name
        leaf: Leaf or LeafList schema element

    Returns:
        Example value string
    """
    # Priority 1: Custom example
    if leaf.example is not None:
        return leaf.example

    # Priority 2: First choice (for enumerations)
    if leaf.choices:
        return leaf.choices[0]

    # Priority 3: Default from leaf if appropriate type
    if isinstance(leaf, Leaf) and leaf.default is not None:
        if leaf.type == ValueType.BOOLEAN:
            return 'enable' if leaf.default else 'disable'
        if leaf.type in (ValueType.INTEGER, ValueType.PORT, ValueType.MED, ValueType.LOCAL_PREF):
            return str(leaf.default)

    # Priority 4: Type-based example
    return VALUE_TYPE_EXAMPLES.get(leaf.type, '<value>')


def generate_leaf_config(
    name: str,
    leaf: Leaf | LeafList,
    indent: str,
    include_comments: bool = True,
) -> list[str]:
    """Generate config line(s) for a leaf.

    Args:
        name: Configuration key name
        leaf: Leaf or LeafList schema element
        indent: Indentation string
        include_comments: Whether to include metadata comments

    Returns:
        List of config lines (comments + value)
    """
    lines: list[str] = []

    # Check if this option should be commented out
    is_commented = name in COMMENTED_OPTIONS

    # Add comments
    if include_comments:
        lines.extend(generate_leaf_comment(name, leaf, indent))

    # Get example value - check for portable override first
    if name in PORTABLE_OVERRIDES:
        example = PORTABLE_OVERRIDES[name]
    else:
        example = get_example_value(name, leaf)

    # Generate the config line
    if leaf.type == ValueType.ATOMIC_AGGREGATE or (leaf.type == ValueType.BOOLEAN and not example):
        config_line = f'{name};'
    elif example:
        config_line = f'{name} {example};'
    else:
        config_line = f'{name};'

    # Comment out if in COMMENTED_OPTIONS
    if is_commented:
        lines.append(f'{indent}# {config_line}  # Commented: requires system-specific setup')
    else:
        lines.append(f'{indent}{config_line}')

    return lines


def generate_container_header(name: str, container: Container, indent: str) -> list[str]:
    """Generate header comments for a container section.

    Args:
        name: Container name
        container: Container schema element
        indent: Indentation string

    Returns:
        List of header comment lines
    """
    lines: list[str] = []
    lines.append(f'{indent}# {"-" * 75}')
    lines.append(f'{indent}# {name.upper()}')
    lines.append(f'{indent}# {"-" * 75}')
    if container.description:
        lines.append(f'{indent}# {container.description}')
    return lines


def generate_container(
    name: str,
    container: Container,
    indent: str = '',
    include_header: bool = True,
    skip_subsections: bool = False,
) -> list[str]:
    """Recursively generate config for a container with full documentation.

    Args:
        name: Container name
        container: Container schema element
        indent: Indentation string
        include_header: Whether to include section header comments
        skip_subsections: Whether to skip nested containers

    Returns:
        List of config lines
    """
    lines: list[str] = []
    inner_indent = indent + '    '

    # Header comments
    if include_header and container.description:
        lines.extend(generate_container_header(name, container, indent))

    # Process children
    for child_name, child in container.children.items():
        if isinstance(child, (Leaf, LeafList)):
            lines.extend(generate_leaf_config(child_name, child, inner_indent))
            lines.append('')  # Blank line after each leaf
        elif isinstance(child, (Container, RouteBuilder, TypeSelectorBuilder)) and not skip_subsections:
            # Nested container - generate recursively
            if child.children:
                lines.append('')
                lines.extend(generate_container_header(child_name, child, inner_indent))
                lines.append(f'{inner_indent}{child_name} {{')
                lines.extend(generate_container(child_name, child, inner_indent, include_header=False))
                lines.append(f'{inner_indent}}}')
            else:
                # Empty container placeholder
                lines.append(f'{inner_indent}# {child_name}: {child.description or "Configuration section"}')
                lines.append(f'{inner_indent}# {child_name} {{ ... }}')
                lines.append('')

    return lines


def _get_root_schema() -> Container:
    """Build the root configuration schema from all section schemas.

    Returns:
        Combined Container representing the full ExaBGP config schema.
    """
    from exabgp.configuration.schema import SchemaElement

    children: dict[str, SchemaElement] = {}

    # Import and add each section schema
    try:
        from exabgp.configuration.neighbor import ParseNeighbor

        if hasattr(ParseNeighbor, 'schema') and ParseNeighbor.schema:
            children['neighbor'] = ParseNeighbor.schema
    except ImportError:
        pass

    try:
        from exabgp.configuration.process import ParseProcess

        if hasattr(ParseProcess, 'schema') and ParseProcess.schema:
            children['process'] = ParseProcess.schema
    except ImportError:
        pass

    try:
        from exabgp.configuration.template import ParseTemplate

        if hasattr(ParseTemplate, 'schema') and ParseTemplate.schema:
            children['template'] = ParseTemplate.schema
    except ImportError:
        pass

    return Container(
        description='ExaBGP Configuration',
        children=children,
    )


def generate_neighbor_example() -> str:
    """Generate a complete neighbor configuration example.

    Returns:
        Documented neighbor configuration string
    """
    try:
        from exabgp.configuration.neighbor import ParseNeighbor

        schema = ParseNeighbor.schema
    except (ImportError, AttributeError):
        return '# Neighbor schema not available\n'

    lines: list[str] = []

    # File header
    lines.append('# =============================================================================')
    lines.append('# EXABGP CONFIGURATION EXAMPLE')
    lines.append('# =============================================================================')
    lines.append('# Generated from schema definitions')
    lines.append('# This file documents all available configuration options')
    lines.append('#')
    lines.append('# Usage: ./sbin/exabgp configuration example > example.conf')
    lines.append('#        ./sbin/exabgp configuration validate example.conf')
    lines.append('# =============================================================================')
    lines.append('')

    # Generate neighbor section
    lines.append('# =============================================================================')
    lines.append('# NEIGHBOR CONFIGURATION')
    lines.append('# =============================================================================')
    lines.append('# BGP neighbor (peer) configuration')
    lines.append('')

    # Get peer-address example from schema (not hardcoded)
    peer_address_leaf = schema.children.get('peer-address')
    if isinstance(peer_address_leaf, Leaf):
        peer_address = get_example_value('peer-address', peer_address_leaf)
    else:
        peer_address = '127.0.0.1'  # Fallback
    lines.append(f'neighbor {peer_address} {{')

    # Generate neighbor children (skip subsections for now, handle them specially)
    inner_indent = '    '

    # Session parameters first
    session_keys = [
        'router-id',
        'local-address',
        'local-as',
        'peer-as',
        'description',
        'host-name',
        'domain-name',
    ]
    for key in session_keys:
        if key in schema.children:
            child = schema.children[key]
            if isinstance(child, (Leaf, LeafList)):
                lines.extend(generate_leaf_config(key, child, inner_indent))
                lines.append('')

    # Timers
    timer_keys = ['hold-time', 'rate-limit']
    for key in timer_keys:
        if key in schema.children:
            child = schema.children[key]
            if isinstance(child, (Leaf, LeafList)):
                lines.extend(generate_leaf_config(key, child, inner_indent))
                lines.append('')

    # Connection options
    conn_keys = ['passive', 'listen', 'connect', 'source-interface', 'outgoing-ttl', 'incoming-ttl']
    for key in conn_keys:
        if key in schema.children:
            child = schema.children[key]
            if isinstance(child, (Leaf, LeafList)):
                lines.extend(generate_leaf_config(key, child, inner_indent))
                lines.append('')

    # Authentication
    auth_keys = ['md5-password', 'md5-base64', 'md5-ip']
    for key in auth_keys:
        if key in schema.children:
            child = schema.children[key]
            if isinstance(child, (Leaf, LeafList)):
                lines.extend(generate_leaf_config(key, child, inner_indent))
                lines.append('')

    # Behavior options
    behavior_keys = ['group-updates', 'auto-flush', 'adj-rib-out', 'adj-rib-in', 'manual-eor']
    for key in behavior_keys:
        if key in schema.children:
            child = schema.children[key]
            if isinstance(child, (Leaf, LeafList)):
                lines.extend(generate_leaf_config(key, child, inner_indent))
                lines.append('')

    # Generate capability subsection
    lines.append('')
    lines.append(f'{inner_indent}# {"-" * 71}')
    lines.append(f'{inner_indent}# CAPABILITY')
    lines.append(f'{inner_indent}# {"-" * 71}')
    lines.append(f'{inner_indent}# BGP capabilities to negotiate with the peer')
    lines.append(f'{inner_indent}capability {{')
    try:
        from exabgp.configuration.capability import ParseCapability

        cap_schema = ParseCapability.schema
        for key, child in cap_schema.children.items():
            if isinstance(child, (Leaf, LeafList)):
                lines.extend(generate_leaf_config(key, child, inner_indent + '    '))
                lines.append('')
    except (ImportError, AttributeError):
        lines.append(f'{inner_indent}    # Capability schema not available')
    lines.append(f'{inner_indent}}}')

    # Generate family subsection (placeholder)
    lines.append('')
    lines.append(f'{inner_indent}# {"-" * 71}')
    lines.append(f'{inner_indent}# FAMILY')
    lines.append(f'{inner_indent}# {"-" * 71}')
    lines.append(f'{inner_indent}# Address families to negotiate')
    lines.append(f'{inner_indent}family {{')
    lines.append(f'{inner_indent}    # ipv4: IPv4 address families')
    lines.append(f'{inner_indent}    # Choices: unicast, multicast, nlri-mpls, mpls-vpn, mcast-vpn, flow, flow-vpn')
    lines.append(f'{inner_indent}    ipv4 unicast;')
    lines.append('')
    lines.append(f'{inner_indent}    # ipv6: IPv6 address families')
    lines.append(f'{inner_indent}    # Choices: unicast, multicast, nlri-mpls, mpls-vpn, mcast-vpn, flow, flow-vpn')
    lines.append(f'{inner_indent}    ipv6 unicast;')
    lines.append(f'{inner_indent}}}')

    # Generate static routes subsection
    lines.append('')
    lines.append(f'{inner_indent}# {"-" * 71}')
    lines.append(f'{inner_indent}# STATIC ROUTES')
    lines.append(f'{inner_indent}# {"-" * 71}')
    lines.append(f'{inner_indent}# Static routes to announce')
    lines.append(f'{inner_indent}static {{')
    lines.append(f'{inner_indent}    route 10.0.0.0/24 {{')
    try:
        from exabgp.configuration.static.route import ParseStaticRoute

        route_schema = ParseStaticRoute.schema
        route_indent = inner_indent + '        '
        # Key route attributes
        route_keys = [
            'next-hop',
            'origin',
            'as-path',
            'med',
            'local-preference',
            'community',
            'large-community',
            'extended-community',
        ]
        for key in route_keys:
            if key in route_schema.children:
                child = route_schema.children[key]
                if isinstance(child, (Leaf, LeafList)):
                    lines.extend(generate_leaf_config(key, child, route_indent))
                    lines.append('')
    except (ImportError, AttributeError):
        lines.append(f'{inner_indent}        # Route schema not available')
    lines.append(f'{inner_indent}    }}')
    lines.append(f'{inner_indent}}}')

    # Close neighbor block
    lines.append('}')

    return '\n'.join(lines)


def generate_full_example() -> str:
    """Generate complete documented configuration example.

    This is the main entry point for generating a full documented
    configuration example that covers all major sections.

    Returns:
        Complete documented configuration string
    """
    return generate_neighbor_example()


if __name__ == '__main__':
    print(generate_full_example())
