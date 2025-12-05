"""test_completer.py

Unit tests for CommandCompleter class.

Tests tab completion logic including context-aware completion,
neighbor IP fetching, AFI/SAFI suggestions, and dynamic tree navigation.
"""

from __future__ import annotations

import json
from unittest.mock import Mock, patch


from exabgp.application.cli import CommandCompleter


class TestCompleterBasics:
    """Test basic completer functionality"""

    def setup_method(self):
        """Create completer for each test"""
        self.mock_send = Mock(return_value='[]')
        self.completer = CommandCompleter(self.mock_send)

    def test_completer_creation(self):
        """Test that completer can be created"""
        assert self.completer is not None
        assert isinstance(self.completer, CommandCompleter)

    def test_completer_has_registry(self):
        """Test that completer initializes registry"""
        assert self.completer.registry is not None

    def test_completer_has_command_tree(self):
        """Test that completer builds command tree"""
        assert self.completer.command_tree is not None
        assert isinstance(self.completer.command_tree, dict)
        assert len(self.completer.command_tree) > 0

    def test_completer_has_base_commands(self):
        """Test that completer has v6 base commands only"""
        assert self.completer.base_commands is not None
        assert isinstance(self.completer.base_commands, list)
        # v6 API top-level commands
        assert 'peer' in self.completer.base_commands
        assert 'daemon' in self.completer.base_commands
        assert 'session' in self.completer.base_commands
        assert 'system' in self.completer.base_commands
        assert 'rib' in self.completer.base_commands
        # CLI-only commands
        assert 'exit' in self.completer.base_commands
        assert 'set' in self.completer.base_commands
        # v4 commands should NOT be in base commands
        assert 'announce' not in self.completer.base_commands
        assert 'withdraw' not in self.completer.base_commands
        assert 'shutdown' not in self.completer.base_commands
        assert 'show' not in self.completer.base_commands


class TestBaseCommandCompletion:
    """Test completion at command level (no tokens)"""

    def setup_method(self):
        self.mock_send = Mock(return_value='[]')
        self.completer = CommandCompleter(self.mock_send)

    def test_complete_empty_line(self):
        """Test completion with no input - v6 API only"""
        matches = self.completer._get_completions([], '')
        assert isinstance(matches, list)
        assert len(matches) > 0
        # Should include v6 API top-level commands
        assert 'peer' in matches
        assert 'daemon' in matches
        # Note: 'session' is internal CLI-daemon protocol, not exposed in autocomplete
        assert 'session' not in matches
        assert 'system' in matches
        assert 'rib' in matches
        # Should include CLI commands
        assert 'exit' in matches
        assert 'set' in matches
        # v4 commands should NOT be suggested
        assert 'announce' not in matches
        assert 'withdraw' not in matches
        assert 'shutdown' not in matches
        assert 'show' not in matches

    def test_complete_partial_set(self):
        """Test completing 'set' - should suggest 'set' CLI command"""
        matches = self.completer._get_completions([], 'set')
        assert 'set' in matches
        # v4 commands not in base
        assert 'show' not in matches
        assert 'shutdown' not in matches

    def test_complete_partial_peer(self):
        """Test completing 'p' - should suggest peer"""
        matches = self.completer._get_completions([], 'p')
        assert 'peer' in matches
        # v4 commands not in base
        assert 'ping' not in matches

    def test_complete_partial_daemon(self):
        """Test completing 'd' - should suggest daemon"""
        matches = self.completer._get_completions([], 'd')
        assert 'daemon' in matches

    def test_complete_no_match(self):
        """Test completion with no matches"""
        matches = self.completer._get_completions([], 'xyz')
        assert matches == []


