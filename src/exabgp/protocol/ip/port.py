"""port.py

TCP/UDP port number mappings from IANA registry.
https://www.iana.org/assignments/service-names-port-numbers

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import json
import sys
from typing import ClassVar, Dict

from exabgp.protocol.resource import Resource


def _load_port_data() -> Dict[int, str]:
    """Load port name mappings from JSON data file.

    Works with both:
    - Regular package installation (importlib.resources)
    - Zipapp distribution (importlib.resources handles zip archives)

    Returns:
        Dictionary mapping port numbers (int) to service names (str)
    """
    if sys.version_info >= (3, 9):
        # Python 3.9+ has importlib.resources.files()
        from importlib.resources import files

        data_file = files('exabgp.protocol.ip').joinpath('port_data.json')
        content = data_file.read_text(encoding='utf-8')
    else:
        # Python 3.8 compatibility
        from importlib.resources import read_text

        content = read_text('exabgp.protocol.ip', 'port_data.json')

    data = json.loads(content)
    # JSON keys are strings, convert to int
    return {int(k): v for k, v in data['names'].items()}


class Port(Resource):
    """TCP/UDP port number resource.

    Provides bidirectional mapping between port numbers and service names.
    Port data is loaded from port_data.json on first access.
    """

    NAME: ClassVar[str] = 'port'

    # Lazily loaded from JSON
    _names_loaded: ClassVar[bool] = False
    names: ClassVar[Dict[int, str]] = {}
    codes: ClassVar[Dict[str, int]] = {}

    @classmethod
    def _ensure_loaded(cls) -> None:
        """Ensure port data is loaded (lazy initialization)."""
        if not cls._names_loaded:
            cls.names = _load_port_data()
            cls.codes = {name: port for port, name in cls.names.items()}
            cls._names_loaded = True

    def __str__(self) -> str:
        return str(int(self))

    def name(self) -> str:
        self._ensure_loaded()
        return self.names.get(self, '%d' % int(self))

    def short(self) -> str:
        self._ensure_loaded()
        return self.names.get(self, '%ld' % self)

    @classmethod
    def _value(cls, string: str) -> int:
        cls._ensure_loaded()
        return super()._value(string)

    @classmethod
    def named(cls, string: str) -> Resource:
        cls._ensure_loaded()
        return super().named(string)
