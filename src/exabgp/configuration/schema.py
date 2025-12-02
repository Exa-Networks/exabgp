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
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.configuration.validator import Validator


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
        example: Custom syntax hint (overrides auto-generated from type)
    """

    type: ValueType
    description: str = ''
    default: Any = None
    mandatory: bool = False
    parser: Callable | None = None  # Deprecated - use validator
    action: str = 'set-command'
    choices: list[str] | None = None
    min_value: int | None = None
    max_value: int | None = None
    validator: 'Validator[Any] | None' = None  # Explicit validator override
    example: str | None = None  # Custom syntax hint for definition generation

    def get_validator(self) -> 'Validator[Any] | None':
        """Get or create validator from type + constraints.

        Priority:
        1. Explicit self.validator if set
        2. Auto-generated from ValueType + constraints
        3. None if no validator available

        Returns:
            Configured Validator instance, or None
        """
        # Priority 1: Explicit validator
        if self.validator is not None:
            return self.validator

        # Priority 2: Auto-generate from type
        from exabgp.configuration.validator import (
            get_validator,
            IntegerValidator,
            EnumerationValidator,
            BooleanValidator,
        )

        v = get_validator(self.type)
        if v is None:
            return None

        # Auto-apply constraints based on validator type
        if isinstance(v, IntegerValidator):
            if self.min_value is not None or self.max_value is not None:
                v = v.in_range(
                    self.min_value if self.min_value is not None else -(2**31),
                    self.max_value if self.max_value is not None else 2**31 - 1,
                )
        elif isinstance(v, EnumerationValidator):
            if self.choices:
                v = v.with_choices(self.choices)
        elif isinstance(v, BooleanValidator):
            if self.default is not None and isinstance(self.default, bool):
                v = v.with_default(self.default)

        return v


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
        parser: Validation/parsing callback function (deprecated - use validator)
        action: How to handle parsed values (typically 'append-command')
        choices: Valid values for ENUMERATION type elements
        validator: Explicit validator override
        example: Custom syntax hint (overrides auto-generated from type)
    """

    type: ValueType
    description: str = ''
    parser: Callable | None = None  # Deprecated - use validator
    action: str = 'append-command'
    choices: list[str] | None = None
    validator: 'Validator[Any] | None' = None  # Explicit validator override
    example: str | None = None  # Custom syntax hint for definition generation

    def get_validator(self) -> 'Validator[Any] | None':
        """Get or create validator from type + constraints.

        Priority:
        1. Explicit self.validator if set
        2. Auto-generated from ValueType + constraints
        3. None if no validator available

        Returns:
            Configured Validator instance, or None
        """
        # Priority 1: Explicit validator
        if self.validator is not None:
            return self.validator

        # Priority 2: Auto-generate from type
        from exabgp.configuration.validator import get_validator, EnumerationValidator

        v = get_validator(self.type)
        if v is None:
            return None

        # Auto-apply constraints
        if isinstance(v, EnumerationValidator) and self.choices:
            v = v.with_choices(self.choices)

        return v


# =============================================================================
# Definition Generation: Schema → Syntax Hints
# =============================================================================

# Map ValueType to syntax hint string for definition generation
VALUE_TYPE_HINTS: dict[ValueType, str] = {
    # Network types
    ValueType.IP_ADDRESS: '<ip>',
    ValueType.IP_PREFIX: '<ip>/<mask>',
    ValueType.IP_RANGE: '<ip-range>',
    ValueType.ASN: '<asn>',
    ValueType.PORT: '<port>',
    # BGP-specific types
    ValueType.COMMUNITY: '<community>',
    ValueType.EXTENDED_COMMUNITY: '<ext-community>',
    ValueType.LARGE_COMMUNITY: '<large-community>',
    ValueType.RD: '<rd>',
    ValueType.RT: '<rt>',
    ValueType.NEXT_HOP: '<ip>',
    # Basic types
    ValueType.BOOLEAN: '',  # Flag, no value
    ValueType.STRING: '<string>',
    ValueType.INTEGER: '<number>',
    ValueType.ENUMERATION: '<value>',
    ValueType.HEX_STRING: '<hex>',
    # Special types
    ValueType.LABEL: '<label>',
    ValueType.ORIGIN: 'IGP|EGP|INCOMPLETE',
    ValueType.MED: '<number>',
    ValueType.LOCAL_PREF: '<number>',
    ValueType.ATOMIC_AGGREGATE: '',  # Flag
    ValueType.AGGREGATOR: '(<asn>:<ip>)',
    ValueType.AS_PATH: '[ <asn>.. ]',
    ValueType.BANDWIDTH: '<bandwidth>',
}