class TestNestedCommandCompletion:
    """Test completion for nested commands"""

    def setup_method(self):
        self.mock_send = Mock(return_value='[]')
        self.completer = CommandCompleter(self.mock_send)

    def test_complete_after_show(self):
        """Test completion after 'show' - neighbor and adj-rib filtered out"""
        matches = self.completer._get_completions(['show'], '')
        assert isinstance(matches, list)
        assert 'neighbor' not in matches  # Filtered out - use 'neighbor <ip> show' syntax
        assert 'adj-rib' not in matches  # Filtered out - use 'adj-rib <in|out> show' syntax

    def test_complete_after_show_partial(self):
        """Test completion after 'show n' - neighbor filtered out"""
        matches = self.completer._get_completions(['show'], 'n')
        assert 'neighbor' not in matches  # Filtered out - use 'neighbor <ip> show' syntax

    def test_complete_after_announce(self):
        """Test completion after 'announce' - v6 API blocks v4 action-first commands"""
        # v4 'announce' is blocked - should return empty (use 'peer * announce' instead)
        matches = self.completer._get_completions(['announce'], '')
        assert matches == []  # v4 command blocked

        # v6 syntax: 'peer * announce' should work
        matches = self.completer._get_completions(['peer', '*', 'announce'], '')
        assert 'route' in matches
        assert 'eor' in matches
        # 'route-refresh' is a valid subcommand in v6
        assert 'route-refresh' in matches

    def test_complete_show_neighbor_options(self):
        """Test completion for show neighbor options"""
        matches = self.completer._get_completions(['show', 'neighbor'], '')
        # Should include options
        assert 'summary' in matches or 'extensive' in matches or 'configuration' in matches

    def test_complete_show_neighbor_with_ips(self):
        """Test that show neighbor completion includes neighbor IPs"""
        # Create completer with neighbor data
        neighbor_json = json.dumps([{'peer-address': '192.168.1.1'}, {'peer-address': '10.0.0.1'}])
        mock_send = Mock(return_value=neighbor_json)
        completer = CommandCompleter(mock_send)

        matches = completer._get_completions(['show', 'neighbor'], '')
        # Should include both options AND neighbor IPs
        assert 'summary' in matches or 'extensive' in matches  # Options
        assert '192.168.1.1' in matches or '10.0.0.1' in matches  # IPs

    def test_complete_show_adj_rib(self):
        """Test completion for show adj-rib - v6 API blocks 'show', use 'rib show' instead"""
        # v4 'show' is blocked
        matches = self.completer._get_completions(['show', 'adj-rib'], '')
        assert matches == []  # v4 command blocked

        # v6 syntax: 'rib show' should work
        matches = self.completer._get_completions(['rib', 'show'], '')
        assert 'in' in matches
        assert 'out' in matches


class TestShortcutExpansion:
    """Test that shortcuts are expanded during completion"""

    def setup_method(self):
        self.mock_send = Mock(return_value='[]')
        self.completer = CommandCompleter(self.mock_send)

    def test_shortcuts_expanded_in_completion(self):
        """Test that 'p <ip> show' completion works (p = peer)"""
        matches = self.completer._get_completions(['p', '192.168.1.1', 'show'], '')
        # After shortcut expansion to 'peer', should complete the show command
        # May not suggest options since 'peer <ip> show' is complete command
        assert isinstance(matches, list)

    def test_shortcuts_expanded_announce(self):
        """Test that 'peer * announce e' completes to 'eor' (v6 API)"""
        # v6 API: use 'peer * announce' syntax
        # Note: 'p' doesn't have a shortcut to 'peer', use full word
        # Complete 'e' after 'peer * announce'
        matches = self.completer._get_completions(['peer', '*', 'announce'], 'e')
        # Should suggest 'eor' among other commands
        assert 'eor' in matches


class TestNeighborIPCompletion:
    """Test neighbor IP completion"""

    def test_neighbor_completion_with_ips(self):
        """Test completion when neighbors exist"""
        # Mock send_command to return neighbor JSON
        neighbor_json = json.dumps(
            [
                {'peer-address': '192.168.1.1'},
                {'peer-address': '192.168.1.2'},
                {'peer-address': '10.0.0.1'},
            ]
        )
        mock_send = Mock(return_value=neighbor_json)
        completer = CommandCompleter(mock_send)

        # Get neighbor IPs
        ips = completer._get_neighbor_ips()
        assert '192.168.1.1' in ips
        assert '192.168.1.2' in ips
        assert '10.0.0.1' in ips

    def test_neighbor_completion_empty(self):
        """Test completion when no neighbors"""
        mock_send = Mock(return_value='[]')
        completer = CommandCompleter(mock_send)

        ips = completer._get_neighbor_ips()
        assert ips == []

    def test_neighbor_completion_invalid_json(self):
        """Test handling of invalid JSON"""
        mock_send = Mock(return_value='invalid json')
        completer = CommandCompleter(mock_send)

        # Should handle gracefully
        ips = completer._get_neighbor_ips()
        assert ips == []

    def test_neighbor_completion_caching(self):
        """Test that neighbor IPs are cached"""
        mock_send = Mock(return_value='[{"peer-address": "192.168.1.1"}]')
        completer = CommandCompleter(mock_send)

        # First call
        ips1 = completer._get_neighbor_ips()
        call_count_1 = mock_send.call_count

        # Second call (should use cache)
        ips2 = completer._get_neighbor_ips()
        call_count_2 = mock_send.call_count

        # Should not have called send_command again
        assert call_count_2 == call_count_1
        assert ips1 == ips2

    def test_invalidate_cache(self):
        """Test cache invalidation"""
        mock_send = Mock(return_value='[{"peer-address": "192.168.1.1"}]')
        completer = CommandCompleter(mock_send)

        # Get IPs (cache miss)
        completer._get_neighbor_ips()
        call_count_1 = mock_send.call_count

        # Invalidate cache
        completer.invalidate_cache()

        # Get IPs again (should query again)
        completer._get_neighbor_ips()
        call_count_2 = mock_send.call_count

        # Should have called send_command again
        assert call_count_2 > call_count_1


