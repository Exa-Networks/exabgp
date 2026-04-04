"""debug.py

Created by Thomas Mangin on 2011-03-29.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import os
import sys
import pdb  # noqa: T100

from exabgp.debug.report import format_panic


def bug_report(dtype, value, trace):
    sys.stdout.flush()
    sys.stderr.flush()
    sys.stdout.write(f'{format_panic(dtype, value, trace)}\n')
    sys.stdout.flush()


def intercept(dtype, value, trace):
    bug_report(dtype, value, trace)
    if os.environ.get('PDB', None) not in [None, '0', '']:
        pdb.pm()


def trace_interceptor(with_pdb):
    if with_pdb:
        os.environ['PDB'] = '1'
    sys.excepthook = intercept
