"""Test that generated example configuration is valid and parseable.

Tests for the exabgp.configuration.example module that generates
documented configuration examples from schema definitions.
"""

from exabgp.configuration.example import (
    VALUE_TYPE_EXAMPLES,
    generate_full_example,
    generate_neighbor_example,
    generate_leaf_comment,
    get_example_value,
)
from exabgp.configuration.schema import Container, Leaf, ValueType


class TestValueTypeExamples:
    """Test that all ValueType examples are valid."""

    def test_all_value_types_have_examples(self):
        """Every ValueType must have a default example."""
        for vtype in ValueType:
            assert vtype in VALUE_TYPE_EXAMPLES, f'Missing example for {vtype}'

    def test_ip_address_example_valid(self):
        """IP_ADDRESS example should be a valid IP."""
        from exabgp.protocol.ip import IP

        example = VALUE_TYPE_EXAMPLES[ValueType.IP_ADDRESS]
        IP.from_string(example)  # Raises if invalid

    def test_asn_example_valid(self):
        """ASN example should be a valid AS number."""
        example = VALUE_TYPE_EXAMPLES[ValueType.ASN]
        assert example.isdigit() or example == 'auto'

    def test_community_example_valid(self):
        """COMMUNITY example should be valid format."""
        example = VALUE_TYPE_EXAMPLES[ValueType.COMMUNITY]
        assert ':' in example  # AS:value format

    def test_extended_community_example_valid(self):
        """EXTENDED_COMMUNITY example should be valid format."""
        example = VALUE_TYPE_EXAMPLES[ValueType.EXTENDED_COMMUNITY]
        assert ':' in example  # type:AS:value format

    def test_large_community_example_valid(self):
        """LARGE_COMMUNITY example should be valid format."""
        example = VALUE_TYPE_EXAMPLES[ValueType.LARGE_COMMUNITY]
        assert example.count(':') == 2  # AS:value:value format

    def test_origin_example_valid(self):
        """ORIGIN example should be a valid origin value."""
        example = VALUE_TYPE_EXAMPLES[ValueType.ORIGIN]
        assert example in ('igp', 'egp', 'incomplete')

    def test_boolean_example_valid(self):
        """BOOLEAN example should be enable/disable."""
        example = VALUE_TYPE_EXAMPLES[ValueType.BOOLEAN]
        assert example in ('enable', 'disable', 'true', 'false')


class TestLeafComment:
    """Test leaf comment generation."""

    def test_leaf_comment_includes_description(self):
        """Comment should include leaf description."""
        leaf = Leaf(type=ValueType.INTEGER, description='Test description')
        comments = generate_leaf_comment('test', leaf, '    ')
        assert any('Test description' in c for c in comments)

    def test_leaf_comment_includes_type(self):
        """Comment should include type name."""
        leaf = Leaf(type=ValueType.INTEGER, description='Test')
        comments = generate_leaf_comment('test', leaf, '    ')
        assert any('Type:' in c and 'INTEGER' in c for c in comments)

    def test_leaf_comment_includes_mandatory(self):
        """Comment should include mandatory flag when set."""
        leaf = Leaf(type=ValueType.INTEGER, mandatory=True)
        comments = generate_leaf_comment('test', leaf, '    ')
        assert any('Mandatory: yes' in c for c in comments)

    def test_leaf_comment_includes_default(self):
        """Comment should include default value when set."""
        leaf = Leaf(type=ValueType.INTEGER, default=100)
        comments = generate_leaf_comment('test', leaf, '    ')
        assert any('Default: 100' in c for c in comments)

    def test_leaf_comment_includes_range(self):
        """Comment should include range when set."""
        leaf = Leaf(type=ValueType.INTEGER, min_value=0, max_value=255)
        comments = generate_leaf_comment('test', leaf, '    ')
        assert any('Range: 0-255' in c for c in comments)

    def test_leaf_comment_includes_choices(self):
        """Comment should include choices when set."""
        leaf = Leaf(type=ValueType.ENUMERATION, choices=['a', 'b', 'c'])
        comments = generate_leaf_comment('test', leaf, '    ')
        assert any('Choices:' in c and 'a' in c for c in comments)


