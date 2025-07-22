# encoding: utf-8
"""
tui.py

Created by Jules on 2025-07-21.
Copyright (c) 2024-2025 Your Company. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import npyscreen
from src.exabgp.bgp.neural_plasticity import AdaptiveWeightMatrix


class TopPathsGrid(npyscreen.GridColTitles):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.col_titles = ["Pathway", "Weight"]

    def custom_print_cell(self, actual_cell, cell_display_value):
        pass


class Dashboard(npyscreen.FormBaseNew):
    def create(self):
        self.name = "BGP Neural Plasticity Dashboard"
        self.add(
            npyscreen.TitleText,
            name="Top 10 Most Trusted BGP Paths",
            editable=False,
        )
        self.grid = self.add(TopPathsGrid, max_height=12)

    def while_waiting(self):
        self.update_grid()

    def update_grid(self):
        # In a real application, the AdaptiveWeightMatrix would be passed in
        # or accessed through a shared context.
        matrix = AdaptiveWeightMatrix()
        # For demonstration purposes, we'll add some dummy data.
        matrix.set_weight(("AS65001", "AS65002", "AS65003"), 0.9)
        matrix.set_weight(("AS65001", "AS65004", "AS65005"), 0.8)
        matrix.set_weight(("AS65001", "AS65006"), 0.7)

        top_paths = matrix.get_top_paths(10)
        self.grid.values = [[str(path), f"{weight:.2f}"] for path, weight in top_paths]
        self.display()


class App(npyscreen.NPSAppManaged):
    def onStart(self):
        self.addForm("MAIN", Dashboard, name="BGP Neural Plasticity Dashboard")


if __name__ == "__main__":
    app = App()
    app.run()
