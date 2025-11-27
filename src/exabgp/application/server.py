"""exabgp server"""

from __future__ import annotations

import os
import sys
import time
import signal
import argparse
import platform

from exabgp.debug.intercept import trace_interceptor

# import before the fork to improve copy on write memory savings
from exabgp.reactor.loop import Reactor
from exabgp.configuration.configuration import Configuration

from exabgp.util.dns import warn
from exabgp.logger import log, lazymsg

# this is imported from configuration.setup to make sure it was initialised
from exabgp.environment import getenv
from exabgp.environment import getconf
from exabgp.environment import ENVFILE
from exabgp.environment import ROOT

from exabgp.application.pipe import named_pipe
from exabgp.application.unixsocket import unix_socket
from exabgp.version import version

from exabgp.bgp.message.update.attribute import Attribute


def __exit(memory, code):
    if memory:
        from exabgp.vendoring import objgraph

        sys.stdout.write('memory utilisation\n\n')
        sys.stdout.write(objgraph.show_most_common_types(limit=20))
        sys.stdout.write('\n\n\n')
        sys.stdout.write('generating memory utilisation graph\n\n')
        sys.stdout.write('')
        obj = objgraph.by_type('Reactor')
        objgraph.show_backrefs([obj], max_depth=10)
    sys.exit(code)


def _delayed_signal(delay, signalnum):
    if not delay:
        return

    pid = os.fork()
    if pid:
        # the parent process is the one waiting
        # and sending a signa to the child
        try:
            time.sleep(delay)
            os.kill(pid, signalnum)
        finally:
            try:
                pid, code = os.wait()
            finally:
                sys.exit(code)


def setargs(sub):
    # fmt:off
    sub.add_argument('-v', '--verbose', help='toogle all logging', action='store_true')
    sub.add_argument('-d', '--debug', help='start the python debugger on issue and (implies -v, -p)', action='store_true')
    sub.add_argument('-s', '--signal', help='issue a SIGUSR1 to reload the configuration after <time> seconds, only useful for code debugging', type=int)
    sub.add_argument('-1', '--once', help='only perform one attempt to connect to peers', action='store_true')
    sub.add_argument('-p', '--pdb', help='fire the debugger on critical logging, SIGTERM, and exceptions (shortcut for exabgp.pdb.enable=true)', action='store_true')
    sub.add_argument('-P', '--passive', help='only accept incoming connections', action='store_true')
    sub.add_argument('-m', '--memory', help='display memory usage information on exit', action='store_true')
    sub.add_argument('--profile', help='enable profiling and set where the information should be saved', type=str, default='')
    sub.add_argument('configuration', help='configuration file(s)', nargs='+', type=str)
    # fmt:on


def cmdline(cmdarg):
    if not os.path.isfile(ENVFILE):
        comment = f'environment file missing\ngenerate it using "exabgp env > {ENVFILE}"'
    else:
        comment = ''

    env = getenv()
    # Must be done before setting the logger as it modify its behaviour
    if cmdarg.verbose or cmdarg.debug:
        env.log.all = True
        env.log.level = 'DEBUG'
        env.log.short = False

    if cmdarg.debug or cmdarg.pdb:
        env.debug.pdb = True

    log.init(env)
    trace_interceptor(env.debug.pdb)

    if cmdarg.profile:
        env.profile.enable = True
        env.profile.file = cmdarg.profile

    if cmdarg.once:
        env.tcp.once = True

    if cmdarg.memory:
        env.debug.memory = True

    if env.cache.attributes:
        Attribute.caching = env.cache.attributes

    if cmdarg.passive:
        env.bgp.passive = True

    configurations = []
    for configuration in cmdarg.configuration:
        location = getconf(configuration)
        if not location:
            log.critical(
                lambda configuration=configuration: f'{configuration} is not an exabgp config file',
                'configuration',
            )
            sys.exit(1)
        configurations.append(location)

    delay = cmdarg.signal
    _delayed_signal(delay, signal.SIGUSR1)

    if env.debug.rotate or len(configurations) == 1:
        run(comment, configurations)

    if not (env.log.destination in ('syslog', 'stdout', 'stderr') or env.log.destination.startswith('host:')):
        log.error(lambda: 'can not log to files when running multiple configuration (as we fork)', 'configuration')
        sys.exit(1)

    try:
        # run each configuration in its own process
        pids = []
        for configuration in configurations:
            pid = os.fork()
            if pid == 0:
                run(comment, [configuration], os.getpid())
            else:
                pids.append(pid)

        # If we get a ^C / SIGTERM, ignore just continue waiting for our child process
        signal.signal(signal.SIGINT, signal.SIG_IGN)

        # wait for the forked processes
        for pid in pids:
            os.waitpid(pid, 0)
    except OSError as exc:
        log.critical(
            lazymsg('can not fork, errno {errno} : {strerror}', errno=exc.errno, strerror=exc.strerror), 'reactor'
        )
        sys.exit(1)


