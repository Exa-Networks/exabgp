"""Unit tests for noun-first CLI syntax transformation."""

from exabgp.application.noun_first_transform import NounFirstTransform


class TestNounFirstTransform:
    """Test noun-first to API syntax transformation."""

    # Neighbor commands
    def test_neighbor_show_all(self):
        """Test neighbor show → show neighbor (all neighbors)."""
        assert NounFirstTransform.transform('neighbor show') == 'show neighbor'
        assert NounFirstTransform.transform('neighbor show summary') == 'show neighbor summary'
        assert NounFirstTransform.transform('neighbor show extensive') == 'show neighbor extensive'

    def test_neighbor_specific_unchanged(self):
        """Test neighbor <ip> commands pass through (already correct)."""
        assert NounFirstTransform.transform('neighbor 192.168.1.1 show') == 'neighbor 192.168.1.1 show'
        assert (
            NounFirstTransform.transform('neighbor 192.168.1.1 announce route 10.0.0.0/24 next-hop self')
            == 'neighbor 192.168.1.1 announce route 10.0.0.0/24 next-hop self'
        )
        assert (
            NounFirstTransform.transform('neighbor * announce route 10.0.0.0/24 next-hop 1.1.1.1')
            == 'neighbor * announce route 10.0.0.0/24 next-hop 1.1.1.1'
        )

    # RIB commands
    def test_rib_show_in(self):
        """Test rib show in → show adj-rib in."""
        assert NounFirstTransform.transform('rib show in') == 'show adj-rib in'
        assert NounFirstTransform.transform('rib show in extensive') == 'show adj-rib in extensive'
        assert (
            NounFirstTransform.transform('rib show in neighbor 192.168.1.1') == 'show adj-rib in neighbor 192.168.1.1'
        )

    def test_rib_show_out(self):
        """Test rib show out → show adj-rib out."""
        assert NounFirstTransform.transform('rib show out') == 'show adj-rib out'
        assert NounFirstTransform.transform('rib show out extensive') == 'show adj-rib out extensive'
        assert NounFirstTransform.transform('rib show out neighbor 10.0.0.1') == 'show adj-rib out neighbor 10.0.0.1'

    def test_rib_flush(self):
        """Test rib flush out → flush adj-rib out."""
        assert NounFirstTransform.transform('rib flush out') == 'flush adj-rib out'
        assert (
            NounFirstTransform.transform('rib flush out neighbor 192.168.1.1')
            == 'flush adj-rib out neighbor 192.168.1.1'
        )

    def test_rib_clear(self):
        """Test rib clear → clear adj-rib."""
        assert NounFirstTransform.transform('rib clear in') == 'clear adj-rib in'
        assert NounFirstTransform.transform('rib clear out') == 'clear adj-rib out'
        assert NounFirstTransform.transform('rib clear in neighbor 10.0.0.1') == 'clear adj-rib in neighbor 10.0.0.1'

    # Daemon commands
    def test_daemon_shutdown(self):
        """Test daemon shutdown → shutdown."""
        assert NounFirstTransform.transform('daemon shutdown') == 'shutdown'

    def test_daemon_reload(self):
        """Test daemon reload → reload."""
        assert NounFirstTransform.transform('daemon reload') == 'reload'

    def test_daemon_restart(self):
        """Test daemon restart → restart."""
        assert NounFirstTransform.transform('daemon restart') == 'restart'

    def test_daemon_status(self):
        """Test daemon status → status."""
        assert NounFirstTransform.transform('daemon status') == 'status'

    # Session commands (hierarchical)
    def test_session_ack_enable(self):
        """Test session ack enable → enable-ack."""
        assert NounFirstTransform.transform('session ack enable') == 'enable-ack'

    def test_session_ack_disable(self):
        """Test session ack disable → disable-ack."""
        assert NounFirstTransform.transform('session ack disable') == 'disable-ack'

    def test_session_ack_silence(self):
        """Test session ack silence → silence-ack."""
        assert NounFirstTransform.transform('session ack silence') == 'silence-ack'

    def test_session_sync_enable(self):
        """Test session sync enable → enable-sync."""
        assert NounFirstTransform.transform('session sync enable') == 'enable-sync'

    def test_session_sync_disable(self):
        """Test session sync disable → disable-sync."""
        assert NounFirstTransform.transform('session sync disable') == 'disable-sync'

    def test_session_reset(self):
        """Test session reset → reset."""
        assert NounFirstTransform.transform('session reset') == 'reset'

    def test_session_ping(self):
        """Test session ping → ping."""
        assert NounFirstTransform.transform('session ping') == 'ping'
        # With arguments
        assert NounFirstTransform.transform('session ping uuid123 timestamp456') == 'ping uuid123 timestamp456'

    def test_session_bye(self):
        """Test session bye → bye."""
        assert NounFirstTransform.transform('session bye') == 'bye'

    # System commands
    def test_system_help(self):
        """Test system help → help."""
        assert NounFirstTransform.transform('system help') == 'help'

    def test_system_version(self):
        """Test system version → version."""
        assert NounFirstTransform.transform('system version') == 'version'

    def test_system_crash(self):
        """Test system crash → crash."""
        assert NounFirstTransform.transform('system crash') == 'crash'

    # Backward compatibility - old syntax unchanged
    def test_old_syntax_announce_route(self):
        """Test old syntax passes through unchanged."""
        assert (
            NounFirstTransform.transform('announce route 10.0.0.0/24 next-hop 1.1.1.1')
            == 'announce route 10.0.0.0/24 next-hop 1.1.1.1'
        )

    def test_old_syntax_show_neighbor(self):
        """Test old syntax passes through unchanged."""
        assert NounFirstTransform.transform('show neighbor summary') == 'show neighbor summary'
        assert (
            NounFirstTransform.transform('show neighbor 192.168.1.1 extensive') == 'show neighbor 192.168.1.1 extensive'
        )

    def test_old_syntax_flush_adj_rib(self):
        """Test old syntax passes through unchanged."""
        assert NounFirstTransform.transform('flush adj-rib out') == 'flush adj-rib out'

    def test_old_syntax_session_commands(self):
        """Test old flat session commands pass through unchanged."""
        assert NounFirstTransform.transform('enable-ack') == 'enable-ack'
        assert NounFirstTransform.transform('disable-sync') == 'disable-sync'
        assert NounFirstTransform.transform('silence-ack') == 'silence-ack'

    def test_old_syntax_daemon_commands(self):
        """Test old daemon commands pass through unchanged."""
        assert NounFirstTransform.transform('shutdown') == 'shutdown'
        assert NounFirstTransform.transform('reload') == 'reload'
        assert NounFirstTransform.transform('restart') == 'restart'

    # Edge cases
    def test_empty_command(self):
        """Test empty command."""
        assert NounFirstTransform.transform('') == ''
        assert NounFirstTransform.transform('   ') == '   '

    def test_case_insensitivity(self):
        """Test case-insensitive matching."""
        assert NounFirstTransform.transform('DAEMON SHUTDOWN') == 'shutdown'
        assert NounFirstTransform.transform('Daemon Shutdown') == 'shutdown'
        assert NounFirstTransform.transform('RIB SHOW IN') == 'show adj-rib in'
        assert NounFirstTransform.transform('Session Ack Enable') == 'enable-ack'

    def test_extra_whitespace(self):
        """Test handling of extra whitespace."""
        assert NounFirstTransform.transform('daemon  shutdown') == 'shutdown'
        assert NounFirstTransform.transform('rib  show  in') == 'show adj-rib in'

    def test_partial_matches_not_transformed(self):
        """Test that partial matches don't trigger transformation."""
        # These should NOT match because they don't have word boundaries
        assert NounFirstTransform.transform('daemonshutdown') == 'daemonshutdown'
        assert NounFirstTransform.transform('mydaemon shutdown') == 'mydaemon shutdown'

    def test_cli_builtin_commands_unchanged(self):
        """Test CLI built-in commands pass through."""
        assert NounFirstTransform.transform('exit') == 'exit'
        assert NounFirstTransform.transform('quit') == 'quit'
        assert NounFirstTransform.transform('clear') == 'clear'
        assert NounFirstTransform.transform('history') == 'history'
        assert NounFirstTransform.transform('set encoding json') == 'set encoding json'
        assert NounFirstTransform.transform('set display text') == 'set display text'

    def test_complex_neighbor_commands(self):
        """Test complex neighbor commands with attributes."""
        # Should not transform - neighbor with IP/wildcard is already API syntax
        cmd = 'neighbor * announce route 10.0.0.0/24 next-hop 1.1.1.1 as-path [65000 65001] community 100:200'
        assert NounFirstTransform.transform(cmd) == cmd

        cmd2 = 'neighbor 192.168.1.1 withdraw route 10.0.0.0/24'
        assert NounFirstTransform.transform(cmd2) == cmd2

    def test_option_preservation(self):
        """Test that options/arguments after pattern are preserved."""
        assert NounFirstTransform.transform('neighbor show summary extensive') == 'show neighbor summary extensive'
        assert (
            NounFirstTransform.transform('rib show in neighbor 192.168.1.1 extensive')
            == 'show adj-rib in neighbor 192.168.1.1 extensive'
        )
        assert NounFirstTransform.transform('session ping uuid123 ts456') == 'ping uuid123 ts456'
