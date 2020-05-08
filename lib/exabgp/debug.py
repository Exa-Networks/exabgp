# encoding: utf-8
"""
debug.py

Created by Thomas Mangin on 2011-03-29.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import os
import sys
from exabgp.util.panic import PANIC
from exabgp.util.panic import FOOTER


def bug_report(dtype, value, trace):
    sys.stdout.flush()
    sys.stderr.flush()

    print(PANIC)
    sys.stdout.flush()
    sys.stderr.flush()

    import traceback

    print("-- Traceback\n\n")
    traceback.print_exception(dtype, value, trace)

    from exabgp.logger import Logger

    logger = Logger()

    print("\n\n-- Configuration\n\n")
    print(logger.config())
    print("\n\n-- Logging History\n\n")
    print(logger.history())
    print("\n\n\n")

    print(FOOTER)
    sys.stdout.flush()
    sys.stderr.flush()


def intercept(dtype, value, trace):
    bug_report(dtype, value, trace)
    if os.environ.get('PDB', None) not in [None, '0', '']:
        import pdb

        pdb.pm()


def setup_report():
    sys.excepthook = intercept
