# encoding: utf-8

"""exabgp server"""

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
from exabgp.logger import log

# this is imported from configuration.setup to make sure it was initialised
from exabgp.environment import getenv
from exabgp.environment import getconf
from exabgp.environment import ENVFILE
from exabgp.environment import ROOT

from exabgp.application.pipe import named_pipe
from exabgp.version import version

from exabgp.bgp.message.update.attribute import Attribute


def __exit(memory, code):
    if memory:
        from exabgp.vendoring import objgraph

        sys.stdout.write('memory utilisation\n\n')
        sys.stdout.write(objgraph.show_most_common_types(limit=20))
        sys.stdout.write('\n\n\n')
        sys.stdout.write('generating memory utilisation graph\n\n')
        sys.stdout.write()
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
        comment = 'environment file missing\ngenerate it using "exabgp env > %s"' % ENVFILE
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
            log.critical(f'{configuration} is not an exabgp config file', 'configuration')
            sys.exit(1)
        configurations.append(location)

    delay = cmdarg.signal
    _delayed_signal(delay, signal.SIGUSR1)

    if env.debug.rotate or len(configurations) == 1:
        run(comment, configurations)

    if not (env.log.destination in ('syslog', 'stdout', 'stderr') or env.log.destination.startswith('host:')):
        log.error('can not log to files when running multiple configuration (as we fork)', 'configuration')
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
        log.critical('can not fork, errno %d : %s' % (exc.errno, exc.strerror), 'reactor')
        sys.exit(1)


def run(comment, configurations, pid=0):
    env = getenv()

    log.info('Thank you for using ExaBGP', 'welcome')
    log.debug('%s' % version, 'version')
    log.debug('%s' % ROOT, 'location')
    log.debug('%s' % sys.version.replace('\n', ' '), 'python')
    log.debug('%s' % ' '.join(platform.uname()[:5]), 'platform')

    if comment:
        log.error(comment, 'advice')

    warning = warn()
    if warning:
        log.warning(warning, 'advice')

    if env.api.cli:
        pipename = 'exabgp' if env.api.pipename is None else env.api.pipename
        pipes = named_pipe(ROOT, pipename)
        if len(pipes) != 1:
            env.api.cli = False
            log.error(
                'could not find the named pipes (%s.in and %s.out) required for the cli' % (pipename, pipename), 'cli'
            )
            log.error('we scanned the following folders (the number is your PID):', 'cli')
            for location in pipes:
                log.error(' - %s' % location, 'cli control')
            log.error('please make them in one of the folder with the following commands:', 'cli control')
            log.error('> mkfifo %s/run/%s.{in,out}' % (os.getcwd(), pipename), 'cli control')
            log.error('> chmod 600 %s/run/%s.{in,out}' % (os.getcwd(), pipename), 'cli control')
            if os.getuid() != 0:
                log.error(
                    '> chown %d:%d %s/run/%s.{in,out}' % (os.getuid(), os.getgid(), os.getcwd(), pipename),
                    'cli control',
                )
        else:
            pipe = pipes[0]
            os.environ['exabgp_cli_pipe'] = pipe
            os.environ['exabgp_api_pipename'] = pipename

            log.info('named pipes for the cli are:', 'cli control')
            log.info('to send commands  %s%s.in' % (pipe, pipename), 'cli control')
            log.info('to read responses %s%s.out' % (pipe, pipename), 'cli control')

    configuration = Configuration(configurations)

    if not env.profile.enable:
        exit_code = Reactor(configuration).run()
        __exit(env.debug.memory, exit_code)

    import cProfile

    if env.profile.file == 'stdout':
        profiled = 'Reactor(configuration).run()'
        exit_code = cProfile.run(profiled)
        __exit(env.debug.memory, exit_code)

    if pid:
        profile_name = '%s-pid-%d' % (env.profile.file, pid)
    else:
        profile_name = env.profile.file

    notice = ''
    if os.path.isdir(profile_name):
        notice = 'profile can not use this filename as output, it is not a directory (%s)' % profile_name
    if os.path.exists(profile_name):
        notice = 'profile can not use this filename as output, it already exists (%s)' % profile_name

    if notice:
        log.debug('-' * len(notice), 'reactor')
        log.debug(notice, 'reactor')
        log.debug('-' * len(notice), 'reactor')

    cwd = os.getcwd()
    log.debug('profiling ....', 'reactor')

    destination = profile_name if profile_name.startswith('/') else os.path.join(cwd, profile_name)

    with cProfile.Profile() as profiler:
        exit_code = 0
        try:
            exit_code = Reactor(configuration).run()
        except Exception as e:
            exit_code = Reactor.Exit.unknown
            log.critical(str(e))

        try:
            profiler.dump_stats(destination)
        except Exception:
            notice = 'could not save profiling in formation at: ' + destination
            log.debug('-' * len(notice), 'reactor')
            log.debug(notice, 'reactor')
            log.debug('-' * len(notice), 'reactor')

        __exit(env.debug.memory, exit_code)


def main():
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__)
    setargs(parser)
    cmdline(parser, parser.parse_args())


if __name__ == '__main__':
    main()
