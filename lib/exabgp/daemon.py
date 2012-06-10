# encoding: utf-8
"""
daemon.py

Created by Thomas Mangin on 2011-05-02.
Copyright (c) 2009-2012 Exa Networks. All rights reserved.
"""

import os
import sys
import pwd
import errno
import socket

from exabgp.command import load

from exabgp.log import Logger
logger = Logger()

class Daemon (object):
	daemon = load().daemon

	def __init__ (self,supervisor):
		self.supervisor = supervisor
		#mask = os.umask(0137)

	def savepid (self):
		self._saved_pid = False

		if not self.daemon.pid:
			return

		ownid = os.getpid()

		flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
		mode = ((os.R_OK | os.W_OK) << 6) | (os.R_OK << 3) | os.R_OK

		try:
			fd = os.open(self.daemon.pid,flags,mode)
		except OSError:
			logger.daemon("PIDfile already exists, not updated %s" % self.daemon.pid)
			return

		try:
			f = os.fdopen(fd,'w')
			line = "%d\n" % ownid
			f.write(line)
			f.close()
			self._saved_pid = True
		except IOError:
			logger.daemon("Can not create PIDfile %s" % self.daemon.pid,'error')
			return
		logger.daemon("Created PIDfile %s with value %d" % (self.daemon.pid,ownid))

	def removepid (self):
		if not self.daemon.pid or not self._saved_pid:
			return
		try:
			os.remove(self.daemon.pid)
		except OSError, e:
			if e.errno == errno.ENOENT:
				pass
			else:
				logger.daemon("Can not remove PIDfile %s" % self.daemon.pid,'error')
				return
		logger.daemon("Removed PIDfile %s" % self.daemon.pid)

	def drop_privileges (self):
		"""returns true if we are left with insecure privileges"""
		# os.name can be ['posix', 'nt', 'os2', 'ce', 'java', 'riscos']
		if os.name not in ['posix',]:
			return False

		uid = os.getpid()
		gid = os.getgid()

		if uid and gid:
			return False

		try:
			user = pwd.getpwnam(self.daemon.user)
			nuid = int(user.pw_uid)
			ngid = int(user.pw_uid)
		except KeyError:
			return True

		# not sure you can change your gid if you do not have a pid of zero
		try:
			if not uid:
				os.setuid(nuid)
			if not gid:
				os.setgid(ngid)
			return False
		except OSError:
			return True

	def _is_socket (self,fd):
		try:
			s = socket.fromfd(fd, socket.AF_INET, socket.SOCK_RAW)
		except ValueError,e:
			# The file descriptor is closed
			return False
		try:
			s.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE)
		except socket.error, e:
			# It is look like one but it is not a socket ...
			if e.args[0] == errno.ENOTSOCK:
				return False
		return True

	def daemonise (self):
		if not self.daemon.daemonize:
			return

		log = load().log
		if log.enable and log.destination.lower() in ('stdout','stderr'):
			logger.daemon('ExaBGP not fork when logs are going to %s' % log.destination.lower(),'critical')
			return

		def fork_exit ():
			try:
				pid = os.fork()
				if pid > 0:
					os._exit(0)
			except OSError, e:
				logger.supervisor('Can not fork, errno %d : %s' % (e.errno,e.strerror),'critical')

		# do not detach if we are already supervised or run by init like process
		if not self._is_socket(sys.__stdin__.fileno()) and os.getppid() != 1:
			fork_exit()
			os.setsid()
			fork_exit()
