"""debug.py

Created by Thomas Mangin on 2011-03-29.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import os
import sys
import pdb  # noqa: T100
from types import TracebackType

from exabgp.debug.report import format_panic


def bug_report(dtype: type[BaseException], value: BaseException, trace: TracebackType | None) -> None:
    sys.stdout.flush()
    sys.stderr.flush()
    sys.stdout.write(f'{format_panic(dtype, value, trace)}\n')
    sys.stdout.flush()


def intercept(dtype: type[BaseException], value: BaseException, trace: TracebackType | None) -> None:
    bug_report(dtype, value, trace)
    if os.environ.get('PDB', None) not in [None, '0', '']:
        pdb.pm()


def trace_interceptor(with_pdb: bool) -> None:
    if with_pdb:
        os.environ['PDB'] = '1'
    sys.excepthook = intercept