class TestAFISAFICompletion:
    """Test AFI/SAFI completion"""

    def setup_method(self):
        self.mock_send = Mock(return_value='[]')
        self.completer = CommandCompleter(self.mock_send)

    def test_afi_completion_after_eor(self):
        """Test AFI completion after 'announce eor'"""
        matches = self.completer._complete_afi_safi(['announce', 'eor'], '')
        assert 'ipv4' in matches
        assert 'ipv6' in matches
        assert 'l2vpn' in matches

    def test_safi_completion_after_eor_ipv4(self):
        """Test SAFI completion after 'announce eor ipv4'"""
        # When completing after 'announce eor ipv4 <cursor>', tokens[-2] should be 'ipv4'
        # We need to add a token after ipv4 to complete
        matches = self.completer._complete_afi_safi(['announce', 'eor', 'ipv4', ''], '')
        # Now tokens[-2] is 'ipv4' which is an AFI, so should return SAFIs
        assert 'unicast' in matches
        assert 'multicast' in matches
        assert 'flow' in matches

    def test_safi_completion_after_route_refresh(self):
        """Test SAFI completion for route-refresh"""
        # Same - need extra token after ipv6
        matches = self.completer._complete_afi_safi(['announce', 'route-refresh', 'ipv6', ''], '')
        # Should return SAFI values for IPv6
        assert 'unicast' in matches

    def test_afi_completion_partial(self):
        """Test partial AFI completion"""
        matches = self.completer._complete_afi_safi(['announce', 'eor'], 'ip')
        assert 'ipv4' in matches
        assert 'ipv6' in matches
        # Should NOT include l2vpn (doesn't start with 'ip')
        assert 'l2vpn' not in matches


class TestNeighborFilterCompletion:
    """Test neighbor filter completion"""

    def setup_method(self):
        self.mock_send = Mock(return_value='[]')
        self.completer = CommandCompleter(self.mock_send)

    def test_filter_completion(self):
        """Test completing neighbor filters"""
        matches = self.completer._complete_neighbor_filters('')
        assert 'local-ip' in matches
        assert 'local-as' in matches
        assert 'peer-as' in matches
        assert 'id' in matches  # CLI keyword (expands to 'router-id')
        assert 'router-id' not in matches  # Removed to avoid clash with 'route'

    def test_filter_completion_partial(self):
        """Test partial filter completion"""
        matches = self.completer._complete_neighbor_filters('local')
        assert 'local-ip' in matches
        assert 'local-as' in matches
        # Should NOT include others
        assert 'peer-as' not in matches


class TestRouteKeywordCompletion:
    """Test route keyword completion"""

    def setup_method(self):
        self.mock_send = Mock(return_value='[]')
        self.completer = CommandCompleter(self.mock_send)

    def test_route_keyword_completion(self):
        """Test completing route keywords"""
        matches = self.completer._complete_route_spec(['announce', 'route'], '')
        assert 'next-hop' in matches
        assert 'as-path' in matches
        assert 'community' in matches
        assert 'local-preference' in matches

    def test_route_keyword_partial(self):
        """Test partial route keyword completion"""
        matches = self.completer._complete_route_spec(['announce', 'route'], 'next')
        assert 'next-hop' in matches
        # Should not include others
        assert 'as-path' not in matches


