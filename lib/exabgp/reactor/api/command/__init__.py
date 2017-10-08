from exabgp.reactor.api.command.command import Command

from exabgp.reactor.api.command.reactor import register_reactor
from exabgp.reactor.api.command.neighbor import register_neighbor
from exabgp.reactor.api.command.announce import register_announce
from exabgp.reactor.api.command.rib import register_rib
from exabgp.reactor.api.command.watchdog import register_watchdog

register_reactor()
register_neighbor()
register_announce()
register_rib()
register_watchdog()
