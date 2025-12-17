"""formatter.py

Output formatting and colorization for CLI.

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import json
from typing import Any

from exabgp.cli.colors import Colors


class OutputFormatter:
    """Format and colorize output"""

    def __init__(self, use_color: bool = True):
        self.use_color = use_color and Colors.supports_color()

    def format_prompt(self, hostname: str = 'exabgp') -> str:
        """Format the interactive prompt"""
        if self.use_color:
            return f'{Colors.BOLD}{Colors.GREEN}{hostname}{Colors.RESET}{Colors.BOLD}>{Colors.RESET} '
        return f'{hostname}> '

    def format_error(self, message: str) -> str:
        """Format error message"""
        if self.use_color:
            return f'{Colors.BOLD}{Colors.RED}Error:{Colors.RESET} {message}'
        return f'Error: {message}'

    def format_warning(self, message: str) -> str:
        """Format warning message"""
        if self.use_color:
            return f'{Colors.BOLD}{Colors.YELLOW}Warning:{Colors.RESET} {message}'
        return f'Warning: {message}'

    def format_success(self, message: str) -> str:
        """Format success message"""
        if self.use_color:
            return f'{Colors.BOLD}{Colors.GREEN}✓{Colors.RESET} {message}'
        return f'✓ {message}'

    def format_info(self, message: str) -> str:
        """Format info message"""
        if self.use_color:
            return f'{Colors.BOLD}{Colors.CYAN}Info:{Colors.RESET} {message}'
        return f'Info: {message}'

    def _format_json_as_text(self, data: Any) -> str:
        """Convert JSON data to human-readable text format with tables

        Uses only standard library to format data as tables or key-value pairs.
        """
        if data is None:
            return 'null'

        if isinstance(data, bool):
            return 'true' if data else 'false'

        if isinstance(data, (str, int, float)):
            return str(data)

        # List of objects - format as table
        if isinstance(data, list):
            if not data:
                return '(empty list)'

            # Check if all items are dictionaries (tabular data)
            if all(isinstance(item, dict) for item in data):
                return self._format_table_from_list(data)

            # List of simple values
            if all(isinstance(item, (str, int, float, bool, type(None))) for item in data):
                return '\n'.join(f'  - {item}' for item in data)

            # Mixed list - format each item
            lines = []
            for i, item in enumerate(data):
                lines.append(f'[{i}]:')
                lines.append(self._indent(self._format_json_as_text(item), 2))
            return '\n'.join(lines)

        # Single object - format as key-value pairs
        if isinstance(data, dict):
            return self._format_dict(data)

        return str(data)

    def _format_table_from_list(self, data: list[dict[str, Any]]) -> str:
        """Format list of dictionaries as ASCII table or key-value pairs for complex data"""
        if not data:
            return '(empty)'

        # Check if data has complex nested structures (dicts/lists in values)
        has_complex_values = False
        for item in data:
            for value in item.values():
                if isinstance(value, (dict, list)):
                    # Check if dict/list has substantial content
                    if isinstance(value, dict) and len(value) > 3:
                        has_complex_values = True
                        break
                    if isinstance(value, list) and (len(value) > 3 or any(isinstance(v, dict) for v in value)):
                        has_complex_values = True
                        break
            if has_complex_values:
                break

        # If data is complex, format as sections instead of table
        if has_complex_values:
            return self._format_list_as_sections(data)

        # Collect all keys across all objects
        all_keys: list[str] = []
        for item in data:
            for key in item.keys():
                if key not in all_keys:
                    all_keys.append(key)

        # Calculate column widths (with max width limit to prevent ultra-wide tables)
        MAX_COL_WIDTH = 40
        col_widths: dict[str, int] = {}
        for key in all_keys:
            # Start with header width
            col_widths[key] = len(str(key))
            # Check all values
            for item in data:
                if key in item:
                    value_str = self._format_value(item[key])
                    # Cap at max width to keep table readable
                    col_widths[key] = min(max(col_widths[key], len(value_str)), MAX_COL_WIDTH)

        # Build header
        header_parts = []
        separator_parts = []
        for key in all_keys:
            width = col_widths[key]
            header_parts.append(str(key).ljust(width))
            separator_parts.append('-' * width)

        lines = []
        lines.append('  '.join(header_parts))
        lines.append('  '.join(separator_parts))

        # Build rows
        for item in data:
            row_parts = []
            for key in all_keys:
                width = col_widths[key]
                value = item.get(key, '')
                value_str = self._format_value(value)
                # Truncate if too long
                if len(value_str) > MAX_COL_WIDTH:
                    value_str = value_str[: MAX_COL_WIDTH - 3] + '...'
                row_parts.append(value_str.ljust(width))
            lines.append('  '.join(row_parts))

        return '\n'.join(lines)

    def _format_list_as_sections(self, data: list[dict[str, Any]]) -> str:
        """Format list of complex dictionaries as separate sections"""
        lines = []
        for i, item in enumerate(data):
            if i > 0:
                lines.append('')  # Blank line between sections

            # Extract identifier from the data
            identifier = self._extract_identifier(item)

            if identifier:
                lines.append(f'=== {identifier} ===')
            else:
                lines.append(f'=== Item {i + 1} ===')

            lines.append(self._format_dict(item))

        return '\n'.join(lines)

    def _extract_identifier(self, item: dict[str, Any]) -> str | None:
        """Extract a meaningful identifier from a dictionary

        Tries various strategies to find a good identifier:
        1. Nested keys for specific data types (e.g., neighbor data)
        2. Common top-level keys
        3. First string/number value found
        """
        # Strategy 1: Check for nested paths that commonly identify objects
        nested_paths = [
            ['peer', 'address'],  # Neighbor data
            ['local', 'address'],  # Alternative neighbor identifier
            ['neighbor', 'address'],  # Another neighbor pattern
            ['address', 'peer'],  # Reversed pattern
        ]

        for path in nested_paths:
            value = self._get_nested_value(item, path)
            if value is not None:
                return str(value)

        # Strategy 2: Check common top-level identifier keys
        top_level_keys = ['peer-address', 'address', 'name', 'id', 'neighbor', 'route', 'prefix', 'key']

        for key in top_level_keys:
            if key in item:
                value = item[key]
                if value is not None and not isinstance(value, (dict, list)):
                    return str(value)

        # Strategy 3: If item has 'peer' or 'local' dict, try to get address from it
        for container_key in ['peer', 'local', 'remote']:
            if container_key in item and isinstance(item[container_key], dict):
                container = item[container_key]
                for addr_key in ['address', 'ip', 'host', 'peer-address']:
                    if addr_key in container:
                        value = container[addr_key]
                        if value is not None and not isinstance(value, (dict, list)):
                            return str(value)

        # Strategy 4: Find first non-complex value as fallback
        for key, value in item.items():
            if value is not None and not isinstance(value, (dict, list)):
                # Skip internal/metadata keys
                if not key.startswith('_') and key not in ['state', 'status', 'type', 'duration']:
                    return f'{key}={value}'

        return None

    def _get_nested_value(self, data: dict[str, Any], path: list[str]) -> Any:
        """Get value from nested dictionary using path list

        Args:
            data: Dictionary to search
            path: List of keys to traverse (e.g., ['peer', 'address'])

        Returns:
            Value if found, None otherwise
        """
        current: Any = data
        for key in path:
            if not isinstance(current, dict) or key not in current:
                return None
            current = current[key]

        # Return only if it's a simple value (not dict/list)
        if current is not None and not isinstance(current, (dict, list)):
            return current
        return None

    def _format_dict(self, data: dict[str, Any]) -> str:
        """Format dictionary as key-value pairs"""
        if not data:
            return '(empty)'

        # Separate simple keys from complex keys
        simple_keys: list[str] = []
        complex_keys: list[str] = []

        for key, value in data.items():
            if isinstance(value, (dict, list)):
                complex_keys.append(key)
            else:
                simple_keys.append(key)

        # Sort both groups alphabetically
        simple_keys.sort()
        complex_keys.sort()

        # Combine: simple keys first, then complex keys
        sorted_keys = simple_keys + complex_keys

        # Calculate max key width for alignment
        max_key_width = max(len(str(k)) for k in sorted_keys) if sorted_keys else 0

        lines = []
        for key in sorted_keys:
            value = data[key]
            key_str = str(key).ljust(max_key_width)

            # Format value based on type
            if isinstance(value, dict):
                # Nested dict - indent on new lines
                lines.append(f'{key_str}:')
                lines.append(self._indent(self._format_dict(value), 2))
            elif isinstance(value, list):
                # List - format based on content
                if not value:
                    lines.append(f'{key_str}: (empty list)')
                elif all(isinstance(item, (str, int, float, bool, type(None))) for item in value):
                    # Simple list - show inline or multiline
                    if len(value) <= 3:
                        lines.append(f'{key_str}: [{", ".join(str(v) for v in value)}]')
                    else:
                        lines.append(f'{key_str}:')
                        for item in value:
                            lines.append(f'  - {item}')
                else:
                    # Complex list
                    lines.append(f'{key_str}:')
                    lines.append(self._indent(self._format_json_as_text(value), 2))
            else:
                # Simple value
                lines.append(f'{key_str}: {self._format_value(value)}')

        return '\n'.join(lines)

    def _format_value(self, value: Any) -> str:
        """Format a single value for display"""
        if value is None:
            return 'null'
        if isinstance(value, bool):
            return 'true' if value else 'false'
        if isinstance(value, (dict, list)):
            # Compact representation for nested structures in tables
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    def _indent(self, text: str, spaces: int) -> str:
        """Indent all lines in text by given number of spaces"""
        indent_str = ' ' * spaces
        return '\n'.join(indent_str + line for line in text.split('\n'))

    def format_command_output(self, output: str, display_mode: str = 'json') -> str:
        """Format command output with colors and pretty-print JSON or convert to text tables

        Args:
            output: Raw output from command
            display_mode: 'json' for pretty JSON, 'text' for human-readable tables
        """
        if not output:
            return output

        # Strip common response markers
        output_stripped = output.strip()

        # Remove 'done' marker if present (ExaBGP API response suffix)
        if output_stripped.endswith('done'):
            output_stripped = output_stripped[:-4].strip()

        # Try to parse and pretty-print as JSON (single object/array)
        if output_stripped.startswith('{') or output_stripped.startswith('['):
            try:
                # Parse JSON
                parsed = json.loads(output_stripped)

                # Display mode: text - convert JSON to human-readable tables
                if display_mode == 'text':
                    return self._format_json_as_text(parsed)

                # Display mode: json - show pretty-printed JSON
                # Pretty-print with 2-space indent
                pretty_json = json.dumps(parsed, indent=2, ensure_ascii=False)

                # Apply color if enabled
                if self.use_color:
                    # Colorize the JSON output
                    colored_lines = []
                    for line in pretty_json.split('\n'):
                        colored_lines.append(f'{Colors.CYAN}{line}{Colors.RESET}')
                    return '\n'.join(colored_lines)
                else:
                    return pretty_json
            except (json.JSONDecodeError, ValueError):
                # Not valid JSON, try line-by-line parsing for multiple JSON objects
                pass

        # Try line-by-line JSON parsing (for multiple JSON objects on separate lines)
        lines = output_stripped.split('\n')
        formatted_lines = []
        all_json = True

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                formatted_lines.append('')
                continue

            if line_stripped.startswith('{') or line_stripped.startswith('['):
                try:
                    parsed = json.loads(line_stripped)
                    pretty_json = json.dumps(parsed, indent=2, ensure_ascii=False)
                    if self.use_color:
                        colored = '\n'.join(
                            f'{Colors.CYAN}{json_line}{Colors.RESET}' for json_line in pretty_json.split('\n')
                        )
                        formatted_lines.append(colored)
                    else:
                        formatted_lines.append(pretty_json)
                except (json.JSONDecodeError, ValueError):
                    all_json = False
                    break
            else:
                all_json = False
                break

        if all_json and formatted_lines:
            return '\n'.join(formatted_lines)

        # Not JSON or parsing failed - use regular formatting
        if not self.use_color:
            return output

        lines = output.split('\n')
        formatted = []

        for line in lines:
            # Colorize JSON-like output (for partial/invalid JSON)
            if line.strip().startswith('{') or line.strip().startswith('['):
                formatted.append(f'{Colors.CYAN}{line}{Colors.RESET}')
            # Colorize IP addresses
            elif any(c in line for c in ['.', ':']):
                # Simple IP highlighting (can be improved)
                formatted.append(line)
            else:
                formatted.append(line)

        return '\n'.join(formatted)

    def format_table(self, headers: list[str], rows: list[list[str]]) -> str:
        """Format data as a table"""
        if not headers or not rows:
            return ''

        # Calculate column widths
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = max(col_widths[i], len(str(cell)))

        # Build table
        lines = []

        # Header
        if self.use_color:
            header_line = ' │ '.join(f'{Colors.BOLD}{h.ljust(w)}{Colors.RESET}' for h, w in zip(headers, col_widths))
        else:
            header_line = ' | '.join(h.ljust(w) for h, w in zip(headers, col_widths))

        lines.append(header_line)

        # Separator
        sep_char = '─' if self.use_color else '-'
        lines.append(
            '─┼─'.join(sep_char * w for w in col_widths) if self.use_color else '-+-'.join('-' * w for w in col_widths)
        )

        # Rows
        for row in rows:
            line = ' │ ' if self.use_color else ' | '
            line = line.join(str(cell).ljust(w) for cell, w in zip(row, col_widths))
            lines.append(line)

        return '\n'.join(lines)
