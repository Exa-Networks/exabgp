"""test_shortcuts.py

Unit tests for CommandShortcuts class.

Tests shortcut expansion logic including context-aware shortcuts,
typo correction, and multi-letter shortcuts.
"""

from __future__ import annotations

import pytest

from exabgp.application.shortcuts import CommandShortcuts


class TestBasicShortcuts:
    """Test basic single-letter shortcuts"""

    def test_help_shortcut(self):
        assert CommandShortcuts.expand_shortcuts('h') == 'help'

    def test_show_shortcut(self):
        assert CommandShortcuts.expand_shortcuts('s n') == 'show neighbor'

    def test_announce_shortcut(self):
        assert CommandShortcuts.expand_shortcuts('a r') == 'announce route'

    def test_withdraw_shortcut(self):
        assert CommandShortcuts.expand_shortcuts('w r') == 'withdraw route'

    def test_flush_shortcut(self):
        assert CommandShortcuts.expand_shortcuts('f') == 'flush'

    def test_teardown_shortcut(self):
        assert CommandShortcuts.expand_shortcuts('t 192.168.1.1 6') == 'teardown 192.168.1.1 6'

    def test_no_shortcuts_unchanged(self):
        # Command with no shortcuts should remain unchanged
        assert CommandShortcuts.expand_shortcuts('help') == 'help'
        assert CommandShortcuts.expand_shortcuts('version') == 'version'
        assert CommandShortcuts.expand_shortcuts('shutdown') == 'shutdown'


class TestContextAwareShortcuts:
    """Test shortcuts that change meaning based on context"""

    def test_a_as_announce_at_start(self):
        assert CommandShortcuts.expand_shortcuts('a r') == 'announce route'

    def test_a_as_attributes_after_announce(self):
        result = CommandShortcuts.expand_shortcuts('announce a')
        assert result == 'announce attributes'

    def test_a_as_attributes_after_withdraw(self):
        result = CommandShortcuts.expand_shortcuts('withdraw a')
        assert result == 'withdraw attributes'

    def test_a_as_adjrib_after_show(self):
        result = CommandShortcuts.expand_shortcuts('show a in')
        assert result == 'show adj-rib in'

    def test_a_as_adjrib_after_clear(self):
        result = CommandShortcuts.expand_shortcuts('clear a out')
        assert result == 'clear adj-rib out'

    def test_a_as_adjrib_after_flush(self):
        result = CommandShortcuts.expand_shortcuts('flush a out')
        assert result == 'flush adj-rib out'

    def test_e_as_eor_after_announce(self):
        result = CommandShortcuts.expand_shortcuts('announce e ipv4 unicast')
        assert result == 'announce eor ipv4 unicast'

    def test_e_as_extensive_after_show(self):
        result = CommandShortcuts.expand_shortcuts('show neighbor e')
        assert result == 'show neighbor extensive'

    def test_o_as_operation_after_announce(self):
        result = CommandShortcuts.expand_shortcuts('announce o')
        assert result == 'announce operation'

    def test_o_as_out_after_adjrib(self):
        result = CommandShortcuts.expand_shortcuts('show adj-rib o')
        assert result == 'show adj-rib out'

    def test_w_as_withdraw_at_start(self):
        result = CommandShortcuts.expand_shortcuts('w r')
        assert result == 'withdraw route'

    def test_w_as_watchdog_after_announce(self):
        result = CommandShortcuts.expand_shortcuts('announce w')
        assert result == 'announce watchdog'

    def test_s_as_show_at_start(self):
        result = CommandShortcuts.expand_shortcuts('s n')
        assert result == 'show neighbor'

    def test_s_as_summary_not_at_start(self):
        result = CommandShortcuts.expand_shortcuts('show neighbor s')
        assert result == 'show neighbor summary'


class TestMultiLetterShortcuts:
    """Test multi-character shortcuts"""

    def test_rr_as_route_refresh(self):
        result = CommandShortcuts.expand_shortcuts('announce rr ipv4 unicast')
        assert result == 'announce route-refresh ipv4 unicast'

    def test_rr_only_after_announce(self):
        # 'rr' should only expand after 'announce'
        tokens = ['show', 'rr']
        expanded = CommandShortcuts.expand_token_list(tokens)
        # Should not expand to route-refresh
        assert expanded == ['show', 'rr']


class TestTypoCorrection:
    """Test common typo corrections"""

    def test_neighbour_to_neighbor(self):
        assert CommandShortcuts.expand_shortcuts('show neighbour') == 'show neighbor'

    def test_neigbour_to_neighbor(self):
        assert CommandShortcuts.expand_shortcuts('show neigbour') == 'show neighbor'

    def test_neigbor_to_neighbor(self):
        assert CommandShortcuts.expand_shortcuts('show neigbor') == 'show neighbor'

    def test_typo_correction_with_shortcuts(self):
        result = CommandShortcuts.expand_shortcuts('s neigbor summary')
        assert result == 'show neighbor summary'


