# encoding: utf-8
"""
neural_plasticity_test.py

Created by Jules on 2025-07-21.
Copyright (c) 2024-2025 Your Company. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import unittest
import os
import json
from src.exabgp.bgp.neural_plasticity import (
    AdaptiveWeightMatrix,
    NeuralPlasticityEngine,
    AsyncTelemetryService,
    AsyncPathVolatilityMonitor,
    BogusRouteMonitor,
)


class TestNeuralPlasticity(unittest.TestCase):
    def setUp(self):
        self.matrix = AdaptiveWeightMatrix()
        self.engine = NeuralPlasticityEngine(self.matrix)
        self.log_file = "test_telemetry.log"
        self.telemetry_service = AsyncTelemetryService(self.log_file)
        self.engine.subscribe(self.telemetry_service)

    def tearDown(self):
        if os.path.exists(self.log_file):
            os.remove(self.log_file)

    def test_adaptive_weight_matrix(self):
        self.matrix.set_weight(("A", "B"), 0.5)
        self.assertEqual(self.matrix.get_weight(("A", "B")), 0.5)
        self.assertEqual(self.matrix.get_top_paths(1), [(("A", "B"), 0.5)])

    def test_neural_plasticity_engine(self):
        self.engine.strengthen_pathway(("A", "B"), 0.9)
        self.assertGreater(self.matrix.get_weight(("A", "B")), 0.0)
        self.engine.prune_pathway(("A", "B"), 0.8)
        self.assertLess(self.matrix.get_weight(("A", "B")), 0.0)
        self.engine.grow_new_connection(("C", "D"))
        self.assertEqual(self.matrix.get_weight(("C", "D")), 0.1)

    def test_async_telemetry_service(self):
        self.engine.strengthen_pathway(("A", "B"), 0.9)
        with open(self.log_file, "r") as f:
            log_entry = json.loads(f.readline())
            self.assertEqual(log_entry["event_type"], "pathway_strengthened")
            self.assertEqual(log_entry["pathway"], ["A", "B"])

    def test_async_path_volatility_monitor(self):
        log_file = "test_volatility.log"
        try:
            monitor = AsyncPathVolatilityMonitor(threshold=2)
            telemetry_service = AsyncTelemetryService(log_file)
            monitor.subscribe(telemetry_service)

            monitor.on_path_change(("A", "B"))
            monitor.on_path_change(("A", "B"))
            monitor.on_path_change(("A", "B"))

            with open(log_file, "r") as f:
                log_entry = json.loads(f.readline())
                self.assertEqual(log_entry["event_type"], "HIJACK_ALERT")
                self.assertEqual(log_entry["pathway"], ["A", "B"])
        finally:
            if os.path.exists(log_file):
                os.remove(log_file)

    def test_bogus_route_monitor(self):
        log_file = "test_bogus_route.log"
        try:
            bogon_prefixes = ["10.0.0.0/8", "192.168.0.0/16"]
            monitor = BogusRouteMonitor(bogon_prefixes)
            telemetry_service = AsyncTelemetryService(log_file)
            monitor.subscribe(telemetry_service)

            monitor.on_route_announcement("10.1.2.3", ("A", "B"))

            with open(log_file, "r") as f:
                log_entry = json.loads(f.readline())
                self.assertEqual(log_entry["event_type"], "BOGUS_ROUTE_ALERT")
                self.assertEqual(log_entry["pathway"], ["A", "B"])
        finally:
            if os.path.exists(log_file):
                os.remove(log_file)


if __name__ == "__main__":
    unittest.main()
