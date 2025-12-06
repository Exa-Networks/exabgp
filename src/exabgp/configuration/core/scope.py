"""scope.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import pprint
from typing import Any
from typing import TYPE_CHECKING

# from copy import deepcopy
from exabgp.protocol.ip import IP
from exabgp.configuration.core.error import Error

if TYPE_CHECKING:
    from exabgp.rib.route import Route


class Scope(Error):
    _routes: list[Route]

    def __init__(self) -> None:
        Error.__init__(self)
        self._location: list[str] = []
        self._added: set[str] = set()
        self._all: dict[str, Any] = {
            'template': {},
        }
        self._routes = []
        self._current: dict[str, Any] = self._all

    def __repr__(self) -> str:
        return pprint.pformat(self.__dict__, indent=3)

    def clear(self) -> None:
        self._location = []
        self._added = set()
        self._all = {
            'template': {},
        }
        self._routes = []
        self._current = self._all

    # building route list

    def get_routes(self) -> list[Route]:
        return self._routes

    def pop_routes(self) -> list[Route]:
        routes = self._routes
        self._routes = []
        return routes

    def extend_routes(self, value: list[Route]) -> None:
        self._routes.extend(value)

    # building nlri

    def append_route(self, value: Route) -> None:
        self._routes.append(value)

    def get_route(self) -> Route:
        return self._routes[-1]

    def pop_route(self) -> Route:
        return self._routes.pop()

    # context

    def enter(self, location: str) -> None:
        self._location.append(location)

    def leave(self) -> str:
        if not len(self._location):
            return ''  # This is signaling an issue to the caller without raising
        return self._location.pop()

    def location(self) -> str:
        return '/'.join(self._location)

    # context

    def to_context(self, name: str = '') -> None:
        self._current = self._all
        for context in self._location:
            if context not in self._current:
                self._current[context] = {}
            self._current = self._current[context]
        if name:
            self._current = self._current.setdefault(name, {})

    def pop_context(self, name: str) -> Any:
        returned = self._all.pop(name)

        for inherit in returned.get('inherit', []):
            if inherit not in self._all['template'].get('neighbor', {}):
                self.throw('invalid template name referenced')
            self.transfer(self._all['template']['neighbor'][inherit], returned)

        return returned

    # key / value

    def set_value(self, name: str, value: Any) -> None:
        self._current[name] = value

    def attribute_add(self, name: str, data: Any) -> None:
        self.get_route().attributes.add(data)
        if name not in self._added:
            self._added.add(name)

    def nlri_assign(self, name: str, command: str, data: Any) -> None:
        self.get_route().nlri.assign(command, data)

    def nlri_add(self, name: str, command: str, data: Any) -> None:
        self.get_route().nlri.add(data)

    def nlri_nexthop(self, name: str, data: Any) -> None:
        self.get_route().nlri.nexthop = data

    def append(self, name: str, data: Any) -> None:
        self._current.setdefault(name, []).append(data)

    def extend(self, name: str, data: Any) -> None:
        self._current.setdefault(name, []).extend(data)

    def merge(self, name: str, data: dict[str, Any]) -> None:
        for key in data:
            value = data[key]
            if key not in self._current:
                self.set_value(key, value)
            elif isinstance(value, list):
                self._current[key].extend(value)
            elif isinstance(value, dict):
                self.transfer(value, self._current[key])
            else:
                self.set_value(key, value)

    def inherit(self, data: dict[str, Any]) -> None:
        self.transfer(data, self._current)

    def transfer(self, source: dict[str, Any], destination: dict[str, Any]) -> None:
        for key, value in source.items():
            if key not in destination:
                destination[key] = value
            elif isinstance(source[key], list):
                destination[key].extend(value)
            elif isinstance(source[key], dict):
                if key not in destination:
                    destination[key] = source[key]
                else:
                    self.transfer(source[key], destination[key])
            elif isinstance(source[key], int) or isinstance(source[key], IP) or isinstance(source[key], str):
                destination[key] = value
            else:
                self.throw(
                    f'can not copy "{key}" (as it is of type {type(source[key])}) and it exists in both the source and destination',
                )

    def get(self, name: str = '', default: object = None) -> Any:
        if name:
            return self._current.get(name, default)
        return self._current

    def pop(self, name: str = '', default: Any = None) -> Any:
        if name == '':
            return dict((k, self._current.pop(k)) for k in list(self._current))
        return self._current.pop(name, default)

    def template(self, template: str, name: str) -> Any:
        return self._all['template'].get(template, {}).get(name, {})
