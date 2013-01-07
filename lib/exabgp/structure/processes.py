"""
process.py

Created by Thomas Mangin on 2011-05-02.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import os
import errno
import time
import subprocess
import select

from exabgp.api import Text,JSON

from exabgp.version import version
from exabgp.structure.environment import load

from exabgp.structure.log import Logger

class ProcessError (Exception):
	pass

def preexec_helper ():
	# make this process a new process group
	#os.setsid()
	# This prevent the signal to be sent to the children (and create a new process group)
	os.setpgrp()
	#signal.signal(signal.SIGINT, signal.SIG_IGN)

class Processes (object):
	def __init__ (self,supervisor):
		self.logger = Logger()
		self.supervisor = supervisor
		self.clean()
		api = load().api.encoder
		if api == 'json':
			self.api = JSON(self.write,version,'1.0')
		else:
			self.api = Text(self.write,version,'1.0')

	def clean (self):
		self._process = {}
		self._receive_routes = {}
		self._notify = {}
		self._broken = []

	def _terminate (self,process):
		self.logger.processes("Terminating process %s" % process)
		self._process[process].terminate()
		self._process[process].wait()
		del self._process[process]

	def terminate (self):
		for process in list(self._process):
			self.api.shutdown(process)
			self.api.silence = True
		time.sleep(0.1)
		for process in list(self._process):
			try:
				self._terminate(process)
			except OSError:
				# we most likely received a SIGTERM signal and our child is already dead
				self.logger.processes("child process %s was already dead" % process)
				pass
		self.clean()

	def _start (self,process):
		try:
			if process in self._process:
				self.logger.processes("process already running")
				return
			if not process in self.supervisor.configuration.process:
				self.logger.processes("Can not start process, no configuration for it (anymore ?)")
				return
			# Prevent some weird termcap data to be created at the start of the PIPE
			# \x1b[?1034h (no-eol) (esc)
			os.environ['TERM']='dumb'
			self._receive_routes[process] = self.supervisor.configuration.process[process]['receive-routes']
			self._process[process] = subprocess.Popen(self.supervisor.configuration.process[process]['run'],
				stdin=subprocess.PIPE,
				stdout=subprocess.PIPE,
				preexec_fn=preexec_helper
				# This flags exists for python 2.7.3 in the documentation but on on my MAC
				# creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
			)
			neighbor = self.supervisor.configuration.process[process]['neighbor']
			self._notify.setdefault(neighbor,[]).append(process)
			self.logger.processes("Forked process %s" % process)
		except (subprocess.CalledProcessError,OSError,ValueError),e:
			self._broken.append(process)
			self.logger.processes("Could not start process %s" % process)
			self.logger.processes("reason: %s" % str(e))

	def start (self):
		for process in self.supervisor.configuration.process:
			self._start(process)
		for process in list(self._process):
			if not process in self.supervisor.configuration.process:
				self._terminate(process)

	def notify (self,neighbor):
		for process in self._notify.get(neighbor,[]):
			yield process
		for process in self._notify.get('*',[]):
			yield process

	def broken (self,neighbor):
		if self._broken:
			for process in self._notify.get(neighbor,[]):
				if process in self._broken:
					return True
			if '*' in self._broken:
				return True
		return False

	def received (self):
		lines = {}
		for process in list(self._process):
			try:
				proc = self._process[process]
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
							self.logger.processes("Command from process %s : %s " % (process,line))
							lines.setdefault(process,[]).append(line)
			except (subprocess.CalledProcessError,OSError,ValueError):
				self.logger.processes("Issue with the process, terminating it and restarting it")
				self._terminate(process)
				self._start(process)
		return lines

	def write (self,process,string):
		while True:
			try:
				self._process[process].stdin.write('%s\r\n' % string)
			except IOError,e:
				self._broken.append(process)
				if e.errno == errno.EPIPE:
					self._broken.append(process)
					self.logger.processes("Issue while sending data to our helper program")
					raise ProcessError()
				else:
					# Could it have been caused by a signal ? What to do.
					self.logger.processes("REPORT TO DEVELOPERS: IOError received while SENDING data to helper program %s, retrying" % str(e.errno))
					continue
			break

		try:
			self._process[process].stdin.flush()
		except IOError,e:
			# AFAIK, the buffer should be flushed at the next attempt.
			self.logger.processes("REPORT TO DEVELOPERS: IOError received while FLUSHING data to helper program %s, retrying" % str(e.errno))

		return True

	# return all the process which are interrested in route update notification
	def receive_routes (self):
		for process in self._process:
			if self._receive_routes[process]:
				yield process
