"""
environment.py

Created by Thomas Mangin on 2020-05-14.
Copyright (c) 2011-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

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
    return "'%s'" % str(_)


def quote_list(_):
    return "'%s'" % ' '.join([str(x) for x in _])


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
    return "'%s'" % ' '.join(_)


def lower(_):
    return str(_).lower()


def ip(_):
    if isip(_):
        return _
    raise TypeError('ip %s is invalid' % _)


def ip_list(_):
    ips = []
    for ip in _.split(' '):
        if not ip:
            continue
        elif isip(ip):
            ips.append(IP.create(ip))
        else:
            raise TypeError('ip %s is invalid' % ip)
    return ips


def user(_):
    # XXX: incomplete
    try:
        pwd.getpwnam(_)
        # uid = answer[2]
    except KeyError:
        raise TypeError('user %s is not found on this system' % _)
    return _


def folder(path):
    paths = root(path)
    options = [p for p in paths if os.path.exists(path)]
    if not options:
        raise TypeError('%s does not exists' % path)
    first = options[0]
    if not first:
        raise TypeError('%s does not exists' % first)
    return first


def path(path):
    split = sys.argv[0].split('src/exabgp')
    if len(split) > 1:
        prefix = os.sep.join(split[:1])
        if prefix and path.startswith(prefix):
            path = path[len(prefix) :]
    home = os.path.expanduser('~')
    if path.startswith(home):
        return "'~%s'" % path[len(home) :]
    return "'%s'" % path


def conf(path):
    first = folder(path)
    if not os.path.isfile(first):
        raise TypeError('%s is not a file' % path)
    return first


def exe(path):
    first = conf(path)
    if not os.access(first, os.X_OK):
        raise TypeError('%s is not an executable' % first)
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
    return "'%s'" % (oct(_))


def syslog_value(log):
    log = log.upper()
    if log not in levels:
        raise TypeError('invalid log level %s' % log)
    return log


def syslog_name(log):
    log = log.upper()
    if log not in levels:
        raise TypeError('invalid log level %s' % log)
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
