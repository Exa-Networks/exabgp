"""test_command_registry.py

Unit tests for CommandRegistry class.

Tests command introspection, metadata generation, and helper methods.
"""

from __future__ import annotations

from exabgp.reactor.api.command.registry import CommandRegistry, CommandMetadata


class TestCommandRegistryBasics:
    """Test basic registry functionality"""

    def setup_method(self):
        """Create registry instance for each test"""
        self.registry = CommandRegistry()

    def test_registry_creation(self):
        """Test that registry can be created"""
        assert self.registry is not None
        assert isinstance(self.registry, CommandRegistry)

    def test_get_all_commands(self):
        """Test that registry discovers commands"""
        commands = self.registry.get_all_commands()
        assert isinstance(commands, list)
        assert len(commands) > 0

    def test_get_all_commands_contains_known_commands(self):
        """Test that known commands are discovered"""
        commands = self.registry.get_all_commands()
        # These commands should always exist
        assert 'show neighbor' in commands
        assert 'announce route' in commands
        assert 'withdraw route' in commands
        assert 'teardown' in commands

    def test_get_base_commands(self):
        """Test getting base command list"""
        base_commands = self.registry.get_base_commands()
        assert isinstance(base_commands, list)
        assert len(base_commands) > 0
        # Base commands should be first word only
        assert 'show' in base_commands
        assert 'announce' in base_commands
        assert 'withdraw' in base_commands
        # Should NOT contain full commands
        assert 'show neighbor' not in base_commands

    def test_base_commands_are_sorted(self):
        """Test that base commands are sorted"""
        base_commands = self.registry.get_base_commands()
        assert base_commands == sorted(base_commands)

    def test_get_subcommands(self):
        """Test getting subcommands for a prefix"""
        subcommands = self.registry.get_subcommands('show')
        assert isinstance(subcommands, list)
        assert 'neighbor' in subcommands
        assert 'adj-rib' in subcommands

    def test_get_subcommands_announce(self):
        """Test subcommands for announce"""
        subcommands = self.registry.get_subcommands('announce')
        assert 'route' in subcommands
        assert 'eor' in subcommands
        assert 'route-refresh' in subcommands

    def test_get_subcommands_empty_for_leaf(self):
        """Test that leaf commands return empty list"""
        # teardown has no subcommands
        subcommands = self.registry.get_subcommands('teardown')
        assert subcommands == []


class TestCommandMetadata:
    """Test CommandMetadata class"""

    def setup_method(self):
        self.registry = CommandRegistry()

    def test_get_command_metadata_exists(self):
        """Test getting metadata for existing command"""
        metadata = self.registry.get_command_metadata('show neighbor')
        assert metadata is not None
        assert isinstance(metadata, CommandMetadata)

    def test_get_command_metadata_nonexistent(self):
        """Test getting metadata for non-existent command"""
        metadata = self.registry.get_command_metadata('nonexistent command')
        assert metadata is None

    def test_metadata_has_name(self):
        """Test that metadata contains command name"""
        metadata = self.registry.get_command_metadata('show neighbor')
        assert metadata.name == 'show neighbor'

    def test_metadata_has_neighbor_support(self):
        """Test that metadata includes neighbor support flag"""
        metadata = self.registry.get_command_metadata('show neighbor')
        assert isinstance(metadata.neighbor_support, bool)

    def test_metadata_has_json_support(self):
        """Test that metadata includes json support flag"""
        metadata = self.registry.get_command_metadata('show neighbor')
        assert isinstance(metadata.json_support, bool)
        # show neighbor should support JSON
        assert metadata.json_support is True

    def test_metadata_has_options(self):
        """Test that metadata includes options"""
        metadata = self.registry.get_command_metadata('show neighbor')
        # show neighbor has options: summary, extensive, configuration
        assert metadata.options is not None
        assert isinstance(metadata.options, list)
        assert 'summary' in metadata.options
        assert 'extensive' in metadata.options

    def test_metadata_has_syntax(self):
        """Test that metadata generates syntax"""
        metadata = self.registry.get_command_metadata('show neighbor')
        assert metadata.syntax is not None
        assert isinstance(metadata.syntax, str)
        assert 'show neighbor' in metadata.syntax

    def test_metadata_has_category(self):
        """Test that metadata has category"""
        metadata = self.registry.get_command_metadata('show neighbor')
        assert metadata.category is not None
        assert metadata.category == 'show'

    def test_metadata_neighbor_prefix_in_syntax(self):
        """Test that neighbor-supporting commands show prefix in syntax"""
        metadata = self.registry.get_command_metadata('announce route')
        if metadata.neighbor_support:
            assert '[neighbor <ip> [filters]]' in metadata.syntax

    def test_metadata_caching(self):
        """Test that metadata is cached"""
        metadata1 = self.registry.get_command_metadata('show neighbor')
        metadata2 = self.registry.get_command_metadata('show neighbor')
        # Should be same object (cached)
        assert metadata1 is metadata2


