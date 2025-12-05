"""
Unit tests for CLI display format prefix feature

Tests the new 'json'/'text' prefix functionality for controlling output display format.

Created on 2025-11-21.
"""

from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from exabgp.application.cli import InteractiveCLI


class TestDisplayFormatPrefix(unittest.TestCase):
    """Test display format prefix parsing and validation"""

    def setUp(self):
        """Create test CLI instance"""
        self.mock_send = Mock(return_value='{"test": "data"}')
        self.cli = InteractiveCLI(send_command=self.mock_send)

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
        with patch.object(self.cli.formatter, 'format_success'):
            with patch.object(self.cli.formatter, 'format_command_output') as mock_format:
                mock_format.return_value = 'formatted output'

                # Execute command with json prefix (v6 API format)
                self.cli._execute_command('json peer show')

                # Verify command sent to API
                # Note: v6 API is JSON-only, so no encoding suffix is needed
                self.mock_send.assert_called_once()
                sent_cmd = self.mock_send.call_args[0][0]
                self.assertEqual(sent_cmd, 'peer show')  # No suffix, v6 API is JSON-only

                # Verify format_command_output called with display_mode='json'
                mock_format.assert_called_once()
                self.assertEqual(mock_format.call_args[1]['display_mode'], 'json')

    def test_display_prefix_parsing_text(self):
        """Test 'text' prefix is parsed correctly"""
        with patch.object(self.cli.formatter, 'format_success'):
            with patch.object(self.cli.formatter, 'format_command_output') as mock_format:
                mock_format.return_value = 'formatted output'

                # Execute command with text prefix (v6 API format)
                self.cli._execute_command('text peer show')

                # Verify command sent to API
                # Note: v6 API is JSON-only, prefix only controls CLI display
                self.mock_send.assert_called_once()
                sent_cmd = self.mock_send.call_args[0][0]
                self.assertEqual(sent_cmd, 'peer show')  # No suffix, v6 API is JSON-only

                # Verify format_command_output called with display_mode='text'
                mock_format.assert_called_once()
                self.assertEqual(mock_format.call_args[1]['display_mode'], 'text')

    def test_no_prefix_uses_default(self):
        """Test command without prefix uses session default display mode"""
        with patch.object(self.cli.formatter, 'format_success'):
            with patch.object(self.cli.formatter, 'format_command_output') as mock_format:
                mock_format.return_value = 'formatted output'

                # Set session default to text
                self.cli.display_mode = 'text'

                # Execute command without prefix (v6 API format)
                self.cli._execute_command('peer show')

                # Verify format_command_output called with display_mode='text' (session default)
                mock_format.assert_called_once()
                self.assertEqual(mock_format.call_args[1]['display_mode'], 'text')

    def test_valid_combination_json_json(self):
        """Test valid combination: json prefix + json suffix"""
        with patch.object(self.cli.formatter, 'format_success'):
            with patch.object(self.cli.formatter, 'format_command_output') as mock_format:
                mock_format.return_value = 'formatted output'

                # Execute: json peer show json (v6 API format)
                self.cli._execute_command('json peer show json')

                # Should succeed - both json
                self.mock_send.assert_called_once()
                mock_format.assert_called_once()
                self.assertEqual(mock_format.call_args[1]['display_mode'], 'json')

    def test_valid_combination_text_text(self):
        """Test valid combination: text prefix + text suffix"""
        with patch.object(self.cli.formatter, 'format_success'):
            with patch.object(self.cli.formatter, 'format_command_output') as mock_format:
                mock_format.return_value = 'formatted output'

                # Execute: text peer show text (v6 API format)
                self.cli._execute_command('text peer show text')

                # Should succeed - both text
                self.mock_send.assert_called_once()
                mock_format.assert_called_once()
                self.assertEqual(mock_format.call_args[1]['display_mode'], 'text')

    def test_prefix_with_suffix_passes_suffix_through(self):
        """Test that suffix is passed through when prefix is used (v6 API)

        In v6 API, there's no conflict detection - the CLI prefix controls display
        while any suffix in the command is passed to the API as-is.
        """
        with patch.object(self.cli.formatter, 'format_success'):
            with patch.object(self.cli.formatter, 'format_command_output') as mock_format:
                mock_format.return_value = 'formatted output'

                # Execute: text peer show json - suffix is passed through to API
                self.cli._execute_command('text peer show json')

                # Command should be sent with suffix intact
                self.mock_send.assert_called_once()
                sent_cmd = self.mock_send.call_args[0][0]
                self.assertEqual(sent_cmd, 'peer show json')

                # Display mode from prefix
                mock_format.assert_called_once()
                self.assertEqual(mock_format.call_args[1]['display_mode'], 'text')

    def test_json_prefix_with_different_suffix(self):
        """Test json prefix with text suffix (v6 API passes through)"""
        with patch.object(self.cli.formatter, 'format_success'):
            with patch.object(self.cli.formatter, 'format_command_output') as mock_format:
                mock_format.return_value = 'formatted output'

                # Execute: json show neighbor text - suffix passed through
                self.cli._execute_command('json show neighbor text')

                # Command should be sent
                self.mock_send.assert_called_once()
                sent_cmd = self.mock_send.call_args[0][0]
                self.assertEqual(sent_cmd, 'show neighbor text')

                # Display mode from prefix
                mock_format.assert_called_once()
                self.assertEqual(mock_format.call_args[1]['display_mode'], 'json')

    def test_write_command_ignores_display_prefix(self):
        """Test write commands ignore display prefix"""
        self.mock_send.return_value = 'done'

        with patch.object(self.cli.formatter, 'format_success'):
            # Execute: json announce route 1.2.3.4/24
            self.cli._execute_command('json announce route 1.2.3.4/24')

            # Command should be sent (prefix ignored for write commands)
            self.mock_send.assert_called_once()
            sent_cmd = self.mock_send.call_args[0][0]
            self.assertIn('announce route', sent_cmd)
            # Display prefix should be stripped from command
            self.assertNotIn('json announce', sent_cmd)

    def test_json_prefix_with_text_suffix_sends_command(self):
        """Test json display prefix with text suffix (v6 API)

        In v6 API, the display prefix controls CLI rendering while the suffix
        is passed through to the API. No conflict detection needed since
        v6 API is JSON-only - the 'text' suffix is just a parameter.
        """
        with patch.object(self.cli.formatter, 'format_success'):
            with patch.object(self.cli.formatter, 'format_command_output') as mock_format:
                mock_format.return_value = 'formatted output'

                # Execute: json peer show text - suffix passed to API
                self.cli._execute_command('json peer show text')

                # Command should be sent
                self.mock_send.assert_called_once()
                sent_cmd = self.mock_send.call_args[0][0]
                self.assertEqual(sent_cmd, 'peer show text')

                # Display mode from prefix
                mock_format.assert_called_once()
                self.assertEqual(mock_format.call_args[1]['display_mode'], 'json')

    def test_suffix_only_still_works(self):
        """Test backward compatibility: suffix-only format still works"""
        with patch.object(self.cli.formatter, 'format_success'):
            with patch.object(self.cli.formatter, 'format_command_output') as mock_format:
                mock_format.return_value = 'formatted output'

                # Execute: peer show json (no prefix, suffix only, v6 API format)
                self.cli._execute_command('peer show json')

                # Should work normally
                self.mock_send.assert_called_once()
                sent_cmd = self.mock_send.call_args[0][0]
                self.assertIn('peer show', sent_cmd)
                self.assertIn('json', sent_cmd)

                # Display mode should use session default (text)
                mock_format.assert_called_once()
                self.assertEqual(mock_format.call_args[1]['display_mode'], 'text')

    def test_prefix_only_works(self):
        """Test prefix-only format (no suffix) works correctly"""
        with patch.object(self.cli.formatter, 'format_success'):
            with patch.object(self.cli.formatter, 'format_command_output') as mock_format:
                mock_format.return_value = 'formatted output'

                # Execute: json peer show (prefix only, no suffix, v6 API format)
                self.cli._execute_command('json peer show')

                # Should work - API uses default encoding (json)
                self.mock_send.assert_called_once()
                sent_cmd = self.mock_send.call_args[0][0]
                self.assertIn('peer show', sent_cmd)

                # Display mode should be json (from prefix)
                mock_format.assert_called_once()
                self.assertEqual(mock_format.call_args[1]['display_mode'], 'json')


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
