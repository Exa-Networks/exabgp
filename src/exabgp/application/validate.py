"""exabgp configuration validation"""

from __future__ import annotations

import sys
import argparse

from exabgp.environment import getenv
from exabgp.environment import getconf

from exabgp.configuration.configuration import Configuration
from exabgp.bgp.neighbor import NeighborTemplate

from exabgp.debug.intercept import trace_interceptor
from exabgp.logger import log

from exabgp.configuration.check import check_generation


def setargs(sub):
    # fmt:off
    sub.add_argument('-n', '--neighbor', help='check the parsing of the neighbors', action='store_true')
    sub.add_argument('-r', '--route', help='check the parsing of the routes', action='store_true')
    sub.add_argument('-v', '--verbose', help='be verbose in the display', action='store_true')
    sub.add_argument('-p', '--pdb', help='fire the debugger on critical logging, SIGTERM, and exceptions (shortcut for exabgp.pdb.enable=true)', action='store_true')
    sub.add_argument('configuration', help='configuration file(s)', nargs='+', type=str)
    # fmt:on


def cmdline(cmdarg):
    env = getenv()

    # Must be done before setting the logger as it modify its behaviour
    if cmdarg.verbose:
        env.log.all = True
        env.log.level = 'DEBUG'

    if cmdarg.pdb:
        env.debug.pdb = True

    log.init(env)
    trace_interceptor(env.debug.pdb)

    if cmdarg.verbose:
        env.log.parser = True

    for configuration in cmdarg.configuration:
        log.info(lambda configuration=configuration: f'loading {configuration}', 'configuration')
        location = getconf(configuration)
        if not location:
            log.critical(
                lambda configuration=configuration: f'{configuration} is not an exabgp config file', 'configuration'
            )
            sys.exit(1)

        config = Configuration([location])

        if not config.reload():
            log.critical(
                lambda configuration=configuration: f'{configuration} is not a valid config file', 'configuration'
            )
            sys.exit(1)
        log.info(lambda: '\u2713 loading', 'configuration')

        if cmdarg.neighbor:
            log.warning(lambda: 'checking neighbors', 'configuration')
            for name, neighbor in config.neighbors.items():
                reparsed = NeighborTemplate.configuration(neighbor)
                log.debug(lambda reparsed=reparsed: reparsed, configuration)
                log.info(lambda name=name: f'\u2713 neighbor  {name.split()[1]}', 'configuration')

        if cmdarg.route:
            log.warning(lambda: 'checking routes', 'configuration')
            if not check_generation(config.neighbors):
                log.critical(
                    lambda configuration=configuration: f'{configuration} has an invalid route', 'configuration'
                )
                sys.exit(1)
            log.info(lambda: '\u2713 routes', 'configuration')


def main():
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__)
    setargs(parser)
    cmdline(parser.parse_args())


if __name__ == '__main__':
    main()
