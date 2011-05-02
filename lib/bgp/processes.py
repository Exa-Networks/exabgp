#!/usr/bin/env python
# encoding: utf-8
"""
process.py

Created by Thomas Mangin on 2011-05-02.
Copyright (c) 2009-2011 Exa Networks. All rights reserved.
"""

import subprocess
import select

from bgp.log import Logger
logger = Logger()

class Processes (object):
	def __init__ (self,supervisor):
		self.supervisor = supervisor
		self._process = {}

	def _terminate (self,name):
		logger.processes("Terminating process %s" % name)
		self._process[name].terminate()
		self._process[name].wait()
		del self._process[name]

	def terminate (self):
		for name in list(self._process):
			self._terminate(name)

	def _start (self,name):
		try:
			if name in self._process:
				logger.processes("Can not start process, it is alrady running")
				return
			if not name in self.supervisor.configuration.process:
				logger.processes("Can not start process, no configuration for it (anymore ?)")
				return
			self._process[name] = subprocess.Popen([self.supervisor.configuration.process[name],],
				stdin=subprocess.PIPE,
				stdout=subprocess.PIPE,
			)
			logger.processes("Forked process %s" % name)
		except (subprocess.CalledProcessError,OSError,ValueError):
			logger.processes("Could not start process %s" % name)

	def start (self):
		for name in self.supervisor.configuration.process:
			self._start(name)
		for name in list(self._process):
			if not name in self.supervisor.configuration.process:
				self._terminate(name)

	def received (self):
		lines = {}
		for name in list(self._process):
			try:
				proc = self._process[name]
				r = True
				while r:
					r,_,_ = select.select([proc.stdout,],[],[],0)
					if r:
						# XXX: readline is blocking, so we are taking the assuption that it will not block
						# XXX: most likely not going to but perhaps the code should be more robust ?
						line = proc.stdout.readline().rstrip()
						if not line:
							# It seems that when we send ^C this is passed to the children to
							# And if they do not intercept it correctly, select.select returns but
							# there is not data to read
							r = False
						else:
							logger.processes("Command from process %s : %s " % (name,line))
							lines.setdefault(name,[]).append(line)
			except (subprocess.CalledProcessError,OSError,ValueError):
				logger.processes("Issue with the process, terminating it and restarting it")
				self._terminate(name)
				self._start(name)
		return lines

	def write (self,name,string):
		self._process[name].stdin.write('%s\r\n' % string)
		self._process[name].stdin.flush()
