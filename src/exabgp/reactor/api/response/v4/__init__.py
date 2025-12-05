"""v4/__init__.py

API v4 (legacy) response encoders.
These wrap the v6 JSON encoder and convert output to v4 format.

Created by Thomas Mangin on 2024-12-04.
Copyright (c) 2024 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.reactor.api.response.v4.json import V4JSON
from exabgp.reactor.api.response.v4.text import V4Text

__all__ = ['V4JSON', 'V4Text']
