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
        """Test getting completions for base commands"""
        # Empty context, partial match 'sh'
        completions = self.completer._get_completions([], 'sh')

        # 'show' filtered out, should suggest 'shutdown'
        self.assertNotIn('show', completions)
        self.assertIn('shutdown', completions)
        # Should not contain unrelated commands
        self.assertNotIn('neighbor', completions)

    def test_get_completions_with_context(self):
        """Test getting completions with command context"""
        # After 'show', get completions for 'n'
        completions = self.completer._get_completions(['show'], 'n')

        # 'neighbor' filtered out - use 'neighbor <ip> show' syntax instead
        self.assertNotIn('neighbor', completions)

    def test_get_completions_exact_match(self):
        """Test completions when token is exact match"""
        # 'announce' is exact match
        completions = self.completer._get_completions([], 'announce')

        # Should return 'announce' as it's a valid command
        self.assertIn('announce', completions)

    def test_expand_preserves_exact_matches(self):
        """Test that exact matches are preserved during expansion"""
        # 'show neighbor' are both exact matches
        tokens = ['show', 'neighbor']
        expanded, changed = self.completer._try_auto_expand_tokens(tokens)

        self.assertEqual(expanded, ['show', 'neighbor'])
        self.assertFalse(changed)  # No changes since both are exact matches

    def test_completion_metadata(self):
        """Test that completions include metadata for displaying descriptions"""
        # Get completions for base commands
        completions = self.completer._get_completions([], 'ann')

        # Should get completions matching 'ann'
        self.assertIn('announce', completions)

        # Verify metadata was added (used for showing descriptions)
        # This metadata is displayed when multiple matches exist
        self.assertIn('announce', self.completer.match_metadata)
        self.assertIsNotNone(self.completer.match_metadata['announce'].description)

    def test_neighbor_ip_only_shows_announce_withdraw_show(self):
        """Test that after 'neighbor <ip>', only announce/withdraw/show/adj-rib are suggested"""
        # After neighbor IP, should only get announce, withdraw, show, adj-rib
        completions = self.completer._get_completions(['neighbor', '127.0.0.1'], '')

        # Should contain these four
        self.assertIn('announce', completions)
        self.assertIn('withdraw', completions)
        self.assertIn('show', completions)
        self.assertIn('adj-rib', completions)

        # Should NOT contain other commands (ping, help, reload, etc.)
        self.assertNotIn('ping', completions)
        self.assertNotIn('help', completions)
        self.assertNotIn('reload', completions)
        self.assertNotIn('shutdown', completions)
        self.assertNotIn('crash', completions)

        # Should be exactly 4 items
        self.assertEqual(len(completions), 4)

    def test_neighbor_ip_announce_completes_as_root_announce(self):
        """Test that 'neighbor <ip> announce' completes same as root 'announce'"""
        # Get completions after "neighbor 127.0.0.1 announce"
        neighbor_completions = self.completer._get_completions(['neighbor', '127.0.0.1', 'announce'], '')

        # Get completions after just "announce" (root level)
        root_completions = self.completer._get_completions(['announce'], '')

        # Should be identical
        self.assertEqual(sorted(neighbor_completions), sorted(root_completions))

    def test_neighbor_ip_show_completes_as_show_neighbor_ip(self):
        """Test that 'neighbor <ip> show' completes as 'show neighbor <ip>'"""
        # Get completions after "neighbor 127.0.0.1 show"
        neighbor_completions = self.completer._get_completions(['neighbor', '127.0.0.1', 'show'], '')

        # Get completions after "show neighbor 127.0.0.1" (transformed level)
        show_neighbor_completions = self.completer._get_completions(['show', 'neighbor', '127.0.0.1'], '')

        # Should be identical to "show neighbor <ip>" level
        self.assertEqual(sorted(neighbor_completions), sorted(show_neighbor_completions))

        # Should NOT be same as root "show" level
        root_show_completions = self.completer._get_completions(['show'], '')
        self.assertNotEqual(sorted(neighbor_completions), sorted(root_show_completions))

    def test_neighbor_ip_withdraw_completes_as_root_withdraw(self):
        """Test that 'neighbor <ip> withdraw' completes same as root 'withdraw'"""
        # Get completions after "neighbor 127.0.0.1 withdraw"
        neighbor_completions = self.completer._get_completions(['neighbor', '127.0.0.1', 'withdraw'], '')

        # Get completions after just "withdraw" (root level)
        root_completions = self.completer._get_completions(['withdraw'], '')

        # Should be identical
        self.assertEqual(sorted(neighbor_completions), sorted(root_completions))

    def test_show_neighbor_ip_does_not_suggest_ip_again(self):
        """Test that 'show neighbor <ip>' does not suggest the IP again"""
        # Get completions after "show neighbor 127.0.0.1"
        completions = self.completer._get_completions(['show', 'neighbor', '127.0.0.1'], '')

        # Should suggest options (summary, extensive, configuration, json)
        # But should NOT suggest IP addresses again
        for completion in completions:
            # None of the completions should be IP addresses
            self.assertFalse(
                self.completer._is_ip_address(completion), f"Completion '{completion}' should not be an IP address"
            )

    def test_announce_route_prefix_suggests_attributes(self):
        """Test that 'announce route <prefix>' suggests BGP attributes"""
        # Test the basic case first (without neighbor prefix)
        completions = self.completer._get_completions(['announce', 'route', '1.2.3.4/32'], '')

        # Should suggest BGP attributes
        expected_attributes = ['next-hop', 'as-path', 'community', 'local-preference', 'med']
        for attr in expected_attributes:
            self.assertIn(attr, completions, f"Expected attribute '{attr}' not in completions: {completions}")

    def test_neighbor_announce_route_prefix_suggests_attributes(self):
        """Test that 'neighbor <ip> announce route <prefix>' suggests BGP attributes"""
        # Get completions after "neighbor 127.0.0.1 announce route 1.2.3.4/32"
        completions = self.completer._get_completions(['neighbor', '127.0.0.1', 'announce', 'route', '1.2.3.4/32'], '')

        # Should suggest BGP attributes (same as without neighbor prefix)
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


