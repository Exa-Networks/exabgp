#!/usr/bin/env python3
"""
Test CLI tab completion and auto-expansion functionality
"""

import json
import unittest
from exabgp.application.cli import CommandCompleter, OutputFormatter, InteractiveCLI


class TestCLICompletion(unittest.TestCase):
    """Test cases for CLI command completion"""

    def setUp(self):
        """Set up test fixtures"""
        self.completer = CommandCompleter(send_command=lambda cmd: '')

    def test_auto_expand_unambiguous_token(self):
        """Test that unambiguous tokens get auto-expanded"""
        # "n" after "show" no longer expands (neighbor filtered from completions)
        tokens = ['show', 'n']
        expanded, changed = self.completer._try_auto_expand_tokens(tokens)

        self.assertEqual(expanded, ['show', 'n'])  # No expansion - neighbor filtered
        self.assertFalse(changed)

    def test_no_expand_ambiguous_token(self):
        """Test that ambiguous tokens don't get auto-expanded"""
        # "s" alone is ambiguous (show, shutdown, silence-ack)
        tokens = ['s']
        expanded, changed = self.completer._try_auto_expand_tokens(tokens)

        self.assertEqual(expanded, ['s'])
        self.assertFalse(changed)

    def test_no_expand_complete_token(self):
        """Test that complete tokens don't get modified"""
        # "show" is already complete
        tokens = ['show']
        expanded, changed = self.completer._try_auto_expand_tokens(tokens)

        self.assertEqual(expanded, ['show'])
        self.assertFalse(changed)

    def test_expand_multiple_tokens(self):
        """Test expanding multiple unambiguous tokens in context"""
        # 'n' after 'show' no longer expands (neighbor filtered)
        tokens = ['show', 'n']
        expanded, changed = self.completer._try_auto_expand_tokens(tokens)

        # No expansion - neighbor filtered from 'show' completions
        self.assertEqual(len(expanded), 2)
        self.assertEqual(expanded[0], 'show')
        self.assertEqual(expanded[1], 'n')
        self.assertFalse(changed)

    def test_get_completions_base_commands(self):
        """Test getting completions for base commands (v6 API)"""
        # Empty context, partial match 'da'
        completions = self.completer._get_completions([], 'da')

        # Should suggest 'daemon'
        self.assertIn('daemon', completions)
        # v4 commands not in base
        self.assertNotIn('shutdown', completions)

    def test_get_completions_with_context(self):
        """Test getting completions with command context"""
        # After 'daemon', get completions for 'sh'
        completions = self.completer._get_completions(['daemon'], 'sh')

        # Should suggest 'shutdown'
        self.assertIn('shutdown', completions)

    def test_get_completions_exact_match(self):
        """Test completions when token is exact match (v6 API)"""
        # 'peer' is exact match
        completions = self.completer._get_completions([], 'peer')

        # Should return 'peer' as it's a valid command
        self.assertIn('peer', completions)

    def test_expand_preserves_exact_matches(self):
        """Test that exact matches are preserved during expansion"""
        # 'daemon shutdown' are both exact matches
        tokens = ['daemon', 'shutdown']
        expanded, changed = self.completer._try_auto_expand_tokens(tokens)

        self.assertEqual(expanded, ['daemon', 'shutdown'])
        self.assertFalse(changed)  # No changes since both are exact matches

    def test_completion_metadata(self):
        """Test that completions include metadata for displaying descriptions"""
        # Get completions for base commands
        completions = self.completer._get_completions([], 'da')

        # Should get completions matching 'da'
        self.assertIn('daemon', completions)

        # Verify metadata was added (used for showing descriptions)
        # This metadata is displayed when multiple matches exist
        self.assertIn('daemon', self.completer.match_metadata)
        self.assertIsNotNone(self.completer.match_metadata['daemon'].description)

    def test_peer_ip_shows_actions(self):
        """Test that after 'peer <ip>', announce/withdraw/show/teardown are suggested"""
        # After peer IP, should get v6 API actions
        completions = self.completer._get_completions(['peer', '127.0.0.1'], '')

        # Should contain v6 API actions
        self.assertIn('announce', completions)
        self.assertIn('withdraw', completions)
        self.assertIn('show', completions)
        self.assertIn('teardown', completions)

        # Should NOT contain other commands (ping, help, reload, etc.)
        self.assertNotIn('ping', completions)
        self.assertNotIn('help', completions)
        self.assertNotIn('reload', completions)
        self.assertNotIn('shutdown', completions)
        self.assertNotIn('crash', completions)

    def test_peer_list_suggests_list(self):
        """Test that 'peer' suggests 'list' as an option"""
        completions = self.completer._get_completions(['peer'], '')

        # Should contain 'list' for listing all peers
        self.assertIn('list', completions)
        # Should also contain wildcard for operations on all peers
        self.assertIn('*', completions)

    def test_peer_list_partial(self):
        """Test that 'peer l' suggests 'list'"""
        completions = self.completer._get_completions(['peer'], 'l')

        # Should match 'list'
        self.assertIn('list', completions)

    def test_peer_wildcard_shows_actions(self):
        """Test that after 'peer *', announce/withdraw/show/teardown are suggested"""
        completions = self.completer._get_completions(['peer', '*'], '')

        # Should contain v6 API actions
        self.assertIn('announce', completions)
        self.assertIn('withdraw', completions)
        self.assertIn('show', completions)
        self.assertIn('teardown', completions)

    def test_peer_ip_announce_suggests_subcommands(self):
        """Test that 'peer <ip> announce' suggests route, eor, flow, etc."""
        completions = self.completer._get_completions(['peer', '127.0.0.1', 'announce'], '')

        # Should suggest announce subcommands
        self.assertIn('route', completions)
        self.assertIn('eor', completions)
        self.assertIn('flow', completions)

    def test_peer_ip_withdraw_suggests_subcommands(self):
        """Test that 'peer <ip> withdraw' suggests route, flow, etc."""
        completions = self.completer._get_completions(['peer', '127.0.0.1', 'withdraw'], '')

        # Should suggest withdraw subcommands
        self.assertIn('route', completions)
        self.assertIn('flow', completions)

    def test_announce_route_prefix_suggests_attributes(self):
        """Test that 'announce route <prefix>' suggests BGP attributes"""
        # Test the basic case first (without neighbor prefix)
        completions = self.completer._get_completions(['announce', 'route', '1.2.3.4/32'], '')

        # Should suggest BGP attributes
        expected_attributes = ['next-hop', 'as-path', 'community', 'local-preference', 'med']
        for attr in expected_attributes:
            self.assertIn(attr, completions, f"Expected attribute '{attr}' not in completions: {completions}")

    def test_peer_announce_route_prefix_suggests_attributes(self):
        """Test that 'peer <ip> announce route <prefix>' suggests BGP attributes"""
        # Get completions after "peer 127.0.0.1 announce route 1.2.3.4/32"
        completions = self.completer._get_completions(['peer', '127.0.0.1', 'announce', 'route', '1.2.3.4/32'], '')

        # Should suggest BGP attributes
        expected_attributes = ['next-hop', 'as-path', 'community', 'local-preference', 'med']
        for attr in expected_attributes:
            self.assertIn(attr, completions, f"Expected attribute '{attr}' not in completions: {completions}")