def leaf_to_definition(name: str, leaf: Leaf | LeafList) -> str:
    """Generate definition string from Leaf/LeafList schema.

    Priority:
    1. Use leaf.example if provided (custom override)
    2. Use choices joined with | if available
    3. Use VALUE_TYPE_HINTS mapping
    4. Fall back to '<value>'

    Args:
        name: Command name (e.g., 'next-hop', 'origin')
        leaf: Leaf or LeafList schema element

    Returns:
        Definition string (e.g., 'next-hop <ip>', 'origin IGP|EGP|INCOMPLETE')
    """
    # Priority 1: Custom example override
    if leaf.example is not None:
        value_hint = leaf.example
    # Priority 2: Choices (case-insensitive display as uppercase)
    elif leaf.choices:
        value_hint = '|'.join(c.upper() for c in leaf.choices)
    # Priority 3: ValueType mapping
    else:
        value_hint = VALUE_TYPE_HINTS.get(leaf.type, '<value>')

    # For boolean/flag types, no value suffix
    if value_hint:
        return f'{name} {value_hint}'
    return name


def schema_to_definition(children: dict[str, Leaf | LeafList | 'Container']) -> list[str]:
    """Generate definition list from schema children.

    Args:
        children: Dict of child schema elements

    Returns:
        List of definition strings for Leaf/LeafList children
    """
    result = []
    for name, child in children.items():
        if isinstance(child, (Leaf, LeafList)):
            result.append(leaf_to_definition(name, child))
    return result


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


# =============================================================================
# Extended Schema Types for Complex Objects
# =============================================================================


@dataclass
class TupleLeaf(Leaf):
    """Leaf that returns tuples using a conversion map.

    Used for family/nexthop commands that return (AFI, SAFI) or (AFI, SAFI, AFI).
    The conversion_map maps AFI context to SAFI choices to tuple values.

    Example:
        TupleLeaf(
            type=ValueType.ENUMERATION,
            choices=['unicast', 'multicast', ...],
            conversion_map={'ipv4': {'unicast': (AFI.ipv4, SAFI.unicast), ...}},
            afi_context='ipv4',
            track_duplicates=True,
        )

    Attributes:
        conversion_map: Dict mapping AFI → SAFI → tuple result
        afi_context: The AFI context for this leaf (set by command keyword)
        track_duplicates: Whether to track seen values for deduplication
    """

    conversion_map: dict[str, dict[str, tuple[Any, ...]]] | None = None
    afi_context: str = ''
    track_duplicates: bool = False


@dataclass
class CompositeLeaf(Leaf):
    """Leaf that constructs objects from multiple tokens.

    Used for operational messages that parse patterns like:
        asm afi ipv4 safi unicast advisory "message"

    The validator parses key-value pairs and calls the result_factory.

    Example:
        CompositeLeaf(
            parameters=['afi', 'safi', 'advisory'],
            result_factory=Advisory.ASM,
            action='append-name',
        )

    Attributes:
        parameters: List of parameter names to parse in order
        result_factory: Callable to create the result object
        converters: Optional dict mapping parameter names to converter functions
    """

    parameters: list[str] = field(default_factory=list)
    result_factory: Callable[..., Any] | None = None
    converters: dict[str, Callable[[str], Any]] | None = None


