# encoding: utf-8
"""
neural_plasticity.py

Created by Jules on 2025-07-21.
Copyright (c) 2024-2025 Your Company. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
import ipaddress


class AdaptiveWeightMatrix:
    """
    Represents the adaptive weight matrix for BGP paths.
    """

    def __init__(self):
        self.matrix = defaultdict(lambda: defaultdict(float))

    def get_weight(self, path: tuple) -> float:
        """
        Gets the weight of a given path.
        """
        return self.matrix.get(path, 0.0)

    def set_weight(self, path: tuple, weight: float):
        """
        Sets the weight of a given path.
        """
        self.matrix[path] = weight

    def get_top_paths(self, n: int = 10) -> list[tuple]:
        """
        Returns the top n most heavily weighted paths.
        """
        return sorted(self.matrix.items(), key=lambda item: item[1], reverse=True)[:n]


class NeuralPlasticityEngine:
    """
    Simulates the neural plasticity of the BGP routing engine.
    """

    def __init__(self, adaptive_weight_matrix: AdaptiveWeightMatrix):
        self.adaptive_weight_matrix = adaptive_weight_matrix
        self.event_listeners = []

    def subscribe(self, listener):
        """
        Subscribes a listener to receive events.
        """
        self.event_listeners.append(listener)

    def _emit_event(self, event_type: str, pathway: tuple, reason: str):
        """
        Emits an event to all subscribed listeners.
        """
        for listener in self.event_listeners:
            listener.on_event(event_type, pathway, reason)

    def strengthen_pathway(self, pathway: tuple, success_rate: float):
        """
        Strengthens a pathway based on its success rate.
        """
        current_weight = self.adaptive_weight_matrix.get_weight(pathway)
        new_weight = current_weight + (success_rate * 0.1)
        self.adaptive_weight_matrix.set_weight(pathway, new_weight)
        self._emit_event("pathway_strengthened", pathway, f"success_rate > {success_rate}")

    def prune_pathway(self, pathway: tuple, failure_rate: float):
        """
        Prunes a pathway based on its failure rate.
        """
        current_weight = self.adaptive_weight_matrix.get_weight(pathway)
        new_weight = current_weight - (failure_rate * 0.2)
        self.adaptive_weight_matrix.set_weight(pathway, new_weight)
        self._emit_event("pathway_pruned", pathway, f"failure_rate > {failure_rate}")

    def grow_new_connection(self, pathway: tuple):
        """
        Grows a new connection.
        """
        self.adaptive_weight_matrix.set_weight(pathway, 0.1)
        self._emit_event("new_connection_grown", pathway, "new connection")


class AsyncTelemetryService:
    """
    An asynchronous telemetry service that subscribes to events from the
    NeuralPlasticityEngine.
    """

    def __init__(self, log_file: str):
        self.log_file = log_file

    def on_event(self, event_type: str, pathway: tuple, reason: str):
        """
        Handles an event from the NeuralPlasticityEngine.
        """
        log_entry = {
            "timestamp": time.time(),
            "event_type": event_type,
            "pathway": pathway,
            "reason": reason,
        }
        with open(self.log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

    def __repr__(self):
        return f"AsyncTelemetryService(log_file='{self.log_file}')"


class AsyncPathVolatilityMonitor:
    """
    Monitors the volatility of BGP paths.
    """

    def __init__(self, threshold: int = 10):
        self.threshold = threshold
        self.path_changes = defaultdict(int)
        self.event_listeners = []

    def subscribe(self, listener):
        """
        Subscribes a listener to receive events.
        """
        self.event_listeners.append(listener)

    def _emit_event(self, event_type: str, pathway: tuple, reason: str):
        """
        Emits an event to all subscribed listeners.
        """
        for listener in self.event_listeners:
            listener.on_event(event_type, pathway, reason)

    def on_path_change(self, path: tuple):
        """
        Handles a path change event.
        """
        self.path_changes[path] += 1
        if self.path_changes[path] > self.threshold:
            self._emit_event(
                "HIJACK_ALERT",
                path,
                f"path volatility exceeded threshold ({self.threshold})",
            )


class BogusRouteMonitor:
    """
    Monitors for bogus route announcements.
    """

    def __init__(self, bogon_prefixes: list[str]):
        self.bogon_prefixes = bogon_prefixes
        self.event_listeners = []

    def subscribe(self, listener):
        """
        Subscribes a listener to receive events.
        """
        self.event_listeners.append(listener)

    def _emit_event(self, event_type: str, pathway: tuple, reason: str):
        """
        Emits an event to all subscribed listeners.
        """
        for listener in self.event_listeners:
            listener.on_event(event_type, pathway, reason)

    def on_route_announcement(self, route: str, pathway: tuple):
        """
        Handles a route announcement event.
        """
        try:
            ip_route = ipaddress.ip_address(route)
            for prefix_str in self.bogon_prefixes:
                prefix = ipaddress.ip_network(prefix_str)
                if ip_route in prefix:
                    self._emit_event(
                        "BOGUS_ROUTE_ALERT",
                        pathway,
                        f"route announced from bogon prefix {prefix_str}",
                    )
                    break
        except ValueError:
            # Not a valid IP address, so we can't check it.
            pass