class TestOutputFormatter(unittest.TestCase):
    """Test cases for CLI output formatting"""

    def setUp(self):
        """Set up test fixtures"""
        self.formatter = OutputFormatter()

    def test_pretty_print_json_object(self):
        """Test that JSON objects are pretty-printed"""
        # Compact JSON input
        input_json = '{"name":"test","value":123,"nested":{"key":"value"}}'
        output = self.formatter.format_command_output(input_json)

        # Should be formatted with indentation
        self.assertIn('\n', output)  # Has newlines (pretty-printed)
        # Should be valid JSON
        # Remove color codes if present
        clean_output = output.replace('\x1b[36m', '').replace('\x1b[0m', '')
        parsed = json.loads(clean_output)
        self.assertEqual(parsed['name'], 'test')
        self.assertEqual(parsed['value'], 123)
        self.assertEqual(parsed['nested']['key'], 'value')

    def test_pretty_print_json_array(self):
        """Test that JSON arrays are pretty-printed"""
        # Compact JSON array
        input_json = '[{"id":1},{"id":2},{"id":3}]'
        output = self.formatter.format_command_output(input_json)

        # Should be formatted with indentation
        self.assertIn('\n', output)
        # Should be valid JSON
        clean_output = output.replace('\x1b[36m', '').replace('\x1b[0m', '')
        parsed = json.loads(clean_output)
        self.assertEqual(len(parsed), 3)
        self.assertEqual(parsed[0]['id'], 1)

    def test_json_with_unicode(self):
        """Test that JSON with Unicode characters is handled correctly"""
        input_json = '{"message":"Hello 世界 🌍"}'
        output = self.formatter.format_command_output(input_json)

        # Should preserve Unicode (ensure_ascii=False)
        clean_output = output.replace('\x1b[36m', '').replace('\x1b[0m', '')
        self.assertIn('世界', clean_output)
        self.assertIn('🌍', clean_output)

    def test_invalid_json_passthrough(self):
        """Test that invalid JSON is passed through without error"""
        input_text = '{invalid json}'
        output = self.formatter.format_command_output(input_text)

        # Should return something (not crash)
        self.assertIsNotNone(output)
        self.assertIn('invalid', output)

    def test_non_json_text_passthrough(self):
        """Test that non-JSON text is passed through unchanged"""
        input_text = 'This is plain text'
        output = self.formatter.format_command_output(input_text)

        # Should be unchanged (minus any color codes)
        clean_output = output.replace('\x1b[36m', '').replace('\x1b[0m', '')
        self.assertIn('plain text', clean_output)

    def test_empty_output(self):
        """Test that empty output is handled correctly"""
        output = self.formatter.format_command_output('')
        self.assertEqual(output, '')

    def test_json_indent_level(self):
        """Test that JSON is indented with 2 spaces"""
        input_json = '{"outer":{"inner":"value"}}'
        output = self.formatter.format_command_output(input_json)

        # Remove color codes
        clean_output = output.replace('\x1b[36m', '').replace('\x1b[0m', '')

        # Should have 2-space indentation
        lines = clean_output.split('\n')
        # Find a line with "inner" - should be indented 4 spaces (2 levels * 2 spaces)
        inner_line = [line for line in lines if '"inner"' in line][0]
        # Count leading spaces
        leading_spaces = len(inner_line) - len(inner_line.lstrip())
        self.assertEqual(leading_spaces, 4)  # 2 levels of 2-space indent

    def test_json_with_done_marker(self):
        """Test that JSON with 'done' marker is correctly parsed"""
        # ExaBGP API responses often end with "done"
        input_json = '[{"id":1,"name":"test"}]\ndone'
        output = self.formatter.format_command_output(input_json)

        # Should be formatted as JSON (done marker stripped)
        self.assertIn('\n', output)  # Has newlines (pretty-printed)
        # Should NOT contain 'done' in output
        self.assertNotIn('done', output.lower())
        # Should be valid JSON
        clean_output = output.replace('\x1b[36m', '').replace('\x1b[0m', '')
        parsed = json.loads(clean_output)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]['id'], 1)


