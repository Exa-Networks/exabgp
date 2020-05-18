# encoding: utf-8

"""exabgp current version"""

import sys
import argparse
import platform

from exabgp.version import version


def setargs(sub):
    # fmt:off
    pass
    # fmt:on


def main():
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__)
    setargs(parser)
    cmdline(parser.parse_args())


def cmdline(cmdarg):
    sys.stdout.write('ExaBGP : %s\n' % version)
    sys.stdout.write('Python : %s\n' % sys.version.replace('\n', ' '))
    sys.stdout.write('Uname  : %s\n' % ' '.join(platform.uname()[:5]))
    sys.stdout.flush()


if __name__ == '__main__':
    main()
