"""core/__init__.py

Created by Thomas Mangin on 2015-06-19.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# flake8: noqa: F401,E261

from __future__ import annotations

from exabgp.configuration.core.error import Error
from exabgp.configuration.core.scope import Scope
from exabgp.configuration.core.section import Section
from exabgp.configuration.core.parser import Parser

# Backward compatibility alias
Tokeniser = Parser
