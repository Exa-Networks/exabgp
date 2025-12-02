"""schema.py

YANG-inspired configuration schema types for ExaBGP.

This module provides introspectable schema types that enable:
- Editor autocomplete for configuration files
- Type information for values (IP address, ASN, boolean, etc.)
- Documentation of configuration hierarchy and descriptions

The schema is additive - validation remains in code callbacks (parser functions).

Created by Thomas Mangin on 2025-12-02.
Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class ValueType(Enum):
    """YANG-inspired value types for configuration leaves.

    These types provide semantic information about configuration values,
    enabling editor autocomplete and documentation generation.
    """

    # Network types
    IP_ADDRESS = 'ip-address'  # Single IP (v4 or v6)
    IP_PREFIX = 'ip-prefix'  # IP with mask (CIDR notation)
    IP_RANGE = 'ip-range'  # IP range for peer-address
    ASN = 'as-number'  # AS number (2 or 4 byte, or 'auto')
    PORT = 'port'  # TCP/UDP port (1-65535)

    # BGP-specific types
    COMMUNITY = 'community'  # Standard community (AS:value)
    EXTENDED_COMMUNITY = 'ext-community'  # Extended community
    LARGE_COMMUNITY = 'large-community'  # Large community (AS:value:value)
    RD = 'route-distinguisher'  # Route distinguisher
    RT = 'route-target'  # Route target
    NEXT_HOP = 'next-hop'  # Next-hop (IP or 'self')

    # Basic types
    BOOLEAN = 'boolean'  # true/false
    STRING = 'string'  # Free-form string
    INTEGER = 'integer'  # Generic integer
    ENUMERATION = 'enumeration'  # Choice from predefined list
    HEX_STRING = 'hex-string'  # Hexadecimal data

    # Special types
    LABEL = 'label'  # MPLS label
    ORIGIN = 'origin'  # BGP origin attribute (igp, egp, incomplete)
    MED = 'med'  # Multi-exit discriminator
    LOCAL_PREF = 'local-pref'  # Local preference
    ATOMIC_AGGREGATE = 'atomic-aggregate'  # Atomic aggregate flag
    AGGREGATOR = 'aggregator'  # Aggregator (AS + IP)
    AS_PATH = 'as-path'  # AS path list
    BANDWIDTH = 'bandwidth'  # Link bandwidth


@dataclass
class Leaf:
    """Single configuration value (YANG leaf equivalent).

    A leaf represents a terminal configuration value that cannot have children.
    It includes type information, description, and optional validation.

    Example:
        Leaf(
            type=ValueType.INTEGER,
            description='BGP hold time in seconds',
            default=180,
            parser=hold_time,
            min_value=0,
            max_value=65535,
        )

    Attributes:
        type: The semantic type of this value
        description: Human-readable description for documentation
        default: Default value if not specified in configuration
        mandatory: Whether this field must be explicitly set
        parser: Validation/parsing callback function
        action: How to handle parsed value ('set-command', 'append-command', etc.)
        choices: Valid values for ENUMERATION type
        min_value: Minimum value for INTEGER type
        max_value: Maximum value for INTEGER type
    """

    type: ValueType
    description: str = ''
    default: Any = None
    mandatory: bool = False
    parser: Callable | None = None
    action: str = 'set-command'
    choices: list[str] | None = None
    min_value: int | None = None
    max_value: int | None = None


@dataclass
class LeafList:
    """List of values (YANG leaf-list equivalent).

    A leaf-list represents a configuration option that can have multiple values
    of the same type. Values are typically accumulated via 'append-command'.

    Example:
        LeafList(
            type=ValueType.COMMUNITY,
            description='BGP communities to attach',
            parser=community,
        )

    Attributes:
        type: The semantic type of list elements
        description: Human-readable description for documentation
        parser: Validation/parsing callback function
        action: How to handle parsed values (typically 'append-command')
        choices: Valid values for ENUMERATION type elements
    """

    type: ValueType
    description: str = ''
    parser: Callable | None = None
    action: str = 'append-command'
    choices: list[str] | None = None


@dataclass
class Container:
    """Configuration section with children (YANG container equivalent).

    A container groups related configuration options. It can contain
    leaves, leaf-lists, and nested containers.

    Example:
        Container(
            description='BGP neighbor configuration',
            children={
                'peer-address': Leaf(ValueType.IP_RANGE, mandatory=True),
                'hold-time': Leaf(ValueType.INTEGER, default=180),
                'family': Container(description='Address families'),
            }
        )

    Attributes:
        description: Human-readable description for documentation
        children: Dictionary of child schema elements
    """

    description: str = ''
    children: dict[str, Leaf | LeafList | Container] = field(default_factory=dict)


# Type alias for schema elements
SchemaElement = Leaf | LeafList | Container


@dataclass
class Completion:
    """A single autocomplete suggestion.

    Used by the autocomplete API to provide context-aware suggestions
    during configuration editing.

    Attributes:
        keyword: The configuration keyword to suggest
        description: Brief description of what this keyword does
        completion_type: Category of completion ('command', 'section', 'value')
        value_type: For commands, the expected value type
        choices: For enumerations, the valid choices
    """

    keyword: str
    description: str
    completion_type: str  # 'command', 'section', 'value'
    value_type: ValueType | None = None
    choices: list[str] | None = None


def _navigate_to_path(schema: Container, path: list[str]) -> SchemaElement | None:
    """Navigate schema tree to find element at path.

    Args:
        schema: Root schema container
        path: List of path segments (e.g., ['neighbor', 'family'])

    Returns:
        Schema element at path, or None if not found
    """
    current: SchemaElement = schema
    for segment in path:
        if not isinstance(current, Container):
            return None
        if segment not in current.children:
            # Path segment might be a dynamic value (e.g., IP address)
            # In that case, stay at current container level
            continue
        current = current.children[segment]
    return current


def get_completions(schema: Container, path: list[str]) -> list[Completion]:
    """Get valid completions at a configuration path.

    Args:
        schema: Root schema container
        path: List of section names, e.g., ['neighbor', '10.0.0.1', 'family']

    Returns:
        List of valid completions at that path.

    Example:
        >>> get_completions(root_schema, ['neighbor', '10.0.0.1'])
        [
            Completion('peer-as', 'Peer AS number', 'command', ValueType.ASN),
            Completion('local-as', 'Local AS number', 'command', ValueType.ASN),
            Completion('family', 'Address families', 'section'),
            ...
        ]
    """
    element = _navigate_to_path(schema, path)
    if element is None or not isinstance(element, Container):
        return []

    completions: list[Completion] = []
    for name, child in element.children.items():
        if isinstance(child, Container):
            completions.append(
                Completion(
                    keyword=name,
                    description=child.description,
                    completion_type='section',
                )
            )
        elif isinstance(child, Leaf):
            completions.append(
                Completion(
                    keyword=name,
                    description=child.description,
                    completion_type='command',
                    value_type=child.type,
                    choices=child.choices,
                )
            )
        elif isinstance(child, LeafList):
            completions.append(
                Completion(
                    keyword=name,
                    description=child.description,
                    completion_type='command',
                    value_type=child.type,
                    choices=child.choices,
                )
            )

    return completions


def get_value_completions(schema: Container, path: list[str], partial: str = '') -> list[str]:
    """Get value completions for enumeration types.

    Args:
        schema: Root schema container
        path: Full path including the command name
        partial: Partial value typed so far

    Returns:
        List of matching value suggestions.

    Example:
        >>> get_value_completions(root_schema, ['neighbor', '10.0.0.1', 'family', 'ipv4'], 'uni')
        ['unicast']
    """
    if not path:
        return []

    # Navigate to the leaf's parent container
    parent_path = path[:-1]
    command = path[-1]

    parent = _navigate_to_path(schema, parent_path)
    if parent is None or not isinstance(parent, Container):
        return []

    if command not in parent.children:
        return []

    child = parent.children[command]
    if isinstance(child, (Leaf, LeafList)) and child.choices:
        partial_lower = partial.lower()
        return [c for c in child.choices if c.lower().startswith(partial_lower)]

    return []


def schema_to_dict(element: SchemaElement) -> dict[str, Any]:
    """Convert schema element to dictionary for JSON export.

    Useful for generating schema documentation or external tooling integration.

    Args:
        element: Schema element to convert

    Returns:
        Dictionary representation of the schema
    """
    if isinstance(element, Leaf):
        result: dict[str, Any] = {
            'type': 'leaf',
            'value_type': element.type.value,
            'description': element.description,
        }
        if element.default is not None:
            result['default'] = element.default
        if element.mandatory:
            result['mandatory'] = True
        if element.choices:
            result['choices'] = element.choices
        if element.min_value is not None:
            result['min_value'] = element.min_value
        if element.max_value is not None:
            result['max_value'] = element.max_value
        return result

    if isinstance(element, LeafList):
        result = {
            'type': 'leaf-list',
            'value_type': element.type.value,
            'description': element.description,
        }
        if element.choices:
            result['choices'] = element.choices
        return result

    if isinstance(element, Container):
        result = {
            'type': 'container',
            'description': element.description,
            'children': {name: schema_to_dict(child) for name, child in element.children.items()},
        }
        return result

    return {}