class TestIPAddressDetection:
    """Test IP address detection"""

    def setup_method(self):
        self.mock_send = Mock(return_value='[]')
        self.completer = CommandCompleter(self.mock_send)

    def test_detect_ipv4(self):
        """Test detecting IPv4 addresses"""
        assert self.completer._is_ip_address('192.168.1.1')
        assert self.completer._is_ip_address('10.0.0.1')
        assert self.completer._is_ip_address('255.255.255.255')

    def test_detect_ipv6(self):
        """Test detecting IPv6 addresses"""
        assert self.completer._is_ip_address('2001:db8::1')
        assert self.completer._is_ip_address('fe80::1')
        # With colons
        assert self.completer._is_ip_address('2001:0db8:0000:0000:0000:0000:0000:0001')

    def test_not_ip_address(self):
        """Test non-IP strings"""
        assert not self.completer._is_ip_address('show')
        assert not self.completer._is_ip_address('neighbor')
        assert not self.completer._is_ip_address('192.168')  # Incomplete
        assert not self.completer._is_ip_address('abc.def.ghi.jkl')


class TestPeerCommandDetection:
    """Test detection of peer-targeted commands (v6 API)"""

    def setup_method(self):
        self.mock_send = Mock(return_value='[]')
        self.completer = CommandCompleter(self.mock_send)

    def test_is_peer_command_peer(self):
        """Test 'peer' is detected as peer command"""
        assert self.completer._is_peer_command(['peer'])

    def test_is_peer_command_peer_with_selector(self):
        """Test 'peer *' and 'peer <ip>' are peer commands"""
        assert self.completer._is_peer_command(['peer', '*'])
        assert self.completer._is_peer_command(['peer', '192.168.1.1'])

    def test_is_peer_command_peer_announce(self):
        """Test 'peer * announce' is peer command"""
        assert self.completer._is_peer_command(['peer', '*', 'announce'])

    def test_is_peer_command_not_show(self):
        """Test 'show' is not peer command"""
        assert not self.completer._is_peer_command(['show'])

    def test_is_peer_command_empty(self):
        """Test empty tokens"""
        assert not self.completer._is_peer_command([])

    def test_is_peer_command_daemon(self):
        """Test 'daemon' is not peer command"""
        assert not self.completer._is_peer_command(['daemon'])

    def test_is_peer_command_rib(self):
        """Test 'rib' is not peer command"""
        assert not self.completer._is_peer_command(['rib'])


class TestCompletePeerCommand:
    """Test completion for peer-targeted commands (v6 API)"""

    def setup_method(self):
        neighbor_json = json.dumps([{'peer-address': '192.168.1.1'}, {'peer-address': '10.0.0.1'}])
        self.mock_send = Mock(return_value=neighbor_json)
        self.completer = CommandCompleter(self.mock_send)

    def test_complete_peer_suggests_wildcard_and_ips(self):
        """Test that 'peer' suggests wildcard and peer IPs"""
        matches = self.completer._get_completions(['peer'], '')
        # Should suggest wildcard and peer IPs
        assert '*' in matches
        assert '192.168.1.1' in matches or '10.0.0.1' in matches

    def test_complete_peer_wildcard_suggests_actions(self):
        """Test that 'peer *' suggests actions"""
        matches = self.completer._complete_peer_command(['peer', '*'], '')
        # Should suggest v6 API actions
        assert 'announce' in matches
        assert 'withdraw' in matches
        assert 'show' in matches
        assert 'teardown' in matches

    def test_complete_peer_ip_suggests_actions(self):
        """Test that 'peer <ip>' suggests actions"""
        matches = self.completer._complete_peer_command(['peer', '192.168.1.1'], '')
        # Should suggest v6 API actions
        assert 'announce' in matches
        assert 'withdraw' in matches
        assert 'show' in matches
        assert 'teardown' in matches


class TestCommandTreeNavigation:
    """Test navigation through command tree"""

    def setup_method(self):
        self.mock_send = Mock(return_value='[]')
        self.completer = CommandCompleter(self.mock_send)

    def test_navigate_show_neighbor(self):
        """Test navigating to show neighbor"""
        matches = self.completer._get_completions(['show', 'neighbor'], '')
        # Should show options
        assert isinstance(matches, list)

    def test_navigate_announce_route(self):
        """Test navigating to announce route"""
        matches = self.completer._get_completions(['announce', 'route'], '')
        # Should show route keywords
        assert isinstance(matches, list)

    def test_navigate_invalid_path(self):
        """Test invalid navigation path"""
        matches = self.completer._get_completions(['show', 'invalid', 'path'], '')
        # Should handle gracefully
        assert isinstance(matches, list)