class TestNeighborShowTransformation(unittest.TestCase):
    """Test cases for neighbor show command transformation"""

    def setUp(self):
        """Set up test fixtures"""
        self.sent_commands = []

        def mock_send_command(cmd: str) -> str:
            self.sent_commands.append(cmd)
            return 'done'

        self.cli = InteractiveCLI(send_command=mock_send_command)

    def test_neighbor_show_transforms_to_show_neighbor(self):
        """Test that 'neighbor <ip> show' transforms to 'show neighbor <ip>'"""
        # Execute "neighbor 127.0.0.1 show"
        self.cli._execute_command('neighbor 127.0.0.1 show')

        # Should have sent "show neighbor 127.0.0.1 text" (text is default encoding)
        self.assertEqual(len(self.sent_commands), 1)
        sent = self.sent_commands[0]
        self.assertIn('show neighbor 127.0.0.1', sent)

    def test_neighbor_show_with_options(self):
        """Test that 'neighbor <ip> show <options>' preserves options"""
        # Execute "neighbor 127.0.0.1 show summary"
        self.cli._execute_command('neighbor 127.0.0.1 show summary')

        # Should transform to "show neighbor 127.0.0.1 summary"
        self.assertEqual(len(self.sent_commands), 1)
        sent = self.sent_commands[0]
        self.assertIn('show neighbor 127.0.0.1 summary', sent)

    def test_neighbor_announce_not_transformed(self):
        """Test that 'neighbor <ip> announce' is NOT transformed"""
        # Execute "neighbor 127.0.0.1 announce route 1.2.3.0/24"
        self.cli._execute_command('neighbor 127.0.0.1 announce route 1.2.3.0/24')

        # Should send as-is (with encoding appended)
        self.assertEqual(len(self.sent_commands), 1)
        sent = self.sent_commands[0]
        self.assertIn('neighbor 127.0.0.1 announce route 1.2.3.0/24', sent)
        # Should NOT start with "show"
        self.assertFalse(sent.startswith('show'))

    def test_neighbor_withdraw_not_transformed(self):
        """Test that 'neighbor <ip> withdraw' is NOT transformed"""
        # Execute "neighbor 127.0.0.1 withdraw route 1.2.3.0/24"
        self.cli._execute_command('neighbor 127.0.0.1 withdraw route 1.2.3.0/24')

        # Should send as-is (with encoding appended)
        self.assertEqual(len(self.sent_commands), 1)
        sent = self.sent_commands[0]
        self.assertIn('neighbor 127.0.0.1 withdraw route 1.2.3.0/24', sent)
        # Should NOT start with "show"
        self.assertFalse(sent.startswith('show'))


if __name__ == '__main__':
    unittest.main()
