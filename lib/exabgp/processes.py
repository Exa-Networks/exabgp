# encoding: utf-8
"""
process.py

Created by Thomas Mangin on 2011-05-02.
Copyright (c) 2009-2012 Exa Networks. All rights reserved.
"""

import os
import subprocess
import select

from exabgp.log import Logger
logger = Logger()

class ProcessError (Exception):
	pass

class Processes (object):
	def __init__ (self,supervisor):
		self.supervisor = supervisor
		self._process = {}
		self._receive_routes = {}
		self._notify = {}
		self._broken = []

	def _terminate (self,name):
		logger.processes("Terminating process %s" % name)
		self._process[name].terminate()
		self._process[name].wait()
		del self._process[name]

	def terminate (self):
		for name in list(self._process):
			try:
				self._terminate(name)
			except OSError:
				# we most likely received a SIGTERM signal and our child is already dead
				pass

	def _start (self,name):
		try:
			if name in self._process:
				logger.processes("process already running")
				return
			proc = self.supervisor.configuration.process
			if not name in proc:
				logger.processes("Can not start process, no configuration for it (anymore ?)")
				return
			self._receive_routes[name] = proc[name]['receive-routes']
			self._process[name] = subprocess.Popen(proc[name]['run'],
				stdin=subprocess.PIPE,
				stdout=subprocess.PIPE,
				preexec_fn=os.setsid
			)
			neighbor = proc[name]['neighbor']
			self._notify.setdefault(neighbor,[]).append(name)
			logger.processes("Forked process %s" % name)
		except (subprocess.CalledProcessError,OSError,ValueError):
			self._broken.append(name)
			logger.processes("Could not start process %s" % name)

	def start (self):
		proc = self.supervisor.configuration.process
		for name in proc:
			self._start(name)
		for name in list(self._process):
			if not name in proc:
				self._terminate(name)

	def notify (self,neighbor):
		for name in self._notify.get(neighbor,[]):
			yield name
		for name in self._notify.get('*',[]):
			yield name

	def broken (self,neighbor):
		if self._broken:
			for name in self._notify.get(neighbor,[]):
				if name in self._broken:
					return True
			if '*' in self._broken:
				return True
		return False

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
		while True:
			try:
				self._process[name].stdin.write('%s\r\n' % string)
			except IOError,e:
				self._broken.append(name)
				if e.errno == 32:
					self._broken.append(name)
					logger.processes("Issue while sending data to our helper program")
					raise ProcessError()
				else:
					# Could it have been caused by a signal ? What to do. 
					logger.processes("REPORT TO DEVELOPERS: IOError received while SENDING data to helper program %s, retrying" % str(e.errno))
					continue
			break

		try:
			self._process[name].stdin.flush()
		except IOError,e:
			# AFAIK, the buffer should be flushed at the next attempt.
			logger.processes("REPORT TO DEVELOPERS: IOError received while FLUSHING data to helper program %s, retrying" % str(e.errno))

		return True

	# return all the process which are interrested in route update notification
	def receive_routes (self):
		for name in self._process:
			if self._receive_routes[name]:
				yield name
