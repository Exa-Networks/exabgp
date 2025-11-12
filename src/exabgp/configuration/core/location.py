"""location.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import ClassVar

# ===================================================================== Location
# file location


class Location:
    def __init__(self, index_line: int = 0, index_column: int = 0, line: str = '') -> None:
        self.line: str = line
        self.index_line: int = index_line
        self.index_column: int = index_column

    def clear(self) -> None:
        self.index_line = 0
        self.index_column = 0
        self.line = ''


class Error(Exception):
    tabsize: ClassVar[int] = 3
    syntax: ClassVar[str] = ''

    def __init__(self, location: Location, message: str, syntax: str = '') -> None:
        self.line: str = location.line.replace('\t', ' ' * self.tabsize)
        self.index_line: int = location.index_line
        self.index_column: int = location.index_column + (self.tabsize - 1) * location.line[
            : location.index_column
        ].count(
            '\t',
        )

        cleaned_message: str = message.replace('\t', ' ' * self.tabsize)
        self.message: str = '\n\n'.join(
            (
                f'problem parsing configuration file line {location.index_line} position {location.index_column + 1}',
                f'error message: {cleaned_message}',
                f'{self.line}{"-" * self.index_column + "^"}',
            ),
        )
        # allow to give the right syntax in using Raised
        if syntax:
            self.message += '\n\n' + syntax

        Exception.__init__(self)

    def __repr__(self) -> str:
        return self.message
