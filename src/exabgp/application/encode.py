"""encode.py

Encode route configuration text into hex-encoded BGP UPDATE messages.
This is the reverse of decode which takes hex and shows parsed output.

Created on 2025-11-27.
Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import sys
import argparse

from exabgp.configuration.configuration import Configuration

from exabgp.debug.intercept import trace_interceptor

from exabgp.environment import Env
from exabgp.environment import getenv
from exabgp.environment import getconf

from exabgp.configuration.check import _negotiated
from exabgp.bgp.message import UpdateCollection

from exabgp.logger import log


conf_template = """\
neighbor 127.0.0.1 {{
    router-id 10.0.0.2;
    local-address 127.0.0.1;
    local-as {local_as};
    peer-as {peer_as};

    family {{
        {families};
    }}

    capability {{
        {path_information}
    }}

    static {{
        {routes};
    }}
}}
"""


def setargs(sub: argparse.ArgumentParser) -> None:
    # fmt:off
    sub.add_argument('route', help='route in config format (e.g., "route 10.0.0.0/24 next-hop 1.2.3.4")', type=str, nargs='?')
    sub.add_argument('-f', '--family', help='address family (e.g., "ipv4 unicast")', type=str, default='ipv4 unicast')
    sub.add_argument('-a', '--local-as', help='local AS number', type=int, default=65533, dest='local_as')
    sub.add_argument('-z', '--peer-as', help='peer AS number', type=int, default=65533, dest='peer_as')
    sub.add_argument('-i', '--path-information', help='enable add-path', action='store_true', dest='path_information')
    sub.add_argument('-n', '--nlri-only', help='output only NLRI bytes (no UPDATE wrapper)', action='store_true', dest='nlri_only')
    sub.add_argument('--no-header', help='exclude BGP 19-byte header', action='store_true', dest='no_header')
    sub.add_argument('-c', '--configuration', help='use config file instead of route argument', type=str)
    sub.add_argument('-d', '--debug', help='enable debug logging', action='store_true')
    sub.add_argument('-p', '--pdb', help='enable debugger on error', action='store_true')
    # fmt:on


def main() -> int:
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__)
    setargs(parser)
    return cmdline(parser.parse_args())


def cmdline(cmdarg: argparse.Namespace) -> int:
    if not cmdarg.route and not cmdarg.configuration:
        sys.stdout.write('Environment values are:\n{}\n\n'.format('\n'.join(' - {}'.format(_) for _ in Env.default())))
        sys.stdout.write('Usage: exabgp encode "route 10.0.0.0/24 next-hop 1.2.3.4"\n')
        sys.stdout.write('       exabgp encode -c myconfig.conf\n\n')
        sys.stdout.write('Examples:\n')
        sys.stdout.write('  exabgp encode "route 10.0.0.0/24 next-hop 192.168.1.1"\n')
        sys.stdout.write('  exabgp encode "route 10.0.0.0/24 next-hop 1.2.3.4 origin igp as-path [65000 65001]"\n')
        sys.stdout.write('  exabgp encode -f "ipv6 unicast" "route 2001:db8::/32 next-hop 2001:db8::1"\n')
        sys.stdout.write('  exabgp encode -n "route 10.0.0.0/24 next-hop 1.2.3.4"  # NLRI only\n')
        sys.stdout.flush()
        sys.exit(1)

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

    # Build configuration
    if cmdarg.configuration:
        configuration = Configuration([getconf(cmdarg.configuration)])
    else:
        # Parse family argument
        families = cmdarg.family.split()
        if len(families) % 2:
            sys.stdout.write('families provided are invalid\n')
            sys.stdout.flush()
            sys.exit(1)
        families_pair = [families[n : n + 2] for n in range(0, len(families), 2)]
        families_text = ';'.join([f'{a} {s}' for a, s in families_pair])

        # Build config from template
        conf = conf_template.format(
            local_as=cmdarg.local_as,
            peer_as=cmdarg.peer_as,
            families=families_text,
            path_information='add-path send/receive;' if cmdarg.path_information else '',
            routes=cmdarg.route,
        )

        configuration = Configuration([conf], text=True)

    # Parse the configuration
    reloaded = configuration.reload()
    if not reloaded:
        sys.stdout.write(f'configuration error: {configuration.error}\n')
        sys.stdout.flush()
        sys.exit(1)

    if not configuration.neighbors:
        sys.stdout.write('no neighbor defined in configuration\n')
        sys.stdout.flush()
        sys.exit(1)

    # Process each neighbor and encode their routes
    for name in configuration.neighbors.keys():
        neighbor = configuration.neighbors[name]
        _, negotiated_out = _negotiated(neighbor)

        if not neighbor.rib.enabled:
            continue

        # Trigger route processing
        for _ in neighbor.rib.outgoing.updates(False):
            pass

        # Get routes and encode them
        for route in neighbor.rib.outgoing.cached_routes():
            if cmdarg.nlri_only:
                # Output only NLRI bytes
                packed = route.nlri.pack_nlri(negotiated_out)
                sys.stdout.write(packed.hex().upper())
                sys.stdout.write('\n')
            else:
                # Output full UPDATE message(s)
                for packed in UpdateCollection([route.nlri], [], route.attributes).messages(negotiated_out):
                    if cmdarg.no_header:
                        # Skip 19-byte BGP header (16 marker + 2 length + 1 type)
                        packed = packed[19:]
                    sys.stdout.write(packed.hex().upper())
                    sys.stdout.write('\n')

    sys.stdout.flush()
    return 0


if __name__ == '__main__':
    try:
        code = main()
        sys.exit(code)
    except BrokenPipeError:
        # there was a PIPE ( ./sbin/exabgp | command )
        # and command does not work as should
        sys.exit(1)
