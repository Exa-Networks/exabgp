# encoding: utf-8

import sys
import string
import argparse

from exabgp.environment import Env
from exabgp.environment import getenv


def is_bgp(message):
    return all(c in string.hexdigits or c == ':' for c in message)


def args(sub):
    # fmt:off
    sub.add_argument('payload', help='the BGP payload in hexadecimal', type=str)
    # fmt:on


def main():
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__)
    args(parser)
    cmdline(parser.parse_args())


def cmdline(cmdarg):
    if not is_bgp(cmdarg.payload):
        # parser.print_usage()
        sys.stdout.write('Environment values are:\n%s\n\n' % '\n'.join(' - %s' % _ for _ in Env.default()))
        sys.stdout.write('The BGP message must be an hexadecimal string.\n\n')
        sys.stdout.write('All colons or spaces are ignored, for example:\n\n')
        sys.stdout.write('  --decode 001E0200000007900F0003000101\n')
        sys.stdout.write('  --decode 001E:02:0000:0007:900F:0003:0001:01\n')
        sys.stdout.write('  --decode FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF001E0200000007900F0003000101\n')
        sys.stdout.write('  --decode FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:001E:02:0000:0007:900F:0003:0001:01\n')
        sys.stdout.write('  --decode \'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF 001E02 00000007900F0003000101\n\'')
        sys.stdout.flush()
        sys.exit(1)

    env = getenv()
    env.log.parser = True
    env.debug.route = cmdarg.payload
    env.tcp.bind = ''


if __name__ == '__main__':
    main()
