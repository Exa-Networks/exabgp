#!/usr/bin/env python3
"""
Test CLI tab completion and auto-expansion functionality
"""

import json
import unittest
from exabgp.application.cli import CommandCompleter, OutputFormatter


class TestCLICompletion(unittest.TestCase):
    """Test cases for CLI command completion"""

    def setUp(self):
        """Set up test fixtures"""
        self.completer = CommandCompleter(send_command=lambda cmd: '')

    def test_auto_expand_unambiguous_token(self):
        """Test that unambiguous tokens get auto-expanded"""
        # "n" after "show" should expand to "neighbor"
        tokens = ['show', 'n']
        expanded, changed = self.completer._try_auto_expand_tokens(tokens)

        self.assertEqual(expanded, ['show', 'neighbor'])
        self.assertTrue(changed)

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
        # Both tokens might be unambiguous in context
        tokens = ['show', 'n']
        expanded, changed = self.completer._try_auto_expand_tokens(tokens)

        # At minimum, 'n' after 'show' should expand to 'neighbor'
        self.assertEqual(len(expanded), 2)
        self.assertEqual(expanded[0], 'show')
        self.assertEqual(expanded[1], 'neighbor')
        self.assertTrue(changed)

    def test_get_completions_base_commands(self):
        """Test getting completions for base commands"""
        # Empty context, partial match 'sho'
        completions = self.completer._get_completions([], 'sho')

        # Should contain 'show'
        self.assertIn('show', completions)
        # Should not contain unrelated commands
        self.assertNotIn('neighbor', completions)

    def test_get_completions_with_context(self):
        """Test getting completions with command context"""
        # After 'show', get completions for 'n'
        completions = self.completer._get_completions(['show'], 'n')

        # Should contain 'neighbor'
        self.assertIn('neighbor', completions)

    def test_get_completions_exact_match(self):
        """Test completions when token is exact match"""
        # 'show' is exact match
        completions = self.completer._get_completions([], 'show')

        # Should return 'show' as it's a valid command
        self.assertIn('show', completions)

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
        completions = self.completer._get_completions([], 'sho')

        # Should get completions matching 'sho'
        self.assertIn('show', completions)

        # Verify metadata was added (used for showing descriptions)
        # This metadata is displayed when multiple matches exist
        self.assertIn('show', self.completer.match_metadata)
        self.assertIsNotNone(self.completer.match_metadata['show'].description)


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


if __name__ == '__main__':
    unittest.main()