class TestV6APICommands(unittest.TestCase):
    """Test cases for v6 API commands - CLI sends commands directly without transformation"""

    def setUp(self):
        """Set up test fixtures"""
        self.sent_commands = []

        def mock_send_command(cmd: str) -> str:
            self.sent_commands.append(cmd)
            return 'done'

        self.cli = InteractiveCLI(send_command=mock_send_command)

    def test_peer_show_sends_directly(self):
        """Test that 'peer show' is sent directly to daemon"""
        # Execute "peer show"
        self.cli._execute_command('peer show')

        # Should send v6 format directly
        self.assertEqual(len(self.sent_commands), 1)
        sent = self.sent_commands[0]
        self.assertIn('peer show', sent)

    def test_peer_show_with_options(self):
        """Test that 'peer show summary' is sent directly"""
        # Execute "peer show summary"
        self.cli._execute_command('peer show summary')

        # Should send v6 format directly
        self.assertEqual(len(self.sent_commands), 1)
        sent = self.sent_commands[0]
        self.assertIn('peer show summary', sent)

    def test_peer_announce_sends_directly(self):
        """Test that 'peer <ip> announce' is sent directly"""
        # Execute "peer 127.0.0.1 announce route 1.2.3.0/24"
        self.cli._execute_command('peer 127.0.0.1 announce route 1.2.3.0/24')

        # Should send v6 format directly
        self.assertEqual(len(self.sent_commands), 1)
        sent = self.sent_commands[0]
        self.assertIn('peer 127.0.0.1 announce route 1.2.3.0/24', sent)

    def test_peer_withdraw_sends_directly(self):
        """Test that 'peer <ip> withdraw' is sent directly"""
        # Execute "peer 127.0.0.1 withdraw route 1.2.3.0/24"
        self.cli._execute_command('peer 127.0.0.1 withdraw route 1.2.3.0/24')

        # Should send v6 format directly
        self.assertEqual(len(self.sent_commands), 1)
        sent = self.sent_commands[0]
        self.assertIn('peer 127.0.0.1 withdraw route 1.2.3.0/24', sent)

    def test_peer_wildcard_announce(self):
        """Test that 'peer * announce' is sent directly"""
        # Execute "peer * announce route 1.2.3.0/24 next-hop 10.0.0.1"
        self.cli._execute_command('peer * announce route 1.2.3.0/24 next-hop 10.0.0.1')

        # Should send v6 format directly
        self.assertEqual(len(self.sent_commands), 1)
        sent = self.sent_commands[0]
        self.assertIn('peer * announce route 1.2.3.0/24 next-hop 10.0.0.1', sent)

    def test_daemon_shutdown_sends_directly(self):
        """Test that 'daemon shutdown' is sent directly"""
        self.cli._execute_command('daemon shutdown')

        self.assertEqual(len(self.sent_commands), 1)
        sent = self.sent_commands[0]
        self.assertIn('daemon shutdown', sent)


if __name__ == '__main__':
    unittest.main()
