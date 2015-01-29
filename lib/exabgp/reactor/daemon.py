# encoding: utf-8
"""
daemon.py

Created by Thomas Mangin on 2011-05-02.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import os
import sys
import pwd
import errno
import socket

from exabgp.configuration.environment import environment

from exabgp.logger import Logger

MAXFD = 2048


class Daemon (object):

	def __init__ (self, reactor):
		self.pid = environment.settings().daemon.pid
		self.user = environment.settings().daemon.user
		self.daemonize = environment.settings().daemon.daemonize

		self.logger = Logger()

		self.reactor = reactor

		os.chdir('/')
		# os.umask(0)
		os.umask(0137)

	def savepid (self):
		self._saved_pid = False

		if not self.pid:
			return True

		ownid = os.getpid()

		flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
		mode = ((os.R_OK | os.W_OK) << 6) | (os.R_OK << 3) | os.R_OK

		try:
			fd = os.open(self.pid,flags,mode)
		except OSError:
			self.logger.daemon("PIDfile already exists, not updated %s" % self.pid)
			return False

		try:
			f = os.fdopen(fd,'w')
			line = "%d\n" % ownid
			f.write(line)
			f.close()
			self._saved_pid = True
		except IOError:
			self.logger.daemon("Can not create PIDfile %s" % self.pid,'warning')
			return False
		self.logger.daemon("Created PIDfile %s with value %d" % (self.pid,ownid),'warning')
		return True

	def removepid (self):
		if not self.pid or not self._saved_pid:
			return
		try:
			os.remove(self.pid)
		except OSError,exc:
			if exc.errno == errno.ENOENT:
				pass
			else:
				self.logger.daemon("Can not remove PIDfile %s" % self.pid,'error')
				return
		self.logger.daemon("Removed PIDfile %s" % self.pid)

	def drop_privileges (self):
		"""return true if we are left with insecure privileges"""
		# os.name can be ['posix', 'nt', 'os2', 'ce', 'java', 'riscos']
		if os.name not in ['posix',]:
			return True

		uid = os.getuid()
		gid = os.getgid()

		if uid and gid:
			return True

		try:
			user = pwd.getpwnam(self.user)
			nuid = int(user.pw_uid)
			ngid = int(user.pw_gid)
		except KeyError:
			return False

		# not sure you can change your gid if you do not have a pid of zero
		try:
			# we must change the GID first otherwise it may fail after change UID
			if not gid:
				os.setgid(ngid)
			if not uid:
				os.setuid(nuid)

			cuid = os.getuid()
			ceid = os.geteuid()
			cgid = os.getgid()

			if cuid < 0:
				cuid += (1 << 32)

			if cgid < 0:
				cgid += (1 << 32)

			if ceid < 0:
				ceid += (1 << 32)

			if nuid != cuid or nuid != ceid or ngid != cgid:
				return False

		except OSError:
			return False

		return True

	def _is_socket (self, fd):
		try:
			s = socket.fromfd(fd, socket.AF_INET, socket.SOCK_RAW)
		except ValueError:
			# The file descriptor is closed
			return False
		try:
			s.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE)
		except socket.error,exc:
			# It is look like one but it is not a socket ...
			if exc.args[0] == errno.ENOTSOCK:
				return False
		return True

	def daemonise (self):
		if not self.daemonize:
			return

		log = environment.settings().log
		if log.enable and log.destination.lower() in ('stdout','stderr'):
			self.logger.daemon('ExaBGP can not fork when logs are going to %s' % log.destination.lower(),'critical')
			return

		def fork_exit ():
			try:
				pid = os.fork()
				if pid > 0:
					os._exit(0)
			except OSError,exc:
				self.logger.reactor('Can not fork, errno %d : %s' % (exc.errno,exc.strerror),'critical')

		# do not detach if we are already supervised or run by init like process
		if self._is_socket(sys.__stdin__.fileno()) or os.getppid() == 1:
			return

		fork_exit()
		os.setsid()
		fork_exit()
		self.silence()

	def silence (self):
		# closing more would close the log file too if open
		maxfd = 3

		for fd in range(0, maxfd):
			try:
				os.close(fd)
			except OSError:
				pass
		os.open("/dev/null", os.O_RDWR)
		os.dup2(0, 1)
		os.dup2(0, 2)

		# import resource
		# if 'linux' in sys.platform:
		# 	nofile = resource.RLIMIT_NOFILE
		# elif 'bsd' in sys.platform:
		# 	nofile = resource.RLIMIT_OFILE
		# else:
		# 	self.logger.daemon("For platform %s, can not close FDS before forking" % sys.platform)
		# 	nofile = None
		# if nofile:
		# 	maxfd = resource.getrlimit(nofile)[1]
		# 	if (maxfd == resource.RLIM_INFINITY):
		# 		maxfd = MAXFD
		# else:
		# 	maxfd = MAXFD
