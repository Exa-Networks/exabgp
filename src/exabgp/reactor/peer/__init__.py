"""Peer package for BGP peer state management.

This package contains the Peer class and supporting infrastructure
for managing BGP peer connections and message handling.
"""

# Re-export from the main peer module for backward compatibility
from exabgp.reactor.peer._peer import FORCE_GRACEFUL, Interrupted, Peer, Stats

__all__ = ['FORCE_GRACEFUL', 'Interrupted', 'Peer', 'Stats']
