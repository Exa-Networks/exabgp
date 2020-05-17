# encoding: utf-8

import sys
import syslog
import string
import argparse

from exabgp.environment import Env
from exabgp.environment import getenv
from exabgp.environment import ROOT

from exabgp.reactor.loop import Reactor
from exabgp.logger import log


def is_bgp(message):
    return all(c in string.hexdigits or c == ':' for c in message)


def args(sub):
    # fmt:off
    sub.add_argument('-d', '--debug', help='start the python debugger errors', action='store_true')
    sub.add_argument('-p', '--pdb', help='fire the debugger on fault', action='store_true')
    sub.add_argument('configuration', help='configuration file(s)', type=str)
    sub.add_argument('payload', help='the BGP payload in hexadecimal', nargs='+', type=str)
    # fmt:on


def main():
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__)
    args(parser)
    cmdline(parser.parse_args())


def cmdline(cmdarg):
    route = ''.join(cmdarg.payload).replace(' ', '')

    if not is_bgp(route):
        # parser.print_usage()
        sys.stdout.write('Environment values are:\n%s\n\n' % '\n'.join(' - %s' % _ for _ in Env.default()))
        sys.stdout.write('The BGP message must be an hexadecimal string.\n\n')
        sys.stdout.write('All colons or spaces are ignored, for example:\n\n')
        sys.stdout.write('  001E0200000007900F0003000101\n')
        sys.stdout.write('  001E:02:0000:0007:900F:0003:0001:01\n')
        sys.stdout.write('  FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF001E0200000007900F0003000101\n')
        sys.stdout.write('  FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:001E:02:0000:0007:900F:0003:0001:01\n')
        sys.stdout.write("  FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF 001E02 00000007900F0003000101\n")
        sys.stdout.flush()
        sys.exit(1)

    env = getenv()
    env.log.parser = True
    env.debug.route = route
    env.tcp.bind = ''

    if cmdarg.debug:
        env.log.all = True
        env.log.level = 'DEBUG'

    if cmdarg.pdb:
        env.debug.pdb = True

    log.init(env)
    Reactor([cmdarg.configuration]).run(False, ROOT)


if __name__ == '__main__':
    main()
