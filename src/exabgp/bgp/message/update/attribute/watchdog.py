"""watchdog.py

Sentinel class for watchdog attribute.

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations


class Watchdog:
    """Watchdog attribute with name.

    Used as internal pseudo-attribute to track route announcements
    that should be controlled via watchdog commands.
    """

    __slots__ = ('_name',)

    def __init__(self, name: str) -> None:
        self._name = name

    @classmethod
    def _create_sentinel(cls) -> Watchdog:
        """Create the NoWatchdog sentinel instance."""
        return cls('')

    @property
    def name(self) -> str:
        return self._name

    def __bool__(self) -> bool:
        return bool(self._name)

    def __str__(self) -> str:
        return self._name

    def __repr__(self) -> str:
        if self._name:
            return f'Watchdog({self._name!r})'
        return 'NoWatchdog'

    def __hash__(self) -> int:
        return hash(self._name)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Watchdog):
            return self._name == other._name
        return False

    # written out: mypyc fails to derive __ne__ from __eq__ for the subclasses. The operator,
    # not a call to __eq__, so NotImplemented is answered the way Python answers it.
    def __ne__(self, other: object) -> bool:
        return not self == other


# Singleton sentinel - empty name is falsy
NoWatchdog: Watchdog = Watchdog._create_sentinel()
