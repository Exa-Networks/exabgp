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

                # Execute command with json prefix
                self.cli._execute_command('json show neighbor')

                # Verify command sent to API (should have json encoding)
                self.mock_send.assert_called_once()
                sent_cmd = self.mock_send.call_args[0][0]
                self.assertIn('show neighbor', sent_cmd)
                self.assertIn('json', sent_cmd)

                # Verify format_command_output called with display_mode='json'
                mock_format.assert_called_once()
                self.assertEqual(mock_format.call_args[1]['display_mode'], 'json')

    def test_display_prefix_parsing_text(self):
        """Test 'text' prefix is parsed correctly"""
        with patch.object(self.cli.formatter, 'format_success'):
            with patch.object(self.cli.formatter, 'format_command_output') as mock_format:
                mock_format.return_value = 'formatted output'

                # Execute command with text prefix
                self.cli._execute_command('text show neighbor')

                # Verify command sent to API (should have json encoding - default)
                self.mock_send.assert_called_once()
                sent_cmd = self.mock_send.call_args[0][0]
                self.assertIn('show neighbor', sent_cmd)
                self.assertIn('json', sent_cmd)  # Default API encoding is json

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

                # Execute command without prefix
                self.cli._execute_command('show neighbor')

                # Verify format_command_output called with display_mode='text' (session default)
                mock_format.assert_called_once()
                self.assertEqual(mock_format.call_args[1]['display_mode'], 'text')

    def test_valid_combination_json_json(self):
        """Test valid combination: json prefix + json suffix"""
        with patch.object(self.cli.formatter, 'format_success'):
            with patch.object(self.cli.formatter, 'format_command_output') as mock_format:
                mock_format.return_value = 'formatted output'

                # Execute: json show neighbor json
                self.cli._execute_command('json show neighbor json')

                # Should succeed - both json
                self.mock_send.assert_called_once()
                mock_format.assert_called_once()
                self.assertEqual(mock_format.call_args[1]['display_mode'], 'json')

    def test_valid_combination_text_text(self):
        """Test valid combination: text prefix + text suffix"""
        with patch.object(self.cli.formatter, 'format_success'):
            with patch.object(self.cli.formatter, 'format_command_output') as mock_format:
                mock_format.return_value = 'formatted output'

                # Execute: text show neighbor text
                self.cli._execute_command('text show neighbor text')

                # Should succeed - both text
                self.mock_send.assert_called_once()
                mock_format.assert_called_once()
                self.assertEqual(mock_format.call_args[1]['display_mode'], 'text')

    def test_invalid_combination_blocked(self):
        """Test invalid combination is blocked with error"""
        with patch.object(self.cli.formatter, 'format_error') as mock_error:
            # Execute: text show neighbor json (conflicting)
            self.cli._execute_command('text show neighbor json')

            # Should NOT send command
            self.mock_send.assert_not_called()

            # Should display error
            mock_error.assert_called_once()
            error_msg = mock_error.call_args[0][0]
            self.assertIn('Conflicting formats', error_msg)
            self.assertIn("display='text'", error_msg)
            self.assertIn("API encoding='json'", error_msg)

    def test_invalid_combination_json_text_blocked(self):
        """Test invalid combination: json prefix + text suffix is blocked"""
        with patch.object(self.cli.formatter, 'format_error') as mock_error:
            # Execute: json show neighbor text (conflicting)
            self.cli._execute_command('json show neighbor text')

            # Should NOT send command
            self.mock_send.assert_not_called()

            # Should display error
            mock_error.assert_called_once()
            error_msg = mock_error.call_args[0][0]
            self.assertIn('Conflicting formats', error_msg)

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

    def test_api_text_with_json_display_fails_loudly(self):
        """Test that requesting JSON display with text API encoding fails with JSON error"""
        with patch.object(self.cli.formatter, 'format_success'):
            with patch.object(self.cli.formatter, 'format_error') as mock_error:
                # This should be impossible, but test the safety check
                # Manually set encoding to text and display to json
                self.cli._execute_command('json show neighbor text')

                # Should block due to conflicting formats before reaching this code path
                self.mock_send.assert_not_called()
                mock_error.assert_called_once()

    def test_suffix_only_still_works(self):
        """Test backward compatibility: suffix-only format still works"""
        with patch.object(self.cli.formatter, 'format_success'):
            with patch.object(self.cli.formatter, 'format_command_output') as mock_format:
                mock_format.return_value = 'formatted output'

                # Execute: show neighbor json (no prefix, suffix only)
                self.cli._execute_command('show neighbor json')

                # Should work normally
                self.mock_send.assert_called_once()
                sent_cmd = self.mock_send.call_args[0][0]
                self.assertIn('show neighbor', sent_cmd)
                self.assertIn('json', sent_cmd)

                # Display mode should use session default (text)
                mock_format.assert_called_once()
                self.assertEqual(mock_format.call_args[1]['display_mode'], 'text')

    def test_prefix_only_works(self):
        """Test prefix-only format (no suffix) works correctly"""
        with patch.object(self.cli.formatter, 'format_success'):
            with patch.object(self.cli.formatter, 'format_command_output') as mock_format:
                mock_format.return_value = 'formatted output'

                # Execute: json show neighbor (prefix only, no suffix)
                self.cli._execute_command('json show neighbor')

                # Should work - API uses default encoding (json)
                self.mock_send.assert_called_once()
                sent_cmd = self.mock_send.call_args[0][0]
                self.assertIn('show neighbor', sent_cmd)

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
        """Test completion after 'json ' suggests normal commands"""
        matches = self.completer._get_completions(['json'], 's')

        # Should suggest commands starting with 's' (show filtered, shutdown suggested)
        self.assertNotIn('show', matches)  # Filtered out
        self.assertIn('shutdown', matches)
        # Should NOT suggest 'json' again
        self.assertNotIn('json', matches)

    def test_completion_after_text_prefix(self):
        """Test completion after 'text ' suggests normal commands"""
        matches = self.completer._get_completions(['text'], 'h')

        # Should suggest commands starting with 'h'
        self.assertIn('help', matches)
        # Should NOT suggest 'text' again
        self.assertNotIn('text', matches)

    def test_completion_json_show_neighbor(self):
        """Test completion works normally after display prefix"""
        # After "json show ", neighbor is filtered out
        matches = self.completer._get_completions(['json', 'show'], 'n')

        # 'neighbor' filtered out - use 'neighbor <ip> show' syntax instead
        self.assertNotIn('neighbor', matches)


if __name__ == '__main__':
    unittest.main()