class TestGetExampleValue:
    """Test example value retrieval."""

    def test_custom_example_takes_priority(self):
        """Custom leaf.example should take priority."""
        leaf = Leaf(type=ValueType.INTEGER, example='999')
        assert get_example_value('test', leaf) == '999'

    def test_choices_used_when_no_example(self):
        """First choice should be used when no custom example."""
        leaf = Leaf(type=ValueType.ENUMERATION, choices=['first', 'second'])
        assert get_example_value('test', leaf) == 'first'

    def test_boolean_default_true_gives_enable(self):
        """Boolean with default True should give 'enable'."""
        leaf = Leaf(type=ValueType.BOOLEAN, default=True)
        assert get_example_value('test', leaf) == 'enable'

    def test_boolean_default_false_gives_disable(self):
        """Boolean with default False should give 'disable'."""
        leaf = Leaf(type=ValueType.BOOLEAN, default=False)
        assert get_example_value('test', leaf) == 'disable'

    def test_type_example_used_as_fallback(self):
        """VALUE_TYPE_EXAMPLES should be used as fallback."""
        leaf = Leaf(type=ValueType.IP_ADDRESS)
        assert get_example_value('test', leaf) == '127.0.0.1'


class TestSchemaExamples:
    """Test that schema leaf examples are parseable."""

    def test_neighbor_schema_has_examples(self):
        """Neighbor schema should have valid leaves."""
        from exabgp.configuration.neighbor import ParseNeighbor

        schema = ParseNeighbor.schema
        assert isinstance(schema, Container)
        assert 'local-as' in schema.children
        assert 'peer-as' in schema.children

    def test_capability_schema_has_examples(self):
        """Capability schema should have valid leaves."""
        from exabgp.configuration.capability import ParseCapability

        schema = ParseCapability.schema
        assert isinstance(schema, Container)
        assert 'asn4' in schema.children
        assert 'add-path' in schema.children

    def test_static_route_schema_has_examples(self):
        """Static route schema should have valid leaves."""
        from exabgp.configuration.static.route import ParseStaticRoute

        schema = ParseStaticRoute.schema
        assert isinstance(schema, Container)
        assert 'next-hop' in schema.children
        assert 'origin' in schema.children


class TestGeneratedConfig:
    """Test that generated config is valid."""

    def test_generated_example_not_empty(self):
        """Generated example should produce non-empty output."""
        output = generate_full_example()
        assert output
        assert len(output) > 100

    def test_generated_example_has_neighbor(self):
        """Generated example should contain neighbor section."""
        output = generate_full_example()
        assert 'neighbor' in output

    def test_generated_example_has_mandatory_fields(self):
        """Generated example should contain mandatory fields."""
        output = generate_full_example()
        assert 'local-as' in output
        assert 'peer-as' in output

    def test_generated_example_has_capability(self):
        """Generated example should contain capability section."""
        output = generate_full_example()
        assert 'capability' in output
        assert 'asn4' in output

    def test_generated_example_has_static_routes(self):
        """Generated example should contain static routes section."""
        output = generate_full_example()
        assert 'static' in output
        assert 'route' in output
        assert 'next-hop' in output

    def test_generated_example_has_family(self):
        """Generated example should contain family section."""
        output = generate_full_example()
        assert 'family' in output
        assert 'ipv4' in output

    def test_generated_neighbor_example(self):
        """generate_neighbor_example should produce valid output."""
        output = generate_neighbor_example()
        assert 'neighbor' in output
        assert 'local-as' in output
        assert 'peer-as' in output

    def test_generated_example_has_comments(self):
        """Generated example should contain documentation comments."""
        output = generate_full_example()
        # Check for comment markers
        assert '# Type:' in output
        assert '# Mandatory:' in output or '# Default:' in output

    def test_generated_example_has_section_headers(self):
        """Generated example should contain section headers."""
        output = generate_full_example()
        assert '# NEIGHBOR CONFIGURATION' in output
        assert '# CAPABILITY' in output
        assert '# STATIC ROUTES' in output


class TestGeneratedConfigSyntax:
    """Test that generated config has valid syntax."""

    def test_braces_are_balanced(self):
        """Generated config should have balanced braces."""
        output = generate_full_example()
        open_braces = output.count('{')
        close_braces = output.count('}')
        assert open_braces == close_braces, f'Unbalanced braces: {open_braces} open, {close_braces} close'

    def test_statements_end_with_semicolon(self):
        """Config statements should end with semicolons."""
        output = generate_full_example()
        # Find lines that look like config statements (key value)
        for line in output.split('\n'):
            stripped = line.strip()
            # Skip comments, empty lines, braces
            if not stripped or stripped.startswith('#') or stripped in ('{', '}'):
                continue
            # Skip opening braces with content
            if stripped.endswith('{'):
                continue
            # Config statements should end with ;
            if not stripped.endswith(';') and not stripped.endswith('}'):
                # This might be a continuation line, check if it's valid
                assert stripped.endswith(';') or stripped.endswith('{') or stripped.endswith('}'), (
                    f'Line does not end with semicolon or brace: {line}'
                )
