from __future__ import annotations

import pdb  # noqa: T100
import sys
from typing import NoReturn

from exabgp.environment import getenv


class Error(Exception):
    def __init__(self) -> None:
        self.message = ''
        self.debug = getenv().debug.configuration
        self._collect_mode = False
        self._errors: list[str] = []
        self._max_errors = 10

    def enable_collection(self, max_errors: int = 10) -> None:
        """Enable multi-error collection mode.

        In collection mode, errors are accumulated instead of immediately
        stopping parsing. This allows finding multiple configuration errors
        in a single validation pass.

        Args:
            max_errors: Maximum number of errors to collect before stopping
        """
        self._collect_mode = True
        self._max_errors = max_errors
        self._errors = []

    def disable_collection(self) -> None:
        """Disable multi-error collection mode and return to fail-fast."""
        self._collect_mode = False
        self._errors = []

    def get_all_errors(self) -> list[str]:
        """Return all collected errors.

        Returns:
            List of error messages collected during parsing
        """
        return self._errors.copy()

    def has_errors(self) -> bool:
        """Check if any errors have been collected.

        Returns:
            True if errors were collected, False otherwise
        """
        return len(self._errors) > 0

    def set(self, message: str) -> bool:
        if self._collect_mode:
            # Collect error and continue parsing
            self._errors.append(message)
            if len(self._errors) >= self._max_errors:
                # Hit max errors, stop collecting
                self.message = f'Too many errors ({self._max_errors}), stopping validation'
                if self.debug:
                    sys.stdout.write('\n{}\n'.format(self.message))
                    pdb.set_trace()  # noqa: T100
                raise self
            return False
        else:
            # Original fail-fast behavior
            self.message = message
            if self.debug:
                sys.stdout.write('\n{}\n'.format(self.message))
                pdb.set_trace()  # noqa: T100
            return False

    def throw(self, message: str) -> NoReturn:
        if self._collect_mode:
            # In collection mode, collect the error first
            self._errors.append(message)
        self.message = message
        if self.debug:
            sys.stdout.write('\n{}\n'.format(message))
            pdb.set_trace()  # noqa: T100
        raise self

    def clear(self) -> None:
        self.message = ''
        if not self._collect_mode:
            # Only clear collected errors if not in collection mode
            self._errors = []

    def __repr__(self) -> str:
        if self._collect_mode and self._errors:
            return '\n'.join(self._errors)
        return self.message

    def __str__(self) -> str:
        if self._collect_mode and self._errors:
            return '\n'.join(self._errors)
        return self.message


class ParsingError(Error):
    """Base parsing error for configuration."""

    pass


class AFISAFIParsingError(ParsingError):
    """Failed to parse AFI/SAFI value."""

    pass


class IPAddressParsingError(ParsingError):
    """Failed to parse IP address."""

    pass
