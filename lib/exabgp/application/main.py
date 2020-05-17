# encoding: utf-8
"""
__main__.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import os
import sys
import argparse

from exabgp.application import cli
from exabgp.application import server
from exabgp.application import decode
from exabgp.application import environ
from exabgp.application import version
from exabgp.application import validate
from exabgp.application import healthcheck


def main():
    cli_named_pipe = os.environ.get('exabgp_cli_pipe', '')
    if cli_named_pipe:
        from exabgp.application.pipe import main

        main(cli_named_pipe)
        sys.exit(0)

    # compatibility with exabgp 4.x
    if len(sys.argv) > 1 and not ('-h' in sys.argv or '--help' in sys.argv):
        if sys.argv[1] not in ('version', 'cli', 'healthcheck', 'decode', 'server', 'env', 'validate'):
            sys.argv = sys.argv[0:1] + ['server'] + sys.argv[1:]

    formatter = argparse.RawDescriptionHelpFormatter
    parser = argparse.ArgumentParser(description='The BGP swiss army knife of networking')

    subparsers = parser.add_subparsers()

    sub = subparsers.add_parser('version', help='report exabgp version', description=version.__doc__)
    sub.set_defaults(func=version.cmdline)
    version.args(sub)

    sub = subparsers.add_parser('cli', help='control a running exabgp server instance', description=cli.__doc__)
    sub.set_defaults(func=cli.cmdline)
    cli.args(sub)

    sub = subparsers.add_parser(
        'healthcheck',
        help='monitor services and announce/withdraw routes',
        description=healthcheck.__doc__,
        formatter_class=formatter,
    )
    sub.set_defaults(func=healthcheck.cmdline)
    # healthcheck.args(sub)

    sub = subparsers.add_parser('env', help='show exabgp configuration information', description=environ.__doc__)
    sub.set_defaults(func=environ.cmdline)
    environ.args(sub)

    sub = subparsers.add_parser('decode', help='decode hex-encoded bgp packets', description=decode.__doc__)
    sub.set_defaults(func=decode.cmdline)
    decode.args(sub)

    sub = subparsers.add_parser('server', help='start exabgp', description=server.__doc__)
    sub.set_defaults(func=server.cmdline)
    server.args(sub)

    sub = subparsers.add_parser('validate', help='validate configuration', description=validate.__doc__)
    sub.set_defaults(func=validate.cmdline)
    validate.args(sub)

    cmdarg = parser.parse_args()
    options = vars(cmdarg)

    if 'func' in options:
        cmdarg.func(cmdarg)
    else:
        parser.print_help()
        environ.default()


if __name__ == '__main__':
    main()
