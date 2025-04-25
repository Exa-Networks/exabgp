# encoding: utf-8

"""exabgp environement values"""

from __future__ import annotations

import sys
import argparse

from exabgp.environment import Env


def setargs(sub):
    # fmt: off
    sub.add_argument('-d', '--diff', help='show only the different from the defaults', action='store_true')
    sub.add_argument('-e', '--env', help='display using environment (not ini)', action='store_true')
    # fmt: on


def default():
    sys.stdout.write('\nEnvironment values are:\n')
    sys.stdout.write('\n'.join('    %s' % _ for _ in Env.default()))
    sys.stdout.flush()


def cmdline(cmdarg):
    dispatch = {
        True: Env.iter_env,
        False: Env.iter_ini,
    }

    for line in dispatch[cmdarg.env](cmdarg.diff):
        sys.stdout.write('%s\n' % line)
        sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__)
    setargs(parser)
    cmdline(parser.parse_args())


if __name__ == '__main__':
    main()
