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
import fcntl

from exabgp.structure.api import Text,JSON
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
		self.silence = False

	def clean (self):
		self._process = {}
		self._api = {}
		self._api_encoder = {}
		self._neighbor_process = {}
		self._broken = []

	def _terminate (self,process):
		self.logger.processes("Terminating process %s" % process)
		self._process[process].terminate()
		self._process[process].wait()
		del self._process[process]

	def terminate (self):
		for process in list(self._process):
			if not self.silence:
				self.write(process,self._api_encoder[process].shutdown())
		self.silence = True
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

			run = self.supervisor.configuration.process[process].get('run','')
			if run:
				api = self.supervisor.configuration.process[process]['encoder']
				self._api_encoder[process] = JSON('2.0') if api == 'json' else Text('1.0')

				self._process[process] = subprocess.Popen(run,
					stdin=subprocess.PIPE,
					stdout=subprocess.PIPE,
					preexec_fn=preexec_helper
					# This flags exists for python 2.7.3 in the documentation but on on my MAC
					# creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
				)
				fcntl.fcntl(self._process[process].stdout.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)

				self.logger.processes("Forked process %s" % process)

			neighbor = self.supervisor.configuration.process[process]['neighbor']
			self._neighbor_process.setdefault(neighbor,[]).append(process)
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

	def broken (self,neighbor):
		if self._broken:
			if '*' in self._broken:
				return True
			for process in self._neighbor_process.get(neighbor,[]):
				if process in self._broken:
					return True
		return False

	def received (self):
		lines = {}
		for process in list(self._process):
			try:
				proc = self._process[process]
				r,_,_ = select.select([proc.stdout,],[],[],0)
				if r:
					try:
						while True:
							line = proc.stdout.readline().rstrip()
							if line:
								self.logger.processes("Command from process %s : %s " % (process,line))
								lines.setdefault(process,[]).append(line)
							else:
								self.logger.processes("The process died, trying to respawn it")
								self._terminate(process)
								self._start(process)
								break
					except IOError,e:
						if e.errno == errno.EINTR:  # call interrupted
							pass  # we most likely have data, we will try to read them a the next loop iteration
						elif e.errno != errno.EAGAIN:  # no more data
							self.logger.processes("unexpected errno received from forked process: %d [%s]" % (e.errno,errno.errorcode[e.errno]))
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

	def _notify (self,neighbor,event):
		for process in self._neighbor_process.get(neighbor,[]):
			if process in self._process:
				yield process
		for process in self._neighbor_process.get('*',[]):
			if process in self._process:
				yield process

	def up (self,neighbor):
		if self.silence: return
		for process in self._notify(neighbor,'neighbor-changes'):
			self.write(process,self._api_encoder[process].up(neighbor))

	def connected (self,neighbor):
		if self.silence: return
		for process in self._notify(neighbor,'neighbor-changes'):
			self.write(process,self._api_encoder[process].connected(neighbor))

	def down (self,neighbor,reason=''):
		if self.silence: return
		for process in self._notify(neighbor,'neighbor-changes'):
			self.write(process,self._api_encoder[process].down(neighbor))

	def receive (self,neighbor,category,header,body):
		if self.silence: return
		for process in self._notify(neighbor,'receive-packets'):
			self.write(process,self._api_encoder[process].receive(neighbor,category,header,body))

	def send (self,neighbor,category,header,body):
		if self.silence: return
		for process in self._notify(neighbor,'send-packets'):
			self.write(process,self._api_encoder[process].send(neighbor,category,header,body))

	def routes (self,neighbor,routes):
		if self.silence: return
		for process in self._notify(neighbor,'receive-routes'):
			self.write(process,self._api_encoder[process].routes(neighbor,routes))
