"""
process.py

Created by Thomas Mangin on 2011-05-02.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import os
import errno
import time
import subprocess
import select
import fcntl

from exabgp.util.errstr import errstr
from exabgp.reactor.network.error import error

from exabgp.configuration.core.format import formated
from exabgp.reactor.api.response import Response
from exabgp.bgp.message import Message
from exabgp.logger import Logger

from exabgp.version import json as json_version
from exabgp.version import text as text_version


# pylint: disable=no-self-argument,not-callable,unused-argument,invalid-name

class ProcessError (Exception):
	pass


def preexec_helper ():
	# make this process a new process group
	# os.setsid()
	# This prevent the signal to be sent to the children (and create a new process group)
	os.setpgrp()
	# signal.signal(signal.SIGINT, signal.SIG_IGN)


class Processes (object):
	# how many time can a process can respawn in the time interval
	respawn_number = 5
	respawn_timemask = 0xFFFFFF - 0b111111
	# '0b111111111111111111000000' (around a minute, 63 seconds)

	_dispatch = {}

	def __init__ (self, reactor):
		self.logger = Logger()
		self.reactor = reactor
		self.clean()
		self.silence = False

	def clean (self):
		self._process = {}
		self._encoder = {}
		self._broken = []
		self._respawning = {}

	def _terminate (self, process):
		self.logger.processes("Terminating process %s" % process)
		try:
			self._process[process].terminate()
		except OSError:
			# the process is most likely already dead
			pass
		self._process[process].wait()
		del self._process[process]

	def terminate (self):
		for process in list(self._process):
			if not self.silence:
				try:
					self.write(process,self._encoder[process].shutdown())
				except ProcessError:
					pass
		self.silence = True
		time.sleep(0.1)
		for process in list(self._process):
			try:
				self._terminate(process)
			except OSError:
				# we most likely received a SIGTERM signal and our child is already dead
				self.logger.processes("child process %s was already dead" % process)

		self.clean()

	def _start (self, process):
		try:
			if process in self._process:
				self.logger.processes("process already running")
				return
			if process not in self.reactor.configuration.processes:
				self.logger.processes("Can not start process, no configuration for it (anymore ?)")
				return

			# Prevent some weird termcap data to be created at the start of the PIPE
			# \x1b[?1034h (no-eol) (esc)
			os.environ['TERM'] = 'dumb'

			run = self.reactor.configuration.processes[process].get('run','')
			if run:
				api = self.reactor.configuration.processes[process]['encoder']
				self._encoder[process] = Response.Text(text_version) if api == 'text' else Response.JSON(json_version)

				self._process[process] = subprocess.Popen(
					run,
					stdin=subprocess.PIPE,
					stdout=subprocess.PIPE,
					preexec_fn=preexec_helper
					# This flags exists for python 2.7.3 in the documentation but on on my MAC
					# creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
				)
				fcntl.fcntl(self._process[process].stdout.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)

				self.logger.processes("Forked process %s" % process)

				around_now = int(time.time()) & self.respawn_timemask
				if process in self._respawning:
					if around_now in self._respawning[process]:
						self._respawning[process][around_now] += 1
						# we are respawning too fast
						if self._respawning[process][around_now] > self.respawn_number:
							self.logger.processes(
								"Too many respawn for %s (%d) terminating program" % (process,self.respawn_number),
								'critical'
							)
							raise ProcessError()
					else:
						# reset long time since last respawn
						self._respawning[process] = {around_now: 1}
				else:
					# record respawing
					self._respawning[process] = {around_now: 1}

		except (subprocess.CalledProcessError,OSError,ValueError),exc:
			self._broken.append(process)
			self.logger.processes("Could not start process %s" % process)
			self.logger.processes("reason: %s" % str(exc))

	def start (self, restart=False):
		for process in self.reactor.configuration.processes:
			if restart:
				self._terminate(process)
			self._start(process)
		for process in list(self._process):
			if process not in self.reactor.configuration.processes:
				self._terminate(process)

	def broken (self, neighbor):
		if self._broken:
			for process in self.reactor.configuration.processes:
				if process in self._broken:
					return True
		return False

	def fds (self):
		return [self._process[process].stdout for process in self._process]

	def received (self):
		consumed_data = False
		buffered = {}

		for process in list(self._process):
			try:
				proc = self._process[process]
				# proc.poll returns None if the process is still fine
				# -[signal], like -15, if the process was terminated
				if proc.poll() is not None and self.reactor.respawn:
					raise ValueError('child died')
				r,_,_ = select.select([proc.stdout,],[],[],0)
				if r:
					try:
						while True:
							# Calling next() on Linux and OSX works perfectly well
							# but not on OpenBSD where it always raise StopIteration
							# and only readline() works
							raw = buffered.get(process,'') + proc.stdout.readline()

							if not raw.endswith('\n'):
								buffered[process] = raw
								continue

							buffered[process] = ''
							line = raw.rstrip()
							consumed_data = True
							self.logger.processes("Command from process %s : %s " % (process,line))
							if raw == '':
								raise IOError('Child process died')
							yield (process,formated(line))
					except IOError,exc:
						if not exc.errno or exc.errno in error.fatal:
							# if the program exists we can get an IOError with errno code zero !
							self.logger.processes("Issue with the process, terminating it and restarting it")
							self._terminate(process)
							self._start(process)
						elif exc.errno in error.block:
							# we often see errno.EINTR: call interrupted and
							# we most likely have data, we will try to read them a the next loop iteration
							pass
						else:
							self.logger.processes("unexpected errno received from forked process (%s)" % errstr(exc))
					except StopIteration:
						if not consumed_data:
							self.logger.processes("The process died, trying to respawn it")
							self._terminate(process)
							self._start(process)
			except (subprocess.CalledProcessError,OSError,ValueError):
				self.logger.processes("Issue with the process, terminating it and restarting it")
				self._terminate(process)
				self._start(process)

	def write (self, process, string, neighbor=None):
		# XXX: FIXME: This is potentially blocking
		while True:
			try:
				self._process[process].stdin.write('%s\n' % string)
			except IOError,exc:
				self._broken.append(process)
				if exc.errno == errno.EPIPE:
					self._broken.append(process)
					self.logger.processes("Issue while sending data to our helper program")
					raise ProcessError()
				else:
					# Could it have been caused by a signal ? What to do.
					self.logger.processes("Error received while SENDING data to helper program, retrying (%s)" % errstr(exc))
					continue
			break

		try:
			self._process[process].stdin.flush()
		except IOError,exc:
			# AFAIK, the buffer should be flushed at the next attempt.
			self.logger.processes("Error received while FLUSHING data to helper program, retrying (%s)" % errstr(exc))

		return True

	def _notify (self, neighbor, event):
		for process in neighbor.api[event]:
			yield process

	# do not do anything if silenced
	# no-self-argument

	def silenced (function):
		def closure (self, *args):
			if self.silence:
				return
			return function(self,*args)
		return closure

	# invalid-name
	@silenced
	def up (self, neighbor):
		for process in self._notify(neighbor,'neighbor-changes'):
			self.write(process,self._encoder[process].up(neighbor),neighbor)

	@silenced
	def connected (self, neighbor):
		for process in self._notify(neighbor,'neighbor-changes'):
			self.write(process,self._encoder[process].connected(neighbor),neighbor)

	@silenced
	def down (self, neighbor, reason):
		for process in self._notify(neighbor,'neighbor-changes'):
			self.write(process,self._encoder[process].down(neighbor,reason),neighbor)

	@silenced
	def packets (self, neighbor, direction, category, header, body):
		for process in self._notify(neighbor,'%s-packets' % direction):
			self.write(process,self._encoder[process].packets(neighbor,direction,category,header,body),neighbor)

	@silenced
	def notification (self, neighbor, direction, code, subcode, data, header, body):
		for process in self._notify(neighbor,'neighbor-changes'):
			self.write(process,self._encoder[process].notification(neighbor,direction,code,subcode,data,header,body),neighbor)

	@silenced
	def message (self, message_id, neighbor, direction, message, header, *body):
		self._dispatch[message_id](self,neighbor,direction,message,header,*body)

	# registering message functions
	# no-self-argument

	def register_process (message_id, storage=_dispatch):
		def closure (function):
			def wrap (*args):
				function(*args)
			storage[message_id] = wrap
			return wrap
		return closure

	# notifications are handled in the loop as they use different arguments

	@register_process(Message.CODE.OPEN)
	def _open (self, peer, direction, message, header, body):
		for process in self._notify(peer,'receive-%s' % Message.CODE.OPEN.SHORT):
			self.write(process,self._encoder[process].open(peer,direction,message,header,body),peer)

	@register_process(Message.CODE.UPDATE)
	def _update (self, peer, direction, update, header, body):
		for process in self._notify(peer,'receive-%s' % Message.CODE.UPDATE.SHORT):
			self.write(process,self._encoder[process].update(peer,direction,update,header,body),peer)

	@register_process(Message.CODE.NOTIFICATION)
	def _notification (self, peer, direction, message, header, body):
		for process in self._notify(peer,'receive-%s' % Message.CODE.NOTIFICATION.SHORT):
			self.write(process,self._encoder[process].notification(peer,direction,message,header,body),peer)

	# unused-argument, must keep the API
	@register_process(Message.CODE.KEEPALIVE)
	def _keepalive (self, peer, direction, keepalive, header, body):
		for process in self._notify(peer,'receive-%s' % Message.CODE.KEEPALIVE.SHORT):
			self.write(process,self._encoder[process].keepalive(peer,direction,header,body),peer)

	@register_process(Message.CODE.ROUTE_REFRESH)
	def _refresh (self, peer, direction, refresh, header, body):
		for process in self._notify(peer,'receive-%s' % Message.CODE.ROUTE_REFRESH.SHORT):
			self.write(process,self._encoder[process].refresh(peer,direction,refresh,header,body),peer)

	@register_process(Message.CODE.OPERATIONAL)
	def _operational (self, peer, direction, operational, header, body):
		for process in self._notify(peer,'receive-%s' % Message.CODE.OPERATIONAL.SHORT):
			self.write(process,self._encoder[process].operational(peer,direction,operational.category,operational,header,body),peer)
