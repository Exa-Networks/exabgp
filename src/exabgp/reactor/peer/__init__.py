"""Peer package for BGP peer state management.

This package contains the Peer class and supporting infrastructure
for managing BGP peer connections and message handling.
"""

# Re-export from the main peer module
from exabgp.reactor.peer.peer import FORCE_GRACEFUL, Interrupted, Peer, Stats

__all__ = ['FORCE_GRACEFUL', 'Interrupted', 'Peer', 'Stats']
