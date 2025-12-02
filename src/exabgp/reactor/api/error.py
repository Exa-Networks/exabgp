"""error.py

Standardized error handling for API commands.

Created by Thomas Mangin on 2025-12-02.
Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations


def format_api_error(command: str, error: Exception) -> str:
    """Format API error message consistently.

    Args:
        command: The command that failed (e.g., 'announce route', 'neighbor show')
        error: The exception that was raised

    Returns:
        Formatted error message with command context and exception details

    Example:
        >>> format_api_error('announce route', ValueError('invalid prefix'))
        "announce route failed: ValueError: invalid prefix"
    """
    error_type = type(error).__name__
    error_msg = str(error)
    return f'{command} failed: {error_type}: {error_msg}'
