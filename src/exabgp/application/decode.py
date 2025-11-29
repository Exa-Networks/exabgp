from __future__ import annotations

import sys
import string
import argparse

from exabgp.configuration.configuration import Configuration

from exabgp.debug.intercept import trace_interceptor

from exabgp.environment import Env
from exabgp.environment import getenv
from exabgp.environment import getconf

from exabgp.reactor.loop import Reactor
from exabgp.logger import log


conf_template = """\
neighbor 127.0.0.1 {
    router-id 10.0.0.2;
    local-address 127.0.0.1;
    local-as 65533;
    peer-as 65533;

    family {
        [families];
    }

    capability {
        [path-information]
    }
}
"""


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
    env.tcp.bind = ''

    if cmdarg.debug:
        env.log.all = True
        env.log.level = 'DEBUG'
    else:
        log.silence()

    if cmdarg.pdb:
        env.debug.pdb = True

    log.init(env)
    trace_interceptor(env.debug.pdb)

    conf = conf_template.replace('[path-information]', 'add-path send/receive;' if cmdarg.path_information else '')

    if cmdarg.configuration:
        configuration = Configuration([getconf(cmdarg.configuration)])

    elif cmdarg.family:
        families = cmdarg.family.split()
        if len(families) % 2:
            sys.stdout.write('families provided are invalid')
            sys.stdout.flush()
            sys.exit(1)
        families_pair = [families[n : n + 2] for n in range(0, len(families), 2)]
        families_text = ';'.join([f'{a} {s}' for a, s in families_pair])
        conf = conf.replace('[families]', families_text)
        configuration = Configuration([conf], text=True)

    else:
        conf = conf.replace('[families]', 'all')
        configuration = Configuration([conf], text=True)

    reactor = Reactor(configuration)
    all_valid = True

    for payload in payloads:
        route = payload.replace(' ', '').replace(':', '').strip()

        if not is_bgp(route):
            sys.stdout.write(f'invalid hexadecimal: {payload[:50]}{"..." if len(payload) > 50 else ""}\n')
            all_valid = False
            continue

        if not reactor.display(route, cmdarg.nlri):
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
