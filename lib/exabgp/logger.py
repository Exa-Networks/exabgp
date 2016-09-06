# encoding: utf-8
"""
utils.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

# pylint: disable=too-few-public-methods,star-args,import-error

import os
import sys
import stat
import time
import syslog
import logging
import logging.handlers

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.util.od import od
from exabgp.util.hashtable import HashTable
from exabgp.configuration.environment import environment

_SHORT = {
	'CRITICAL': 'CRIT',
	'ERROR': 'ERR'
}

_LONG = {
	'CRIT': 'CRITICAL',
	'ERR': 'ERROR'
}


def short (name):
	return _SHORT.get(name.upper(),name.upper())


def _can_write (location):
	try:
		s  = os.stat(os.path.dirname(location))
	except OSError:
		return None
	mode = s[stat.ST_MODE]
	uid  = os.geteuid()
	gid  = os.getegid()

	return not not (
		((s[stat.ST_UID] == uid) and (mode & stat.S_IWUSR)) or
		((s[stat.ST_GID] == gid) and (mode & stat.S_IWGRP)) or
		(mode & stat.S_IWOTH)
	)


# This delays the evaluation of the od() function which is expensive
# hence why pylint too-few-public-method is disabled

class LazyFormat (object):
	def __init__ (self, prefix, message, formater=od):
		self.prefix = prefix
		self.message = message
		self.formater = formater

	def split (self, char):
		return str(self).split(char)

	def __str__ (self):
		formated = self.formater(self.message)
		return '%s (%4d) %s' % (self.prefix,len(self.message),formated)


class LazyAttribute (object):
	def __init__ (self, flag, aid, length, data):
		self.flag = flag
		self.aid = aid
		self.length = length
		self.data = data

	def split (self, char):
		return str(self).split(char)

	def __str__ (self):
		return 'attribute %-18s flag 0x%02x type 0x%02x len 0x%02x%s' % (
			str(self.aid),
			self.flag,
			int(self.aid),
			self.length,
			' payload %s' % od(self.data) if self.data else ''
		)


class LazyNLRI (object):
	def __init__ (self, afi, safi, addpath, data):
		self.afi = afi
		self.safi = safi
		self.addpath = addpath
		self.data = data

	def split (self, char):
		return str(self).split(char)

	def __str__ (self):
		family = '%s %s' % (AFI(self.afi),SAFI(self.safi))
		path = 'with path-information' if self.addpath else 'without path-information'
		payload = od(self.data) if self.data else 'none'
		return 'NLRI      %-18s %-28s payload %s' % (family,path,payload)


class Logger (object):
	_instance = dict()
	_syslog = None
	_where = ''

	_history = []
	_max_history = 20

	_default = None

	_config = ''
	_pid = os.getpid()
	_cwd = os.getcwd()

	def __new__ (cls):
		if cls._instance.get('class',None) is None:
			return super(Logger, cls).__new__(cls)
		else:
			return cls._instance['class']

	# we use os.pid everytime as we may fork and the class is instance before it

	def pdb (self, level):
		if self._option.pdb and level in ['CRITICAL','critical']:
			# not sure why, pylint reports an import error here
			from pdb import set_trace
			set_trace()

	def config (self, config=None):
		if config is not None:
			self._config = config
		return self._config

	def history (self):
		return "\n".join(self._format(*_) for _ in self._history)

	def _record (self, timestamp, level, source, message):
		if len(self._history) > self._max_history:
			self._history.pop(0)
		self._history.append((timestamp,level,source,message))

	def _format (self, timestamp, level, source, message):
		if self.short:
			return message
		now = time.strftime('%a, %d %b %Y %H:%M:%S',timestamp)
		if self._where in ['stderr','stdout']:
			return "%s | %-8s | %-6d | %-13s | %s" % (now,level,self._pid,source,message)
		elif self._where in ['syslog',]:
			return "%s[%d]: %-13s %s" % (environment.application,self._pid,source,message)
		elif self._where in ['file',]:
			return "%s %-6d %-13s %s" % (now,self._pid,source,message)
		else:
			# failsafe
			return "%s | %-8s | %-6d | %-13s | %s" % (now,level,self._pid,source,message)

	def _prefixed (self, level, source, message):
		timestamp = time.localtime()
		level = _LONG.get(level,level)
		self._record(timestamp,level,source,message)
		return self._format(timestamp,level,source,message)

	def __init__ (self):
		if self._instance.get('class',None) is not None:
			return

		self._instance['class'] = self

		command = environment.settings()
		self.short = command.log.short
		self.level = command.log.level

		self._option = HashTable()
		self._option.pdb           = command.debug.pdb
		self._option.reactor       = command.log.enable and (command.log.all or command.log.reactor)
		self._option.daemon        = command.log.enable and (command.log.all or command.log.daemon)
		self._option.processes     = command.log.enable and (command.log.all or command.log.processes)
		self._option.configuration = command.log.enable and (command.log.all or command.log.configuration)
		self._option.network       = command.log.enable and (command.log.all or command.log.network)
		self._option.wire          = command.log.enable and (command.log.all or command.log.packets)
		self._option.message       = command.log.enable and (command.log.all or command.log.message)
		self._option.rib           = command.log.enable and (command.log.all or command.log.rib)
		self._option.timer         = command.log.enable and (command.log.all or command.log.timers)
		self._option.routes        = command.log.enable and (command.log.all or command.log.routes)
		self._option.parser        = command.log.enable and (command.log.all or command.log.parser)

		if not command.log.enable:
			self.destination = ''
			return

		self.destination = command.log.destination

		self.restart(True)

	def _local_syslog (self):
		if sys.platform == "darwin":
			address = '/var/run/syslog'
		else:
			address = '/dev/log'
		if not os.path.exists(address):
			address = ('localhost', 514)
		handler = logging.handlers.SysLogHandler(address)

		self._syslog.addHandler(handler)
		return True

	def _remote_syslog (self, destination):
		# If the address is invalid, each syslog call will print an error.
		# See how it can be avoided, as the socket error is encapsulated and not returned
		address = (destination, 514)
		handler = logging.handlers.SysLogHandler(address)

		self._syslog.addHandler(handler)
		return True

	def _standard (self, facility):
		handler = logging.StreamHandler(getattr(sys,facility))

		self._syslog.addHandler(handler)
		return True

	def _file (self, destination):
		# folder
		logfile = os.path.realpath(os.path.normpath(os.path.join(self._cwd,destination)))
		can = _can_write(logfile)
		if can is True:
			handler = logging.handlers.RotatingFileHandler(logfile, maxBytes=5*1024*1024, backupCount=5)
		elif can is None:
			self.critical('ExaBGP can not access (perhaps as it does not exist) the log folder provided','logger')
			return False
		else:
			self.critical('ExaBGP does not have the right to write in the requested log directory','logger')
			return False

		self._syslog.addHandler(handler)
		return True

	def restart (self, first=False):
		try:
			if first:
				self._where = 'stderr'
				self._default = logging.StreamHandler(sys.stderr)
				self._syslog = logging.getLogger()
				self._syslog.setLevel(logging.DEBUG)
				self._syslog.addHandler(self._default)
				return True
		except IOError:
			# no way to report anything via stderr, silently failing
			return False

		if not self._syslog:
			# no way to report anything via stderr, silently failing
			return False

		for handler in self._syslog.handlers:
			self._syslog.removeHandler(handler)
		self._syslog.addHandler(self._default)

		try:
			if self.destination in ('stderr',):
				self._where = 'stderr'
				return True
			elif self.destination in ('stdout'):
				self._where = 'out'
				result = self._standard(self.destination)
			elif self.destination in ('','syslog'):
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
			self.critical('Can not set logging (are stdout/stderr closed?)','logger')
			return False

	def report (self, message, source='',level=''):
		for line in message.split('\n'):
			if self._syslog:
				self._syslog.debug(self._prefixed(level,source,line))
			else:
				print self._prefixed(level,source,line)
				sys.stdout.flush()

	def debug (self, message, source='', level='debug'):
		self.report(message,source,level)

	def info (self, message, source='', level='info'):
		self.report(message,source,level)

	def warning (self, message, source='', level='warning'):
		self.report(message,source,level)

	def error (self, message, source='', level='error'):
		self.report(message,source,level)

	def critical (self, message, source='', level='critical'):
		self.report(message,source,level)

	def raw (self, message):
		for line in message.split('\n'):
			if self._syslog:
				self._syslog.critical(line)
			else:
				print line
				sys.stdout.flush()

	# show the message on the wire
	def network (self, message, recorder='info'):
		level = short(recorder)
		if self._option.network and getattr(syslog,'LOG_%s' % level) <= self.level:
			getattr(self,recorder)(message,'network',level)
		else:
			self._record(time.localtime(),'network',recorder,message)
		self.pdb(recorder)

	# show the message on the wire
	def wire (self, message, recorder='debug'):
		level = short(recorder)
		if self._option.wire and getattr(syslog,'LOG_%s' % level) <= self.level:
			getattr(self,recorder)(message,'wire',level)
		else:
			self._record(time.localtime(),'wire',recorder,message)
		self.pdb(recorder)

	# show the exchange of message between peers
	def message (self, message, recorder='info'):
		level = short(recorder)
		if self._option.message and getattr(syslog,'LOG_%s' % level) <= self.level:
			getattr(self,recorder)(message,'message',level)
		else:
			self._record(time.localtime(),'message',recorder,message)
		self.pdb(recorder)

	# show the parsing of the configuration
	def configuration (self, message, recorder='info'):
		level = short(recorder)
		if self._option.configuration and getattr(syslog,'LOG_%s' % level) <= self.level:
			getattr(self,recorder)(message,'configuration',level)
		else:
			self._record(time.localtime(),'configuration',recorder,message)
		self.pdb(recorder)

	# show the exchange of message generated by the reactor (^C and signal received)
	def reactor (self, message, recorder='info'):
		level = short(recorder)
		if self._option.reactor and getattr(syslog,'LOG_%s' % level) <= self.level:
			getattr(self,recorder)(message,'reactor',level)
		else:
			self._record(time.localtime(),'reactor',recorder,message)
		self.pdb(recorder)

	# show the change of rib table
	def rib (self, message, recorder='info'):
		level = short(recorder)
		if self._option.rib and getattr(syslog,'LOG_%s' % level) <= self.level:
			getattr(self,recorder)(message,'rib',level)
		else:
			self._record(time.localtime(),'rib',recorder,message)
		self.pdb(recorder)

	# show the change of rib table
	def timers (self, message, recorder='debug'):
		level = short(recorder)
		if self._option.timer and getattr(syslog,'LOG_%s' % level) <= self.level:
			getattr(self,recorder)(message,'timers',level)
		else:
			self._record(time.localtime(),'timers',recorder,message)
		self.pdb(recorder)

	# show the exchange of message generated by the daemon feature (change pid, fork, ...)
	def daemon (self, message, recorder='info'):
		level = short(recorder)
		if self._option.daemon and getattr(syslog,'LOG_%s' % level) <= self.level:
			getattr(self,recorder)(message,'daemon',level)
		else:
			self._record(time.localtime(),'daemon',recorder,message)
		self.pdb(recorder)

	# show the exchange of message generated by the forked processes
	def processes (self, message, recorder='info'):
		level = short(recorder)
		if self._option.processes and getattr(syslog,'LOG_%s' % level) <= self.level:
			getattr(self,recorder)(message,'processes',level)
		else:
			self._record(time.localtime(),'processes',recorder,message)
		self.pdb(recorder)

	# show the exchange of message generated by the routes received
	def routes (self, message, recorder='info'):
		level = short(recorder)
		if self._option.routes and getattr(syslog,'LOG_%s' % level) <= self.level:
			getattr(self,recorder)(message,'routes',level)
		else:
			self._record(time.localtime(),'routes',recorder,message)
		self.pdb(recorder)

	# show how the message received are parsed
	def parser (self, message, recorder='info'):
		level = short(recorder)
		if self._option.parser and getattr(syslog,'LOG_%s' % level) <= self.level:
			getattr(self,recorder)(message,'parser',level)
		self.pdb(recorder)


class FakeLogger (object):
	def __getattr__ (self, name):
		def printf (data, _=None):
			sys.stdout.write('Fake logger [%s]\n' % str(data))
		return printf

# if __name__ == '__main__':
# 	logger = Logger()
# 	logger.wire('wire packet content')
# 	logger.message('message exchanged')
# 	logger.debug('debug test')
