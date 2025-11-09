"""
environment.py

Created by Thomas Mangin on 2020-05-14.
Copyright (c) 2011-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import os
import sys
import pwd

from exabgp.logger.handler import levels

from exabgp.util.ip import isip
from exabgp.protocol.ip import IP

from exabgp.environment import base


def integer(_):
    return int(_)


def real(_):
    return float(_)


def lowunquote(_):
    return _.strip().strip('\'"').lower()


def unquote(_):
    return _.strip().strip('\'"')


def quote(_):
    return f"'{str(_)}'"


def quote_list(_):
    joined = ' '.join([str(x) for x in _])
    return f"'{joined}'"


def nop(_):
    return _


def boolean(_):
    return _.lower() in ('1', 'yes', 'on', 'enable', 'true')


def api(_):
    encoder = _.lower()
    if encoder not in ('text', 'json'):
        raise TypeError('invalid encoder')
    return encoder


def methods(_):
    return _.upper().split()


def list(_):
    joined = ' '.join(_)
    return f"'{joined}'"


def lower(_):
    return str(_).lower()


def ip(_):
    if isip(_):
        return _
    raise TypeError(f'ip {_} is invalid')


def ip_list(_):
    ips = []
    for ip in _.split(' '):
        if not ip:
            continue
        elif isip(ip):
            ips.append(IP.create(ip))
        else:
            raise TypeError(f'ip {ip} is invalid')
    return ips


def user(_):
    # XXX: incomplete
    try:
        pwd.getpwnam(_)
        # uid = answer[2]
    except KeyError:
        raise TypeError(f'user {_} is not found on this system') from None
    return _


def folder(path):
    paths = root(path)
    options = [p for p in paths if os.path.exists(path)]
    if not options:
        raise TypeError(f'{path} does not exists')
    first = options[0]
    if not first:
        raise TypeError(f'{first} does not exists')
    return first


def path(path):
    split = sys.argv[0].split('src/exabgp')
    if len(split) > 1:
        prefix = os.sep.join(split[:1])
        if prefix and path.startswith(prefix):
            path = path[len(prefix) :]
    home = os.path.expanduser('~')
    if path.startswith(home):
        return f"'~{path[len(home) :]}'"
    return f"'{path}'"


def conf(path):
    first = folder(path)
    if not os.path.isfile(first):
        raise TypeError(f'{path} is not a file')
    return first


def exe(path):
    first = conf(path)
    if not os.access(first, os.X_OK):
        raise TypeError(f'{first} is not an executable')
    return first


# def syslog(path):
#     path = unquote(path)
#     if path in ('stdout', 'stderr'):
#         return path
#     if path.startswith('host:'):
#         return path
#     return path


def umask_read(_):
    return int(_, 8)


def umask_write(_):
    return f"'{oct(_)}'"


def syslog_value(log):
    log = log.upper()
    if log not in levels:
        raise TypeError(f'invalid log level {log}')
    return log


def syslog_name(log):
    log = log.upper()
    if log not in levels:
        raise TypeError(f'invalid log level {log}')
    return log


def root(path):
    roots = base.root.split(os.sep)
    location = []
    for index in range(len(roots) - 1, -1, -1):
        if roots[index] == 'src':
            if index:
                location = roots[:index]
            break
    root = os.path.join(*location)
    paths = [
        os.path.normpath(os.path.join(os.path.join(os.sep, root, path))),
        os.path.normpath(os.path.expanduser(unquote(path))),
        os.path.normpath(os.path.join('/', path)),
    ]
    return paths