@dataclass
class RouteBuilder(Container):
    """Container that builds Change objects from child commands.

    Replaces custom ip() and vpls() functions with schema-driven route building.
    The nlri_factory creates the NLRI, prefix_parser parses the prefix,
    and children define the attribute/nlri sub-commands.

    Example:
        RouteBuilder(
            nlri_factory=INET,
            prefix_parser=prefix,
            children={
                'next-hop': Leaf(type=ValueType.NEXT_HOP, action='nexthop-and-attribute'),
                'origin': Leaf(type=ValueType.ORIGIN, action='attribute-add'),
                ...
            },
        )

    Attributes:
        nlri_factory: Callable to create NLRI object (e.g., INET, VPLS)
        prefix_parser: Callable to parse the prefix/route target
        assign: Dict mapping command names to NLRI field names for nlri-set actions
        factory_with_afi: If True, factory is called with (afi, safi, action) even without prefix
                          (used for FlowSpec where NLRI needs AFI/SAFI but has no prefix)
    """

    nlri_factory: Callable[..., Any] | None = None
    prefix_parser: Callable[..., Any] | None = None
    assign: dict[str, str] = field(default_factory=dict)
    factory_with_afi: bool = False

    @property
    def definition(self) -> list[str]:
        """Generate definition list from schema children."""
        return schema_to_definition(self.children)

    @property
    def syntax(self) -> str:
        """Generate syntax string from definition."""
        defn = ' ;\n   '.join(self.definition)
        return f'<safi> <ip>/<netmask> {{ \n   {defn}\n}}'


@dataclass
class TypeSelectorBuilder(Container):
    """Container that selects NLRI type from first token, then builds route.

    Used for MUP and MVPN routes where first token selects the NLRI constructor,
    which parses NLRI-specific fields, then common attributes follow.

    Example:
        TypeSelectorBuilder(
            type_factories={
                'mup-isd': srv6_mup_isd,
                'mup-dsd': srv6_mup_dsd,
            },
            factory_needs_action=False,  # MUP: factory(tokeniser, afi)
            children={
                'next-hop': Leaf(type=ValueType.NEXT_HOP, action='nexthop-and-attribute'),
                ...
            },
        )

    Attributes:
        type_factories: Dict mapping type name to factory function
        factory_needs_action: If True, factory is called with (tokeniser, afi, action)
                              If False, factory is called with (tokeniser, afi)
    """

    type_factories: dict[str, Callable[..., Any]] = field(default_factory=dict)
    factory_needs_action: bool = False

    @property
    def definition(self) -> list[str]:
        """Generate definition list from schema children."""
        return schema_to_definition(self.children)


# Type alias for schema elements
SchemaElement = Leaf | LeafList | Container | TupleLeaf | CompositeLeaf | RouteBuilder | TypeSelectorBuilder


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


def schema_to_json_schema(element: SchemaElement) -> dict[str, Any]:
    """Convert schema element to JSON Schema format.

    Generates a JSON Schema (draft-07 compatible) representation of the
    configuration schema. This can be used for:
    - IDE autocomplete integration
    - Configuration file validation
    - External tooling and documentation

    Args:
        element: Schema element to convert

    Returns:
        JSON Schema representation

    Example:
        >>> leaf = Leaf(type=ValueType.INTEGER, min_value=0, max_value=100)
        >>> schema_to_json_schema(leaf)
        {'type': 'integer', 'minimum': 0, 'maximum': 100}
    """
    if isinstance(element, Leaf):
        # Get JSON Schema from validator if available
        validator = element.get_validator()
        if validator is not None:
            schema = validator.to_schema()
        else:
            schema = {'type': 'string'}

        # Add description and default
        if element.description:
            schema['description'] = element.description
        if element.default is not None:
            schema['default'] = element.default

        return schema

    if isinstance(element, LeafList):
        # Get item schema from validator if available
        validator = element.get_validator()
        if validator is not None:
            item_schema = validator.to_schema()
        else:
            item_schema = {'type': 'string'}

        leaf_list_schema: dict[str, Any] = {
            'type': 'array',
            'items': item_schema,
        }
        if element.description:
            leaf_list_schema['description'] = element.description

        return leaf_list_schema

    if isinstance(element, Container):
        properties: dict[str, Any] = {}
        required: list[str] = []

        for name, child in element.children.items():
            properties[name] = schema_to_json_schema(child)
            # Check if child is mandatory
            if isinstance(child, Leaf) and child.mandatory:
                required.append(name)

        container_schema: dict[str, Any] = {
            'type': 'object',
            'properties': properties,
            'additionalProperties': False,
        }
        if element.description:
            container_schema['description'] = element.description
        if required:
            container_schema['required'] = required

        return container_schema

    return {}
