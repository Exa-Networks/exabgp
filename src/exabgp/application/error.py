"""error.py

CLI exception hierarchy for ExaBGP application layer.

Created for exception handling refactor.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations


class CLIError(Exception):
    """Base exception for CLI operations."""


class CLIConnectionError(CLIError):
    """Failed to connect to ExaBGP daemon."""


class CLISocketError(CLIConnectionError):
    """Unix socket communication error."""


class CLIPipeError(CLIConnectionError):
    """Named pipe communication error."""


class CLITimeoutError(CLIError):
    """CLI operation timed out."""
