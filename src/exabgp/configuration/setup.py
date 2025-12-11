"""setup.py - Helper functions for programmatic configuration setup.

This module provides convenience functions for creating BGP configurations
programmatically without parsing config files.

Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.neighbor.settings import NeighborSettings, SessionSettings
from exabgp.configuration.settings import ConfigurationSettings
from exabgp.protocol.family import AFI, SAFI, Family
from exabgp.protocol.ip import IP

if TYPE_CHECKING:
    from exabgp.configuration.configuration import Configuration


def parse_family(family_text: str) -> list[tuple[AFI, SAFI]]:
    """Parse family text into AFI/SAFI tuples.

    Args:
        family_text: Space-separated AFI SAFI pairs, or 'all'
                     e.g., 'ipv4 unicast', 'ipv4 unicast ipv6 unicast', 'all'

    Returns:
        List of (AFI, SAFI) tuples

    Raises:
        ValueError: If family_text format is invalid or contains unknown families.
    """
    if family_text.lower().strip() == 'all':
        return Family.all_families()

    words = family_text.lower().split()
    if len(words) % 2:
        raise ValueError(f'Invalid family format: {family_text}')

    families: list[tuple[AFI, SAFI]] = []
    for i in range(0, len(words), 2):
        afi = AFI.from_string(words[i])
        safi = SAFI.from_string(words[i + 1])
        if afi == AFI.undefined or safi == SAFI.undefined:
            raise ValueError(f'Unknown family: {words[i]} {words[i + 1]}')
        families.append((afi, safi))
    return families


def create_minimal_configuration(
    peer_address: str = '127.0.0.1',
    local_address: str = '127.0.0.1',
    local_as: int = 65533,
    peer_as: int = 65533,
    families: str = 'ipv4 unicast',
    add_path: bool = False,
) -> 'Configuration':
    """Create a minimal configuration for encode/decode operations.

    This is a convenience function for creating simple configurations
    without parsing config files. Useful for testing and CLI tools.

    Args:
        peer_address: BGP peer IP address (default: 127.0.0.1)
        local_address: Local IP address (default: 127.0.0.1)
        local_as: Local AS number (default: 65533)
        peer_as: Peer AS number (default: 65533)
        families: Space-separated address families or 'all' (default: 'ipv4 unicast')
        add_path: Enable ADD-PATH for configured families (default: False)

    Returns:
        Configured Configuration instance with one neighbor.

    Raises:
        ValueError: If families format is invalid or settings validation fails.
    """
    from exabgp.configuration.configuration import Configuration

    session = SessionSettings()
    session.peer_address = IP.from_string(peer_address)
    session.local_address = IP.from_string(local_address)
    session.local_as = ASN(local_as)
    session.peer_as = ASN(peer_as)

    neighbor_settings = NeighborSettings()
    neighbor_settings.session = session
    neighbor_settings.families = parse_family(families)

    if add_path:
        neighbor_settings.addpaths = neighbor_settings.families.copy()

    config_settings = ConfigurationSettings()
    config_settings.neighbors = [neighbor_settings]

    return Configuration.from_settings(config_settings)