class TestCommandCategories:
    """Test command categorization"""

    def setup_method(self):
        self.registry = CommandRegistry()

    def test_get_commands_by_category_show(self):
        """Test getting show commands"""
        commands = self.registry.get_commands_by_category('show')
        assert isinstance(commands, list)
        assert len(commands) > 0
        # All should be CommandMetadata objects
        assert all(isinstance(cmd, CommandMetadata) for cmd in commands)
        # All should have category 'show'
        assert all(cmd.category == 'show' for cmd in commands)

    def test_get_commands_by_category_announce(self):
        """Test getting announce commands"""
        commands = self.registry.get_commands_by_category('announce')
        assert len(commands) > 0
        assert all(cmd.category == 'announce' for cmd in commands)

    def test_get_commands_by_category_control(self):
        """Test getting control commands"""
        commands = self.registry.get_commands_by_category('control')
        assert len(commands) > 0
        # Should include teardown, shutdown, etc.
        command_names = [cmd.name for cmd in commands]
        assert 'teardown' in command_names

    def test_get_commands_by_category_empty(self):
        """Test getting commands for non-existent category"""
        commands = self.registry.get_commands_by_category('nonexistent')
        assert commands == []


class TestAFISAFIValues:
    """Test AFI/SAFI value access"""

    def setup_method(self):
        self.registry = CommandRegistry()

    def test_get_afi_values(self):
        """Test getting AFI values"""
        afi_values = self.registry.get_afi_values()
        assert isinstance(afi_values, list)
        assert len(afi_values) > 0
        # Should include standard AFI values
        assert 'ipv4' in afi_values
        assert 'ipv6' in afi_values
        assert 'l2vpn' in afi_values

    def test_get_safi_values_all(self):
        """Test getting all SAFI values"""
        safi_values = self.registry.get_safi_values()
        assert isinstance(safi_values, list)
        assert len(safi_values) > 0
        # Should include standard SAFI values
        assert 'unicast' in safi_values
        assert 'multicast' in safi_values
        assert 'mpls-vpn' in safi_values

    def test_get_safi_values_for_ipv4(self):
        """Test getting SAFI values for IPv4"""
        safi_values = self.registry.get_safi_values('ipv4')
        assert isinstance(safi_values, list)
        assert len(safi_values) > 0
        # IPv4 should support unicast
        assert 'unicast' in safi_values
        assert 'multicast' in safi_values
        assert 'flow' in safi_values

    def test_get_safi_values_for_ipv6(self):
        """Test getting SAFI values for IPv6"""
        safi_values = self.registry.get_safi_values('ipv6')
        assert isinstance(safi_values, list)
        # IPv6 should support unicast
        assert 'unicast' in safi_values
        # IPv6 might not support all SAFIs that IPv4 does
        assert 'flow' in safi_values

    def test_get_safi_values_for_l2vpn(self):
        """Test getting SAFI values for L2VPN"""
        safi_values = self.registry.get_safi_values('l2vpn')
        assert isinstance(safi_values, list)
        # L2VPN should support VPLS and EVPN
        assert 'vpls' in safi_values
        assert 'evpn' in safi_values


