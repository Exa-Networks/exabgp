"""__init__.py

Created by Thomas Mangin on 2015-05-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import time
import socket


__warned: bool = False
__host_name: str = ''
__domain_name: str = ''

__warning: str = """
Your OS is very slow when returning the host FQDN
Most likely you do not have valid forward/reverse DNS setup
Adding your hostname to the /etc/hosts file should fix the issue
"""


def host() -> str:
    global __host_name
    if not __host_name:
        value = socket.gethostname()
        __host_name = value.split('.')[0] if value else 'localhost'
    return __host_name


def domain() -> str:
    global __domain_name
    if not __domain_name:
        value = socket.getfqdn()
        __domain_name = value.split('.')[0] if value else 'localhost'
    return __domain_name


def warn() -> str:
    if __warned:
        return ''

    now = time.time()
    _ = host(), domain()
    if time.time() - now > 1.0:
        return __warning
    return ''
