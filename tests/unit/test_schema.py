"""test_schema.py

Unit tests for the YANG-inspired configuration schema module.

Created by Thomas Mangin on 2025-12-02.
Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import pytest

from exabgp.configuration.schema import (
    Completion,
    Container,
    Leaf,
    LeafList,
    ValueType,
    get_completions,
    get_value_completions,
    schema_to_dict,
)


class TestValueType:
    """Tests for ValueType enum."""

    def test_value_types_have_string_values(self):
        """All ValueType members have non-empty string values."""
        for member in ValueType:
            assert isinstance(member.value, str)
            assert len(member.value) > 0

    def test_network_types_exist(self):
        """Network-related types are defined."""
        assert ValueType.IP_ADDRESS.value == 'ip-address'
        assert ValueType.IP_PREFIX.value == 'ip-prefix'
        assert ValueType.IP_RANGE.value == 'ip-range'
        assert ValueType.ASN.value == 'as-number'
        assert ValueType.PORT.value == 'port'

    def test_bgp_types_exist(self):
        """BGP-specific types are defined."""
        assert ValueType.COMMUNITY.value == 'community'
        assert ValueType.EXTENDED_COMMUNITY.value == 'ext-community'
        assert ValueType.LARGE_COMMUNITY.value == 'large-community'
        assert ValueType.RD.value == 'route-distinguisher'
        assert ValueType.RT.value == 'route-target'
        assert ValueType.NEXT_HOP.value == 'next-hop'

    def test_basic_types_exist(self):
        """Basic types are defined."""
        assert ValueType.BOOLEAN.value == 'boolean'
        assert ValueType.STRING.value == 'string'
        assert ValueType.INTEGER.value == 'integer'
        assert ValueType.ENUMERATION.value == 'enumeration'
        assert ValueType.HEX_STRING.value == 'hex-string'


class TestLeaf:
    """Tests for Leaf dataclass."""

    def test_leaf_minimal(self):
        """Leaf can be created with just type."""
        leaf = Leaf(type=ValueType.INTEGER)
        assert leaf.type == ValueType.INTEGER
        assert leaf.description == ''
        assert leaf.default is None
        assert leaf.mandatory is False
        assert leaf.parser is None
        assert leaf.choices is None
        assert leaf.min_value is None
        assert leaf.max_value is None
        # Action defaults
        assert leaf.target is None
        assert leaf.operation is None
        assert leaf.key is None

    def test_leaf_full(self):
        """Leaf can be created with all attributes."""
        from exabgp.configuration.validator import IntegerValidator
        from exabgp.configuration.schema import ActionTarget, ActionOperation, ActionKey

        dummy_validator = IntegerValidator(min_value=0, max_value=65535)

        leaf = Leaf(
            type=ValueType.INTEGER,
            description='Test integer',
            default=100,
            mandatory=True,
            validator=dummy_validator,
            target=ActionTarget.SCOPE,
            operation=ActionOperation.APPEND,
            key=ActionKey.COMMAND,
            min_value=0,
            max_value=65535,
        )
        assert leaf.type == ValueType.INTEGER
        assert leaf.description == 'Test integer'
        assert leaf.default == 100
        assert leaf.mandatory is True
        assert leaf.validator is dummy_validator
        assert leaf.target == ActionTarget.SCOPE
        assert leaf.operation == ActionOperation.APPEND
        assert leaf.key == ActionKey.COMMAND
        assert leaf.min_value == 0
        assert leaf.max_value == 65535

    def test_leaf_enumeration(self):
        """Leaf with enumeration type has choices."""
        leaf = Leaf(
            type=ValueType.ENUMERATION,
            description='Origin type',
            choices=['igp', 'egp', 'incomplete'],
        )
        assert leaf.type == ValueType.ENUMERATION
        assert leaf.choices == ['igp', 'egp', 'incomplete']

    def test_leaf_default_types(self):
        """Default values can be different types."""
        # Integer default
        leaf_int = Leaf(type=ValueType.INTEGER, default=180)
        assert leaf_int.default == 180

        # Boolean default
        leaf_bool = Leaf(type=ValueType.BOOLEAN, default=True)
        assert leaf_bool.default is True

        # String default
        leaf_str = Leaf(type=ValueType.STRING, default='test')
        assert leaf_str.default == 'test'


class TestLeafList:
    """Tests for LeafList dataclass."""

    def test_leaflist_minimal(self):
        """LeafList can be created with just type."""
        leaflist = LeafList(type=ValueType.COMMUNITY)
        assert leaflist.type == ValueType.COMMUNITY
        assert leaflist.description == ''
        assert leaflist.parser is None
        assert leaflist.choices is None
        # Action defaults
        assert leaflist.target is None
        assert leaflist.operation is None
        assert leaflist.key is None

    def test_leaflist_full(self):
        """LeafList can be created with all attributes."""
        from exabgp.configuration.validator import StringValidator
        from exabgp.configuration.schema import ActionTarget, ActionOperation, ActionKey

        dummy_validator = StringValidator()

        leaflist = LeafList(
            type=ValueType.COMMUNITY,
            description='BGP communities',
            validator=dummy_validator,
            target=ActionTarget.SCOPE,
            operation=ActionOperation.EXTEND,
            key=ActionKey.COMMAND,
            choices=['no-export', 'no-advertise'],
        )
        assert leaflist.type == ValueType.COMMUNITY
        assert leaflist.description == 'BGP communities'
        assert leaflist.validator is dummy_validator
        assert leaflist.target == ActionTarget.SCOPE
        assert leaflist.operation == ActionOperation.EXTEND
        assert leaflist.key == ActionKey.COMMAND
        assert leaflist.choices == ['no-export', 'no-advertise']


class TestContainer:
    """Tests for Container dataclass."""

    def test_container_empty(self):
        """Container can be created empty."""
        container = Container()
        assert container.description == ''
        assert container.children == {}

    def test_container_with_description(self):
        """Container can have description."""
        container = Container(description='Test container')
        assert container.description == 'Test container'

    def test_container_with_leaf_children(self):
        """Container can have Leaf children."""
        container = Container(
            description='Test',
            children={
                'hold-time': Leaf(type=ValueType.INTEGER, default=180),
                'passive': Leaf(type=ValueType.BOOLEAN, default=True),
            },
        )
        assert len(container.children) == 2
        assert isinstance(container.children['hold-time'], Leaf)
        assert isinstance(container.children['passive'], Leaf)

    def test_container_with_nested_containers(self):
        """Container can have nested Container children."""
        container = Container(
            description='Neighbor',
            children={
                'family': Container(description='Address families'),
                'capability': Container(description='BGP capabilities'),
            },
        )
        assert len(container.children) == 2
        assert isinstance(container.children['family'], Container)
        assert isinstance(container.children['capability'], Container)

    def test_container_with_mixed_children(self):
        """Container can have mixed child types."""
        container = Container(
            description='Neighbor',
            children={
                'peer-as': Leaf(type=ValueType.ASN, mandatory=True),
                'community': LeafList(type=ValueType.COMMUNITY),
                'family': Container(description='Address families'),
            },
        )
        assert isinstance(container.children['peer-as'], Leaf)
        assert isinstance(container.children['community'], LeafList)
        assert isinstance(container.children['family'], Container)


class TestCompletion:
    """Tests for Completion dataclass."""

    def test_completion_minimal(self):
        """Completion can be created with required fields."""
        completion = Completion(
            keyword='peer-as',
            description='Peer AS number',
            completion_type='command',
        )
        assert completion.keyword == 'peer-as'
        assert completion.description == 'Peer AS number'
        assert completion.completion_type == 'command'
        assert completion.value_type is None
        assert completion.choices is None

    def test_completion_full(self):
        """Completion can be created with all fields."""
        completion = Completion(
            keyword='origin',
            description='BGP origin',
            completion_type='command',
            value_type=ValueType.ENUMERATION,
            choices=['igp', 'egp', 'incomplete'],
        )
        assert completion.keyword == 'origin'
        assert completion.value_type == ValueType.ENUMERATION
        assert completion.choices == ['igp', 'egp', 'incomplete']


class TestGetCompletions:
    """Tests for get_completions function."""

    @pytest.fixture
    def sample_schema(self):
        """Create a sample schema for testing."""
        return Container(
            description='Root',
            children={
                'neighbor': Container(
                    description='BGP neighbor',
                    children={
                        'peer-as': Leaf(type=ValueType.ASN, description='Peer AS number', mandatory=True),
                        'local-as': Leaf(type=ValueType.ASN, description='Local AS number', mandatory=True),
                        'hold-time': Leaf(type=ValueType.INTEGER, description='Hold time', default=180),
                        'passive': Leaf(type=ValueType.BOOLEAN, description='Passive mode', default=True),
                        'family': Container(
                            description='Address families',
                            children={
                                'ipv4': Leaf(
                                    type=ValueType.ENUMERATION,
                                    description='IPv4 family',
                                    choices=['unicast', 'multicast', 'nlri-mpls', 'mpls-vpn', 'flow'],
                                ),
                                'ipv6': Leaf(
                                    type=ValueType.ENUMERATION,
                                    description='IPv6 family',
                                    choices=['unicast', 'multicast', 'nlri-mpls', 'mpls-vpn', 'flow'],
                                ),
                            },
                        ),
                        'capability': Container(description='BGP capabilities'),
                    },
                ),
                'process': Container(description='External process'),
            },
        )

    def test_completions_at_root(self, sample_schema):
        """Completions at root return top-level sections."""
        completions = get_completions(sample_schema, [])
        assert len(completions) == 2
        keywords = {c.keyword for c in completions}
        assert keywords == {'neighbor', 'process'}

    def test_completions_at_neighbor(self, sample_schema):
        """Completions in neighbor section return all commands and subsections."""
        completions = get_completions(sample_schema, ['neighbor'])
        assert len(completions) == 6

        # Check for commands
        commands = [c for c in completions if c.completion_type == 'command']
        assert len(commands) == 4
        command_keywords = {c.keyword for c in commands}
        assert 'peer-as' in command_keywords
        assert 'local-as' in command_keywords
        assert 'hold-time' in command_keywords
        assert 'passive' in command_keywords

        # Check for sections
        sections = [c for c in completions if c.completion_type == 'section']
        assert len(sections) == 2
        section_keywords = {c.keyword for c in sections}
        assert section_keywords == {'family', 'capability'}

    def test_completions_with_dynamic_value(self, sample_schema):
        """Completions work when path contains dynamic values (like IP addresses)."""
        # In real usage: ['neighbor', '10.0.0.1', 'family']
        # The '10.0.0.1' is skipped as it's not in schema
        completions = get_completions(sample_schema, ['neighbor', '10.0.0.1'])
        # Should still return neighbor's children
        assert len(completions) == 6

    def test_completions_nested(self, sample_schema):
        """Completions work for nested containers."""
        completions = get_completions(sample_schema, ['neighbor', 'family'])
        assert len(completions) == 2
        keywords = {c.keyword for c in completions}
        assert keywords == {'ipv4', 'ipv6'}

    def test_completions_include_value_type(self, sample_schema):
        """Command completions include value type."""
        completions = get_completions(sample_schema, ['neighbor'])
        peer_as = next(c for c in completions if c.keyword == 'peer-as')
        assert peer_as.value_type == ValueType.ASN

    def test_completions_include_choices(self, sample_schema):
        """Enumeration completions include choices."""
        completions = get_completions(sample_schema, ['neighbor', 'family'])
        ipv4 = next(c for c in completions if c.keyword == 'ipv4')
        assert ipv4.choices == ['unicast', 'multicast', 'nlri-mpls', 'mpls-vpn', 'flow']

    def test_completions_empty_path_invalid(self, sample_schema):
        """Empty schema returns empty completions."""
        empty_schema = Container()
        completions = get_completions(empty_schema, [])
        assert completions == []

    def test_completions_at_leaf_returns_empty(self, sample_schema):
        """Trying to get completions at a leaf returns empty."""
        completions = get_completions(sample_schema, ['neighbor', 'peer-as'])
        assert completions == []


class TestGetValueCompletions:
    """Tests for get_value_completions function."""

    @pytest.fixture
    def sample_schema(self):
        """Create a sample schema for testing."""
        return Container(
            description='Root',
            children={
                'neighbor': Container(
                    description='BGP neighbor',
                    children={
                        'family': Container(
                            description='Address families',
                            children={
                                'ipv4': Leaf(
                                    type=ValueType.ENUMERATION,
                                    description='IPv4 family',
                                    choices=['unicast', 'multicast', 'nlri-mpls', 'mpls-vpn', 'flow'],
                                ),
                            },
                        ),
                        'origin': Leaf(
                            type=ValueType.ENUMERATION,
                            description='Origin',
                            choices=['igp', 'egp', 'incomplete'],
                        ),
                        'hold-time': Leaf(type=ValueType.INTEGER, description='Hold time'),
                    },
                ),
            },
        )

    def test_value_completions_full_match(self, sample_schema):
        """Get all choices when no partial is given."""
        completions = get_value_completions(sample_schema, ['neighbor', 'origin'], '')
        assert completions == ['igp', 'egp', 'incomplete']

    def test_value_completions_partial_match(self, sample_schema):
        """Get matching choices when partial is given."""
        completions = get_value_completions(sample_schema, ['neighbor', 'family', 'ipv4'], 'uni')
        assert completions == ['unicast']

    def test_value_completions_partial_multiple_matches(self, sample_schema):
        """Get multiple matches when partial matches several choices."""
        completions = get_value_completions(sample_schema, ['neighbor', 'family', 'ipv4'], 'm')
        assert set(completions) == {'multicast', 'mpls-vpn'}

    def test_value_completions_case_insensitive(self, sample_schema):
        """Partial matching is case-insensitive."""
        completions = get_value_completions(sample_schema, ['neighbor', 'origin'], 'IGP')
        assert completions == ['igp']

    def test_value_completions_no_match(self, sample_schema):
        """Return empty list when no choices match."""
        completions = get_value_completions(sample_schema, ['neighbor', 'origin'], 'xyz')
        assert completions == []

    def test_value_completions_non_enum(self, sample_schema):
        """Return empty for non-enumeration types."""
        completions = get_value_completions(sample_schema, ['neighbor', 'hold-time'], '')
        assert completions == []

    def test_value_completions_invalid_path(self, sample_schema):
        """Return empty for invalid paths."""
        completions = get_value_completions(sample_schema, ['invalid', 'path'], '')
        assert completions == []

    def test_value_completions_empty_path(self, sample_schema):
        """Return empty for empty path."""
        completions = get_value_completions(sample_schema, [], '')
        assert completions == []


class TestSchemaToDict:
    """Tests for schema_to_dict function."""

    def test_leaf_to_dict_minimal(self):
        """Leaf converts to dict with basic fields."""
        leaf = Leaf(type=ValueType.INTEGER, description='Test')
        result = schema_to_dict(leaf)
        assert result == {
            'type': 'leaf',
            'value_type': 'integer',
            'description': 'Test',
        }

    def test_leaf_to_dict_full(self):
        """Leaf converts to dict with all fields."""
        leaf = Leaf(
            type=ValueType.INTEGER,
            description='Test',
            default=100,
            mandatory=True,
            min_value=0,
            max_value=65535,
        )
        result = schema_to_dict(leaf)
        assert result == {
            'type': 'leaf',
            'value_type': 'integer',
            'description': 'Test',
            'default': 100,
            'mandatory': True,
            'min_value': 0,
            'max_value': 65535,
        }

    def test_leaf_to_dict_with_choices(self):
        """Leaf with choices includes them in dict."""
        leaf = Leaf(
            type=ValueType.ENUMERATION,
            description='Origin',
            choices=['igp', 'egp', 'incomplete'],
        )
        result = schema_to_dict(leaf)
        assert result['choices'] == ['igp', 'egp', 'incomplete']

    def test_leaflist_to_dict(self):
        """LeafList converts to dict."""
        leaflist = LeafList(
            type=ValueType.COMMUNITY,
            description='Communities',
        )
        result = schema_to_dict(leaflist)
        assert result == {
            'type': 'leaf-list',
            'value_type': 'community',
            'description': 'Communities',
        }

    def test_container_to_dict(self):
        """Container converts to dict with children."""
        container = Container(
            description='Test container',
            children={
                'value': Leaf(type=ValueType.INTEGER, description='A value'),
            },
        )
        result = schema_to_dict(container)
        assert result['type'] == 'container'
        assert result['description'] == 'Test container'
        assert 'value' in result['children']
        assert result['children']['value']['type'] == 'leaf'

    def test_nested_container_to_dict(self):
        """Nested containers convert correctly."""
        container = Container(
            description='Root',
            children={
                'nested': Container(
                    description='Nested',
                    children={
                        'leaf': Leaf(type=ValueType.STRING, description='Deep'),
                    },
                ),
            },
        )
        result = schema_to_dict(container)
        assert result['children']['nested']['type'] == 'container'
        assert result['children']['nested']['children']['leaf']['type'] == 'leaf'


class TestParserSchemaIntegration:
    """Integration tests verifying actual parser schemas work correctly."""

    def test_parse_family_has_schema(self):
        """ParseFamily has a valid schema."""
        from exabgp.configuration.neighbor.family import ParseFamily

        assert ParseFamily.has_schema()
        completions = ParseFamily.get_schema_completions()
        keywords = {c.keyword for c in completions}
        assert 'ipv4' in keywords
        assert 'ipv6' in keywords
        assert 'l2vpn' in keywords

    def test_parse_family_value_completions(self):
        """ParseFamily provides value completions for ipv4."""
        from exabgp.configuration.neighbor.family import ParseFamily

        completions = ParseFamily.get_schema_value_completions('ipv4', 'uni')
        assert 'unicast' in completions

    def test_parse_capability_has_schema(self):
        """ParseCapability has a valid schema."""
        from exabgp.configuration.capability import ParseCapability

        assert ParseCapability.has_schema()
        completions = ParseCapability.get_schema_completions()
        keywords = {c.keyword for c in completions}
        assert 'asn4' in keywords
        assert 'graceful-restart' in keywords
        assert 'add-path' in keywords

    def test_parse_capability_add_path_completions(self):
        """ParseCapability provides value completions for add-path."""
        from exabgp.configuration.capability import ParseCapability

        completions = ParseCapability.get_schema_value_completions('add-path', '')
        assert 'disable' in completions
        assert 'send' in completions
        assert 'receive' in completions

    def test_parse_static_route_has_schema(self):
        """ParseStaticRoute has a valid schema."""
        from exabgp.configuration.static.route import ParseStaticRoute

        assert ParseStaticRoute.has_schema()
        completions = ParseStaticRoute.get_schema_completions()
        keywords = {c.keyword for c in completions}
        assert 'next-hop' in keywords
        assert 'origin' in keywords
        assert 'community' in keywords
        assert 'as-path' in keywords

    def test_parse_static_route_origin_completions(self):
        """ParseStaticRoute provides value completions for origin."""
        from exabgp.configuration.static.route import ParseStaticRoute

        completions = ParseStaticRoute.get_schema_value_completions('origin', '')
        assert 'igp' in completions
        assert 'egp' in completions
        assert 'incomplete' in completions

    def test_parse_flow_match_has_schema(self):
        """ParseFlowMatch has a valid schema."""
        from exabgp.configuration.flow.match import ParseFlowMatch

        assert ParseFlowMatch.has_schema()
        completions = ParseFlowMatch.get_schema_completions()
        keywords = {c.keyword for c in completions}
        assert 'source' in keywords
        assert 'destination' in keywords
        assert 'protocol' in keywords

    def test_parse_flow_then_has_schema(self):
        """ParseFlowThen has a valid schema."""
        from exabgp.configuration.flow.then import ParseFlowThen

        assert ParseFlowThen.has_schema()
        completions = ParseFlowThen.get_schema_completions()
        keywords = {c.keyword for c in completions}
        assert 'accept' in keywords
        assert 'discard' in keywords
        assert 'rate-limit' in keywords
        assert 'redirect' in keywords

    def test_parse_vpls_has_schema(self):
        """ParseVPLS has a valid schema."""
        from exabgp.configuration.l2vpn.vpls import ParseVPLS

        assert ParseVPLS.has_schema()
        completions = ParseVPLS.get_schema_completions()
        keywords = {c.keyword for c in completions}
        assert 'endpoint' in keywords
        assert 'base' in keywords
        assert 'rd' in keywords

    def test_parse_operational_has_schema(self):
        """ParseOperational has a valid schema."""
        from exabgp.configuration.operational import ParseOperational

        assert ParseOperational.has_schema()
        completions = ParseOperational.get_schema_completions()
        keywords = {c.keyword for c in completions}
        assert 'asm' in keywords
        assert 'adm' in keywords

    def test_section_base_has_no_schema(self):
        """Base Section class has no schema (None)."""
        from exabgp.configuration.core import Section

        assert not Section.has_schema()
        assert Section.get_schema_completions() == []

    def test_all_parsers_with_schema_have_descriptions(self):
        """All schema children have descriptions."""
        from exabgp.configuration.neighbor.family import ParseFamily
        from exabgp.configuration.capability import ParseCapability
        from exabgp.configuration.static.route import ParseStaticRoute

        for parser_cls in [ParseFamily, ParseCapability, ParseStaticRoute]:
            if parser_cls.schema:
                for name, child in parser_cls.schema.children.items():
                    assert child.description, f'{parser_cls.__name__}.schema.{name} missing description'