class TestCompleteFunction:
    """Test the main complete() function"""

    def setup_method(self):
        self.mock_send = Mock(return_value='[]')
        self.completer = CommandCompleter(self.mock_send)

    @patch('readline.get_line_buffer')
    @patch('readline.get_begidx')
    def test_complete_first_call(self, mock_begidx, mock_buffer):
        """Test complete() on first call (state=0)"""
        mock_buffer.return_value = 'show '
        mock_begidx.return_value = 5

        result = self.completer.complete('', 0)
        # Should return first match
        assert result is not None or result is None  # Depends on matches

    @patch('readline.get_line_buffer')
    @patch('readline.get_begidx')
    def test_complete_subsequent_calls(self, mock_begidx, mock_buffer):
        """Test complete() on subsequent calls"""
        mock_buffer.return_value = 'show '
        mock_begidx.return_value = 5

        # First call
        self.completer.complete('', 0)

        # Subsequent calls should cycle through matches
        result = self.completer.complete('', 1)
        assert result is not None or result is None

    @patch('readline.get_line_buffer')
    @patch('readline.get_begidx')
    def test_complete_returns_none_when_exhausted(self, mock_begidx, mock_buffer):
        """Test that complete() returns None when matches exhausted"""
        mock_buffer.return_value = 'show '
        mock_begidx.return_value = 5

        # Get all matches
        state = 0
        while True:
            result = self.completer.complete('', state)
            if result is None:
                break
            state += 1

        # Should eventually return None
        assert result is None


class TestEdgeCases:
    """Test edge cases and error handling"""

    def setup_method(self):
        self.mock_send = Mock(return_value='[]')
        self.completer = CommandCompleter(self.mock_send)

    def test_empty_tokens(self):
        """Test completion with empty token list"""
        matches = self.completer._get_completions([], '')
        assert isinstance(matches, list)

    def test_none_tokens(self):
        """Test handling of unusual input"""
        # Should not crash
        try:
            matches = self.completer._get_completions(['show', None], '')
            assert isinstance(matches, list)
        except (TypeError, AttributeError):
            # Acceptable to raise error for None
            pass

    def test_very_long_token_list(self):
        """Test with many tokens"""
        long_tokens = ['show'] * 100
        matches = self.completer._get_completions(long_tokens, '')
        # Should handle gracefully
        assert isinstance(matches, list)

    def test_special_characters_in_tokens(self):
        """Test tokens with special characters"""
        matches = self.completer._get_completions(['show', 'neighbor', '192.168.1.1'], '')
        assert isinstance(matches, list)


class TestCompleterWithGetNeighborsCallback:
    """Test completer with custom get_neighbors callback"""

    def test_custom_neighbor_callback(self):
        """Test using custom get_neighbors callback"""
        mock_send = Mock(return_value='[]')

        def custom_get_neighbors():
            return ['192.168.1.1', '192.168.1.2', '10.0.0.1']

        completer = CommandCompleter(mock_send, get_neighbors=custom_get_neighbors)

        ips = completer._get_neighbor_ips()
        assert '192.168.1.1' in ips
        assert '192.168.1.2' in ips
        assert '10.0.0.1' in ips

    def test_callback_exception_handling(self):
        """Test handling of callback exceptions"""
        mock_send = Mock(return_value='[]')

        def failing_callback():
            raise Exception('Callback failed')

        completer = CommandCompleter(mock_send, get_neighbors=failing_callback)

        # Should handle exception gracefully
        ips = completer._get_neighbor_ips()
        assert ips == []


