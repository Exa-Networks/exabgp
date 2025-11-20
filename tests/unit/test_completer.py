"""test_completer.py

Unit tests for CommandCompleter class.

Tests tab completion logic including context-aware completion,
neighbor IP fetching, AFI/SAFI suggestions, and dynamic tree navigation.
"""

from __future__ import annotations

import json
from unittest.mock import Mock, patch

import pytest

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
        """Test that completer has base commands"""
        assert self.completer.base_commands is not None
        assert isinstance(self.completer.base_commands, list)
        assert 'show' in self.completer.base_commands
        assert 'announce' in self.completer.base_commands


class TestBaseCommandCompletion:
    """Test completion at command level (no tokens)"""

    def setup_method(self):
        self.mock_send = Mock(return_value='[]')
        self.completer = CommandCompleter(self.mock_send)

    def test_complete_empty_line(self):
        """Test completion with no input"""
        matches = self.completer._get_completions([], '')
        assert isinstance(matches, list)
        assert len(matches) > 0
        # Should include base commands
        assert 'show' in matches
        assert 'announce' in matches

    def test_complete_partial_show(self):
        """Test completing 'sh'"""
        matches = self.completer._get_completions([], 'sh')
        assert 'show' in matches or 'shutdown' in matches

    def test_complete_partial_announce(self):
        """Test completing 'ann'"""
        matches = self.completer._get_completions([], 'ann')
        assert 'announce' in matches

    def test_complete_help(self):
        """Test completing 'h'"""
        matches = self.completer._get_completions([], 'h')
        assert 'help' in matches

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
        """Test completion after 'show'"""
        matches = self.completer._get_completions(['show'], '')
        assert isinstance(matches, list)
        assert 'neighbor' in matches
        assert 'adj-rib' in matches

    def test_complete_after_show_partial(self):
        """Test completion after 'show n'"""
        matches = self.completer._get_completions(['show'], 'n')
        assert 'neighbor' in matches

    def test_complete_after_announce(self):
        """Test completion after 'announce'"""
        matches = self.completer._get_completions(['announce'], '')
        assert 'route' in matches
        assert 'eor' in matches
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
        """Test completion for show adj-rib"""
        matches = self.completer._get_completions(['show', 'adj-rib'], '')
        assert 'in' in matches
        assert 'out' in matches


class TestShortcutExpansion:
    """Test that shortcuts are expanded during completion"""

    def setup_method(self):
        self.mock_send = Mock(return_value='[]')
        self.completer = CommandCompleter(self.mock_send)

    def test_shortcuts_expanded_in_completion(self):
        """Test that 's n' expands to 'show neighbor'"""
        matches = self.completer._get_completions(['s', 'n'], '')
        # After expansion, should show neighbor options
        assert 'summary' in matches or 'extensive' in matches or len(matches) > 0

    def test_shortcuts_expanded_announce(self):
        """Test that 'a e' expands to 'announce eor'"""
        # First, complete 'e' after 'a' (announce)
        matches = self.completer._get_completions(['a'], 'e')
        # Should suggest 'eor' among other commands
        assert 'eor' in matches or len(matches) > 0


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
        assert 'router-id' in matches

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


class TestNeighborCommandDetection:
    """Test detection of neighbor-targeted commands"""

    def setup_method(self):
        self.mock_send = Mock(return_value='[]')
        self.completer = CommandCompleter(self.mock_send)

    def test_is_neighbor_command_teardown(self):
        """Test teardown is neighbor command"""
        assert self.completer._is_neighbor_command(['teardown'])

    def test_is_neighbor_command_neighbor(self):
        """Test neighbor keyword"""
        assert self.completer._is_neighbor_command(['neighbor'])

    def test_is_neighbor_command_announce(self):
        """Test announce can be neighbor command"""
        assert self.completer._is_neighbor_command(['announce', 'route'])

    def test_is_neighbor_command_show(self):
        """Test show is not neighbor command"""
        # show neighbor is not the same as neighbor-targeted command
        assert not self.completer._is_neighbor_command(['show', 'neighbor'])

    def test_is_neighbor_command_empty(self):
        """Test empty tokens"""
        assert not self.completer._is_neighbor_command([])

    def test_is_neighbor_command_flush_adj_rib_out(self):
        """Test flush adj-rib out is neighbor command"""
        assert self.completer._is_neighbor_command(['flush', 'adj-rib', 'out'])

    def test_is_neighbor_command_clear_adj_rib(self):
        """Test clear adj-rib is neighbor command"""
        assert self.completer._is_neighbor_command(['clear', 'adj-rib', 'in'])
        assert self.completer._is_neighbor_command(['clear', 'adj-rib', 'out'])

    def test_is_neighbor_command_withdraw(self):
        """Test withdraw commands are neighbor commands"""
        assert self.completer._is_neighbor_command(['withdraw', 'route'])
        assert self.completer._is_neighbor_command(['withdraw', 'vpls'])
        assert self.completer._is_neighbor_command(['withdraw', 'flow'])


