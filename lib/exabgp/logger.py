# encoding: utf-8
"""
utils.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import os
import sys
import time
import syslog
import logging
import logging.handlers

from exabgp.configuration.environment import environment

_short = {
	'CRITICAL': 'CRIT',
	'ERROR': 'ERR'
}

def short (name):
	return _short.get(name.upper(),name.upper())

class LazyFormat (object):
	def __init__ (self,prefix,format,message):
		self.prefix = prefix
		self.format = format
		self.message = message

	def __str__ (self):
		if self.format:
			return self.prefix + self.format(self.message)
		return self.prefix + self.message

	def split (self,c):
		return str(self).split(c)

class _Logger (object):
	_instance = None
	_syslog = None

	_history = []
	_max_history = 20

	_config = ''
	_pid = os.getpid()

	# we use os.pid everytime as we may fork and the class is instance before it

	def pdb (self,level):
		if self._pdb and level in ['CRITICAL','critical']:
			import pdb
			pdb.set_trace()

	def config (self,config=None):
		if config is not None:
			self._config = config
		return self._config

	def history (self):
		return "\n".join(self._format(*_) for _ in self._history)

	def _record (self,timestamp,level,source,message):
		if len(self._history) > self._max_history:
			self._history.pop(0)
		self._history.append((timestamp,level,source,message))

	def _format (self,timestamp,level,source,message):
		if self.short: return message
		now = time.strftime('%a, %d %b %Y %H:%M:%S',timestamp)
		return "%s | %-8s | %-6d | %-13s | %s" % (now,level,self._pid,source,message)

	def _prefixed (self,level,source,message):
		ts = time.localtime()
		self._record(ts,level,source,message)
		return self._format(ts,level,source,message)

	def __init__ (self):
		command = environment.settings()
		self.short = command.log.short
		self.level = command.log.level

		self._pdb = command.debug.pdb

		self._reactor       = command.log.enable and (command.log.all or command.log.reactor)
		self._daemon        = command.log.enable and (command.log.all or command.log.daemon)
		self._processes     = command.log.enable and (command.log.all or command.log.processes)
		self._configuration = command.log.enable and (command.log.all or command.log.configuration)
		self._network       = command.log.enable and (command.log.all or command.log.network)
		self._wire          = command.log.enable and (command.log.all or command.log.packets)
		self._message       = command.log.enable and (command.log.all or command.log.message)
		self._rib           = command.log.enable and (command.log.all or command.log.rib)
		self._timer         = command.log.enable and (command.log.all or command.log.timers)
		self._routes        = command.log.enable and (command.log.all or command.log.routes)
		self._parser        = command.log.enable and (command.log.all or command.log.parser)

		if not command.log.enable:
			return

		destination = command.log.destination

		try:
			if destination in ('','syslog'):
				if sys.platform == "darwin":
					address = '/var/run/syslog'
				else:
					address = '/dev/log'
				if not os.path.exists(address):
					address = ('localhost', 514)
				handler = logging.handlers.SysLogHandler(address)
			elif destination.lower().startswith('host:'):
				# If the address is invalid, each syslog call will print an error.
				# See how it can be avoided, as the socket error is encapsulated and not returned
				address = (destination[5:].strip(), 514)
				handler = logging.handlers.SysLogHandler(address)
			else:
				if destination.lower() == 'stdout':
					handler = logging.StreamHandler(sys.stdout)
				elif destination.lower() == 'stderr':
					handler = logging.StreamHandler(sys.stderr)
				else:
					handler = logging.handlers.RotatingFileHandler(destination, maxBytes=5*1024*1024, backupCount=5)
			self._syslog = logging.getLogger()
			self._syslog.setLevel(logging.DEBUG)
			self._syslog.addHandler(handler)
		except IOError:
			self.critical('Can not use SYSLOG, failing back to stdout')

	def debug (self,message,source='',level='DEBUG'):
		for line in message.split('\n'):
			if self._syslog:
				self._syslog.debug(self._prefixed(level,source,line))
			else:
				print self._prefixed(level,source,line)
				sys.stdout.flush()

	def info (self,message,source='',level='INFO'):
		for line in message.split('\n'):
			if self._syslog:
				self._syslog.info(self._prefixed(level,source,line))
			else:
				print self._prefixed(level,source,line)
				sys.stdout.flush()

	def warning (self,message,source='',level='WARNING'):
		for line in message.split('\n'):
			if self._syslog:
				self._syslog.warning(self._prefixed(level,source,line))
			else:
				print self._prefixed(level,source,line)
				sys.stdout.flush()

	def error (self,message,source='',level='ERROR'):
		for line in message.split('\n'):
			if self._syslog:
				self._syslog.error(self._prefixed(level,source,line))
			else:
				print self._prefixed(level,source,line)
				sys.stdout.flush()

	def critical (self,message,source='',level='CRITICAL'):
		for line in message.split('\n'):
			if self._syslog:
				self._syslog.critical(self._prefixed(level,source,line))
			else:
				print self._prefixed(level,source,line)
				sys.stdout.flush()
		self.pdb(level)

	# show the message on the wire
	def network (self,message,recorder='info'):
		up = short(recorder)
		if self._network and getattr(syslog,'LOG_%s' % up) <= self.level:
			getattr(self,recorder.lower())(message,'network')
		else:
			self._record(time.localtime(),'network',recorder,message)
		self.pdb(recorder)

	# show the message on the wire
	def wire (self,message,recorder='debug'):
		up = short(recorder)
		if self._wire and getattr(syslog,'LOG_%s' % up) <= self.level:
			getattr(self,recorder.lower())(message,'wire')
		else:
			self._record(time.localtime(),'wire',recorder,message)
		self.pdb(recorder)

	# show the exchange of message between peers
	def message (self,message,recorder='info'):
		up = short(recorder)
		if self._message and getattr(syslog,'LOG_%s' % up) <= self.level:
			getattr(self,recorder.lower())(message,'message')
		else:
			self._record(time.localtime(),'message',recorder,message)
		self.pdb(recorder)

	# show the parsing of the configuration
	def configuration (self,message,recorder='info'):
		up = short(recorder)
		if self._configuration and getattr(syslog,'LOG_%s' % up) <= self.level:
			getattr(self,recorder.lower())(message,'configuration')
		else:
			self._record(time.localtime(),'configuration',recorder,message)
		self.pdb(recorder)

	# show the exchange of message generated by the reactor (^C and signal received)
	def reactor (self,message,recorder='info'):
		up = short(recorder)
		if self._reactor and getattr(syslog,'LOG_%s' % up) <= self.level:
			getattr(self,recorder.lower())(message,'reactor')
		else:
			self._record(time.localtime(),'reactor',recorder,message)
		self.pdb(recorder)

	# show the change of rib table
	def rib (self,message,recorder='info'):
		up = short(recorder)
		if self._rib and getattr(syslog,'LOG_%s' % up) <= self.level:
			getattr(self,recorder.lower())(message,'rib')
		else:
			self._record(time.localtime(),'rib',recorder,message)
		self.pdb(recorder)

	# show the change of rib table
	def timers (self,message,recorder='debug'):
		up = short(recorder)
		if self._timer and getattr(syslog,'LOG_%s' % up) <= self.level:
			getattr(self,recorder.lower())(message,'timers')
		else:
			self._record(time.localtime(),'timers',recorder,message)
		self.pdb(recorder)

	# show the exchange of message generated by the daemon feature (change pid, fork, ...)
	def daemon (self,message,recorder='info'):
		up = short(recorder)
		if self._daemon and getattr(syslog,'LOG_%s' % up) <= self.level:
			getattr(self,recorder.lower())(message,'daemon')
		else:
			self._record(time.localtime(),'daemon',recorder,message)
		self.pdb(recorder)

	# show the exchange of message generated by the forked processes
	def processes (self,message,recorder='info'):
		up = short(recorder)
		if self._processes and getattr(syslog,'LOG_%s' % up) <= self.level:
			getattr(self,recorder.lower())(message,'processes')
		else:
			self._record(time.localtime(),'processes',recorder,message)
		self.pdb(recorder)

	# show the exchange of message generated by the routes received
	def routes (self,message,recorder='info'):
		up = short(recorder)
		if self._routes and getattr(syslog,'LOG_%s' % up) <= self.level:
			getattr(self,recorder.lower())(message,'routes')
		else:
			self._record(time.localtime(),'routes',recorder,message)
		self.pdb(recorder)

	# show how the message received are parsed
	def parser (self,message,recorder='info'):
		up = short(recorder)
		if self._parser and getattr(syslog,'LOG_%s' % up) <= self.level:
			getattr(self,recorder.lower())(message,'parser')
		self.pdb(recorder)

def Logger ():
	if _Logger._instance is not None:
		return _Logger._instance
	instance = _Logger()
	_Logger._instance = instance
	return instance

class FakeLogger:
	def __getattr__ (self,name):
		return lambda data,_=None: sys.stdout.write('Fake logger [%s]\n' % str(data))

if __name__ == '__main__':
	logger = Logger()
	logger.wire('wire packet content')
	logger.message('message exchanged')
	logger.debug('debug test')
