"""
Unit tests for CLI display format prefix feature

Tests the new 'json'/'text' prefix functionality for controlling output display format.

Created on 2025-11-21.
"""

from __future__ import annotations

import contextlib
import io
import os
import unittest
from unittest.mock import Mock, patch

from exabgp.application.cli import InteractiveCLI
from exabgp.cli.formatter import OutputFormatter


REPLY = '{"test": "data"}'


def rendered(display_mode: str) -> str:
    """How the CLI's formatter shows REPLY in display_mode."""
    return OutputFormatter().format_command_output(REPLY, display_mode=display_mode)


class TestDisplayFormatPrefix(unittest.TestCase):
    """Test display format prefix parsing and validation

    The display mode is read from what the CLI prints: the formatter is a compiled object
    whose methods cannot be replaced, and each mode renders the reply differently.
    """

    def setUp(self):
        """Create test CLI instance"""
        # Keep the operator's command history out of the test.
        environment = patch.dict(os.environ, {'exabgp_cli_history': 'false'})
        environment.start()
        self.addCleanup(environment.stop)
        self.mock_send = Mock(return_value=REPLY)
        self.cli = InteractiveCLI(send_command=self.mock_send)
        self.assertNotEqual(rendered('json'), rendered('text'))

    def execute(self, command: str) -> str:
        """Run command through the CLI and return what it printed."""
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.cli._execute_command(command)
        return output.getvalue()

    def assertDisplayedAs(self, output: str, display_mode: str) -> None:
        other = 'text' if display_mode == 'json' else 'json'
        self.assertIn(rendered(display_mode), output)
        self.assertNotIn(rendered(other), output)

    def sent(self) -> str:
        self.mock_send.assert_called_once()
        return self.mock_send.call_args[0][0]

    def test_read_command_detection(self):
        """Test _is_read_command() correctly identifies read vs write commands"""
        # Read commands
        self.assertTrue(self.cli._is_read_command('show neighbor'))
        self.assertTrue(self.cli._is_read_command('show neighbor summary'))
        self.assertTrue(self.cli._is_read_command('list neighbors'))
        self.assertTrue(self.cli._is_read_command('help'))
        self.assertTrue(self.cli._is_read_command('version'))
        self.assertTrue(self.cli._is_read_command('history'))
        self.assertTrue(self.cli._is_read_command('set encoding json'))

        # Write commands
        self.assertFalse(self.cli._is_read_command('announce route 1.2.3.4/24'))
        self.assertFalse(self.cli._is_read_command('withdraw route 1.2.3.4/24'))
        self.assertFalse(self.cli._is_read_command('flush adj-rib out'))
        self.assertFalse(self.cli._is_read_command('clear adj-rib'))
        self.assertFalse(self.cli._is_read_command('shutdown'))
        self.assertFalse(self.cli._is_read_command('reload'))
        self.assertFalse(self.cli._is_read_command('restart'))

    def test_display_prefix_parsing_json(self):
        """Test 'json' prefix is parsed correctly"""
        output = self.execute('json peer show')
        # v6 API is JSON-only, so no encoding suffix is needed
        self.assertEqual(self.sent(), 'peer show')
        self.assertDisplayedAs(output, 'json')

    def test_display_prefix_parsing_text(self):
        """Test 'text' prefix is parsed correctly"""
        self.cli.display_mode = 'json'
        output = self.execute('text peer show')
        # v6 API is JSON-only, the prefix only controls CLI display
        self.assertEqual(self.sent(), 'peer show')
        self.assertDisplayedAs(output, 'text')

    def test_no_prefix_uses_default(self):
        """Test command without prefix uses session default display mode"""
        for display_mode in ('text', 'json'):
            self.mock_send.reset_mock()
            self.cli.display_mode = display_mode
            output = self.execute('peer show')
            self.assertEqual(self.sent(), 'peer show')
            self.assertDisplayedAs(output, display_mode)

    def test_valid_combination_json_json(self):
        """Test valid combination: json prefix + json suffix"""
        output = self.execute('json peer show json')
        self.assertEqual(self.sent(), 'peer show json')
        self.assertDisplayedAs(output, 'json')

    def test_valid_combination_text_text(self):
        """Test valid combination: text prefix + text suffix"""
        self.cli.display_mode = 'json'
        output = self.execute('text peer show text')
        self.assertEqual(self.sent(), 'peer show text')
        self.assertDisplayedAs(output, 'text')

    def test_prefix_with_suffix_passes_suffix_through(self):
        """Test that suffix is passed through when prefix is used (v6 API)

        In v6 API, there's no conflict detection - the CLI prefix controls display
        while any suffix in the command is passed to the API as-is.
        """
        self.cli.display_mode = 'json'
        output = self.execute('text peer show json')
        self.assertEqual(self.sent(), 'peer show json')
        self.assertDisplayedAs(output, 'text')

    def test_json_prefix_with_different_suffix(self):
        """Test json prefix with text suffix (v6 API passes through)"""
        output = self.execute('json show neighbor text')
        self.assertEqual(self.sent(), 'show neighbor text')
        self.assertDisplayedAs(output, 'json')

    def test_write_command_ignores_display_prefix(self):
        """Test write commands ignore display prefix"""
        self.mock_send.return_value = 'done'

        output = self.execute('json announce route 1.2.3.4/24')

        # Command should be sent (prefix ignored for write commands)
        sent_cmd = self.sent()
        self.assertIn('announce route', sent_cmd)
        # Display prefix should be stripped from command
        self.assertNotIn('json announce', sent_cmd)
        self.assertIn('Command accepted', output)

    def test_json_prefix_with_text_suffix_sends_command(self):
        """Test json display prefix with text suffix (v6 API)

        In v6 API, the display prefix controls CLI rendering while the suffix
        is passed through to the API. No conflict detection needed since
        v6 API is JSON-only - the 'text' suffix is just a parameter.
        """
        output = self.execute('json peer show text')
        self.assertEqual(self.sent(), 'peer show text')
        self.assertDisplayedAs(output, 'json')

    def test_suffix_only_still_works(self):
        """Test backward compatibility: suffix-only format still works"""
        output = self.execute('peer show json')
        sent_cmd = self.sent()
        self.assertIn('peer show', sent_cmd)
        self.assertIn('json', sent_cmd)
        # Display mode should use session default (text)
        self.assertDisplayedAs(output, 'text')

    def test_prefix_only_works(self):
        """Test prefix-only format (no suffix) works correctly"""
        output = self.execute('json peer show')
        self.assertIn('peer show', self.sent())
        self.assertDisplayedAs(output, 'json')