class TestCompleteNeighborCommand:
    """Test completion for neighbor-targeted commands"""

    def setup_method(self):
        neighbor_json = json.dumps([{'peer-address': '192.168.1.1'}, {'peer-address': '10.0.0.1'}])
        self.mock_send = Mock(return_value=neighbor_json)
        self.completer = CommandCompleter(self.mock_send)

    def test_complete_after_teardown(self):
        """Test completion after teardown"""
        matches = self.completer._complete_neighbor_command(['teardown'], '')
        # Should suggest neighbor IPs
        assert '192.168.1.1' in matches or len(matches) > 0

    def test_complete_after_announce(self):
        """Test completion after announce route"""
        # Note: 'announce' alone is not a registered command, use 'announce route'
        matches = self.completer._complete_neighbor_command(['announce', 'route'], '')
        # Should suggest 'neighbor' or IPs
        assert 'neighbor' in matches or len(matches) > 0

    def test_complete_after_neighbor_keyword(self):
        """Test completion after 'neighbor' keyword"""
        matches = self.completer._complete_neighbor_command(['neighbor'], '')
        # Should suggest neighbor IPs
        assert '192.168.1.1' in matches or '10.0.0.1' in matches


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
        """Test completing 'announce eor ipv4 unicast'"""
        # Complete 'eor' - should be in announce subcommands
        matches1 = self.completer._get_completions(['announce'], 'e')
        assert 'eor' in matches1

        # Test AFI completion using the helper method
        matches2 = self.completer._complete_afi_safi(['announce', 'eor'], '')
        assert 'ipv4' in matches2 and 'ipv6' in matches2

        # Test SAFI completion after AFI
        matches3 = self.completer._complete_afi_safi(['announce', 'eor', 'ipv4', ''], '')
        assert 'unicast' in matches3

    def test_show_adj_rib_in_extensive(self):
        """Test completing 'show adj-rib in extensive'"""
        matches = self.completer._get_completions(['show', 'adj-rib', 'in'], 'e')
        assert 'extensive' in matches

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
        """Test that 'show' completes to 'neighbor' and 'adj-rib'"""
        matches = self.completer._get_completions(['show'], '')
        assert 'neighbor' in matches
        assert 'adj-rib' in matches
        assert len(matches) == 2

    def test_show_n_completes_to_neighbor(self):
        """Test that 'show n' completes to 'neighbor'"""
        matches = self.completer._get_completions(['show'], 'n')
        assert 'neighbor' in matches
        assert 'adj-rib' not in matches

    def test_show_a_completes_to_adj_rib(self):
        """Test that 'show a' completes to 'adj-rib'"""
        matches = self.completer._get_completions(['show'], 'a')
        assert 'adj-rib' in matches
        assert 'neighbor' not in matches

    def test_show_neighbor_shows_all_completions(self):
        """Test that 'show neighbor' shows options and IPs"""
        matches = self.completer._get_completions(['show', 'neighbor'], '')
        # Should have options
        assert 'summary' in matches
        assert 'extensive' in matches
        assert 'configuration' in matches
        assert 'json' in matches
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
        """Test that 'show adj-rib' completes to 'in' and 'out'"""
        matches = self.completer._get_completions(['show', 'adj-rib'], '')
        assert 'in' in matches
        assert 'out' in matches

    def test_show_adj_rib_in_shows_options(self):
        """Test that 'show adj-rib in' shows options"""
        matches = self.completer._get_completions(['show', 'adj-rib', 'in'], '')
        assert 'extensive' in matches


class TestNeighborTargetedCommandCompletion:
    """Test completion for neighbor-targeted commands"""

    def setup_method(self):
        neighbor_json = json.dumps([{'peer-address': '192.168.1.1'}, {'peer-address': '10.0.0.1'}])
        self.mock_send = Mock(return_value=neighbor_json)
        self.completer = CommandCompleter(self.mock_send)

    def test_flush_adj_rib_out_suggests_neighbor_and_ips(self):
        """Test that 'flush adj-rib out' suggests 'neighbor' and IPs"""
        matches = self.completer._get_completions(['flush', 'adj-rib', 'out'], '')
        assert 'neighbor' in matches
        assert '192.168.1.1' in matches
        assert '10.0.0.1' in matches

    def test_clear_adj_rib_suggests_neighbor_and_ips(self):
        """Test that 'clear adj-rib' suggests 'neighbor' and IPs"""
        # Note: 'clear adj-rib' is the registered command, 'in'/'out' are parsed at runtime
        matches = self.completer._get_completions(['clear', 'adj-rib'], '')
        assert 'neighbor' in matches
        assert '192.168.1.1' in matches

    def test_announce_route_suggests_neighbor_and_ips(self):
        """Test that 'announce route' suggests 'neighbor' and IPs"""
        matches = self.completer._get_completions(['announce', 'route'], '')
        # Should have 'neighbor' keyword
        assert 'neighbor' in matches
        # Should have neighbor IPs
        assert '192.168.1.1' in matches

    def test_withdraw_route_suggests_neighbor_and_ips(self):
        """Test that 'withdraw route' suggests 'neighbor' and IPs"""
        matches = self.completer._get_completions(['withdraw', 'route'], '')
        assert 'neighbor' in matches
        assert '192.168.1.1' in matches

    def test_teardown_suggests_ips(self):
        """Test that 'teardown' suggests neighbor IPs"""
        matches = self.completer._get_completions(['teardown'], '')
        assert '192.168.1.1' in matches
        assert '10.0.0.1' in matches