class TestNeighborFilters:
    """Test neighbor filter keywords"""

    def setup_method(self):
        self.registry = CommandRegistry()

    def test_get_neighbor_filters(self):
        """Test getting neighbor filter keywords"""
        filters = self.registry.get_neighbor_filters()
        assert isinstance(filters, list)
        assert len(filters) > 0
        # Should include standard filter keywords
        assert 'local-ip' in filters
        assert 'local-as' in filters
        assert 'peer-as' in filters
        assert 'id' in filters  # CLI keyword (expands to 'router-id')
        assert 'router-id' not in filters  # Removed to avoid clash with 'route'


class TestRouteKeywords:
    """Test route specification keywords"""

    def setup_method(self):
        self.registry = CommandRegistry()

    def test_get_route_keywords(self):
        """Test getting route keywords"""
        keywords = self.registry.get_route_keywords()
        assert isinstance(keywords, list)
        assert len(keywords) > 0
        # Should include standard route keywords
        assert 'next-hop' in keywords
        assert 'as-path' in keywords
        assert 'community' in keywords
        assert 'local-preference' in keywords
        assert 'med' in keywords


class TestCommandTree:
    """Test command tree building"""

    def setup_method(self):
        self.registry = CommandRegistry()

    def test_build_command_tree(self):
        """Test building command tree"""
        tree = self.registry.build_command_tree()
        assert isinstance(tree, dict)
        assert len(tree) > 0

    def test_command_tree_has_show(self):
        """Test that tree includes show commands"""
        tree = self.registry.build_command_tree()
        assert 'show' in tree
        assert isinstance(tree['show'], dict)

    def test_command_tree_has_announce(self):
        """Test that tree includes announce commands"""
        tree = self.registry.build_command_tree()
        assert 'announce' in tree
        assert isinstance(tree['announce'], dict)

    def test_command_tree_nested_structure(self):
        """Test that tree has nested structure"""
        tree = self.registry.build_command_tree()
        # show -> neighbor should exist
        assert 'show' in tree
        assert 'neighbor' in tree['show']

    def test_command_tree_has_options(self):
        """Test that tree includes options"""
        tree = self.registry.build_command_tree()
        # Navigate to show neighbor
        show_neighbor = tree['show']['neighbor']
        # Should have __options__ key
        assert '__options__' in show_neighbor
        options = show_neighbor['__options__']
        assert isinstance(options, list)

    def test_command_tree_options_content(self):
        """Test that options contain expected values"""
        tree = self.registry.build_command_tree()
        options = tree['show']['neighbor']['__options__']
        # show neighbor should have summary, extensive, etc.
        assert 'summary' in options or len(options) > 0

    def test_command_tree_adj_rib(self):
        """Test adj-rib in tree"""
        tree = self.registry.build_command_tree()
        assert 'show' in tree
        assert 'adj-rib' in tree['show']
        adj_rib = tree['show']['adj-rib']
        assert 'in' in adj_rib
        assert 'out' in adj_rib


class TestFormatCommandHelp:
    """Test command help formatting"""

    def setup_method(self):
        self.registry = CommandRegistry()

    def test_format_command_help(self):
        """Test formatting help for a command"""
        help_text = self.registry.format_command_help('show neighbor')
        assert isinstance(help_text, str)
        assert len(help_text) > 0
        assert 'show neighbor' in help_text

    def test_format_command_help_includes_syntax(self):
        """Test that help includes syntax"""
        help_text = self.registry.format_command_help('show neighbor')
        assert 'Syntax:' in help_text or 'syntax' in help_text.lower()

    def test_format_command_help_unknown_command(self):
        """Test formatting help for unknown command"""
        help_text = self.registry.format_command_help('nonexistent')
        assert 'Unknown' in help_text or 'unknown' in help_text.lower()


