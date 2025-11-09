
"""parse_process.py

Created by Thomas Mangin on 2015-06-18.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import os
import stat


def encoder(tokeniser):
    value = tokeniser()

    if value not in ('text', 'json'):
        raise ValueError('"%s" is an invalid option' % value)
    return value


def _make_path(prg):
    parts = prg.split('/')

    env = os.environ.get('EXABGP_ETC', '')
    if env:
        options = [os.path.join(env.rstrip('/'), os.path.join(*parts[2:])), '/etc/exabgp']
    else:
        options = []
        options.append('/etc/exabgp')
        pwd = os.environ.get('PWD', '').split('/')
        if pwd:
            # without abspath the path is not / prefixed !
            if pwd[-1] in ('etc', 'sbin'):
                options.append(os.path.abspath(os.path.join(os.path.join(*pwd[:-1]), os.path.join(*parts))))
            if 'etc' not in pwd:
                options.append(os.path.abspath(os.path.join(os.path.join(*pwd), os.path.join(*parts))))
    return options


def run(tokeniser):
    """Parse and validate the 'run' command for a process.

    Args:
        tokeniser: Configuration tokeniser providing command tokens

    Returns:
        List containing program path and arguments

    Raises:
        ValueError: If program cannot be found or validated
        OSError: If file access fails
    """
    prg = tokeniser()

    if prg[0] != '/':
        if prg.startswith('etc/exabgp'):
            options = _make_path(prg)
        else:
            options = [
                os.path.abspath(os.path.join('/etc/exabgp', prg)),
                os.path.abspath(os.path.join(os.path.dirname(tokeniser.fname), prg)),
            ]
            options.extend(os.path.abspath(os.path.join(p, prg)) for p in os.getenv('PATH').split(':'))
        for option in options:
            if os.path.exists(option):
                prg = option

    # Validate program using file descriptor to mitigate TOCTOU attacks
    # Open file first to get a handle, then validate using fstat on the handle
    #
    # Security note: We allow following symlinks (no O_NOFOLLOW) because:
    # 1. Symlinks are commonly used for executables (e.g., /usr/bin/python3)
    # 2. TOCTOU protection comes from using fstat() on the file descriptor,
    #    not from blocking symlinks
    # 3. We validate the final target file that the descriptor points to
    fd = None
    try:
        try:
            fd = os.open(prg, os.O_RDONLY)
        except OSError as e:
            if e.errno == 2:  # ENOENT
                raise ValueError('can not locate the program "%s"' % prg) from e
            # Preserve exception chain for debugging while providing clear message
            raise ValueError('can not access program "%s": %s' % (prg, e)) from e

        # Use fstat on file descriptor - this is safe from TOCTOU
        # The file descriptor points to the final target, even if prg was a symlink
        s = os.fstat(fd)

        if stat.S_ISDIR(s.st_mode):
            raise ValueError('can not execute directories "%s"' % prg)

        # Security check: refuse to run setuid/setgid programs
        if s.st_mode & stat.S_ISUID:
            raise ValueError('refusing to run setuid programs "%s"' % prg)

        if s.st_mode & stat.S_ISGID:
            raise ValueError('refusing to run setgid programs "%s"' % prg)

        # Check if file is executable by current user
        check = stat.S_IXOTH
        if s.st_uid == os.getuid():
            check |= stat.S_IXUSR
        if s.st_gid == os.getgid():
            check |= stat.S_IXGRP

        if not (check & s.st_mode):
            raise ValueError('exabgp will not be able to run this program "%s"' % prg)

        # Additional security check: ensure it's a regular file
        if not stat.S_ISREG(s.st_mode):
            raise ValueError('program must be a regular file "%s"' % prg)

    finally:
        if fd is not None:
            os.close(fd)

    return [prg] + [_ for _ in tokeniser.generator]