def run(comment, configurations, pid=0):
    env = getenv()

    log.info(lambda: 'Thank you for using ExaBGP', 'startup')
    log.debug(lambda: version, 'startup')
    log.debug(lambda: ROOT, 'startup')
    python_version = sys.version.replace('\n', ' ')
    log.debug(lambda: python_version, 'startup')
    platform_info = ' '.join(platform.uname()[:5])
    log.debug(lambda: platform_info, 'startup')

    if comment:
        log.error(lambda: comment, 'startup')

    warning = warn()
    if warning:
        log.warning(lambda: warning, 'startup')

    # Check if socket will be available (check for explicit disable)
    socket_disabled = os.environ.get('exabgp_cli_socket', None) == ''

    # Only check for named pipes if socket is disabled
    if env.api.cli and socket_disabled:
        pipename = 'exabgp' if env.api.pipename is None else env.api.pipename
        pipes = named_pipe(ROOT, pipename)
        if len(pipes) == 1:
            # Pipes found - enable pipe-based CLI process
            pipe = pipes[0]
            os.environ['exabgp_cli_pipe'] = pipe
            os.environ['exabgp_api_pipename'] = pipename

            log.info(lambda: 'named pipes for the cli are:', 'cli')
            log.info(lambda: f'to send commands  {pipe}{pipename}.in', 'cli')
            log.info(lambda: f'to read responses {pipe}{pipename}.out', 'cli')
        else:
            # Socket disabled AND no pipes - show pipe setup instructions
            log.error(
                lambda: f'could not find the named pipes ({pipename}.in and {pipename}.out) required for the cli',
                'cli',
            )
            log.error(lambda: 'we scanned the following folders (the number is your PID):', 'cli')
            for location in pipes:
                log.error(lazymsg(' - {location}', location=location), 'cli')
            log.error(lambda: 'please make them in one of the folder with the following commands:', 'cli')

            # NOTE: Logging full paths (os.getcwd()) is intentional for user guidance
            # Security review: Accepted as necessary for troubleshooting
            log.error(lambda: f'> mkfifo {os.getcwd()}/run/{pipename}.{{in,out}}', 'cli')
            log.error(lambda: f'> chmod 600 {os.getcwd()}/run/{pipename}.{{in,out}}', 'cli')

            if os.getuid() != 0:
                log.error(
                    lambda: f'> chown {os.getuid()}:{os.getgid()} {os.getcwd()}/run/{pipename}.{{in,out}}',
                    'cli',
                )
    elif env.api.cli:
        # Socket enabled - also enable pipes silently if they exist (for dual transport)
        pipename = 'exabgp' if env.api.pipename is None else env.api.pipename
        pipes = named_pipe(ROOT, pipename)
        if len(pipes) == 1:
            pipe = pipes[0]
            os.environ['exabgp_cli_pipe'] = pipe
            os.environ['exabgp_api_pipename'] = pipename
            # Don't log - socket is primary, pipes are bonus

    # Enable Unix socket for CLI (auto-enabled unless explicitly disabled)
    if env.api.cli and not socket_disabled:
        socketname = 'exabgp' if env.api.socketname is None else env.api.socketname
        sockets = unix_socket(ROOT, socketname)

        # Socket is auto-enabled: use existing location if found, otherwise use default
        if len(sockets) == 1:
            # Found existing socket directory
            socket_path = sockets[0]
            log.info(lambda: 'Unix socket for the cli (existing directory):', 'cli')
        else:
            # Use default location (will be auto-created by socket process)
            socket_path = ROOT + '/run/'
            log.info(lambda: 'Unix socket for the cli (will be auto-created):', 'cli')

        os.environ['exabgp_cli_socket'] = socket_path
        os.environ['exabgp_api_socketname'] = socketname
        log.info(lambda: f'socket path: {socket_path}{socketname}.sock', 'cli')

    configuration = Configuration(configurations)

    if not env.profile.enable:
        exit_code = Reactor(configuration).run()
        __exit(env.debug.memory, exit_code)

    import cProfile

    if env.profile.file == 'stdout':
        profiled = 'Reactor(configuration).run()'
        cProfile.run(profiled)
        __exit(env.debug.memory, 0)

    if pid:
        profile_name = f'{env.profile.file}-pid-{pid}'
    else:
        profile_name = env.profile.file

    notice = ''
    if os.path.isdir(profile_name):
        notice = f'profile can not use this filename as output, it is not a directory ({profile_name})'
    if os.path.exists(profile_name):
        notice = f'profile can not use this filename as output, it already exists ({profile_name})'

    if notice:
        log.debug(lambda: '-' * len(notice), 'reactor')
        log.debug(lambda: notice, 'reactor')
        log.debug(lambda: '-' * len(notice), 'reactor')

    cwd = os.getcwd()
    log.debug(lambda: 'profiling ....', 'reactor')

    destination = profile_name if profile_name.startswith('/') else os.path.join(cwd, profile_name)

    with cProfile.Profile() as profiler:
        exit_code = 0
        try:
            exit_code = Reactor(configuration).run()
        except Exception as e:
            exit_code = Reactor.Exit.unknown
            log.critical(lazymsg('{error}', error=str(e)))

        try:
            profiler.dump_stats(destination)
        except OSError:
            notice = 'could not save profiling in formation at: ' + destination
            log.debug(lambda: '-' * len(notice), 'reactor')
            log.debug(lambda: notice, 'reactor')
            log.debug(lambda: '-' * len(notice), 'reactor')

        __exit(env.debug.memory, exit_code)


def main():
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__)
    setargs(parser)
    cmdline(parser.parse_args())


if __name__ == '__main__':
    main()
