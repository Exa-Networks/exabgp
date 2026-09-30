"""colors.py

ANSI color codes for terminal output.

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import os
import sys
from typing import ClassVar


class Colors:
    """ANSI color codes for terminal output"""

    # ClassVar: mypyc reads an unannotated class constant as an instance attribute,
    # and every caller reads these through the class
    RESET: ClassVar[str] = '\033[0m'
    BOLD: ClassVar[str] = '\033[1m'
    DIM: ClassVar[str] = '\033[2m'

    # Foreground colors
    BLACK: ClassVar[str] = '\033[30m'
    RED: ClassVar[str] = '\033[31m'
    GREEN: ClassVar[str] = '\033[32m'
    YELLOW: ClassVar[str] = '\033[33m'
    BLUE: ClassVar[str] = '\033[34m'
    MAGENTA: ClassVar[str] = '\033[35m'
    CYAN: ClassVar[str] = '\033[36m'
    WHITE: ClassVar[str] = '\033[37m'

    # Bright colors
    BRIGHT_BLACK: ClassVar[str] = '\033[90m'
    BRIGHT_RED: ClassVar[str] = '\033[91m'
    BRIGHT_GREEN: ClassVar[str] = '\033[92m'
    BRIGHT_YELLOW: ClassVar[str] = '\033[93m'
    BRIGHT_BLUE: ClassVar[str] = '\033[94m'
    BRIGHT_MAGENTA: ClassVar[str] = '\033[95m'
    BRIGHT_CYAN: ClassVar[str] = '\033[96m'
    BRIGHT_WHITE: ClassVar[str] = '\033[97m'

    @classmethod
    def supports_color(cls) -> bool:
        """Check if terminal supports ANSI colors"""
        # Check if stdout is a terminal
        if not hasattr(sys.stdout, 'isatty') or not sys.stdout.isatty():
            return False

        # Check TERM environment variable
        term = os.environ.get('TERM', '')
        if term in ('dumb', ''):
            return False

        # Check NO_COLOR environment variable (https://no-color.org/)
        if os.environ.get('NO_COLOR'):
            return False

        return True
