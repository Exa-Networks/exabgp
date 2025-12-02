"""exabgp configuration export to JSON"""

from __future__ import annotations

import sys
import argparse

from exabgp.environment import getenv
from exabgp.environment import getconf

from exabgp.configuration.configuration import Configuration
from exabgp.configuration.encoder import config_to_json

from exabgp.debug.intercept import trace_interceptor
from exabgp.logger import log, lazymsg


def setargs(sub: argparse.ArgumentParser) -> None:
    # fmt:off
    sub.add_argument('-o', '--output', help='output file (default: stdout)', type=str, default=None)
    sub.add_argument('-i', '--indent', help='JSON indentation (default: 2)', type=int, default=2)
    sub.add_argument('-p', '--pdb', help='fire the debugger on critical logging, SIGTERM, and exceptions', action='store_true')
    sub.add_argument('configuration', help='configuration file', type=str)
    # fmt:on


def cmdline(cmdarg: argparse.Namespace) -> None:
    env = getenv()

    if cmdarg.pdb:
        env.debug.pdb = True

    log.init(env)
    trace_interceptor(env.debug.pdb)

    configuration = cmdarg.configuration
    log.info(lazymsg('loading {configuration}', configuration=configuration), 'configuration')
    location = getconf(configuration)
    if not location:
        log.critical(
            lazymsg('{configuration} is not an exabgp config file', configuration=configuration), 'configuration'
        )
        sys.exit(1)

    config = Configuration([location])

    if not config.reload():
        log.critical(
            lazymsg('{configuration} is not a valid config file', configuration=configuration), 'configuration'
        )
        log.critical(lazymsg('error: {error}', error=str(config.error)), 'configuration')
        sys.exit(1)

    log.info(lazymsg('export.loading status=success'), 'configuration')

    # Export configuration to JSON
    json_output = config_to_json(config.to_dict(), indent=cmdarg.indent)

    if cmdarg.output:
        with open(cmdarg.output, 'w') as f:
            f.write(json_output)
            f.write('\n')
        log.info(lazymsg('export.written file={output}', output=cmdarg.output), 'configuration')
    else:
        print(json_output)


def main() -> None:
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__)
    setargs(parser)
    cmdline(parser.parse_args())


if __name__ == '__main__':
    main()