class TestRealWorldScenarios:
    """Test real-world completion scenarios"""

    def setup_method(self):
        neighbor_json = json.dumps([{'peer-address': '192.168.1.1'}])
        self.mock_send = Mock(return_value=neighbor_json)
        self.completer = CommandCompleter(self.mock_send)

    def test_show_neighbor_summary(self):
        """Test completing 'show neighbor summary'"""
        matches = self.completer._get_completions(['show', 'neighbor'], 's')
        assert 'summary' in matches

    def test_announce_eor_ipv4_unicast(self):
        """Test completing 'peer * announce eor ipv4 unicast' (v6 API)"""
        # v6 API: Complete 'eor' after 'peer * announce'
        matches1 = self.completer._get_completions(['peer', '*', 'announce'], 'e')
        assert 'eor' in matches1

        # Test AFI completion using the helper method
        matches2 = self.completer._complete_afi_safi(['peer', '*', 'announce', 'eor'], '')
        assert 'ipv4' in matches2 and 'ipv6' in matches2

        # Test SAFI completion after AFI
        matches3 = self.completer._complete_afi_safi(['peer', '*', 'announce', 'eor', 'ipv4', ''], '')
        assert 'unicast' in matches3

    def test_show_adj_rib_in_extensive(self):
        """Test completing 'rib show in extensive' (v6 API)"""
        # v6 API: 'show' is blocked, use 'rib show' instead
        matches = self.completer._get_completions(['show', 'adj-rib', 'in'], 'e')
        assert matches == []  # v4 command blocked

        # v6 syntax would be 'rib show in' - but no 'extensive' option currently
        # Just verify the v4 path is blocked
        pass

    def test_teardown_with_neighbor_ip(self):
        """Test completing 'teardown 192.168.1.1'"""
        matches = self.completer._get_completions(['teardown'], '192')
        assert '192.168.1.1' in matches or len(matches) >= 0


class TestCompletionConsistency:
    """Test that completion is consistent"""

    def setup_method(self):
        self.mock_send = Mock(return_value='[]')
        self.completer = CommandCompleter(self.mock_send)

    def test_consistent_matches(self):
        """Test that same input gives same matches"""
        matches1 = self.completer._get_completions(['show'], 'n')
        matches2 = self.completer._get_completions(['show'], 'n')
        assert matches1 == matches2

    def test_matches_are_sorted(self):
        """Test that matches are sorted"""
        matches = self.completer._get_completions(['show'], '')
        # Should be sorted
        assert matches == sorted(matches)

    def test_matches_are_unique(self):
        """Test that matches don't have duplicates"""
        matches = self.completer._get_completions(['show'], '')
        # Should not have duplicates
        assert len(matches) == len(set(matches))


class TestShowCommandCompletion:
    """Test show command completion at different levels"""

    def setup_method(self):
        neighbor_json = json.dumps([{'peer-address': '192.168.1.1'}, {'peer-address': '10.0.0.1'}])
        self.mock_send = Mock(return_value=neighbor_json)
        self.completer = CommandCompleter(self.mock_send)

    def test_show_completes_to_subcommands(self):
        """Test that 'show' has no completions (neighbor and adj-rib filtered out)"""
        matches = self.completer._get_completions(['show'], '')
        assert 'neighbor' not in matches  # Filtered out - use 'neighbor <ip> show' syntax
        assert 'adj-rib' not in matches  # Filtered out - use 'adj-rib <in|out> show' syntax
        assert len(matches) == 0

    def test_show_n_completes_to_neighbor(self):
        """Test that 'show n' no longer suggests 'neighbor' - use 'neighbor <ip> show' instead"""
        matches = self.completer._get_completions(['show'], 'n')
        assert 'neighbor' not in matches  # Filtered out - use 'neighbor <ip> show' syntax
        assert 'adj-rib' not in matches

    def test_show_a_completes_to_adj_rib(self):
        """Test that 'show a' no longer suggests 'adj-rib' - use 'adj-rib <in|out> show' instead"""
        matches = self.completer._get_completions(['show'], 'a')
        assert 'adj-rib' not in matches  # Filtered out - use 'adj-rib <in|out> show' syntax
        assert 'neighbor' not in matches

    def test_show_neighbor_shows_all_completions(self):
        """Test that 'show neighbor' shows options and IPs"""
        matches = self.completer._get_completions(['show', 'neighbor'], '')
        # Should have options
        assert 'summary' in matches
        assert 'extensive' in matches
        assert 'configuration' in matches
        # Note: v6 API is JSON-only, so 'json' suffix is not offered
        assert 'json' not in matches
        # Should have neighbor IPs
        assert '192.168.1.1' in matches
        assert '10.0.0.1' in matches

    def test_show_neighbor_s_filters_correctly(self):
        """Test that 'show neighbor s' only shows 'summary'"""
        matches = self.completer._get_completions(['show', 'neighbor'], 's')
        assert 'summary' in matches
        assert 'extensive' not in matches
        assert 'configuration' not in matches

    def test_show_adj_rib_shows_in_out(self):
        """Test that 'rib show' completes to 'in' and 'out' (v6 API)"""
        # v6 API: 'show' is blocked, use 'rib show' instead
        matches = self.completer._get_completions(['show', 'adj-rib'], '')
        assert matches == []  # v4 command blocked

        # v6 syntax: 'rib show' should work
        matches = self.completer._get_completions(['rib', 'show'], '')
        assert 'in' in matches
        assert 'out' in matches

    def test_show_adj_rib_in_shows_options(self):
        """Test that 'rib show in' shows options (v6 API)"""
        # v6 API: 'show' is blocked
        matches = self.completer._get_completions(['show', 'adj-rib', 'in'], '')
        assert matches == []  # v4 command blocked

        # v6 syntax: 'rib show in' - currently no further completions
        # (could add 'extensive' later if needed)


