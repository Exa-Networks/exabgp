"""cli_process.py

The processes exabgp runs for its own command line: one for the named pipe, one for the
unix socket, each when the environment enables it.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import os
import sys
import uuid
from typing import Any

API_PREFIX = 'api-internal-cli'  # the name of a process exabgp adds itself starts with it

# the environment variable enabling the process, and the mode the process is told
MODES = (('exabgp_cli_pipe', 'pipe'), ('exabgp_cli_socket', 'socket'))


def cli_processes() -> dict[str, dict[str, Any]]:
    """The processes of the command line, by name, as a configuration names a process."""
    program = os.path.join(os.environ.get('PWD', ''), sys.argv[0])
    found: dict[str, dict[str, Any]] = {}
    for variable, mode in MODES:
        if not os.environ.get(variable, ''):
            continue
        name = '{}-{}-{:x}'.format(API_PREFIX, mode, uuid.uuid1().fields[0])
        found[name] = {
            'run': [sys.executable, program],
            'encoder': 'text',
            'respawn': True,
            'env': {'exabgp_api_cli_mode': mode},
        }
    return found
