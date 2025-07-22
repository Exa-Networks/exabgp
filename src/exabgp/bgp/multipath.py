# encoding: utf-8
"""
multipath.py

Created by Thomas Mangin on 2024-07-21.
Copyright (c) 2009-2024 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import random

from exabgp.bgp.message.update.attribute import Attributes, ASPath, NextHop, Attribute
from exabgp.bgp.message.update.nlri.vpls import VPLS
from exabgp.protocol.ip import IP
from exabgp.protocol.family import AFI, SAFI

class SuperpositionRouting:
    def __init__(self, neighbor):
        self.neighbor = neighbor

    def generate_paths(self, prefix, num_paths=3):
        """
        Generates multiple potential paths for a given prefix.
        """
        paths = []
        for _ in range(num_paths):
            paths.append(self._generate_random_path(prefix))
        return paths

    def _generate_random_path(self, prefix):
        """
        Generates a single random path for a given prefix.
        """
        # This is a simplified implementation. In a real-world scenario,
        # this function would need to generate more realistic paths.
        as_path = ASPath([self.neighbor['local-as'], random.randint(1, 65535)])
        next_hop = NextHop(str(IP.create('192.168.0.{}'.format(random.randint(1, 254)))))
        attributes = Attributes()
        attributes.add(as_path)
        attributes.add(next_hop)
        return {
            'prefix': prefix,
            'attributes': attributes,
        }

    def collapse_route_state(self, paths):
        """
        Collapses the route state to the single most optimal path.
        """
        if not paths:
            return None

        # For simplicity, we'll choose the path with the shortest AS_PATH.
        return min(paths, key=lambda p: self.get_as_path_length(p['attributes'].get(Attribute.CODE.AS_PATH)))

    def get_as_path_length(self, as_path_attribute: any) -> int:
        """
        Safely calculates the number of ASNs in a BGP AS_PATH attribute.

        This function handles multiple common formats for the AS_PATH:
        - A list or tuple of ASNs.
        - A space-separated string of ASNs.
        - A None type or empty attribute.

        Args:
            as_path_attribute: The AS_PATH attribute from the BGP route.

        Returns:
            The integer length of the path, or a very high number (infinity analog)
            if the path is invalid or empty, to ensure it's not preferred.
        """
        # A large number to represent an invalid or infinite path length
        INFINITY = 1_000_000

        if hasattr(as_path_attribute, 'aspath'):
            return len(as_path_attribute.aspath)

        if not as_path_attribute:
            return INFINITY

        # Case 1: The attribute is already a list or tuple
        if isinstance(as_path_attribute, (list, tuple)):
            return len(as_path_attribute)

        # Case 2: The attribute is a string of space-separated ASNs
        if isinstance(as_path_attribute, str):
            # Split the string by whitespace and filter out any empty strings
            # that might result from multiple spaces.
            asns = [asn for asn in as_path_attribute.strip().split(' ') if asn]
            return len(asns)

        if hasattr(as_path_attribute, 'aspath'):
            return sum(len(segment) for segment in as_path_attribute.aspath)

        # If the type is unexpected, return infinity to penalize this route
        return INFINITY


class EntanglementProtocols:
    def __init__(self, neighbor):
        self.neighbor = neighbor

    def establish_entanglement(self, peer):
        """
        Establishes entanglement with a peer.
        """
        self.neighbor.entangled_peers[peer.name()] = peer

    def break_entanglement(self, peer):
        """
        Breaks entanglement with a peer.
        """
        if peer.name() in self.neighbor.entangled_peers:
            del self.neighbor.entangled_peers[peer.name()]

    def instantaneous_failure_detection(self, peer):
        """
        Detects failures instantaneously across the network.
        """
        if peer.name() in self.neighbor.entangled_peers:
            # In a real-world scenario, this would involve a more complex
            # mechanism to detect failures.
            return not peer.is_up()
        return False

    def distributed_coherence(self):
        """
        Ensures multi-site data and state synchronization.
        """
        # This is a simplified implementation. In a real-world scenario,
        # this would involve a more complex mechanism to synchronize data.
        for peer in self.neighbor.entangled_peers.values():
            if not peer.is_up():
                self.break_entanglement(peer)