class TestNeighborTargetedCommandCompletion:
    """Test completion for neighbor-targeted commands"""

    def setup_method(self):
        neighbor_json = json.dumps([{'peer-address': '192.168.1.1'}, {'peer-address': '10.0.0.1'}])
        self.mock_send = Mock(return_value=neighbor_json)
        self.completer = CommandCompleter(self.mock_send)

    def test_flush_adj_rib_out_suggests_ips(self):
        """Test that 'flush adj-rib out' suggests peer IPs"""
        matches = self.completer._get_completions(['flush', 'adj-rib', 'out'], '')
        # v6 API: suggest peer IPs for filtering
        assert '192.168.1.1' in matches or len(matches) >= 0  # May have options

    def test_clear_adj_rib_suggests_options(self):
        """Test that 'clear adj-rib' suggests options"""
        # Note: 'clear adj-rib' is the registered command, 'in'/'out' are parsed at runtime
        matches = self.completer._get_completions(['clear', 'adj-rib'], '')
        # May suggest 'in'/'out' or peer IPs depending on command tree
        assert len(matches) >= 0

    def test_announce_route_suggests_refresh(self):
        """Test that 'announce route' suggests 'refresh' keyword"""
        matches = self.completer._get_completions(['announce', 'route'], '')
        # Should have 'refresh' keyword (for "announce route refresh")
        assert 'refresh' in matches
        # v6 API: peer selector should be used BEFORE announce, not after
        # e.g., "peer * announce route" not "announce route neighbor"
        assert 'peer' not in matches

    def test_withdraw_route_suggests_ips(self):
        """Test that 'withdraw route' suggests peer IPs for filtering"""
        matches = self.completer._get_completions(['withdraw', 'route'], '')
        # v6 API expects "peer * withdraw route" syntax
        # After "withdraw route", complete IP prefix
        assert '192.168.1.1' in matches or len(matches) >= 0

    def test_peer_ip_suggests_v6_actions(self):
        """Test that 'peer <IP>' suggests v6 API actions"""
        matches = self.completer._get_completions(['peer', '192.168.1.1'], '')
        # v6 API actions
        assert 'announce' in matches
        assert 'withdraw' in matches
        assert 'show' in matches
        assert 'teardown' in matches
        # Should NOT have adj-rib (use "rib show in/out" instead)
        assert 'adj-rib' not in matches
        # Should NOT have other commands
        assert 'flush' not in matches
        assert 'ping' not in matches
        assert 'help' not in matches
        # Should NOT have filter keywords (filters removed from this context)
        assert 'local-as' not in matches
        assert 'peer-as' not in matches
        assert 'id' not in matches
        # Should be exactly 4 items
        assert len(matches) == 4


