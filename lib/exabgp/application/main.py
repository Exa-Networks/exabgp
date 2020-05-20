# encoding: utf-8
"""
__main__.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import sys

from exabgp.application import run_exabgp
from exabgp.application import run_exabmp
from exabgp.application import run_cli
from exabgp.application import run_healthcheck


def main():
    if len(sys.argv) == 1:
        run_exabgp()
        return

    if sys.argv[1] == 'bgp':
        sys.argv = sys.argv[1:]
        run_exabgp()
        return

    if sys.argv[1] == 'bmp':
        sys.argv = sys.argv[1:]
        run_exabgp()
        return

    if sys.argv[1] == 'healthcheck':
        sys.argv = sys.argv[1:]
        run_healthcheck()
        return

    if sys.argv[1] == 'cli':
        sys.argv = sys.argv[1:]
        run_cli()
        return

    run_exabgp()


if __name__ == '__main__':
    main()
