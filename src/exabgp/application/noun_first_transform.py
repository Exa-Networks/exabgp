"""Noun-first CLI syntax transformation.

Transform noun-first CLI syntax to API-compatible verb-first syntax.

Examples:
    neighbor * announce route 10.0.0.0/24 next-hop 1.1.1.1
      → announce route 10.0.0.0/24 next-hop 1.1.1.1

    neighbor 192.168.1.1 show summary
      → show neighbor 192.168.1.1 summary

    rib show in
      → show adj-rib in

    daemon shutdown
      → shutdown

    session ack enable
      → enable-ack

    session sync disable
      → disable-sync

The transformation is applied before shortcut expansion and command execution.
Old syntax passes through unchanged, maintaining 100% backward compatibility.
"""

import re


class NounFirstTransform:
    """Transform noun-first CLI commands to API syntax."""

    # Transformation patterns: (cli_pattern, api_pattern, preserves_tail)
    # preserves_tail=True means everything after the pattern is appended to result
    TRANSFORMS: list[tuple[str, str, bool]] = [
        # Neighbor commands
        # neighbor show → show neighbor (for all neighbors)
        (r'^neighbor\s+show\b', 'show neighbor', True),
        # RIB commands
        (r'^rib\s+show\s+in\b', 'show adj-rib in', True),
        (r'^rib\s+show\s+out\b', 'show adj-rib out', True),
        (r'^rib\s+flush\s+out\b', 'flush adj-rib out', True),
        (r'^rib\s+clear\s+in\b', 'clear adj-rib in', True),
        (r'^rib\s+clear\s+out\b', 'clear adj-rib out', True),
        # Daemon commands
        (r'^daemon\s+shutdown\b', 'shutdown', True),
        (r'^daemon\s+reload\b', 'reload', True),
        (r'^daemon\s+restart\b', 'restart', True),
        (r'^daemon\s+status\b', 'status', True),
        # Session commands (hierarchical)
        (r'^session\s+ack\s+enable\b', 'enable-ack', True),
        (r'^session\s+ack\s+disable\b', 'disable-ack', True),
        (r'^session\s+ack\s+silence\b', 'silence-ack', True),
        (r'^session\s+sync\s+enable\b', 'enable-sync', True),
        (r'^session\s+sync\s+disable\b', 'disable-sync', True),
        (r'^session\s+reset\b', 'reset', True),
        (r'^session\s+ping\b', 'ping', True),
        (r'^session\s+bye\b', 'bye', True),
        # System commands
        (r'^system\s+help\b', 'help', True),
        (r'^system\s+version\b', 'version', True),
        (r'^system\s+crash\b', 'crash', True),
    ]

    @classmethod
    def transform(cls, command: str) -> str:
        """Transform noun-first syntax to API syntax.

        Args:
            command: Command string (before shortcut expansion)

        Returns:
            API-compatible command string

        Examples:
            >>> NounFirstTransform.transform('daemon shutdown')
            'shutdown'
            >>> NounFirstTransform.transform('rib show in')
            'show adj-rib in'
            >>> NounFirstTransform.transform('session ack enable')
            'enable-ack'
            >>> NounFirstTransform.transform('neighbor show summary')
            'show neighbor summary'
            >>> NounFirstTransform.transform('show neighbor summary')
            'show neighbor summary'
        """
        if not command or not command.strip():
            return command

        command = command.strip()

        # Try each transformation pattern
        for pattern, replacement, preserves_tail in cls.TRANSFORMS:
            match = re.match(pattern, command, re.IGNORECASE)
            if match:
                # Get the matched portion and the tail
                matched_text = match.group(0)
                tail = command[len(matched_text) :].strip()

                if preserves_tail and tail:
                    return f'{replacement} {tail}'
                return replacement

        # No transformation needed (old syntax or built-in CLI command)
        return command
