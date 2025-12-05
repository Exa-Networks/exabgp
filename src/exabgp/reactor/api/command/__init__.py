from __future__ import annotations

from exabgp.reactor.api.command.command import Command as Command  # Re-export

# Note: The register_* functions are kept for backward compatibility
# but the decorators they trigger are no longer used for dispatch.
# Dispatch is handled by exabgp.reactor.api.dispatch module.
from exabgp.reactor.api.command.reactor import register_reactor
from exabgp.reactor.api.command.neighbor import register_neighbor
from exabgp.reactor.api.command.peer import register_peer
from exabgp.reactor.api.command.announce import register_announce
from exabgp.reactor.api.command.rib import register_rib
from exabgp.reactor.api.command.watchdog import register_watchdog

# Trigger decorator registration (for any code that still uses Command.callback)
register_reactor()
register_neighbor()
register_peer()
register_announce()
register_rib()
register_watchdog()