class TestGetAllMetadata:
    """Test getting all metadata at once"""

    def setup_method(self):
        self.registry = CommandRegistry()

    def test_get_all_metadata(self):
        """Test getting metadata for all commands"""
        all_metadata = self.registry.get_all_metadata()
        assert isinstance(all_metadata, list)
        assert len(all_metadata) > 0
        # All should be CommandMetadata objects
        assert all(isinstance(m, CommandMetadata) for m in all_metadata)

    def test_get_all_metadata_count_matches_commands(self):
        """Test that metadata count matches command count"""
        all_metadata = self.registry.get_all_metadata()
        all_commands = self.registry.get_all_commands()
        # Should have metadata for each command
        assert len(all_metadata) == len(all_commands)


class TestCommandMetadataDefaults:
    """Test CommandMetadata default values"""

    def test_metadata_default_category(self):
        """Test default category is 'general'"""
        metadata = CommandMetadata(
            name='test',
            neighbor_support=False,
            json_support=False,
        )
        assert metadata.category == 'general'

    def test_metadata_generates_syntax(self):
        """Test that syntax is auto-generated"""
        metadata = CommandMetadata(
            name='test command',
            neighbor_support=False,
            json_support=False,
        )
        # Syntax should be auto-generated from name
        assert metadata.syntax == 'test command'

    def test_metadata_syntax_with_neighbor_support(self):
        """Test syntax generation with neighbor support"""
        metadata = CommandMetadata(
            name='test',
            neighbor_support=True,
            json_support=False,
        )
        assert '[neighbor <ip> [filters]]' in metadata.syntax

    def test_metadata_syntax_with_options(self):
        """Test syntax generation with options"""
        metadata = CommandMetadata(
            name='test',
            neighbor_support=False,
            json_support=False,
            options=['opt1', 'opt2'],
        )
        assert '[opt1]' in metadata.syntax
        assert '[opt2]' in metadata.syntax


class TestRegistryConstants:
    """Test that registry constants are defined"""

    def setup_method(self):
        self.registry = CommandRegistry()

    def test_afi_names_constant(self):
        """Test AFI_NAMES constant exists"""
        assert hasattr(CommandRegistry, 'AFI_NAMES')
        assert isinstance(CommandRegistry.AFI_NAMES, list)

    def test_safi_names_constant(self):
        """Test SAFI_NAMES constant exists"""
        assert hasattr(CommandRegistry, 'SAFI_NAMES')
        assert isinstance(CommandRegistry.SAFI_NAMES, list)

    def test_afi_safi_map_constant(self):
        """Test AFI_SAFI_MAP constant exists"""
        assert hasattr(CommandRegistry, 'AFI_SAFI_MAP')
        assert isinstance(CommandRegistry.AFI_SAFI_MAP, dict)

    def test_neighbor_filters_constant(self):
        """Test NEIGHBOR_FILTERS constant exists"""
        assert hasattr(CommandRegistry, 'NEIGHBOR_FILTERS')
        assert isinstance(CommandRegistry.NEIGHBOR_FILTERS, list)

    def test_route_keywords_constant(self):
        """Test ROUTE_KEYWORDS constant exists"""
        assert hasattr(CommandRegistry, 'ROUTE_KEYWORDS')
        assert isinstance(CommandRegistry.ROUTE_KEYWORDS, list)

    def test_categories_constant(self):
        """Test CATEGORIES constant exists"""
        assert hasattr(CommandRegistry, 'CATEGORIES')
        assert isinstance(CommandRegistry.CATEGORIES, dict)


class TestRegistryPerformance:
    """Test that registry operations are efficient"""

    def setup_method(self):
        self.registry = CommandRegistry()

    def test_get_all_commands_is_fast(self):
        """Test that getting all commands is fast"""
        import time

        start = time.time()
        for _ in range(100):
            self.registry.get_all_commands()
        elapsed = time.time() - start
        # Should be very fast (< 0.1s for 100 calls)
        assert elapsed < 0.1

    def test_metadata_caching_improves_performance(self):
        """Test that metadata caching works"""
        import time

        # First call (cache miss)
        start = time.time()
        self.registry.get_command_metadata('show neighbor')
        first_call = time.time() - start

        # Second call (cache hit)
        start = time.time()
        self.registry.get_command_metadata('show neighbor')
        second_call = time.time() - start

        # Second call should be faster (or at least not slower)
        assert second_call <= first_call * 2  # Allow for some variance