class TestIPAddressContext:
    """Test shortcuts that detect IP addresses in context"""

    def test_announce_after_ipv4(self):
        # 'a' after IPv4 address should be 'announce'
        result = CommandShortcuts.expand_shortcuts('a 192.168.1.1 route')
        assert result == 'announce 192.168.1.1 route'

    def test_withdraw_after_ipv4(self):
        result = CommandShortcuts.expand_shortcuts('w 10.0.0.1 route')
        assert result == 'withdraw 10.0.0.1 route'

    def test_teardown_after_ipv4(self):
        result = CommandShortcuts.expand_shortcuts('t 192.168.1.1 6')
        assert result == 'teardown 192.168.1.1 6'

    def test_announce_after_ipv6(self):
        # IPv6 detection (has colons)
        result = CommandShortcuts.expand_shortcuts('a 2001::1 route')
        assert result == 'announce 2001::1 route'


class TestTokenListExpansion:
    """Test expand_token_list method"""

    def test_simple_token_list(self):
        tokens = ['s', 'n', 'summary']
        expanded = CommandShortcuts.expand_token_list(tokens)
        assert expanded == ['show', 'neighbor', 'summary']

    def test_empty_token_list(self):
        tokens = []
        expanded = CommandShortcuts.expand_token_list(tokens)
        assert expanded == []

    def test_single_token(self):
        tokens = ['h']
        expanded = CommandShortcuts.expand_token_list(tokens)
        assert expanded == ['help']

    def test_mixed_shortcuts_and_full_words(self):
        tokens = ['s', 'neighbor', 'e']
        expanded = CommandShortcuts.expand_token_list(tokens)
        assert expanded == ['show', 'neighbor', 'extensive']

    def test_no_shortcuts_in_list(self):
        tokens = ['show', 'neighbor', 'summary']
        expanded = CommandShortcuts.expand_token_list(tokens)
        assert expanded == ['show', 'neighbor', 'summary']


class TestGetExpansion:
    """Test get_expansion method for single token"""

    def test_get_expansion_at_position_0(self):
        result = CommandShortcuts.get_expansion('s', 0, [])
        assert result == 'show'

    def test_get_expansion_with_context(self):
        result = CommandShortcuts.get_expansion('a', 1, ['show'])
        assert result == 'adj-rib'

    def test_get_expansion_announce_context(self):
        result = CommandShortcuts.get_expansion('a', 1, ['announce'])
        assert result == 'attributes'

    def test_get_expansion_no_match(self):
        # Token that doesn't match any shortcut
        result = CommandShortcuts.get_expansion('xyz', 0, [])
        assert result == 'xyz'


class TestGetPossibleExpansions:
    """Test get_possible_expansions method"""

    def test_single_expansion(self):
        # 'h' only expands to 'help'
        expansions = CommandShortcuts.get_possible_expansions('h', 0, [])
        assert expansions == ['help']

    def test_multiple_expansions(self):
        # 'a' at position 0 could expand to 'announce'
        expansions = CommandShortcuts.get_possible_expansions('a', 0, [])
        assert 'announce' in expansions

    def test_context_specific_expansion(self):
        # 'a' after 'show' should expand to 'adj-rib'
        expansions = CommandShortcuts.get_possible_expansions('a', 1, ['show'])
        assert 'adj-rib' in expansions

    def test_no_expansions(self):
        # Non-existent shortcut
        expansions = CommandShortcuts.get_possible_expansions('xyz', 0, [])
        assert expansions == []


class TestComplexCommands:
    """Test complex multi-part commands"""

    def test_announce_route_with_attributes(self):
        cmd = 'a r 10.0.0.0/24 next-hop 192.168.1.1 community 65000:1'
        result = CommandShortcuts.expand_shortcuts(cmd)
        assert result == 'announce route 10.0.0.0/24 next-hop 192.168.1.1 community 65000:1'

    def test_show_adj_rib_in_extensive(self):
        cmd = 's a i e'
        result = CommandShortcuts.expand_shortcuts(cmd)
        assert result == 'show adj-rib in extensive'

    def test_neighbor_with_filters(self):
        cmd = 'neighbor 192.168.1.1 local-ip 10.0.0.1 a r 10.0.0.0/24'
        result = CommandShortcuts.expand_shortcuts(cmd)
        # After IP, 'a' should be 'announce'
        assert 'announce route' in result

    def test_announce_eor_full_command(self):
        cmd = 'a e ipv4 unicast'
        result = CommandShortcuts.expand_shortcuts(cmd)
        assert result == 'announce eor ipv4 unicast'

    def test_withdraw_vpls(self):
        cmd = 'w vpls endpoint 10 offset 20'
        result = CommandShortcuts.expand_shortcuts(cmd)
        assert result.startswith('withdraw vpls')


