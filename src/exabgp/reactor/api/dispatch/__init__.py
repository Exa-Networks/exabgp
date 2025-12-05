"""dispatch/__init__.py

API command dispatch module.

Provides parallel v4 and v6 dispatchers that parse commands in their native
format and route to the appropriate handler functions.

Created on 2025-12-05.
Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.reactor.api.dispatch.common import (
    Handler,
    UnknownCommand,
    NoMatchingPeers,
    COMMANDS,
    get_commands,
    # Tree dispatch infrastructure
    DispatchTree,
    DispatchNode,
    SELECTOR_KEY,
    dispatch,
    extract_selector,
)
from exabgp.reactor.api.dispatch.v4 import dispatch_v4
from exabgp.reactor.api.dispatch.v6 import dispatch_v6

__all__ = [
    'Handler',
    'UnknownCommand',
    'NoMatchingPeers',
    'COMMANDS',
    'get_commands',
    # Tree dispatch infrastructure
    'DispatchTree',
    'DispatchNode',
    'SELECTOR_KEY',
    'dispatch',
    'extract_selector',
    # Dispatchers
    'dispatch_v4',
    'dispatch_v6',
]
