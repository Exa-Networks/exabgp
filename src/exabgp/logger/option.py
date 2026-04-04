from __future__ import annotations

import os
import sys
import time

from exabgp.logger.handler import get_logger
from exabgp.logger.format import formater


def echo(_):
    return _


class option:
    logger = None
    formater = echo

    short = False
    level = 'WARNING'
    logit = {}

    cwd = ''

    # where the log should go, stdout, stderr, file, syslog, ...
    destination = ''

    enabled = {
        'pdb': False,
        'reactor': False,
        'daemon': False,
        'processes': False,
        'configuration': False,
        'network': False,
        'statistics': False,
        'wire': False,
        'message': False,
        'rib': False,
        'timer': False,
        'routes': False,
        'parser': False,
    }

    @classmethod
    def _set_level(cls, level):
        cls.level = level

        levels = 'FATAL CRITICAL ERROR WARNING INFO DEBUG NOTSET'
        index = levels.index(level)
        for level in levels.split():
            cls.logit[level] = levels.index(level) <= index

    @classmethod
    def log_enabled(cls, source, level):
        return cls.enabled.get(source, True) and cls.logit.get(level, False)

    @classmethod
    def load(cls, env):
        cls.pid = os.getpid()
        cls.cwd = os.getcwd()

        cls.short = env.log.short

        cls._set_level(env.log.level)

        cls.option = {
            'pdb': env.debug.pdb,
            'reactor': env.log.enable and (env.log.all or env.log.reactor),
            'daemon': env.log.enable and (env.log.all or env.log.daemon),
            'processes': env.log.enable and (env.log.all or env.log.processes),
            'configuration': env.log.enable and (env.log.all or env.log.configuration),
            'network': env.log.enable and (env.log.all or env.log.network),
            'statistics': env.log.enable and (env.log.all or env.log.statistics),
            'wire': env.log.enable and (env.log.all or env.log.packets),
            'message': env.log.enable and (env.log.all or env.log.message),
            'rib': env.log.enable and (env.log.all or env.log.rib),
            'timer': env.log.enable and (env.log.all or env.log.timers),
            'routes': env.log.enable and (env.log.all or env.log.routes),
            'parser': env.log.enable and (env.log.all or env.log.parser),
        }

        destination = env.log.destination

        if destination in ('stdout', 'stderr', 'syslog'):
            cls.destination = destination
        elif destination.startswith('file:'):
            cls.destination = destination[5:]
        else:
            cls.destination = 'stdout'

    @classmethod
    def setup(cls, env):
        cls.load(env)

        # the time is used as we will need to re-init the logger once
        # we have dropped root privileges so that any permission issues
        # can be noticed at start time (and not once we try to rotate file for example)
        now = str(time.time())

        if cls.destination == 'stdout':
            cls.logger = get_logger(
                f'ExaBGP stdout {now}',
                format='%(message)s',
                stream=sys.stderr,
                level=cls.level,
            )
            cls.formater = formater(env.log.short, 'stdout')
            return

        if cls.destination == 'stderr':
            cls.logger = get_logger(
                f'ExaBGP stderr {now}',
                format='%(message)s',
                stream=sys.stderr,
                level=cls.level,
            )
            cls.formater = formater(env.log.short, 'stderr')
            return

        # if cls.destination == 'file':
        #     os.path.realpath(os.path.normpath(os.path.join(cls._cwd, destination)))
        #     _logger = get_logger('ExaBGP file', filename='')
        #     _format = formater(cls.enabled, 'stderr')

        if cls.destination == 'syslog':
            cls.logger = get_logger(
                f'ExaBGP syslog {now}',
                format='%(message)s',
                address='/var/run/syslog' if sys.platform == 'darwin' else '/dev/log',
                level=cls.level,
            )
            cls.formater = formater(env.log.short, 'syslog')

        # need to re-add remote syslog
