"""exabgp configuration validation"""

from __future__ import annotations

import sys
import argparse
from typing import NoReturn

from exabgp.environment import getenv
from exabgp.environment import getconf

from exabgp.configuration.configuration import Configuration
from exabgp.bgp.neighbor import NeighborTemplate

from exabgp.debug.intercept import trace_interceptor
from exabgp.logger import log, lazymsg

from exabgp.configuration import compare
from exabgp.configuration.check import check_generation


def setargs(sub: argparse.ArgumentParser) -> None:
    # fmt:off
    sub.add_argument('-n', '--neighbor', help='check the parsing of the neighbors', action='store_true')
    sub.add_argument('-r', '--route', help='check the parsing of the routes', action='store_true')
    sub.add_argument('-v', '--verbose', help='be verbose in the display', action='store_true')
    sub.add_argument('-p', '--pdb', help='fire the debugger on critical logging, SIGTERM, and exceptions (shortcut for exabgp.pdb.enable=true)', action='store_true')
    sub.add_argument('--parser', help='the configuration parser to use, or both to compare them (development)', choices=compare.PARSERS, default=compare.LEGACY)
    sub.add_argument('configuration', help='configuration file(s)', nargs='+', type=str)
    # fmt:on


def cmdline(cmdarg: argparse.Namespace) -> None:
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
        log.info(lazymsg('loading {configuration}', configuration=configuration), 'configuration')
        location = getconf(configuration)
        if not location:
            msg = f'{configuration} is not an exabgp config file (file not found)'
            log.critical(lazymsg('{msg}', msg=msg), 'configuration')
            sys.stderr.write(f'error: {msg}\n')
            sys.exit(1)

        config = _load(configuration, location, cmdarg.parser)
        log.info(lazymsg('validate.loading status=success'), 'configuration')

        if cmdarg.neighbor:
            log.warning(lazymsg('validate.checking type=neighbors'), 'configuration')
            for name, neighbor in config.neighbors.items():
                reparsed = NeighborTemplate.configuration(neighbor)
                log.debug(lazymsg('{reparsed}', reparsed=reparsed), configuration)
                log.info(lazymsg('\u2713 neighbor  {neighbor_name}', neighbor_name=name.split()[1]), 'configuration')

        if cmdarg.route:
            log.warning(lazymsg('validate.checking type=routes'), 'configuration')
            if not check_generation(config.neighbors):
                log.critical(
                    lazymsg('{configuration} has an invalid route', configuration=configuration), 'configuration'
                )
                sys.exit(1)
            log.info(lazymsg('validate.routes status=success'), 'configuration')


def _fail(msg: str) -> NoReturn:
    log.critical(lazymsg('{msg}', msg=msg), 'configuration')
    sys.stderr.write(f'error: {msg}\n')
    sys.exit(1)


def _load(configuration: str, location: str, parser: str) -> Configuration:
    """Read the configuration with the parser asked for, or with both and require they agree."""
    if parser == compare.LEGACY:
        config = Configuration([location])
        if not config.reload():
            _fail(f'{configuration} is not a valid config file: {config.error!s}')
        return config

    outcome, grammar = compare.grammar_file(location)
    if parser == compare.BOTH:
        legacy_outcome, _ = compare.legacy_file(location)
        difference = compare.difference(legacy_outcome, outcome)
        if difference:
            _fail(f'{configuration} is read differently by the two parsers: {difference}')
    if isinstance(outcome, compare.Rejected):
        _fail(f'{configuration} is not a valid config file: {outcome.message}')
    return grammar


def main() -> None:
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__)
    setargs(parser)
    cmdline(parser.parse_args())


if __name__ == '__main__':
    main()
