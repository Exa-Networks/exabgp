"""__main__.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import os
import sys
import argparse

from exabgp.application import cli
from exabgp.application import run
from exabgp.application import server
from exabgp.application import decode
from exabgp.application import environ
from exabgp.application import version
from exabgp.application import validate
from exabgp.application import healthcheck
from exabgp.application import shell


def main():
    # Check if this is a CLI subprocess (pipe or socket)
    cli_mode = os.environ.get('exabgp_api_cli_mode', '')

    if cli_mode == 'pipe':
        cli_named_pipe = os.environ.get('exabgp_cli_pipe', '')
        if cli_named_pipe:
            from exabgp.application.pipe import main

            main(cli_named_pipe)
            sys.exit(0)
    elif cli_mode == 'socket':
        cli_unix_socket = os.environ.get('exabgp_cli_socket', '')
        if cli_unix_socket:
            from exabgp.application.unixsocket import main

            main(cli_unix_socket)
            sys.exit(0)

    # compatibility with exabgp 4.x
    if len(sys.argv) > 1 and not ('-h' in sys.argv or '--help' in sys.argv):
        if sys.argv[1] not in ('version', 'cli', 'run', 'healthcheck', 'decode', 'server', 'env', 'validate', 'shell'):
            sys.argv = sys.argv[0:1] + ['server'] + sys.argv[1:]

    formatter = argparse.RawDescriptionHelpFormatter
    parser = argparse.ArgumentParser(description='The BGP swiss army knife of networking')

    subparsers = parser.add_subparsers()

    sub = subparsers.add_parser('version', help='report exabgp version', description=version.__doc__)
    sub.set_defaults(func=version.cmdline)
    version.setargs(sub)

    sub = subparsers.add_parser(
        'cli',
        help='interactive CLI with tab completion',
        description='Interactive REPL mode with intelligent tab completion',
    )
    sub.set_defaults(
        func=lambda args: cli.cmdline_interactive(
            args.pipename if hasattr(args, 'pipename') else 'exabgp', 'exabgp', False, args
        )
    )
    sub.add_argument('--pipename', dest='pipename', metavar='NAME', help='Name of the pipe')
    sub.add_argument('--no-color', dest='no_color', action='store_true', help='Disable colored output')

    sub = subparsers.add_parser('run', help='execute single command (non-interactive)', description=run.__doc__)
    sub.set_defaults(func=run.cmdline)
    run.setargs(sub)

    sub = subparsers.add_parser(
        'healthcheck',
        help='monitor services and announce/withdraw routes',
        description=healthcheck.__doc__,
        formatter_class=formatter,
    )
    sub.set_defaults(func=healthcheck.cmdline)
    healthcheck.setargs(sub)

    sub = subparsers.add_parser('env', help='show exabgp configuration information', description=environ.__doc__)
    sub.set_defaults(func=environ.cmdline)
    environ.setargs(sub)

    sub = subparsers.add_parser('decode', help='decode hex-encoded bgp packets', description=decode.__doc__)
    sub.set_defaults(func=decode.cmdline)
    decode.setargs(sub)

    sub = subparsers.add_parser('server', help='start exabgp', description=server.__doc__)
    sub.set_defaults(func=server.cmdline)
    server.setargs(sub)

    sub = subparsers.add_parser('validate', help='validate configuration', description=validate.__doc__)
    sub.set_defaults(func=validate.cmdline)
    validate.setargs(sub)

    sub = subparsers.add_parser(
        'shell', help='manage shell completion', description='Install or uninstall shell completion scripts'
    )
    sub.set_defaults(func=shell.cmdline)
    shell.setargs(sub)

    try:
        cmdarg = parser.parse_args()
    except Exception as exc:
        sys.exit(exc.args[-1])

    options = vars(cmdarg)

    if 'func' in options:
        return cmdarg.func(cmdarg)
    parser.print_help()
    environ.default()
    return 1


if __name__ == '__main__':
    try:
        code = main()
        sys.exit(code)
    except BrokenPipeError:
        # there was a PIPE ( ./sbin/exabgp | command )
        # and command does not work as should
        sys.exit(1)
