"""Tests for API command transformation between v4 and v6 formats."""

import pytest

from exabgp.reactor.api.transform import v4_to_v6, is_v4_command


class TestV4toV6Transform:
    """Test v4 (action-first) to v6 (target-first) transformation."""

    # === Daemon control commands ===

    def test_shutdown(self) -> None:
        assert v4_to_v6('shutdown') == 'daemon shutdown'

    def test_reload(self) -> None:
        assert v4_to_v6('reload') == 'daemon reload'

    def test_restart(self) -> None:
        assert v4_to_v6('restart') == 'daemon restart'

    def test_status(self) -> None:
        assert v4_to_v6('status') == 'daemon status'

    # === Session management commands ===

    def test_enable_ack(self) -> None:
        assert v4_to_v6('enable-ack') == 'session ack enable'

    def test_disable_ack(self) -> None:
        assert v4_to_v6('disable-ack') == 'session ack disable'

    def test_silence_ack(self) -> None:
        assert v4_to_v6('silence-ack') == 'session ack silence'

    def test_enable_sync(self) -> None:
        assert v4_to_v6('enable-sync') == 'session sync enable'

    def test_disable_sync(self) -> None:
        assert v4_to_v6('disable-sync') == 'session sync disable'

    def test_reset(self) -> None:
        assert v4_to_v6('reset') == 'session reset'

    def test_ping(self) -> None:
        assert v4_to_v6('ping') == 'session ping'

    def test_ping_with_args(self) -> None:
        assert v4_to_v6('ping uuid-123 1234567890') == 'session ping uuid-123 1234567890'

    def test_bye(self) -> None:
        assert v4_to_v6('bye') == 'session bye'

    # === System commands ===

    def test_help(self) -> None:
        assert v4_to_v6('help') == 'system help'

    def test_version(self) -> None:
        assert v4_to_v6('version') == 'system version'

    def test_crash(self) -> None:
        assert v4_to_v6('crash') == 'system crash'

    def test_queue_status(self) -> None:
        assert v4_to_v6('queue-status') == 'system queue-status'

    def test_api_version(self) -> None:
        assert v4_to_v6('api version') == 'system api version'

    def test_api_version_with_arg(self) -> None:
        assert v4_to_v6('api version 4') == 'system api version 4'

    # === RIB operations ===

    def test_show_adj_rib_in(self) -> None:
        assert v4_to_v6('show adj-rib in') == 'rib show in'

    def test_show_adj_rib_in_with_ip(self) -> None:
        assert v4_to_v6('show adj-rib in 192.168.1.1') == 'rib show in 192.168.1.1'

    def test_show_adj_rib_out(self) -> None:
        assert v4_to_v6('show adj-rib out') == 'rib show out'

    def test_flush_adj_rib_out(self) -> None:
        assert v4_to_v6('flush adj-rib out') == 'rib flush out'

    def test_clear_adj_rib_in(self) -> None:
        assert v4_to_v6('clear adj-rib in') == 'rib clear in'

    def test_clear_adj_rib_out(self) -> None:
        assert v4_to_v6('clear adj-rib out') == 'rib clear out'

    # === Neighbor operations ===

    def test_show_neighbor(self) -> None:
        assert v4_to_v6('show neighbor') == 'peer show'

    def test_show_neighbor_summary(self) -> None:
        assert v4_to_v6('show neighbor summary') == 'peer show summary'

    def test_show_neighbor_ip_extensive(self) -> None:
        assert v4_to_v6('show neighbor 192.168.1.1 extensive') == 'peer show 192.168.1.1 extensive'

    def test_teardown(self) -> None:
        assert v4_to_v6('teardown') == 'peer * teardown'

    def test_teardown_with_code(self) -> None:
        assert v4_to_v6('teardown 6') == 'peer * teardown 6'

    # === Announce commands (to ALL peers) ===

    def test_announce_route(self) -> None:
        result = v4_to_v6('announce route 10.0.0.0/24 next-hop 1.2.3.4')
        assert result == 'peer * announce route 10.0.0.0/24 next-hop 1.2.3.4'

    def test_announce_ipv4(self) -> None:
        result = v4_to_v6('announce ipv4 unicast 10.0.0.0/24 next-hop 1.2.3.4')
        assert result == 'peer * announce ipv4 unicast 10.0.0.0/24 next-hop 1.2.3.4'

    def test_announce_ipv6(self) -> None:
        result = v4_to_v6('announce ipv6 unicast 2001:db8::/32 next-hop 2001:db8::1')
        assert result == 'peer * announce ipv6 unicast 2001:db8::/32 next-hop 2001:db8::1'

    def test_announce_eor(self) -> None:
        result = v4_to_v6('announce eor ipv4 unicast')
        assert result == 'peer * announce eor ipv4 unicast'

    def test_announce_route_refresh(self) -> None:
        result = v4_to_v6('announce route-refresh ipv4 unicast')
        assert result == 'peer * announce route-refresh ipv4 unicast'

    def test_announce_flow(self) -> None:
        result = v4_to_v6('announce flow route destination 10.0.0.0/24 then discard')
        assert result == 'peer * announce flow route destination 10.0.0.0/24 then discard'

    def test_announce_watchdog(self) -> None:
        result = v4_to_v6('announce watchdog healthcheck')
        assert result == 'peer * announce watchdog healthcheck'

    # === Withdraw commands (from ALL peers) ===

    def test_withdraw_route(self) -> None:
        result = v4_to_v6('withdraw route 10.0.0.0/24')
        assert result == 'peer * withdraw route 10.0.0.0/24'

    def test_withdraw_flow(self) -> None:
        result = v4_to_v6('withdraw flow route destination 10.0.0.0/24')
        assert result == 'peer * withdraw flow route destination 10.0.0.0/24'

    # === Peer management ===

    def test_create_neighbor(self) -> None:
        result = v4_to_v6('create neighbor 192.168.1.1 { router-id 1.1.1.1; }')
        assert result == 'peer create 192.168.1.1 { router-id 1.1.1.1; }'

    def test_delete_neighbor(self) -> None:
        result = v4_to_v6('delete neighbor 192.168.1.1')
        assert result == 'peer delete 192.168.1.1'

    # === Commands that should NOT be transformed ===

    def test_neighbor_to_peer_transformation(self) -> None:
        """Commands with 'neighbor <ip>' are transformed to 'peer <ip>'."""
        v4_cmd = 'neighbor 192.168.1.1 announce route 10.0.0.0/24 next-hop 1.2.3.4'
        v6_cmd = 'peer 192.168.1.1 announce route 10.0.0.0/24 next-hop 1.2.3.4'
        assert v4_to_v6(v4_cmd) == v6_cmd

    def test_neighbor_teardown_to_peer(self) -> None:
        """Neighbor-specific teardown transformed to peer."""
        v4_cmd = 'neighbor 192.168.1.1 teardown 6'
        v6_cmd = 'peer 192.168.1.1 teardown 6'
        assert v4_to_v6(v4_cmd) == v6_cmd

    def test_comment_unchanged(self) -> None:
        """Comments should not be transformed."""
        assert v4_to_v6('# this is a comment') == '# this is a comment'

    def test_empty_unchanged(self) -> None:
        """Empty string should not be transformed."""
        assert v4_to_v6('') == ''

    def test_whitespace_stripped(self) -> None:
        """Leading/trailing whitespace should be stripped."""
        assert v4_to_v6('  shutdown  ') == 'daemon shutdown'

    def test_v6_command_unchanged(self) -> None:
        """Commands already in v6 format should not be transformed."""
        assert v4_to_v6('daemon shutdown') == 'daemon shutdown'
        assert v4_to_v6('session ping') == 'session ping'
        assert v4_to_v6('system help') == 'system help'
        assert v4_to_v6('rib show in') == 'rib show in'
        assert v4_to_v6('peer 192.168.1.1 announce route') == 'peer 192.168.1.1 announce route'


