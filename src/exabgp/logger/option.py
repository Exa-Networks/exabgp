from __future__ import annotations

import os
import sys
import time
from typing import ClassVar, Dict, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from exabgp.environment.environment import Env

from exabgp.logger.handler import get_logger
from exabgp.logger.format import formater as get_formater, FormatterFunc


def echo(message: str, source: str, level: str, timestamp: time.struct_time) -> str:
    """Fallback formatter that just returns the message unchanged"""
    return message


class option:
    logger: ClassVar[logging.Logger | None] = None
    # Formatter function - either a proper formatter or the echo fallback
    formater: ClassVar[FormatterFunc] = echo

    short: ClassVar[bool] = False
    level: ClassVar[str] = 'WARNING'
    logit: ClassVar[Dict[str, bool]] = {}

    pid: ClassVar[int]  # Set in load()
    cwd: ClassVar[str] = ''

    # where the log should go, stdout, stderr, file, syslog, ...
    destination: ClassVar[str] = ''

    option: ClassVar[Dict[str, bool]]  # Set in load()

    enabled: ClassVar[Dict[str, bool]] = {
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
        # Additional categories
        'startup': False,
        'cli': False,
        'api': False,
    }

    @classmethod
    def _set_level(cls, level: str) -> None:
        cls.level = level

        levels = 'FATAL CRITICAL ERROR WARNING INFO DEBUG NOTSET'
        index = levels.index(level)
        for level in levels.split():
            cls.logit[level] = levels.index(level) <= index

    @classmethod
    def log_enabled(cls, source: str, level: str) -> bool:
        return cls.enabled.get(source, True) and cls.logit.get(level, False)

    @classmethod
    def load(cls, env: 'Env') -> None:
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
            # Additional categories - always enabled when logging enabled
            'startup': env.log.enable,
            'cli': env.log.enable,
            'api': env.log.enable,
        }

        destination = env.log.destination

        if destination in ('stdout', 'stderr', 'syslog'):
            cls.destination = destination
        elif destination.startswith('file:'):
            cls.destination = destination[5:]
        else:
            cls.destination = 'stdout'

    @classmethod
    def setup(cls, env: 'Env') -> None:
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
            fmt = get_formater(env.log.short, 'stdout')
            cls.formater = fmt if fmt else echo
            return

        if cls.destination == 'stderr':
            cls.logger = get_logger(
                f'ExaBGP stderr {now}',
                format='%(message)s',
                stream=sys.stderr,
                level=cls.level,
            )
            fmt = get_formater(env.log.short, 'stderr')
            cls.formater = fmt if fmt else echo
            return

        # if cls.destination == 'file':
        #     os.path.realpath(os.path.normpath(os.path.join(cls._cwd, destination)))
        #     _logger = get_logger('ExaBGP file', filename='')
        #     _format = get_formater(cls.enabled, 'stderr')

        if cls.destination == 'syslog':
            cls.logger = get_logger(
                f'ExaBGP syslog {now}',
                format='%(message)s',
                address='/var/run/syslog' if sys.platform == 'darwin' else '/dev/log',
                level=cls.level,
            )
            fmt = get_formater(env.log.short, 'syslog')
            cls.formater = fmt if fmt else echo

        # need to re-add remote syslog
