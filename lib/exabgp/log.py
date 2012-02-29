# encoding: utf-8
"""
utils.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009-2012 Exa Networks. All rights reserved.
"""

import os
import sys
import time
import logging
import logging.handlers

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
		if os.environ.get('DEBUG_SUPERVISOR','1') in ['1','yes','Yes','YES']: self._supervisor = True
		else: self._supervisor = False

		if os.environ.get('DEBUG_DAEMON','1') in ['1','yes','Yes','YES']: self._daemon = True
		else: self._daemon = False

		if os.environ.get('DEBUG_PROCESSES','1') in ['1','yes','Yes','YES']: self._processes = True
		else: self._processes = False

		if os.environ.get('DEBUG_CONFIGURATION','0') == '0': self._configuration = False
		else: self._configuration = True

		if os.environ.get('DEBUG_WIRE','0') == '0': self._wire = False
		else: self._wire = True

		if os.environ.get('DEBUG_MESSAGE','0') in ['1','yes','Yes','YES']: self._message = True
		else: self._message = False

		if os.environ.get('DEBUG_RIB','0') == '0': self._rib = False
		else: self._rib = True

		if os.environ.get('DEBUG_TIMER','0') == '0': self._timer = False
		else: self._timer = True

		if os.environ.get('DEBUG_ROUTE','0') == '0': self._routes = False
		else: self._routes = True

		# DEPRECATED, kept for compatibility in 2.0.x series
		if os.environ.get('DEBUG_ROUTES','0') == '0': self._routes = False
		else: self._routes = True

		if os.environ.get('DEBUG_PARSER','0') == '0': self._parser = False
		else: self._parser = True

		if not os.environ.get('DEBUG_ALL','0') == '0':
			self._supervisor = True
			self._daemon = True
			self._processes = True
			self._configuration = True
			self._wire = True
			self._message = True
			self._rib = True
			self._timer = True
			self._routes = True
			self._parser = True

		if not os.environ.get('DEBUG_CORE','0') == '0':
			self._supervisor = True
			self._daemon = True
			self._processes = True
			#self._configuration = True
			#self._wire = True
			self._message = True
			#self._rib = True
			self._timer = True
			self._routes = True
			self._parser = False

		destination = os.environ.get('SYSLOG',None)
		if destination is None:
			return

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
	def wire (self,message):
		if self._wire:
			self.debug(message,'wire')
		else:
			self._record(time.localtime(),'wire','DEBUG',message)

	# show the exchange of message between peers
	def message (self,message):
		if self._message:
			self.info(message,'message')
		else:
			self._record(time.localtime(),'message','info',message)

	# show the parsing of the configuration
	def configuration (self,message):
		if self._configuration:
			self.info(message,'configuration')
		else:
			self._record(time.localtime(),'configuration','info',message)

	# show the exchange of message generated by the supervisor (^C and signal received)
	def supervisor (self,message):
		if self._supervisor:
			self.info(message,'supervisor')
		else:
			self._record(time.localtime(),'supervisor','info',message)

	# show the change of rib table
	def rib (self,message):
		if self._rib:
			self.info(message,'rib')
		else:
			self._record(time.localtime(),'rib','info',message)

	# show the change of rib table
	def timers (self,message):
		if self._timer:
			self.info(message,'timers')
		else:
			self._record(time.localtime(),'timers','info',message)

	# show the exchange of message generated by the daemon feature (change pid, fork, ...)
	def daemon (self,message):
		if self._daemon:
			self.info(message,'daemon')
		else:
			self._record(time.localtime(),'daemon','info',message)

	# show the exchange of message generated by the forked processes
	def processes (self,message):
		if self._processes:
			self.info(message,'processes')
		else:
			self._record(time.localtime(),'processes','info',message)

	# show the exchange of message generated by the routes received
	def routes (self,message):
		if self._routes:
			self.info(message,'route')
		else:
			self._record(time.localtime(),'route','info',message)

	# show how the message received are parsed
	def parser (self,message):
		if self._parser:
			self.info(message,'parser')

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

