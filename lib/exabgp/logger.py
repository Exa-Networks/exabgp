# encoding: utf-8
"""
logger.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import print_function

import os
import sys
import stat
import time
import syslog
import logging
import logging.handlers
import pdb
from collections import deque

from exabgp.util.od import od
from exabgp.environment import getenv
from exabgp.environment import APPLICATION


def _can_write(location):
    try:
        s = os.stat(os.path.dirname(location))
    except OSError:
        return None
    mode = s[stat.ST_MODE]
    uid = os.geteuid()
    gid = os.getegid()

    return not not (
        ((s[stat.ST_UID] == uid) and (mode & stat.S_IWUSR))
        or ((s[stat.ST_GID] == gid) and (mode & stat.S_IWGRP))
        or (mode & stat.S_IWOTH)
    )


# This delays the evaluation of the od() function which is expensive
# hence why pylint too-few-public-method is disabled


class LazyFormat(object):
    def __init__(self, prefix, message, formater=od):
        self.prefix = prefix
        self.message = message
        self.formater = formater

    def split(self, char):
        return str(self).split(char)

    def __str__(self):
        formated = self.formater(self.message)
        return '%s (%4d) %s' % (self.prefix, len(self.message), formated)


class LazyAttribute(object):
    def __init__(self, flag, aid, length, data):
        self.flag = flag
        self.aid = aid
        self.length = length
        self.data = data

    def split(self, char):
        return str(self).split(char)

    def __str__(self):
        return 'attribute %-18s flag 0x%02x type 0x%02x len 0x%02x%s' % (
            str(self.aid),
            self.flag,
            int(self.aid),
            self.length,
            ' payload %s' % od(self.data) if self.data else '',
        )


class LazyNLRI(object):
    def __init__(self, afi, safi, addpath, data):
        self.afi = afi
        self.safi = safi
        self.addpath = addpath
        self.data = data

    def split(self, char):
        return str(self).split(char)

    def __str__(self):
        family = '%s %s' % (self.afi, self.safi)
        path = 'with path-information' if self.addpath else 'without path-information'
        payload = od(self.data) if self.data else 'none'
        return 'NLRI      %-18s %-28s payload %s' % (family, path, payload)


def istty(std):
    try:
        return std.isatty()
    except Exception:
        return False


class log(object):
    RECORD = {
        'START': '\033[01;32m',  # Green
        'DEBUG': '',
        'INFO': '\033[01;32m',  # Green
        'NOTICE': '\033[01;34m',  # Blue
        'WARNING': '\033[01;33m',  # Yellow
        'ERR': '\033[01;31m',  # Red
        'CRIT': '\033[00;31m',  # Strong Red
    }

    MESSAGE = {
        'START': '\033[1m',  # Green
        'DEBUG': '',
        'INFO': '\033[1m',  # Green
        'NOTICE': '\033[1m',  # Blue
        'WARNING': '\033[1m',  # Yellow
        'ERR': '\033[1m',  # Red
        'CRIT': '\033[1m',  # Strong Red
    }

    END = '\033[0m'

    TTY = {
        'stderr': lambda: istty(sys.stderr),
        'stdout': lambda: istty(sys.stdout),
        'out': lambda: istty(sys.stdout),
    }

    _instance = dict()
    _syslog = None
    _where = ''

    _history = deque()
    _max_history = 20

    _default = None

    _config = ''
    _pid = os.getpid()
    _cwd = os.getcwd()

    _instance = None

    _short = False
    _level = syslog.LOG_DEBUG

    _option = {
        'pdb': False,
        'reactor': False,
        'daemon': False,
        'processes': False,
        'configuration': False,
        'network': False,
        'wire': False,
        'message': False,
        'rib': False,
        'timer': False,
        'routes': False,
        'parser': False,
    }

    # we use os.pid everytime as we may fork and the class is instance before it

    @classmethod
    def pdb(cls, level):
        if cls._option['pdb'] and level == 'CRIT':
            # not sure why, pylint reports an import error here
            pdb.set_trace()

    @classmethod
    def config(cls, config=None):
        if config is not None:
            cls._config = config
        return cls._config

    @classmethod
    def history(cls):
        return "\n".join(cls._format(*_) for _ in cls._history)

    @classmethod
    def _record(cls, timestamp, message, source, level):
        if len(cls._history) > cls._max_history:
            cls._history.popleft()
        cls._history.append((message, source, level, timestamp))

    @classmethod
    def init(cls):
        env = getenv()

        cls._short = env.log.short
        cls._level = env.log.level

        cls._option = {
            'pdb': env.debug.pdb,
            'reactor': env.log.enable and (env.log.all or env.log.reactor),
            'daemon': env.log.enable and (env.log.all or env.log.daemon),
            'processes': env.log.enable and (env.log.all or env.log.processes),
            'configuration': env.log.enable and (env.log.all or env.log.configuration),
            'network': env.log.enable and (env.log.all or env.log.network),
            'wire': env.log.enable and (env.log.all or env.log.packets),
            'message': env.log.enable and (env.log.all or env.log.message),
            'rib': env.log.enable and (env.log.all or env.log.rib),
            'timer': env.log.enable and (env.log.all or env.log.timers),
            'routes': env.log.enable and (env.log.all or env.log.routes),
            'parser': env.log.enable and (env.log.all or env.log.parser),
        }

        if not env.log.enable:
            cls.destination = ''
            return

        cls.destination = env.log.destination

        cls.restart(True)

    @classmethod
    def _local_syslog(cls):
        if sys.platform == "darwin":
            address = '/var/run/syslog'
        else:
            address = '/dev/log'
        if not os.path.exists(address):
            address = ('localhost', 514)
        handler = logging.handlers.SysLogHandler(address)

        cls._syslog.addHandler(handler)
        return True

    @classmethod
    def _remote_syslog(cls, destination):
        # If the address is invalid, each syslog call will print an error.
        # See how it can be avoided, as the socket error is encapsulated and not returned
        address = (destination, 514)
        handler = logging.handlers.SysLogHandler(address)

        cls._syslog.addHandler(handler)
        return True

    @classmethod
    def _standard(cls, facility):
        handler = logging.StreamHandler(getattr(sys, facility))

        cls._syslog.addHandler(handler)
        return True

    @classmethod
    def _file(cls, destination):
        # folder
        logfile = os.path.realpath(os.path.normpath(os.path.join(cls._cwd, destination)))
        can = _can_write(logfile)
        if can is True:
            handler = logging.handlers.RotatingFileHandler(logfile, maxBytes=5 * 1024 * 1024, backupCount=5)
        elif can is None:
            cls.critical('ExaBGP can not access (perhaps as it does not exist) the log folder provided', 'logger')
            return False
        else:
            cls.critical('ExaBGP does not have the right to write in the requested log directory', 'logger')
            return False

        cls._syslog.addHandler(handler)
        return True

    @classmethod
    def restart(cls, first=False):
        try:
            if first:
                cls._where = 'stdout'
                cls._default = logging.StreamHandler(sys.stdout)
                cls._syslog = logging.getLogger()
                cls._syslog.setLevel(logging.DEBUG)
                cls._syslog.addHandler(cls._default)
                return True
        except IOError:
            # no way to report anything via stdout, silently failing
            return False

        if not cls._syslog:
            # no way to report anything via stdout, silently failing
            return False

        for handler in cls._syslog.handlers:
            cls._syslog.removeHandler(handler)
        cls._syslog.addHandler(cls._default)

        try:
            if cls.destination == 'stderr':
                cls._where = 'stderr'
                return True
            elif cls.destination == 'stdout':
                cls._where = 'out'
                result = cls._standard(cls.destination)
            elif cls.destination in ('', 'syslog'):
                cls._where = 'syslog'
                result = cls._local_syslog()
            elif cls.destination.startswith('host:'):
                cls._where = 'syslog'
                result = cls._remote_syslog(cls.destination[5:].strip())
            else:
                cls._where = 'file'
                result = cls._file(cls.destination)

            if result:
                cls._syslog.removeHandler(cls._default)
            return result
        except IOError:
            cls.critical('Can not set logging (are stdout/stderr closed?)', 'logger')
            return False

    @classmethod
    def _format(cls, message, source, level, timestamp=None):
        if timestamp is None:
            timestamp = time.localtime()
            cls._record(timestamp, message, source, level)

        if cls._short:
            return message

        if cls._where in ['stdout', 'stderr', 'out']:
            now = time.strftime('%H:%M:%S', timestamp)
            if not cls.TTY[cls._where]():
                return "%s | %-6d | %-15s | %s" % (now, cls._pid, source, message)
            return "%s | %-6d | %s%-13s%s | %s%-8s%s" % (
                now,
                cls._pid,
                cls.RECORD.get(level, ''),
                source,
                cls.END,
                cls.MESSAGE.get(level, ''),
                message,
                cls.END,
            )
        elif cls._where in [
            'syslog',
        ]:
            return "%s[%d]: %-13s %s" % (APPLICATION, cls._pid, source, message)
        elif cls._where in [
            'file',
        ]:
            now = time.strftime('%a, %d %b %Y %H:%M:%S', timestamp)
            return "%s %-6d %-13s %s" % (now, cls._pid, source, message)
        else:
            # failsafe
            return "%s | %-8s | %-6d | %-13s | %s" % (now, level, cls._pid, source, message)

    @classmethod
    def _report(cls, message, source, level):
        if source.startswith('incoming-'):
            src = 'wire'
        elif source.startswith('outgoing-'):
            src = 'wire'
        elif source.startswith('ka-'):
            src = 'timer'
        elif source.startswith('peer-'):
            src = 'network'
        else:
            src = source

        log = cls._option.get(src, True) and getattr(syslog, 'LOG_%s' % level) <= cls._level

        if not log:
            return

        for line in message.split('\n'):
            if cls._syslog:
                cls._syslog.debug(cls._format(line, source, level))
            else:
                print(cls._format(line, source, level))
                sys.stdout.flush()

    @classmethod
    def debug(cls, message, source='', level='DEBUG'):
        cls._report(message, source, level)

    @classmethod
    def info(cls, message, source='', level='INFO'):
        cls._report(message, source, level)

    @classmethod
    def notice(cls, message, source='', level='NOTICE'):
        cls._report(message, source, level)

    @classmethod
    def warning(cls, message, source='', level='WARNING'):
        cls._report(message, source, level)

    @classmethod
    def error(cls, message, source='', level='ERR'):
        cls._report(message, source, level)

    @classmethod
    def critical(cls, message, source='', level='CRIT'):
        cls._report(message, source, level)