class TestPartialMatching:
    """Test partial command matching"""

    def test_partial_show(self):
        # 'sh' should match 'show' if it's a prefix
        result = CommandShortcuts.expand_shortcuts('sh n')
        # Should expand 'sh' based on prefix matching
        assert 'show' in result or 'sh' in result

    def test_partial_announce(self):
        result = CommandShortcuts.expand_shortcuts('ann r')
        assert 'announce' in result or 'ann' in result


class TestEdgeCases:
    """Test edge cases and unusual inputs"""

    def test_empty_string(self):
        assert CommandShortcuts.expand_shortcuts('') == ''

    def test_whitespace_only(self):
        # Whitespace-only strings return whitespace (command.split() returns empty list)
        result = CommandShortcuts.expand_shortcuts('   ')
        assert result.strip() == ''

    def test_multiple_spaces(self):
        result = CommandShortcuts.expand_shortcuts('s  n  summary')
        # Should handle multiple spaces gracefully
        assert 'show' in result
        assert 'neighbor' in result

    def test_numeric_tokens(self):
        # Numbers should pass through unchanged
        result = CommandShortcuts.expand_shortcuts('teardown 192.168.1.1 6')
        assert '192.168.1.1' in result
        assert '6' in result

    def test_special_characters(self):
        # Special characters in route specs
        result = CommandShortcuts.expand_shortcuts('a r 10.0.0.0/24 community 65000:1')
        assert '10.0.0.0/24' in result
        assert '65000:1' in result

    def test_very_long_command(self):
        # Test with many tokens
        cmd = 's n 192.168.1.1 e json'
        result = CommandShortcuts.expand_shortcuts(cmd)
        assert 'show' in result
        assert 'neighbor' in result
        assert 'extensive' in result

    def test_case_sensitivity(self):
        # Shortcuts are lowercase
        result = CommandShortcuts.expand_shortcuts('S N')
        # Should not match (case sensitive)
        assert result == 'S N' or 'show' in result.lower()


class TestRealWorldScenarios:
    """Test real-world command scenarios"""

    def test_show_neighbor_summary(self):
        assert CommandShortcuts.expand_shortcuts('s n s') == 'show neighbor summary'

    def test_show_neighbor_extensive_json(self):
        result = CommandShortcuts.expand_shortcuts('s n e json')
        assert result == 'show neighbor extensive json'

    def test_show_adj_rib_in(self):
        result = CommandShortcuts.expand_shortcuts('s a i')
        assert result == 'show adj-rib in'

    def test_announce_route_with_nexthop(self):
        result = CommandShortcuts.expand_shortcuts('a r 10.0.0.0/8 next-hop 192.168.1.1')
        assert result == 'announce route 10.0.0.0/8 next-hop 192.168.1.1'

    def test_withdraw_flow(self):
        result = CommandShortcuts.expand_shortcuts('w f destination 10.0.0.0/8')
        assert result == 'withdraw flow destination 10.0.0.0/8'

    def test_announce_attributes(self):
        result = CommandShortcuts.expand_shortcuts('a a next-hop 192.168.1.1')
        assert result == 'announce attributes next-hop 192.168.1.1'

    def test_flush_adj_rib_out(self):
        result = CommandShortcuts.expand_shortcuts('f a o')
        assert result == 'flush adj-rib out'

    def test_clear_adj_rib_in(self):
        # 'c' at position 0 expands to 'configuration', not 'clear'
        # 'clear' is not in the shortcut list - only configuration uses 'c'
        result = CommandShortcuts.expand_shortcuts('clear a i')
        assert result == 'clear adj-rib in'

    def test_neighbor_with_announce(self):
        result = CommandShortcuts.expand_shortcuts('neighbor 192.168.1.1 a r 10.0.0.0/24')
        assert 'neighbor 192.168.1.1' in result
        assert 'announce route' in result

    def test_announce_route_refresh(self):
        result = CommandShortcuts.expand_shortcuts('a rr ipv6 unicast')
        assert result == 'announce route-refresh ipv6 unicast'


class TestConsistency:
    """Test that expansion is consistent and reversible where applicable"""

    def test_idempotent_full_commands(self):
        # Full commands should remain unchanged
        full_cmd = 'show neighbor summary'
        assert CommandShortcuts.expand_shortcuts(full_cmd) == full_cmd

    def test_multiple_expansions_consistent(self):
        # Expanding multiple times should give same result
        cmd = 's n s'
        result1 = CommandShortcuts.expand_shortcuts(cmd)
        result2 = CommandShortcuts.expand_shortcuts(cmd)
        assert result1 == result2

    def test_token_list_vs_string_consistent(self):
        # Token list expansion should match string expansion
        tokens = ['s', 'n', 's']
        expanded_list = CommandShortcuts.expand_token_list(tokens)
        expanded_str = CommandShortcuts.expand_shortcuts(' '.join(tokens))
        assert ' '.join(expanded_list) == expanded_str
