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
from exabgp.configuration.environment import environment


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
    except KeyboardInterrupt:
        raise
    except Exception:
        return False


class Logger(object):
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

    def __new__(cls):
        if cls._instance.get('class', None) is None:
            return super(Logger, cls).__new__(cls)
        else:
            return cls._instance['class']

    # we use os.pid everytime as we may fork and the class is instance before it

    def pdb(self, level):
        if self._option['pdb'] and level == 'CRIT':
            # not sure why, pylint reports an import error here
            pdb.set_trace()

    def config(self, config=None):
        if config is not None:
            self._config = config
        return self._config

    def history(self):
        return "\n".join(self._format(*_) for _ in self._history)

    def _record(self, timestamp, message, source, level):
        if len(self._history) > self._max_history:
            self._history.popleft()
        self._history.append((message, source, level, timestamp))

    def __init__(self):
        if self._instance.get('class', None) is not None:
            return

        self._instance['class'] = self

        command = environment.settings()
        self.short = command.log.short
        self.level = command.log.level

        self._option = {
            'pdb': command.debug.pdb,
            'reactor': command.log.enable and (command.log.all or command.log.reactor),
            'daemon': command.log.enable and (command.log.all or command.log.daemon),
            'processes': command.log.enable and (command.log.all or command.log.processes),
            'configuration': command.log.enable and (command.log.all or command.log.configuration),
            'network': command.log.enable and (command.log.all or command.log.network),
            'wire': command.log.enable and (command.log.all or command.log.packets),
            'message': command.log.enable and (command.log.all or command.log.message),
            'rib': command.log.enable and (command.log.all or command.log.rib),
            'timer': command.log.enable and (command.log.all or command.log.timers),
            'routes': command.log.enable and (command.log.all or command.log.routes),
            'parser': command.log.enable and (command.log.all or command.log.parser),
        }

        if not command.log.enable:
            self.destination = ''
            return

        self.destination = command.log.destination

        self.restart(True)

    def _local_syslog(self):
        if sys.platform == "darwin":
            address = '/var/run/syslog'
        else:
            address = '/dev/log'
        if not os.path.exists(address):
            address = ('localhost', 514)
        handler = logging.handlers.SysLogHandler(address)

        self._syslog.addHandler(handler)
        return True

    def _remote_syslog(self, destination):
        # If the address is invalid, each syslog call will print an error.
        # See how it can be avoided, as the socket error is encapsulated and not returned
        address = (destination, 514)
        handler = logging.handlers.SysLogHandler(address)

        self._syslog.addHandler(handler)
        return True

    def _standard(self, facility):
        handler = logging.StreamHandler(getattr(sys, facility))

        self._syslog.addHandler(handler)
        return True

    def _file(self, destination):
        # folder
        logfile = os.path.realpath(os.path.normpath(os.path.join(self._cwd, destination)))
        can = _can_write(logfile)
        if can is True:
            handler = logging.handlers.RotatingFileHandler(logfile, maxBytes=5 * 1024 * 1024, backupCount=5)
        elif can is None:
            self.critical('ExaBGP can not access (perhaps as it does not exist) the log folder provided', 'logger')
            return False
        else:
            self.critical('ExaBGP does not have the right to write in the requested log directory', 'logger')
            return False

        self._syslog.addHandler(handler)
        return True

    def restart(self, first=False):
        try:
            if first:
                self._where = 'stdout'
                self._default = logging.StreamHandler(sys.stdout)
                self._syslog = logging.getLogger()
                self._syslog.setLevel(logging.DEBUG)
                self._syslog.addHandler(self._default)
                return True
        except IOError:
            # no way to report anything via stdout, silently failing
            return False

        if not self._syslog:
            # no way to report anything via stdout, silently failing
            return False

        for handler in self._syslog.handlers:
            self._syslog.removeHandler(handler)
        self._syslog.addHandler(self._default)

        try:
            if self.destination == 'stderr':
                self._where = 'stderr'
                return True
            elif self.destination == 'stdout':
                self._where = 'out'
                result = self._standard(self.destination)
            elif self.destination in ('', 'syslog'):
                self._where = 'syslog'
                result = self._local_syslog()
            elif self.destination.startswith('host:'):
                self._where = 'syslog'
                result = self._remote_syslog(self.destination[5:].strip())
            else:
                self._where = 'file'
                result = self._file(self.destination)

            if result:
                self._syslog.removeHandler(self._default)
            return result
        except IOError:
            self.critical('Can not set logging (are stdout/stderr closed?)', 'logger')
            return False

    def _format(self, message, source, level, timestamp=None):
        if timestamp is None:
            timestamp = time.localtime()
            self._record(timestamp, message, source, level)

        if self.short:
            return message

        if self._where in ['stdout', 'stderr', 'out']:
            now = time.strftime('%H:%M:%S', timestamp)
            if not self.TTY[self._where]():
                return "%s | %-6d | %-15s | %s" % (now, self._pid, source, message)
            return "%s | %-6d | %s%-13s%s | %s%-8s%s" % (
                now,
                self._pid,
                self.RECORD.get(level, ''),
                source,
                self.END,
                self.MESSAGE.get(level, ''),
                message,
                self.END,
            )
        elif self._where in [
            'syslog',
        ]:
            return "%s[%d]: %-13s %s" % (environment.application, self._pid, source, message)
        elif self._where in [
            'file',
        ]:
            now = time.strftime('%a, %d %b %Y %H:%M:%S', timestamp)
            return "%s %-6d %-13s %s" % (now, self._pid, source, message)
        else:
            # failsafe
            return "%s | %-8s | %-6d | %-13s | %s" % (now, level, self._pid, source, message)

    def _report(self, message, source, level):
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

        log = self._option.get(src, True) and getattr(syslog, 'LOG_%s' % level) <= self.level

        if not log:
            return

        for line in message.split('\n'):
            if self._syslog:
                self._syslog.debug(self._format(line, source, level))
            else:
                print(self._format(line, source, level))
                sys.stdout.flush()

    def debug(self, message, source='', level='DEBUG'):
        self._report(message, source, level)

    def info(self, message, source='', level='INFO'):
        self._report(message, source, level)

    def notice(self, message, source='', level='NOTICE'):
        self._report(message, source, level)

    def warning(self, message, source='', level='WARNING'):
        self._report(message, source, level)

    def error(self, message, source='', level='ERR'):
        self._report(message, source, level)

    def critical(self, message, source='', level='CRIT'):
        self._report(message, source, level)


class FakeLogger(object):
    def __getattr__(self, name):
        def printf(data, _=None):
            sys.stdout.write('Fake logger [%s]\n' % str(data))

        return printf
