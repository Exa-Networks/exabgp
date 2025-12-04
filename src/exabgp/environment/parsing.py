"""environment.py

Created by Thomas Mangin on 2020-05-14.
Copyright (c) 2011-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import os
import sys
import pwd
from typing import Any

from exabgp.logger.handler import levels

from exabgp.util.ip import isip
from exabgp.protocol.ip import IP

from exabgp.environment import base


def integer(_: Any) -> int:
    return int(_)


def real(_: Any) -> float:
    return float(_)


def lowunquote(_: str) -> str:
    return _.strip().strip('\'"').lower()


def unquote(_: str) -> str:
    return _.strip().strip('\'"')


def quote(_: Any) -> str:
    return f"'{_!s}'"


def quote_list(_: list[Any]) -> str:
    joined = ' '.join([str(x) for x in _])
    return f"'{joined}'"


def nop(_: Any) -> Any:
    return _


def boolean(_: str) -> bool:
    return _.lower() in ('1', 'yes', 'on', 'enable', 'true')


def api(_: str) -> str:
    encoder = _.lower()
    if encoder not in ('text', 'json'):
        raise TypeError('invalid encoder')
    return encoder


def methods(_: str) -> list[str]:
    return _.upper().split()


def format_list(_: list[str]) -> str:
    joined = ' '.join(_)
    return f"'{joined}'"


def lower(_: Any) -> str:
    return str(_).lower()


def ip(_: str) -> str:
    if isip(_):
        return _
    raise TypeError(f'ip {_} is invalid')


def ip_list(_: str) -> list[IP]:
    ips: list[IP] = []
    for ip in _.split(' '):
        if not ip:
            continue
        elif isip(ip):
            ips.append(IP.from_string(ip))
        else:
            raise TypeError(f'ip {ip} is invalid')
    return ips


def user(_: str) -> str:
    # XXX: incomplete
    try:
        pwd.getpwnam(_)
        # uid = answer[2]
    except KeyError:
        raise TypeError(f'user {_} is not found on this system') from None
    return _


def folder(path: str) -> str:
    paths: list[str] = root(path)
    options: list[str] = [p for p in paths if os.path.exists(path)]
    if not options:
        raise TypeError(f'{path} does not exists')
    first: str = options[0]
    if not first:
        raise TypeError(f'{first} does not exists')
    return first


def path(path: str) -> str:
    split: list[str] = sys.argv[0].split('src/exabgp')
    if len(split) > 1:
        prefix: str = os.sep.join(split[:1])
        if prefix and path.startswith(prefix):
            path = path[len(prefix) :]
    home: str = os.path.expanduser('~')
    if path.startswith(home):
        return f"'~{path[len(home) :]}'"
    return f"'{path}'"


def conf(path: str) -> str:
    first: str = folder(path)
    if not os.path.isfile(first):
        raise TypeError(f'{path} is not a file')
    return first


def exe(path: str) -> str:
    first: str = conf(path)
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


def umask_read(_: str) -> int:
    return int(_, 8)


def umask_write(_: int) -> str:
    return f"'{oct(_)}'"


def syslog_value(log: str) -> str:
    log = log.upper()
    if log not in levels:
        raise TypeError(f'invalid log level {log}')
    return log


def syslog_name(log: str) -> str:
    log = log.upper()
    if log not in levels:
        raise TypeError(f'invalid log level {log}')
    return log


def root(path: str) -> list[str]:
    roots: list[str] = base.ROOT.split(os.sep)
    location: list[str] = []
    for index in range(len(roots) - 1, -1, -1):
        if roots[index] == 'src':
            if index:
                location = roots[:index]
            break
    root_path: str = os.path.join(*location)
    paths: list[str] = [
        os.path.normpath(os.path.join(os.path.join(os.sep, root_path, path))),
        os.path.normpath(os.path.expanduser(unquote(path))),
        os.path.normpath(os.path.join('/', path)),
    ]
    return paths