class TestRegistrySingleton:
    """Test global registry instance"""

    def test_get_registry_function(self):
        """Test get_registry() function"""
        from exabgp.reactor.api.command.registry import get_registry

        registry = get_registry()
        assert registry is not None
        assert isinstance(registry, CommandRegistry)

    def test_get_registry_returns_same_instance(self):
        """Test that get_registry() returns singleton"""
        from exabgp.reactor.api.command.registry import get_registry

        registry1 = get_registry()
        registry2 = get_registry()
        # Should be same object
        assert registry1 is registry2


class TestJsonSupport:
    """Test JSON support for commands"""

    def setup_method(self):
        self.registry = CommandRegistry()

    def test_announce_route_has_json_support(self):
        """Test that announce route supports JSON (regression test for KeyError bug)"""
        metadata = self.registry.get_command_metadata('announce route')
        assert metadata is not None
        assert metadata.json_support is True, 'announce route must support JSON to avoid KeyError'

    def test_withdraw_route_has_json_support(self):
        """Test that withdraw route supports JSON"""
        metadata = self.registry.get_command_metadata('withdraw route')
        assert metadata is not None
        assert metadata.json_support is True

    def test_announce_commands_have_json_support(self):
        """Test that all announce commands support JSON"""
        announce_commands = [
            'announce route',
            'announce vpls',
            'announce attribute',
            'announce attributes',
            'announce flow',
            'announce eor',
            'announce operational',
            'announce ipv4',
            'announce ipv6',
            'announce route-refresh',
            'announce watchdog',
        ]
        for cmd in announce_commands:
            metadata = self.registry.get_command_metadata(cmd)
            if metadata:  # Some commands might not exist in all builds
                assert metadata.json_support is True, f'{cmd} must support JSON'

    def test_withdraw_commands_have_json_support(self):
        """Test that all withdraw commands support JSON"""
        withdraw_commands = [
            'withdraw route',
            'withdraw vpls',
            'withdraw attribute',
            'withdraw attributes',
            'withdraw flow',
            'withdraw ipv4',
            'withdraw ipv6',
            'withdraw watchdog',
        ]
        for cmd in withdraw_commands:
            metadata = self.registry.get_command_metadata(cmd)
            if metadata:
                assert metadata.json_support is True, f'{cmd} must support JSON'

    def test_rib_commands_have_json_support(self):
        """Test that RIB commands support JSON"""
        rib_commands = [
            'show adj-rib in',
            'show adj-rib out',
            'flush adj-rib out',
            'clear adj-rib',
        ]
        for cmd in rib_commands:
            metadata = self.registry.get_command_metadata(cmd)
            if metadata:
                assert metadata.json_support is True, f'{cmd} must support JSON'

    def test_teardown_has_json_support(self):
        """Test that teardown supports JSON"""
        metadata = self.registry.get_command_metadata('teardown')
        assert metadata is not None
        assert metadata.json_support is True


class TestEdgeCases:
    """Test edge cases and error handling"""

    def setup_method(self):
        self.registry = CommandRegistry()

    def test_empty_command_name(self):
        """Test handling of empty command name"""
        metadata = self.registry.get_command_metadata('')
        assert metadata is None

    def test_get_subcommands_empty_prefix(self):
        """Test subcommands with empty prefix"""
        subcommands = self.registry.get_subcommands('')
        # Should return empty or handle gracefully
        assert isinstance(subcommands, list)

    def test_get_safi_values_invalid_afi(self):
        """Test SAFI values with invalid AFI"""
        safi_values = self.registry.get_safi_values('invalid-afi')
        # Should return default SAFI list
        assert isinstance(safi_values, list)

    def test_get_commands_by_category_none(self):
        """Test getting commands with None category"""
        commands = self.registry.get_commands_by_category(None)
        assert isinstance(commands, list)