class TestNeighborParsing:
    """Test neighbor command parsing and validation (v4 neighbor → v6 peer)."""

    # === Valid neighbor commands (transformed to peer) ===

    def test_neighbor_ip_announce_route(self) -> None:
        v4 = 'neighbor 192.168.1.1 announce route 10.0.0.0/24 next-hop 1.2.3.4'
        v6 = 'peer 192.168.1.1 announce route 10.0.0.0/24 next-hop 1.2.3.4'
        assert v4_to_v6(v4) == v6

    def test_neighbor_wildcard_announce(self) -> None:
        v4 = 'neighbor * announce route 10.0.0.0/24 next-hop 1.2.3.4'
        v6 = 'peer * announce route 10.0.0.0/24 next-hop 1.2.3.4'
        assert v4_to_v6(v4) == v6

    def test_neighbor_ipv6_announce(self) -> None:
        v4 = 'neighbor 2001:db8::1 announce route 10.0.0.0/24 next-hop 1.2.3.4'
        v6 = 'peer 2001:db8::1 announce route 10.0.0.0/24 next-hop 1.2.3.4'
        assert v4_to_v6(v4) == v6

    def test_neighbor_with_peer_as_selector(self) -> None:
        v4 = 'neighbor 192.168.1.1 peer-as 65000 announce route 10.0.0.0/24'
        v6 = 'peer 192.168.1.1 peer-as 65000 announce route 10.0.0.0/24'
        assert v4_to_v6(v4) == v6

    def test_neighbor_with_local_as_selector(self) -> None:
        v4 = 'neighbor 192.168.1.1 local-as 65001 announce eor ipv4 unicast'
        v6 = 'peer 192.168.1.1 local-as 65001 announce eor ipv4 unicast'
        assert v4_to_v6(v4) == v6

    def test_neighbor_with_multiple_selectors(self) -> None:
        v4 = 'neighbor 192.168.1.1 peer-as 65000 local-as 65001 announce route 10.0.0.0/24'
        v6 = 'peer 192.168.1.1 peer-as 65000 local-as 65001 announce route 10.0.0.0/24'
        assert v4_to_v6(v4) == v6

    def test_neighbor_with_family_allowed(self) -> None:
        v4 = 'neighbor 192.168.1.1 family-allowed ipv4 unicast announce eor ipv4 unicast'
        v6 = 'peer 192.168.1.1 family-allowed ipv4 unicast announce eor ipv4 unicast'
        assert v4_to_v6(v4) == v6

    def test_neighbor_teardown(self) -> None:
        v4 = 'neighbor 192.168.1.1 teardown'
        v6 = 'peer 192.168.1.1 teardown'
        assert v4_to_v6(v4) == v6

    def test_neighbor_teardown_with_code(self) -> None:
        v4 = 'neighbor 192.168.1.1 teardown 6'
        v6 = 'peer 192.168.1.1 teardown 6'
        assert v4_to_v6(v4) == v6

    def test_neighbor_withdraw(self) -> None:
        v4 = 'neighbor 192.168.1.1 withdraw route 10.0.0.0/24'
        v6 = 'peer 192.168.1.1 withdraw route 10.0.0.0/24'
        assert v4_to_v6(v4) == v6

    def test_neighbor_all_announce_subcommands(self) -> None:
        """Test all valid announce subcommands after neighbor."""
        subcommands = [
            'route',
            'route-refresh',
            'ipv4',
            'ipv6',
            'flow',
            'eor',
            'watchdog',
            'attribute',
            'attributes',
            'operational',
            'vpls',
        ]
        for sub in subcommands:
            v4 = f'neighbor 192.168.1.1 announce {sub} args'
            v6 = f'peer 192.168.1.1 announce {sub} args'
            assert v4_to_v6(v4) == v6, f'failed for announce {sub}'

    def test_neighbor_all_withdraw_subcommands(self) -> None:
        """Test all valid withdraw subcommands after neighbor."""
        subcommands = ['route', 'ipv4', 'ipv6', 'flow', 'watchdog', 'attribute', 'attributes', 'vpls']
        for sub in subcommands:
            v4 = f'neighbor 192.168.1.1 withdraw {sub} args'
            v6 = f'peer 192.168.1.1 withdraw {sub} args'
            assert v4_to_v6(v4) == v6, f'failed for withdraw {sub}'

    # === Comma-separated neighbor selectors ===

    def test_neighbor_comma_separated_selectors(self) -> None:
        """Test comma-separated neighbor selectors are transformed to bracket syntax."""
        v4 = 'neighbor 127.0.0.1 router-id 1.2.3.4, neighbor 127.0.0.1 announce route 1.1.0.0/25 next-hop 101.1.101.1'
        # v6 uses bracket syntax for multiple selectors
        v6 = 'peer [127.0.0.1 router-id 1.2.3.4, 127.0.0.1] announce route 1.1.0.0/25 next-hop 101.1.101.1'
        assert v4_to_v6(v4) == v6

    def test_neighbor_multiple_comma_selectors(self) -> None:
        """Test multiple comma-separated neighbor selectors use bracket syntax."""
        v4 = 'neighbor 10.0.0.1 local-as 65000, neighbor 10.0.0.2 peer-as 65001, neighbor * announce route 1.0.0.0/8'
        # v6 uses bracket syntax for multiple selectors
        v6 = 'peer [10.0.0.1 local-as 65000, 10.0.0.2 peer-as 65001, *] announce route 1.0.0.0/8'
        assert v4_to_v6(v4) == v6

    # === family-allowed special cases ===

    def test_neighbor_family_allowed_in_open(self) -> None:
        """Test family-allowed in-open (single value)."""
        v4 = 'neighbor 127.0.0.1 family-allowed in-open announce route 1.0.0.0/24 next-hop 1.1.1.1'
        v6 = 'peer 127.0.0.1 family-allowed in-open announce route 1.0.0.0/24 next-hop 1.1.1.1'
        assert v4_to_v6(v4) == v6

    def test_neighbor_family_allowed_hyphenated(self) -> None:
        """Test family-allowed with hyphenated afi-safi (single value)."""
        v4 = 'neighbor 127.0.0.1 family-allowed ipv4-unicast announce route 1.0.0.0/24 next-hop 1.1.1.1'
        v6 = 'peer 127.0.0.1 family-allowed ipv4-unicast announce route 1.0.0.0/24 next-hop 1.1.1.1'
        assert v4_to_v6(v4) == v6

    def test_neighbor_family_allowed_two_values(self) -> None:
        """Test family-allowed with separate afi safi (two values)."""
        v4 = 'neighbor 127.0.0.1 family-allowed ipv4 unicast announce route 1.0.0.0/24 next-hop 1.1.1.1'
        v6 = 'peer 127.0.0.1 family-allowed ipv4 unicast announce route 1.0.0.0/24 next-hop 1.1.1.1'
        assert v4_to_v6(v4) == v6

    # === Invalid neighbor commands ===

    def test_neighbor_missing_ip_raises(self) -> None:
        with pytest.raises(ValueError, match='neighbor requires at least'):
            v4_to_v6('neighbor')

    def test_neighbor_invalid_ip_raises(self) -> None:
        with pytest.raises(ValueError, match='expected IP or \\*'):
            v4_to_v6('neighbor notanip announce route')

    def test_neighbor_missing_action_raises(self) -> None:
        with pytest.raises(ValueError, match='missing action'):
            v4_to_v6('neighbor 192.168.1.1')

    def test_neighbor_unknown_selector_raises(self) -> None:
        # Unknown word after IP is treated as end of selector, then next word
        # is parsed as a new selector (which fails since it's not an IP)
        with pytest.raises(ValueError, match='expected IP or \\* in selector'):
            v4_to_v6('neighbor 192.168.1.1 unknown-key value announce route')

    def test_neighbor_selector_missing_value_raises(self) -> None:
        with pytest.raises(ValueError, match='requires a value'):
            v4_to_v6('neighbor 192.168.1.1 peer-as')

    def test_neighbor_family_allowed_missing_safi_raises(self) -> None:
        with pytest.raises(ValueError, match='requires afi and safi'):
            v4_to_v6('neighbor 192.168.1.1 family-allowed ipv4')

    def test_neighbor_unknown_announce_subcommand_raises(self) -> None:
        with pytest.raises(ValueError, match='unknown announce subcommand'):
            v4_to_v6('neighbor 192.168.1.1 announce badcmd 10.0.0.0/24')

    def test_neighbor_unknown_withdraw_subcommand_raises(self) -> None:
        with pytest.raises(ValueError, match='unknown withdraw subcommand'):
            v4_to_v6('neighbor 192.168.1.1 withdraw badcmd 10.0.0.0/24')


class TestIsV4Command:
    """Test is_v4_command detection."""

    def test_is_v4_command_true(self) -> None:
        assert is_v4_command('shutdown') is True
        assert is_v4_command('announce route 10.0.0.0/24') is True
        assert is_v4_command('show neighbor') is True
        assert is_v4_command('show adj-rib in') is True

    def test_is_v4_command_false(self) -> None:
        # v6-only prefixes
        assert is_v4_command('daemon shutdown') is False
        assert is_v4_command('rib show in') is False
        assert is_v4_command('session ping') is False
        assert is_v4_command('system help') is False
        assert is_v4_command('peer create') is False
        # Comments and empty
        assert is_v4_command('# comment') is False
        assert is_v4_command('') is False

    def test_neighbor_is_v4_command(self) -> None:
        # neighbor-prefixed commands are valid v4 (parsed but unchanged)
        assert is_v4_command('neighbor 192.168.1.1 announce route') is True
        assert is_v4_command('neighbor * teardown') is True
        assert is_v4_command('neighbor 10.0.0.1 peer-as 65000 announce eor') is True
