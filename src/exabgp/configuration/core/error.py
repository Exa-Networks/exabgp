from __future__ import annotations

import pdb  # noqa: T100
import sys
from typing import NoReturn

from exabgp.environment import getenv


class Error(Exception):
    def __init__(self) -> None:
        self.message = ''
        self.debug = getenv().debug.configuration

    def set(self, message: str) -> bool:
        self.message = message
        if self.debug:
            sys.stdout.write('\n{}\n'.format(self.message))
            pdb.set_trace()  # noqa: T100
        return False

    def throw(self, message: str) -> NoReturn:
        self.message = message
        if self.debug:
            sys.stdout.write('\n{}\n'.format(message))
            pdb.set_trace()  # noqa: T100
        raise self

    def clear(self) -> None:
        self.message = ''

    def __repr__(self) -> str:
        return self.message

    def __str__(self) -> str:
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