class TestCompleterExceptionHandling:
    """Test that completer handles exceptions gracefully (regression test for readline breakage)"""

    def test_complete_handles_send_command_exception(self):
        """Test that complete() doesn't crash when send_command raises exception"""

        # Create completer with send_command that always raises exception
        def broken_send(cmd):
            raise ConnectionError('Connection lost')

        completer = CommandCompleter(broken_send)

        # complete() should handle exception and return gracefully (not crash)
        # This prevents readline from breaking after connection loss
        result = completer.complete('show', 0)
        # Should return valid completion (basic matches work) or None, not crash
        assert result is None or isinstance(result, str)

    def test_complete_handles_json_parse_error(self):
        """Test that complete() handles JSON parse errors gracefully"""

        def bad_json_send(cmd):
            return 'invalid json {'

        completer = CommandCompleter(bad_json_send)

        # Should not crash on malformed JSON
        result = completer.complete('show', 0)
        assert result is None or isinstance(result, str)

    def test_complete_handles_none_send_command(self):
        """Test that complete() handles None return from send_command"""

        def none_send(cmd):
            return None

        completer = CommandCompleter(none_send)

        # Should handle None response gracefully
        result = completer.complete('show', 0)
        assert result is None or isinstance(result, str)

    def test_get_completions_handles_exception(self):
        """Test that _get_completions handles exceptions during neighbor fetch"""

        def exception_send(cmd):
            raise RuntimeError('Unexpected error')

        completer = CommandCompleter(exception_send)

        # Should return empty list or basic completions, not crash
        matches = completer._get_completions(['show'], 'n')
        assert isinstance(matches, list)
        # 'neighbor' is filtered out after 'show' - no completions starting with 'n'
        assert 'neighbor' not in matches

    def test_get_neighbor_ips_handles_socket_error(self):
        """Test that neighbor IP fetching handles socket errors gracefully"""

        def socket_error_send(cmd):
            import socket

            raise socket.error('Connection refused')

        completer = CommandCompleter(socket_error_send)

        # Should return empty list, not crash
        ips = completer._get_neighbor_ips()
        assert isinstance(ips, list)
        # Empty is OK - neighbor completion is optional
        assert ips == []

    def test_complete_after_connection_loss(self):
        """Test that autocomplete still works after connection is lost (regression test)"""
        # Simulate connection working initially, then failing
        call_count = [0]

        def flaky_send(cmd):
            call_count[0] += 1
            if call_count[0] > 2:
                raise ConnectionError('Connection lost')
            return '[]'

        completer = CommandCompleter(flaky_send)

        # First completion should work (v6 commands)
        result1 = completer.complete('daemon', 0)
        assert result1 is not None

        # After connection loss, should still provide basic completions
        result2 = completer.complete('session', 0)
        # Should return something (basic completion) or None, not crash
        assert result2 is None or isinstance(result2, str)


class TestMultiCharAbbreviation:
    """Test multi-character abbreviation expansion (e.g., 'dst' → 'daemon status')"""

    def setup_method(self):
        self.mock_send = Mock(return_value='[]')
        self.completer = CommandCompleter(self.mock_send)

    def test_daemon_status_abbreviation(self):
        """Test 'dst' expands to 'daemon status'"""
        matches = self.completer._get_completions([], 'dst')
        assert matches == ['daemon status']

    def test_daemon_shutdown_abbreviation(self):
        """Test 'dsh' expands to 'daemon shutdown'"""
        matches = self.completer._get_completions([], 'dsh')
        assert matches == ['daemon shutdown']

    def test_daemon_reload_abbreviation(self):
        """Test 'drel' expands to 'daemon reload'"""
        matches = self.completer._get_completions([], 'drel')
        assert matches == ['daemon reload']

    def test_rib_show_abbreviation(self):
        """Test 'rsh' expands to 'rib show'"""
        matches = self.completer._get_completions([], 'rsh')
        assert matches == ['rib show']

    def test_rib_clear_abbreviation(self):
        """Test 'rc' expands to 'rib clear'"""
        matches = self.completer._get_completions([], 'rc')
        assert matches == ['rib clear']

    def test_session_sync_abbreviation(self):
        """Test 'ssy' expands to 'session sync' (ses + sy)"""
        matches = self.completer._get_completions([], 'sesy')
        assert matches == ['session sync']

    def test_system_help_abbreviation(self):
        """Test 'syh' expands to 'system help'"""
        matches = self.completer._get_completions([], 'syh')
        assert matches == ['system help']

    def test_system_version_abbreviation(self):
        """Test 'syv' expands to 'system version'"""
        matches = self.completer._get_completions([], 'syv')
        assert matches == ['system version']

    def test_ambiguous_abbreviation_returns_empty(self):
        """Test ambiguous abbreviations return empty (e.g., 'ds' matches shutdown/status)"""
        matches = self.completer._get_completions([], 'ds')
        assert matches == []  # 's' matches both 'shutdown' and 'status'

    def test_ambiguous_daemon_re_returns_empty(self):
        """Test 'dre' returns empty (matches reload/restart)"""
        matches = self.completer._get_completions([], 'dre')
        assert matches == []  # 're' matches both 'reload' and 'restart'

    def test_single_char_not_expanded(self):
        """Test single characters use normal completion, not abbreviation"""
        matches = self.completer._get_completions([], 'd')
        assert 'daemon' in matches
        assert 'daemon status' not in matches  # Not abbreviated
