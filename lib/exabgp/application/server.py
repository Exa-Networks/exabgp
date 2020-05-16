# encoding: utf-8

"""exabgp server"""


import os
import sys
import syslog
import argparse
import platform

from exabgp.debug import setup_report

# import before the fork to improve copy on write memory savings
from exabgp.reactor.loop import Reactor

from exabgp.util.dns import warn
from exabgp.logger import log

# this is imported from configuration.setup to make sure it was initialised
from exabgp.environment import getenv
from exabgp.environment import ENVFILE
from exabgp.environment import ROOT
from exabgp.environment import ETC

from exabgp.application.pipe import named_pipe
from exabgp.version import version


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


def args(sub):
    # fmt:off
    sub.add_argument('-t', '--test', help='perform a configuration validity check only', action='store_true')
    sub.add_argument('-d', '--debug', help='start the python debugger on serious logging and on SIGTERM (shortcut for exabgp.log.all=true exabgp.log.level=DEBUG)', action='store_true')
    sub.add_argument('-s', '--signal', help='issue a SIGUSR1 to reload the configuration after <time> seconds, only useful for code debugging', type=int)
    sub.add_argument('-v', '--validate', help='validate the configuration file format only', action='store_true')
    sub.add_argument('-1', '--once', help='only perform one attempt to connect to peers', action='store_true')
    sub.add_argument('-p', '--pdb', help='fire the debugger on critical logging, SIGTERM, and exceptions (shortcut for exabgp.pdb.enable=true)', action='store_true')
    sub.add_argument('-m', '--memory', help='display memory usage information on exit', action='store_true')
    sub.add_argument('--profile', help='enable profiling (shortcut for exabgp.profile.enable=true exabgp.profile.file=PROFILE)', type=int)
    sub.add_argument('configuration', help='configuration file(s)', nargs='+', type=str)
    # fmt:on


def cmdline(cmdarg):
    if not os.path.isfile(ENVFILE):
        comment = 'environment file missing\ngenerate it using "exabgp env --fi > %s"' % ENVFILE
    else:
        comment = ''

    env = getenv()
    # Must be done before setting the logger as it modify its behaviour
    if cmdarg.debug:
        env.log.all = True
        env.log.level = syslog.LOG_DEBUG

    log.init()

    duration = cmdarg.signal
    if duration and duration.isdigit():
        pid = os.fork()
        if pid:
            import time
            import signal

            try:
                time.sleep(int(duration))
                os.kill(pid, signal.SIGUSR1)
            except KeyboardInterrupt:
                pass
            try:
                pid, code = os.wait()
                sys.exit(code)
            except KeyboardInterrupt:
                try:
                    pid, code = os.wait()
                    sys.exit(code)
                except Exception:
                    sys.exit(0)

    if cmdarg.profile:
        env.profile.enable = True
        if cmdarg.profile.lower() in ['1', 'true']:
            env.profile.file = True
        elif cmdarg.profile.lower() in ['0', 'false']:
            env.profile.file = False
        else:
            env.profile.file = cmdarg.profile

    if cmdarg.once:
        env.tcp.once = True

    if cmdarg.pdb:
        env.debug.pdb = True

    if cmdarg.test:
        env.debug.selfcheck = True
        env.log.parser = True

    if cmdarg.memory:
        env.debug.memory = True

    configurations = []
    # check the file only once that we have parsed all the command line options and allowed them to run
    for f in cmdarg.configuration:
        # some users are using symlinks for atomic change of the configuration file
        # using mv may however be better practice :p
        normalised = os.path.realpath(os.path.normpath(f))
        target = os.path.realpath(normalised)
        if os.path.isfile(target):
            configurations.append(normalised)
            continue
        if f.startswith('etc/exabgp'):
            normalised = os.path.join(ETC, f[11:])
            if os.path.isfile(normalised):
                configurations.append(normalised)
                continue

        log.debug('one of the arguments passed as configuration is not a file (%s)' % f, 'configuration')
        sys.exit(1)

    from exabgp.bgp.message.update.attribute import Attribute

    Attribute.caching = env.cache.attributes

    if env.debug.rotate or len(configurations) == 1:
        run(comment, configurations, cmdarg.validate)

        log.error('can not log to files when running multiple configuration (as we fork)', 'configuration')
        sys.exit(1)

    try:
        # run each configuration in its own process
        pids = []
        for configuration in configurations:
            pid = os.fork()
            if pid == 0:
                run(comment, [configuration], cmdarg.validate, os.getpid())
            else:
                pids.append(pid)

        # If we get a ^C / SIGTERM, ignore just continue waiting for our child process
        import signal

        signal.signal(signal.SIGINT, signal.SIG_IGN)

        # wait for the forked processes
        for pid in pids:
            os.waitpid(pid, 0)
    except OSError as exc:
        log.critical('can not fork, errno %d : %s' % (exc.errno, exc.strerror), 'reactor')
        sys.exit(1)


def run(comment, configurations, validate, pid=0):
    env = getenv()

    log.notice('Thank you for using ExaBGP', 'welcome')
    log.notice('%s' % version, 'version')
    log.notice('%s' % sys.version.replace('\n', ' '), 'interpreter')
    log.notice('%s' % ' '.join(platform.uname()[:5]), 'os')
    log.notice('%s' % ROOT, 'installation')

    if comment:
        log.notice(comment, 'advice')

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

    if not env.profile.enable:
        exit_code = Reactor(configurations).run(validate, ROOT)
        __exit(env.debug.memory, exit_code)

    try:
        import cProfile as profile
    except ImportError:
        import profile

    if env.profile.file == 'stdout':
        profiled = 'Reactor(%s).run(%s,"%s")' % (str(configurations), str(validate), str(ROOT))
        exit_code = profile.run(profiled)
        __exit(env.debug.memory, exit_code)

    if pid:
        profile_name = "%s-pid-%d" % (env.profile.file, pid)
    else:
        profile_name = env.profile.file

    notice = ''
    if os.path.isdir(profile_name):
        notice = 'profile can not use this filename as output, it is not a directory (%s)' % profile_name
    if os.path.exists(profile_name):
        notice = 'profile can not use this filename as output, it already exists (%s)' % profile_name

    if not notice:
        cwd = os.getcwd()
        log.debug('profiling ....', 'reactor')
        profiler = profile.Profile()
        profiler.enable()
        try:
            exit_code = Reactor(configurations).run(validate, ROOT)
        except Exception:
            exit_code = Reactor.Exit.unknown
            raise
        finally:
            from exabgp.vendoring import lsprofcalltree

            profiler.disable()
            kprofile = lsprofcalltree.KCacheGrind(profiler)
            try:
                destination = profile_name if profile_name.startswith('/') else os.path.join(cwd, profile_name)
                with open(destination, 'w+') as write:
                    kprofile.output(write)
            except IOError:
                notice = 'could not save profiling in formation at: ' + destination
                log.debug("-" * len(notice), 'reactor')
                log.debug(notice, 'reactor')
                log.debug("-" * len(notice), 'reactor')
            __exit(env.debug.memory, exit_code)
    else:
        log.debug("-" * len(notice), 'reactor')
        log.debug(notice, 'reactor')
        log.debug("-" * len(notice), 'reactor')
        Reactor(configurations).run(validate, ROOT)
        __exit(env.debug.memory, 1)


def main():
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__)
    args(parser)
    setup_report()
    cmdline(parser, parser.parse_args())


if __name__ == '__main__':
    main()
