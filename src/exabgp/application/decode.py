from __future__ import annotations

import sys
import string
import argparse

from exabgp.configuration.configuration import Configuration
from exabgp.configuration.setup import create_minimal_configuration

from exabgp.debug.intercept import trace_interceptor

from exabgp.environment import Env
from exabgp.environment import getenv
from exabgp.environment import getconf

from exabgp.reactor.loop import Reactor
from exabgp.logger import log


def is_bgp(message: str) -> bool:
    return all(c in string.hexdigits or c == ':' for c in message)


def setargs(sub: argparse.ArgumentParser) -> None:
    # fmt:off
    sub.add_argument('-n', '--nlri', help='the data is only the NLRI', action='store_true')
    sub.add_argument('-u', '--update', help='the data is an update message (does nothing)', action='store_true')
    sub.add_argument('-o', '--open', help='the data is an open message (does nothing)', action='store_true')
    sub.add_argument('-d', '--debug', help='start the python debugger errors', action='store_true')
    sub.add_argument('-p', '--pdb', help='fire the debugger on fault', action='store_true')
    sub.add_argument('-c', '--configuration', help='configuration file(s)', type=str)
    sub.add_argument('-f', '--family', help='family expected (format like "ipv4 unicast")', type=str)
    sub.add_argument('-i', '--path-information', help='decode path-information', action='store_true')
    sub.add_argument('-g', '--generic', help='output generic attributes as hex (for round-trip)', action='store_true')
    sub.add_argument('-j', '--json', help='output as JSON (default)', action='store_true', default=True)
    sub.add_argument('-m', '--command', help='output as API command instead of JSON', action='store_true')
    sub.add_argument('payload', help='the BGP payload in hexadecimal (reads from stdin if not provided)', type=str, nargs='?')
    # fmt:on


def main() -> int:
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__)
    setargs(parser)
    return cmdline(parser.parse_args())


def cmdline(cmdarg: argparse.Namespace) -> int:
    # Read from stdin if no payload provided
    if cmdarg.payload is None:
        if sys.stdin.isatty():
            sys.stdout.write(
                'Environment values are:\n{}\n\n'.format('\n'.join(' - {}'.format(_) for _ in Env.default()))
            )
            sys.stdout.write('Usage: exabgp decode <hex>\n')
            sys.stdout.write('       exabgp encode "route ..." | exabgp decode\n')
            sys.stdout.write('       echo "<hex>" | exabgp decode\n\n')
            sys.stdout.write('The BGP message must be an hexadecimal string.\n')
            sys.stdout.flush()
            sys.exit(1)
        payloads = [line.strip() for line in sys.stdin if line.strip()]
    else:
        payloads = [cmdarg.payload]

    env = getenv()
    env.bgp.passive = True
    env.log.parser = True
    env.tcp.bind = []

    if cmdarg.debug:
        env.log.all = True
        env.log.level = 'DEBUG'
    else:
        log.silence()

    if cmdarg.pdb:
        env.debug.pdb = True

    log.init(env)
    trace_interceptor(env.debug.pdb)

    if cmdarg.configuration:
        # Use config file
        configuration = Configuration([getconf(cmdarg.configuration)])
        reloaded = configuration.reload()
        if not reloaded:
            sys.stdout.write(f'configuration error: {configuration.error}\n')
            sys.stdout.flush()
            sys.exit(1)
    else:
        # Use programmatic configuration setup
        families = cmdarg.family if cmdarg.family else 'all'
        try:
            configuration = create_minimal_configuration(
                families=families,
                add_path=cmdarg.path_information,
            )
        except ValueError as e:
            sys.stdout.write(f'configuration error: {e}\n')
            sys.stdout.flush()
            sys.exit(1)

    reactor = Reactor(configuration)
    all_valid = True

    for payload in payloads:
        route = payload.replace(' ', '').replace(':', '').strip()

        if not is_bgp(route):
            sys.stdout.write(f'invalid hexadecimal: {payload[:50]}{"..." if len(payload) > 50 else ""}\n')
            all_valid = False
            continue

        if not reactor.display(route, cmdarg.nlri, generic=cmdarg.generic, command=cmdarg.command):
            sys.stdout.write('invalid payload\n')
            all_valid = False

    return 0 if all_valid else 1


if __name__ == '__main__':
    try:
        code = main()
        sys.exit(code)
    except BrokenPipeError:
        # there was a PIPE ( ./sbin/exabgp | command )
        # and command does not work as should
        sys.exit(1)
