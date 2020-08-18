# encoding: utf-8
"""
parse_process.py

Created by Thomas Mangin on 2015-06-18.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

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
    prg = tokeniser()

    if prg[0] != '/':
        if prg.startswith('etc/exabgp'):
            options = _make_path(prg)
        else:
            options = [
                os.path.abspath(os.path.join('/etc/exabgp', prg)),
                os.path.abspath(os.path.join(os.path.dirname(tokeniser.fname), prg)),
            ]
            options.extend((os.path.abspath(os.path.join(p, prg)) for p in os.getenv('PATH').split(':')))
        for option in options:
            if os.path.exists(option):
                prg = option

    if not os.path.exists(prg):
        raise ValueError('can not locate the the program "%s"' % prg)

    # race conditions are possible, those are sanity checks not security ones ...
    s = os.stat(prg)

    if stat.S_ISDIR(s.st_mode):
        raise ValueError('can not execute directories "%s"' % prg)

    if s.st_mode & stat.S_ISUID:
        raise ValueError('refusing to run setuid programs "%s"' % prg)

    check = stat.S_IXOTH
    if s.st_uid == os.getuid():
        check |= stat.S_IXUSR
    if s.st_gid == os.getgid():
        check |= stat.S_IXGRP

    if not check & s.st_mode:
        raise ValueError('exabgp will not be able to run this program "%s"' % prg)

    return [prg] + [_ for _ in tokeniser.generator]
