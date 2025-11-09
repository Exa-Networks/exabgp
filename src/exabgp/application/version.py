# encoding: utf-8

"""exabgp current version"""

from __future__ import annotations

import sys
import argparse
import platform

from exabgp.version import version, get_root


def setargs(sub):
    # fmt:off
    pass
    # fmt:on


def main():
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__)
    setargs(parser)
    cmdline(parser.parse_args())


def cmdline(cmdarg):
    sys.stdout.write(f'ExaBGP : {version}\n')
    sys.stdout.write(f'Python : {sys.version.replace("\n", " ")}\n')
    sys.stdout.write(f'Uname  : {" ".join(platform.uname()[:5])}\n')
    sys.stdout.write(f'From   : {get_root()}\n')
    sys.stdout.flush()


if __name__ == '__main__':
    main()
