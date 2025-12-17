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
from exabgp.logger import log, lazyexc, lazymsg

# this is imported from configuration.setup to make sure it was initialised
from exabgp.environment import getenv
from exabgp.environment import getconf
from exabgp.environment import ENVFILE
from exabgp.environment import ROOT

from exabgp.application.pipe import named_pipe
from exabgp.application.unixsocket import unix_socket
from exabgp.version import version

from exabgp.bgp.message.update.attribute import Attribute


def __exit(memory: bool, code: int) -> None:
    if memory:
        from exabgp.vendoring import objgraph

        sys.stdout.write('memory utilisation\n\n')
        objgraph.show_most_common_types(limit=20)  # Prints directly to stdout
        sys.stdout.write('\n\n\n')
        sys.stdout.write('generating memory utilisation graph\n\n')
        obj = objgraph.by_type('Reactor')
        objgraph.show_backrefs([obj], max_depth=10)
    sys.exit(code)


def _delayed_signal(delay: int | None, signalnum: signal.Signals) -> None:
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


def setargs(sub: argparse.ArgumentParser) -> None:
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


def cmdline(cmdarg: argparse.Namespace) -> None:
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
                lazymsg('config.invalid file={f}', f=configuration),
                'configuration',
            )
            sys.exit(1)
        configurations.append(location)

    delay = cmdarg.signal
    _delayed_signal(delay, signal.SIGUSR1)

    if env.debug.rotate or len(configurations) == 1:
        run(comment, configurations)

    if not (env.log.destination in ('syslog', 'stdout', 'stderr') or env.log.destination.startswith('host:')):
        log.error(lazymsg('config.error reason=multiple_configs_file_log'), 'configuration')
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


def run(comment: str, configurations: list[str], pid: int = 0) -> None:
    env = getenv()

    log.info(lazymsg('startup.banner message=thank_you_for_using_exabgp'), 'startup')
    log.debug(lazymsg('startup.version version={v}', v=version), 'startup')
    log.debug(lazymsg('startup.root path={r}', r=ROOT), 'startup')
    python_version = sys.version.replace('\n', ' ')
    log.debug(lazymsg('startup.python version={v}', v=python_version), 'startup')
    platform_info = ' '.join(platform.uname()[:5])
    log.debug(lazymsg('startup.platform info={p}', p=platform_info), 'startup')

    if comment:
        log.error(lazymsg('startup.comment message={c}', c=comment), 'startup')

    warning = warn()
    if warning:
        log.warning(lazymsg('startup.warning message={w}', w=warning), 'startup')

    # Check if socket will be available (check for explicit disable)
    socket_disabled = os.environ.get('exabgp_cli_socket', None) == ''

    # Only check for named pipes if socket is disabled
    if env.api.cli and socket_disabled:
        pipename = env.api.pipename
        pipes = named_pipe(ROOT, pipename)
        if len(pipes) == 1:
            # Pipes found - enable pipe-based CLI process
            pipe = pipes[0]
            os.environ['exabgp_cli_pipe'] = pipe
            os.environ['exabgp_api_pipename'] = pipename

            log.info(lazymsg('cli.pipes.found'), 'cli')
            log.info(lazymsg('cli.pipes.input path={p}', p=f'{pipe}{pipename}.in'), 'cli')
            log.info(lazymsg('cli.pipes.output path={p}', p=f'{pipe}{pipename}.out'), 'cli')
        else:
            # Socket disabled AND no pipes - show pipe setup instructions
            log.error(
                lazymsg('cli.pipes.missing name={n}', n=pipename),
                'cli',
            )
            log.error(lazymsg('cli.pipes.scanned.folders'), 'cli')
            for location in pipes:
                log.error(lazymsg('cli.pipes.folder path={location}', location=location), 'cli')
            log.error(lazymsg('cli.pipes.create.instructions'), 'cli')

            # NOTE: Logging full paths (os.getcwd()) is intentional for user guidance
            # Security review: Accepted as necessary for troubleshooting
            log.error(lazymsg('cli.pipes.mkfifo path={p}', p=f'{os.getcwd()}/run/{pipename}.{{in,out}}'), 'cli')
            log.error(lazymsg('cli.pipes.chmod path={p}', p=f'{os.getcwd()}/run/{pipename}.{{in,out}}'), 'cli')

            if os.getuid() != 0:
                log.error(
                    lazymsg(
                        'cli.pipes.chown uid={u} gid={g} path={p}',
                        u=os.getuid(),
                        g=os.getgid(),
                        p=f'{os.getcwd()}/run/{pipename}.{{in,out}}',
                    ),
                    'cli',
                )
    elif env.api.cli:
        # Socket enabled - also enable pipes silently if they exist (for dual transport)
        pipename = env.api.pipename
        pipes = named_pipe(ROOT, pipename)
        if len(pipes) == 1:
            pipe = pipes[0]
            os.environ['exabgp_cli_pipe'] = pipe
            os.environ['exabgp_api_pipename'] = pipename
            # Don't log - socket is primary, pipes are bonus

    # Enable Unix socket for CLI (auto-enabled unless explicitly disabled)
    if env.api.cli and not socket_disabled:
        socketname = env.api.socketname
        sockets = unix_socket(ROOT, socketname)

        # Socket is auto-enabled: use existing location if found, otherwise use default
        if len(sockets) == 1:
            # Found existing socket directory
            socket_path = sockets[0]
            log.info(lazymsg('cli.socket.found.existing'), 'cli')
        else:
            # Use default location (will be auto-created by socket process)
            socket_path = ROOT + '/run/'
            log.info(lazymsg('cli.socket.autocreate'), 'cli')

        os.environ['exabgp_cli_socket'] = socket_path
        os.environ['exabgp_api_socketname'] = socketname
        log.info(lazymsg('cli.socket.path path={p}', p=f'{socket_path}{socketname}.sock'), 'cli')

    configuration = Configuration(configurations)

    if not env.profile.enable:
        exit_code = Reactor(configuration).run()
        # Flush any pending log messages before exit
        sys.stdout.flush()
        sys.stderr.flush()
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
        log.debug(lazymsg('profile.error message={m}', m=notice), 'reactor')

    cwd = os.getcwd()
    log.debug(lazymsg('profile.starting'), 'reactor')

    destination = profile_name if profile_name.startswith('/') else os.path.join(cwd, profile_name)

    with cProfile.Profile() as profiler:
        exit_code = 0
        try:
            exit_code = Reactor(configuration).run()
        except Exception as e:
            exit_code = Reactor.Exit.unknown
            log.critical(lazyexc('profile.exception error={exc}', e))

        try:
            profiler.dump_stats(destination)
        except OSError:
            log.debug(lazymsg('profile.save.failed destination={d}', d=destination), 'reactor')

        __exit(env.debug.memory, exit_code)


def main() -> None:
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__)
    setargs(parser)
    cmdline(parser.parse_args())


if __name__ == '__main__':
    main()
