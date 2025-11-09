
"""daemon.py

Created by Thomas Mangin on 2011-05-02.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import os
import sys
import pwd
import errno
import socket

from exabgp.environment import getenv

from exabgp.logger import log

MAXFD = 2048


class Daemon:
    # NOTE: This class logs full PID file paths (self.pid) for operational clarity
    # Security review: Accepted as necessary for troubleshooting and debugging
    def __init__(self, reactor):
        self.pid = getenv().daemon.pid
        self.user = getenv().daemon.user
        self.daemonize = getenv().daemon.daemonize
        self.umask = getenv().daemon.umask
        self._saved_pid = False

        self.reactor = reactor

        os.chdir('/')
        os.umask(self.umask)

    @staticmethod
    def check_pid(pid):
        if pid < 0:  # user input error
            return False
        if pid == 0:  # all processes
            return False
        try:
            os.kill(pid, 0)
            return True
        except OSError as err:
            if err.errno == errno.EPERM:  # a process we were denied access to
                return True
            if err.errno == errno.ESRCH:  # No such process
                return False
            # should never happen
            return False

    def savepid(self):
        if not self.pid:
            return True

        ownid = os.getpid()

        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        mode = ((os.R_OK | os.W_OK) << 6) | (os.R_OK << 3) | os.R_OK

        try:
            fd = os.open(self.pid, flags, mode)
        except OSError:
            try:
                pid = open(self.pid, 'r').readline().strip()
                if self.check_pid(int(pid)):
                    log.debug(lambda: f'PIDfile already exists and program still running {self.pid}', 'daemon')
                    return False
                else:
                    # If pid is not running, reopen file without O_EXCL
                    fd = os.open(self.pid, flags ^ os.O_EXCL, mode)
            except (OSError, IOError, ValueError):
                log.debug(lambda: f'issue accessing PID file {self.pid} (most likely permission or ownership)', 'daemon')
                return False

        try:
            f = os.fdopen(fd, 'w')
            line = f'{ownid}\n'
            f.write(line)
            f.close()
            self._saved_pid = True
        except IOError:
            log.warning(lambda: f'Can not create PIDfile {self.pid}', 'daemon')
            return False
        log.warning(lambda: f'Created PIDfile {self.pid} with value {ownid}', 'daemon')
        return True

    def removepid(self):
        if not self.pid or not self._saved_pid:
            return
        try:
            os.remove(self.pid)
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                pass
            else:
                log.error(lambda: f'Can not remove PIDfile {self.pid}', 'daemon')
                return
        log.debug(lambda: f'Removed PIDfile {self.pid}', 'daemon')

    def drop_privileges(self):
        """return true if we are left with insecure privileges"""
        # os.name can be ['posix', 'nt', 'os2', 'ce', 'java', 'riscos']
        if os.name not in [
            'posix',
        ]:
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
                cuid += 1 << 32

            if cgid < 0:
                cgid += 1 << 32

            if ceid < 0:
                ceid += 1 << 32

            if nuid != cuid or nuid != ceid or ngid != cgid:
                return False

        except OSError:
            return False

        return True

    @staticmethod
    def _is_socket(fd):
        try:
            s = socket.fromfd(fd, socket.AF_INET, socket.SOCK_RAW)
        except (ValueError, OSError):
            # The file descriptor is closed
            return False
        try:
            s.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE)
        except socket.error as exc:
            # It is look like one but it is not a socket ...
            if exc.args[0] == errno.ENOTSOCK:
                return False
        return True

    def daemonise(self):
        if not self.daemonize:
            return

        logging = getenv().log
        if logging.enable and logging.destination.lower() in ('stdout', 'stderr'):
            log.critical(lambda: f'ExaBGP can not fork when logs are going to {logging.destination.lower()}', 'daemon')
            return

        def fork_exit():
            try:
                pid = os.fork()
                if pid > 0:
                    os._exit(0)
            except OSError as exc:
                log.critical(lambda exc=exc: f'can not fork, errno {exc.errno} : {exc.strerror}', 'daemon')

        # do not detach if we are already supervised or run by init like process
        if self._is_socket(sys.__stdin__.fileno()) or os.getppid() == 1:
            return

        fork_exit()
        os.setsid()
        fork_exit()
        self.silence()

    @staticmethod
    def silence():
        # closing more would close the log file too if open
        maxfd = 3

        for fd in range(0, maxfd):
            try:
                os.close(fd)
            except OSError:
                pass
        os.open('/dev/null', os.O_RDWR)
        os.dup2(0, 1)
        os.dup2(0, 2)

        # import resource
        # if 'linux' in sys.platform:
        # 	nofile = resource.RLIMIT_NOFILE
        # elif 'bsd' in sys.platform:
        # 	nofile = resource.RLIMIT_OFILE
        # else:
        # 	log.daemon("For platform %s, can not close FDS before forking" % sys.platform)
        # 	nofile = None
        # if nofile:
        # 	maxfd = resource.getrlimit(nofile)[1]
        # 	if (maxfd == resource.RLIM_INFINITY):
        # 		maxfd = MAXFD
        # else:
        # 	maxfd = MAXFD
