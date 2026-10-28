"""daemon.py

Created by Thomas Mangin on 2011-05-02.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import contextlib
import errno
import importlib
import os
import pkgutil
import pwd
import socket
import stat
import sys
import warnings
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.reactor.loop import Reactor

from exabgp.environment import getenv
from exabgp.logger import lazymsg, log
from exabgp.version import get_root

MAXFD: int = 2048
# the directory of the exabgp package, which the daemon imports from long after it started,
# or the zipapp it is imported from, in which a module has no path of its own to check
PACKAGE: str = get_root()


def preload() -> list[str]:
    """Import every module of the package, and the names of those which could not be."""
    import exabgp

    unloaded = []
    # a module which warns when it is imported (the vendored profiler, without psutil) would
    # print it at every start as root, for a feature nobody asked for
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for module in pkgutil.walk_packages(exabgp.__path__, 'exabgp.'):
            try:
                importlib.import_module(module.name)
            except ImportError as exc:
                unloaded.append(f'{module.name}({exc})')
    return unloaded


def permitted(status: os.stat_result, uid: int, gids: set[int], bits: tuple[int, int, int]) -> bool:
    """Whether a user who is not root has the permission whose owner, group and other bits these are."""
    owner, group, other = bits
    if status.st_uid == uid:
        return bool(status.st_mode & owner)
    if status.st_gid in gids:
        return bool(status.st_mode & group)
    return bool(status.st_mode & other)


def can_enter(status: os.stat_result, uid: int, gids: set[int]) -> bool:
    """Whether a user who is not root may enter the directory: the bits the kernel reads."""
    return permitted(status, uid, gids, (stat.S_IXUSR, stat.S_IXGRP, stat.S_IXOTH))


def can_read(status: os.stat_result, uid: int, gids: set[int]) -> bool:
    """Whether a user who is not root may read the file."""
    return permitted(status, uid, gids, (stat.S_IRUSR, stat.S_IRGRP, stat.S_IROTH))


def unreachable_by(path: str, uid: int, gids: set[int]) -> str:
    """The first directory on the way to `path` which the user can not enter, or ''.

    `path` is the directory of the package, or the zipapp it is imported from: a file, which
    the user must be able to read, and which needs no execute bit (`python3 exabgp.pyz`).
    """
    assert os.path.isabs(path), 'the path is checked from the root down'
    for directory in reversed(Path(path).parents):
        if not can_enter(os.stat(directory), uid, gids):
            return str(directory)
    status = os.stat(path)
    reachable = can_read if stat.S_ISREG(status.st_mode) else can_enter
    return '' if reachable(status, uid, gids) else path


class Daemon:
    # NOTE: This class logs full PID file paths (self.pid) for operational clarity
    # Security review: Accepted as necessary for troubleshooting and debugging
    def __init__(self, reactor: Reactor) -> None:
        self.pid: str = getenv().daemon.pid
        self.user: str = getenv().daemon.user
        self.daemonize: bool = getenv().daemon.daemonize
        self.umask: int = getenv().daemon.umask
        self._saved_pid: bool = False

        self.reactor: Reactor = reactor

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
                # closed once read: the descriptor used to stay open until collected
                with open(self.pid) as existing:
                    pid = existing.readline().strip()
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

        # exabgp imports some of its modules only when it first needs them: installed where the
        # user can not read (a venv in a 0700 directory, as `mktemp -d` makes; the directory a
        # one-file binary unpacks itself in), every session was reset as soon as it was up,
        # with nothing logged to say why. Every module is imported now, while it still can be
        unloaded = preload()
        if unloaded:
            log.warning(lazymsg('daemon.preload.failed modules={m}', m=' '.join(unloaded)), 'reactor')
        # the helpers it starts run as the user too, and import the package from where it is
        # installed; a one-file binary's helpers unpack a copy of their own, as that user
        frozen = bool(getattr(sys, 'frozen', False))
        blocked = '' if not nuid or frozen else unreachable_by(PACKAGE, nuid, set(os.getgrouplist(self.user, ngid)))
        if blocked:
            log.critical(lazymsg('daemon.privileges.unreadable user={u} path={p}', u=self.user, p=blocked), 'reactor')
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
        if sys.__stdin__ is not None and self._is_socket(sys.__stdin__.fileno()):
            return
        if os.getppid() == 1:
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
            # stdin, stdout and stderr are being detached from the terminal. One of them
            # already being closed is the normal case when exabgp was started from
            # something which had closed it, and there is nothing to do about a descriptor
            # which is already gone.
            with contextlib.suppress(OSError):
                os.close(fd)
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
