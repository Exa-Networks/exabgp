"""root.py

The top of the configuration.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.bgp.neighbor.settings import NeighborSettings
from exabgp.configuration.grammar.context import ReadContext
from exabgp.configuration.grammar.nodes import Block
from exabgp.configuration.grammar.section import Section, Values
from exabgp.configuration.grammar.tree.neighbor import NEIGHBOR, TEMPLATE
from exabgp.configuration.grammar.tree.process import PROCESS
from exabgp.configuration.settings import ConfigurationSettings, ProcessSettings


class ConfigurationSection(Section[ConfigurationSettings]):
    def build(self, name: str, values: Values, context: ReadContext) -> ConfigurationSettings:
        processes: dict[str, ProcessSettings] = values.get('processes', {})
        neighbors: list[NeighborSettings] = values.get('neighbors', [])
        return ConfigurationSettings(neighbors=neighbors, processes=processes)


ROOT = Block('', field='', section=ConfigurationSection(), children=(PROCESS, NEIGHBOR, TEMPLATE))
