"""__init__.py

Created by Thomas Mangin on 2015-05-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import socket


__host_name: str = ''
# None until resolved: '' is an answer (no domain known) and must be cached like any other
__domain_name: str | None = None


def host() -> str:
    global __host_name
    if not __host_name:
        value = socket.gethostname()
        __host_name = value.split('.')[0] if value else 'localhost'
    return __host_name


def domain() -> str:
    """What follows the host in the FQDN, '' when the resolver knows no domain.

    This returned the first label, the host again, from 2015.  Nothing sent it: the
    Hostname capability takes its names from the configuration, and only fills in from
    here when built with no arguments, which the daemon never does.
    """
    global __domain_name
    if __domain_name is None:
        _, _, __domain_name = socket.getfqdn().rstrip('.').partition('.')
    return __domain_name
