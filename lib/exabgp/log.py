# encoding: utf-8
"""
utils.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009-2012 Exa Networks. All rights reserved.
"""

import os
import sys
import time
import syslog
import logging
import logging.handlers

from exabgp.environment import load

level_value = {
#	'emmergency' : syslog.LOG_EMERG,
#	'alert'      : syslog.LOG_ALERT,
	'critical'   : syslog.LOG_CRIT,
	'error'      : syslog.LOG_ERR,
	'warning'    : syslog.LOG_WARNING,
#	'notice'     : syslog.LOG_NOTICE,
	'info'       : syslog.LOG_INFO,
	'debug'      : syslog.LOG_DEBUG,
}


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
		now = time.strftime('%a, %d %b %Y %H:%M:%S',timestamp)
		return "%s %-8s %-6d %-13s %s" % (now,level,self._pid,source,message)

	def _prefixed (self,level,source,message):
		ts = time.localtime()
		self._record(ts,level,source,message)
		return self._format(ts,level,source,message)

	def __init__ (self):
		command = load()
		self.level = command.log.level

		self._supervisor    = command.log.enable and (command.log.all or command.log.supervisor)
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

#		if not os.environ.get('DEBUG_CORE','0') == '0':
#			self._supervisor = True
#			self._daemon = True
#			self._processes = True
#			self._message = True
#			self._timer = True
#			self._routes = True
#			self._parser = False

		if not command.log.enable:
			return

		destination = command.log.destination

		try:
			if destination == '':
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

	# show the message on the wire
	def network (self,message,recorder='info'):
		if self._wire and level_value[recorder] <= self.level:
			getattr(self,recorder)(message,'network')
		else:
			self._record(time.localtime(),'network',recorder.upper(),message)

	# show the message on the wire
	def wire (self,message,recorder='debug'):
		if self._wire and level_value[recorder] <= self.level:
			getattr(self,recorder)(message,'wire')
		else:
			self._record(time.localtime(),'wire',recorder.upper(),message)

	# show the exchange of message between peers
	def message (self,message,recorder='info'):
		if self._message and level_value[recorder] <= self.level:
			getattr(self,recorder)(message,'message')
		else:
			self._record(time.localtime(),'message',recorder.upper(),message)

	# show the parsing of the configuration
	def configuration (self,message,recorder='info'):
		if self._configuration and level_value[recorder] <= self.level:
			getattr(self,recorder)(message,'configuration')
		else:
			self._record(time.localtime(),'configuration',recorder.upper(),message)

	# show the exchange of message generated by the supervisor (^C and signal received)
	def supervisor (self,message,recorder='info'):
		if self._supervisor and level_value[recorder] <= self.level:
			getattr(self,recorder)(message,'supervisor')
		else:
			self._record(time.localtime(),'supervisor',recorder.upper(),message)

	# show the change of rib table
	def rib (self,message,recorder='info'):
		if self._rib and level_value[recorder] <= self.level:
			getattr(self,recorder)(message,'rib')
		else:
			self._record(time.localtime(),'rib',recorder.upper(),message)

	# show the change of rib table
	def timers (self,message,recorder='debug'):
		if self._timer and level_value[recorder] <= self.level:
			getattr(self,recorder)(message,'timers')
		else:
			self._record(time.localtime(),'timers',recorder.upper(),message)

	# show the exchange of message generated by the daemon feature (change pid, fork, ...)
	def daemon (self,message,recorder='info'):
		if self._daemon and level_value[recorder] <= self.level:
			getattr(self,recorder)(message,'daemon')
		else:
			self._record(time.localtime(),'daemon',recorder.upper(),message)

	# show the exchange of message generated by the forked processes
	def processes (self,message,recorder='info'):
		if self._processes and level_value[recorder] <= self.level:
			getattr(self,recorder)(message,'processes')
		else:
			self._record(time.localtime(),'processes',recorder.upper(),message)

	# show the exchange of message generated by the routes received
	def routes (self,message,recorder='info'):
		if self._routes and level_value[recorder] <= self.level:
			getattr(self,recorder)(message,'route')
		else:
			self._record(time.localtime(),'route',recorder.upper(),message)

	# show how the message received are parsed
	def parser (self,message,recorder='info'):
		if self._parser and level_value[recorder] <= self.level:
			getattr(self,recorder)(message,'parser')

def Logger ():
	if _Logger._instance:
		return _Logger._instance
	instance = _Logger()
	_Logger._instance = instance
	return instance

if __name__ == '__main__':
	logger = Logger()
	logger.wire('wire packet content')
	logger.message('message exchanged')
	logger.debug('debug test')