class TestCompletionWithPrefix(unittest.TestCase):
    """Test auto-completion for display format prefix"""

    def setUp(self):
        """Create test completer"""
        self.mock_send = Mock(return_value='{"test": "data"}')
        self.cli = InteractiveCLI(send_command=self.mock_send)
        self.completer = self.cli.completer

    def test_completion_at_start_includes_json_text(self):
        """Test completion at start of line suggests json and text"""
        # No tokens yet - should suggest json, text, and base commands
        matches = self.completer._get_completions([], 'j')

        # Should include 'json'
        self.assertIn('json', matches)

    def test_completion_at_start_text_prefix(self):
        """Test completion 't' at start suggests text"""
        matches = self.completer._get_completions([], 't')

        # Should include 'text'
        self.assertIn('text', matches)

    def test_completion_after_json_prefix(self):
        """Test completion after 'json ' suggests v6 commands"""
        matches = self.completer._get_completions(['json'], 's')

        # Should suggest v6 commands starting with 's' (session, system, set)
        self.assertIn('session', matches)
        self.assertIn('system', matches)
        # v4 commands not in base
        self.assertNotIn('shutdown', matches)
        # Should NOT suggest 'json' again
        self.assertNotIn('json', matches)

    def test_completion_after_text_prefix(self):
        """Test completion after 'text ' suggests v6 commands"""
        matches = self.completer._get_completions(['text'], 'd')

        # Should suggest v6 commands starting with 'd'
        self.assertIn('daemon', matches)
        # Should NOT suggest 'text' again
        self.assertNotIn('text', matches)

    def test_completion_json_peer_show(self):
        """Test completion works normally after display prefix (v6 API)"""
        # After "json peer ", should suggest wildcard and peer IPs
        matches = self.completer._get_completions(['json', 'peer'], '')

        # Should suggest wildcard
        self.assertIn('*', matches)


if __name__ == '__main__':
    unittest.main()
