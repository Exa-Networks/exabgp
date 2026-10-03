"""__main__.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import os
import sys
import argparse
from collections.abc import MutableMapping
from types import ModuleType
from typing import cast

from exabgp.application import cli
from exabgp.application import run
from exabgp.application import server
from exabgp.application import decode
from exabgp.application import encode
from exabgp.application import environ
from exabgp.application import version
from exabgp.application import validate
from exabgp.application import syntax
from exabgp.application import healthcheck
from exabgp.application import shell
from exabgp.application import schema
from exabgp.application import export
from exabgp.application import example
from exabgp.application import migrate
from exabgp.environment.config import EnvironmentValueError


# what a PyInstaller one-file binary points at the libraries it unpacked, keeping the value it
# found under <name>_ORIG (LIBPATH is the AIX name of LD_LIBRARY_PATH)
FROZEN_LIBRARY_PATHS = ('LD_LIBRARY_PATH', 'LIBPATH')


def restore_library_path(environment: MutableMapping[str, str]) -> None:
    """Give back the library path a one-file binary replaced, so what it starts sees the host's.

    Only for the binary (qa/bin/build_binary calls it before main). Its bootloader puts its
    unpacked directory first, and every helper, healthcheck command or shell inherits it. A
    python3 which finds its libpython through that path, as the one of GitHub's runners does,
    then loads the bundled libpython instead, cannot find its standard library, and dies.
    The daemon itself is unaffected: the loader read the path when the binary started.
    """
    for name in FROZEN_LIBRARY_PATHS:
        original = environment.pop(f'{name}_ORIG', None)
        if original is None:
            environment.pop(name, None)
        else:
            environment[name] = original


def _description(module: ModuleType) -> str | None:
    """The docstring of a subcommand's module, which a module compiled with mypyc does not keep.

    Read as `module.__doc__`, the type checker takes a module's docstring to be a `str`, and
    compiled code then refuses the None a compiled module has in its place.
    """
    docstring: str | None = getattr(module, '__doc__', None)
    return docstring


def _tool_arguments(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """The subcommands which group further ones: configuration and migrate."""
    # Configuration subcommand group
    config_parser = subparsers.add_parser(
        'configuration', help='configuration tools (validate, export)', description='Configuration management tools'
    )
    config_subparsers = config_parser.add_subparsers(dest='config_command')

    config_validate = config_subparsers.add_parser(
        'validate', help='validate configuration file', description=_description(validate)
    )
    config_validate.set_defaults(func=validate.cmdline)
    validate.setargs(config_validate)

    config_export = config_subparsers.add_parser(
        'export', help='export parsed configuration to JSON', description=_description(export)
    )
    config_export.set_defaults(func=export.cmdline)
    export.setargs(config_export)

    config_syntax = config_subparsers.add_parser(
        'syntax', help='show what the configuration accepts', description=_description(syntax)
    )
    config_syntax.set_defaults(func=syntax.cmdline)
    syntax.setargs(config_syntax)

    config_example = config_subparsers.add_parser(
        'example', help='generate documented configuration example', description=_description(example)
    )
    config_example.set_defaults(func=example.cmdline)
    example.setargs(config_example)

    # Migration tools subcommand group
    migrate_parser = subparsers.add_parser(
        'migrate', help='migrate configuration/API between versions', description=_description(migrate)
    )
    migrate_parser.set_defaults(func=migrate.cmdline)
    migrate.setargs(migrate_parser)


def arguments() -> argparse.ArgumentParser:
    """The command line, one subparser per subcommand."""
    formatter = argparse.RawDescriptionHelpFormatter
    parser = argparse.ArgumentParser(
        description='The BGP swiss army knife of networking\n\n'
        'A configuration file can be passed directly:\n'
        '  exabgp config.conf     (equivalent to: exabgp server config.conf)\n\n'
        'Environment file override:\n'
        '  exabgp --env-file /path/to/exabgp.env server config.conf\n'
        '  EXABGP_ENVFILE=/path/to/exabgp.env exabgp server config.conf',
        formatter_class=formatter,
    )

    subparsers = parser.add_subparsers()

    sub = subparsers.add_parser('version', help='report exabgp version', description=_description(version))
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

    sub = subparsers.add_parser('run', help='execute single command (non-interactive)', description=_description(run))
    sub.set_defaults(func=run.cmdline)
    run.setargs(sub)

    sub = subparsers.add_parser(
        'healthcheck',
        help='monitor services and announce/withdraw routes',
        description=_description(healthcheck),
        formatter_class=formatter,
    )
    sub.set_defaults(func=healthcheck.cmdline)
    healthcheck.setargs(sub)

    sub = subparsers.add_parser('env', help='show exabgp configuration information', description=_description(environ))
    sub.set_defaults(func=environ.cmdline)
    environ.setargs(sub)

    sub = subparsers.add_parser('decode', help='decode hex-encoded bgp packets', description=_description(decode))
    sub.set_defaults(func=decode.cmdline)
    decode.setargs(sub)

    sub = subparsers.add_parser(
        'encode', help='encode route config to hex-encoded bgp packets', description=_description(encode)
    )
    sub.set_defaults(func=encode.cmdline)
    encode.setargs(sub)

    sub = subparsers.add_parser('server', help='start exabgp', description=_description(server))
    sub.set_defaults(func=server.cmdline)
    server.setargs(sub)

    sub = subparsers.add_parser(
        'shell', help='manage shell completion', description='Install or uninstall shell completion scripts'
    )
    sub.set_defaults(func=shell.cmdline)
    shell.setargs(sub)

    sub = subparsers.add_parser('schema', help='export configuration schema', description=_description(schema))
    sub.set_defaults(func=schema.cmdline)
    schema.setargs(sub)

    _tool_arguments(subparsers)

    return parser


def main() -> int | None:
    # Handle --env-file early, before Environment.setup() is called
    from exabgp.environment import base as envbase

    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == '--env-file' and i < len(sys.argv) - 1:
            envbase.ENVFILE = sys.argv[i + 1]
            sys.argv = sys.argv[:i] + sys.argv[i + 2 :]
            break
        if arg.startswith('--env-file='):
            envbase.ENVFILE = arg.split('=', 1)[1]
            sys.argv = sys.argv[:i] + sys.argv[i + 1 :]
            break

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
        if sys.argv[1] not in shell.SUBCOMMANDS:
            sys.argv = sys.argv[0:1] + ['server'] + sys.argv[1:]

    parser = arguments()

    try:
        cmdarg = parser.parse_args()
    except Exception as exc:
        sys.exit(exc.args[-1])

    options = vars(cmdarg)

    if 'func' in options:
        try:
            return cast(int | None, cmdarg.func(cmdarg))
        except EnvironmentValueError as exc:
            sys.stderr.write(f'error: {exc}\n')
            return 1
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
