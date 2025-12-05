from __future__ import annotations

# Command modules provide handler functions used by dispatch/v4.py and dispatch/v6.py
from exabgp.reactor.api.command.reactor import register_reactor
from exabgp.reactor.api.command.neighbor import register_neighbor
from exabgp.reactor.api.command.peer import register_peer
from exabgp.reactor.api.command.announce import register_announce
from exabgp.reactor.api.command.rib import register_rib
from exabgp.reactor.api.command.watchdog import register_watchdog

# Initialize modules (no-op functions kept for compatibility)
register_reactor()
register_neighbor()
register_peer()
register_announce()
register_rib()
register_watchdog()
