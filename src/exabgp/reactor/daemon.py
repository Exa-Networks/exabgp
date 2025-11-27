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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.reactor.loop import Reactor

from exabgp.environment import getenv

from exabgp.logger import log, lazymsg

MAXFD: int = 2048


class Daemon:
    # NOTE: This class logs full PID file paths (self.pid) for operational clarity
    # Security review: Accepted as necessary for troubleshooting and debugging
    def __init__(self, reactor: 'Reactor') -> None:
        self.pid: str = getenv().daemon.pid
        self.user: str = getenv().daemon.user
        self.daemonize: bool = getenv().daemon.daemonize
        self.umask: int = getenv().daemon.umask
        self._saved_pid: bool = False

        self.reactor: 'Reactor' = reactor

        os.chdir('/')
        os.umask(self.umask)

    @staticmethod
    def check_pid(pid: int) -> bool:
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

    def savepid(self) -> bool:
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
                    log.debug(lazymsg('pid.exists.running path={p}', p=self.pid), 'daemon')
                    return False
                # If pid is not running, reopen file without O_EXCL
                fd = os.open(self.pid, flags ^ os.O_EXCL, mode)
            except (OSError, ValueError):
                log.debug(lazymsg('pid.access.error path={p} reason=permission_or_ownership', p=self.pid), 'daemon')
                return False

        try:
            f = os.fdopen(fd, 'w')
            line = f'{ownid}\n'
            f.write(line)
            f.close()
            self._saved_pid = True
        except OSError:
            log.warning(lazymsg('pid.create.failed path={p}', p=self.pid), 'daemon')
            return False
        log.warning(lazymsg('pid.created path={p} value={v}', p=self.pid, v=ownid), 'daemon')
        return True

    def removepid(self) -> None:
        if not self.pid or not self._saved_pid:
            return
        try:
            os.remove(self.pid)
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                pass
            else:
                log.error(lazymsg('pid.remove.failed path={p}', p=self.pid), 'daemon')
                return
        log.debug(lazymsg('pid.removed path={p}', p=self.pid), 'daemon')

    def drop_privileges(self) -> bool:
        """Return true if we are left with insecure privileges"""
        # os.name can be ['posix', 'nt', 'os2', 'ce', 'java', 'riscos']
        if os.name not in [
            'posix',
        ]:
            return True

        uid: int = os.getuid()
        gid: int = os.getgid()

        if uid and gid:
            return True

        try:
            user: pwd.struct_passwd = pwd.getpwnam(self.user)
            nuid: int = int(user.pw_uid)
            ngid: int = int(user.pw_gid)
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
    def _is_socket(fd: int) -> bool:
        try:
            s: socket.socket = socket.fromfd(fd, socket.AF_INET, socket.SOCK_RAW)
        except (ValueError, OSError):
            # The file descriptor is closed
            return False
        try:
            s.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE)
        except OSError as exc:
            # It is look like one but it is not a socket ...
            if exc.args[0] == errno.ENOTSOCK:
                return False
        return True

    def daemonise(self) -> None:
        if not self.daemonize:
            return

        logging = getenv().log
        if logging.enable and logging.destination.lower() in ('stdout', 'stderr'):
            log.critical(lazymsg('daemon.fork.disabled destination={d}', d=logging.destination.lower()), 'daemon')
            return

        def fork_exit() -> None:
            try:
                pid: int = os.fork()
                if pid > 0:
                    os._exit(0)
            except OSError as exc:
                log.critical(
                    lazymsg('can not fork, errno {errno} : {strerror}', errno=exc.errno, strerror=exc.strerror),
                    'daemon',
                )

        # do not detach if we are already supervised or run by init like process
        if self._is_socket(sys.__stdin__.fileno()) or os.getppid() == 1:  # type: ignore[union-attr]
            return

        fork_exit()
        os.setsid()
        fork_exit()
        self.silence()

    @staticmethod
    def silence() -> None:
        # closing more would close the log file too if open
        maxfd = 3

        for fd in range(maxfd):
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
