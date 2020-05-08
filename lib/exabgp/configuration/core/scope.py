# encoding: utf-8
"""
scope.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import sys
import pprint

# from copy import deepcopy
from exabgp.vendoring import six
from exabgp.protocol.ip import IP
from exabgp.configuration.core.error import Error


if sys.version_info > (3,):
    long = int


class Scope(Error):
    def __init__(self):
        Error.__init__(self)
        self._location = []
        self._added = set()
        self._all = {
            'template': {},
        }
        self._routes = []
        self._current = self._all

    def __repr__(self):
        return pprint.pformat(self.__dict__, indent=3)

    def clear(self):
        self._location = []
        self._added = set()
        self._all = {
            'template': {},
        }
        self._routes = []
        self._current = self._all

    # building route list

    def get_routes(self):
        return self._routes

    def pop_routes(self):
        routes = self._routes
        self._routes = []
        return routes

    def extend_routes(self, value):
        self._routes.extend(value)

    # building nlri

    def append_route(self, value):
        return self._routes.append(value)

    def get_route(self):
        return self._routes[-1]

    def pop_route(self):
        return self._routes.pop()

    # context

    def enter(self, location):
        self._location.append(location)

    def leave(self):
        if not len(self._location):
            return ''  # This is signaling an issue to the caller without raising
        return self._location.pop()

    def location(self):
        return '/'.join(self._location)

    # context

    def to_context(self, name=''):
        self._current = self._all
        for context in self._location:
            if context not in self._current:
                self._current[context] = {}
            self._current = self._current[context]
        if name:
            self._current = self._current.setdefault(name, {})

    def pop_context(self, name):
        returned = self._all.pop(name)

        for inherit in returned.get('inherit', []):
            if inherit not in self._all['template'].get('neighbor', {}):
                self.throw('invalid template name referenced')
            self.transfer(self._all['template']['neighbor'][inherit], returned)

        return returned

    # key / value

    def set(self, name, value):
        self._current[name] = value

    def attribute_add(self, name, data):
        # .add_and_merge() and not .add() is required
        # flow spec to have multiple keywords adding to the extended-community
        self.get_route().attributes.add_and_merge(data)
        if name not in self._added:
            self._added.add(name)

    def nlri_assign(self, name, command, data):
        self.get_route().nlri.assign(command, data)

    def nlri_add(self, name, command, data):
        self.get_route().nlri.add(data)

    def nlri_nexthop(self, name, data):
        self.get_route().nlri.nexthop = data

    def append(self, name, data):
        self._current.setdefault(name, []).append(data)

    def extend(self, name, data):
        self._current.setdefault(name, []).extend(data)

    def merge(self, name, data):
        for key in data:
            value = data[key]
            if key not in self._current:
                self.set(key, value)
            elif isinstance(value, list):
                self._current[key].extend(value)
            elif isinstance(value, dict):
                self.transfer(value, self._current[key])
            else:
                self.set(key, value)

    def inherit(self, data):
        return self.transfer(data, self._current)

    def transfer(self, source, destination):
        for key, value in six.iteritems(source):
            if key not in destination:
                destination[key] = value
            elif isinstance(source[key], list):
                destination[key].extend(value)
            elif isinstance(source[key], dict):
                if key not in destination:
                    destination[key] = source[key]
                else:
                    self.transfer(source[key], destination[key])
            elif isinstance(source[key], int):
                destination[key] = value
            elif isinstance(source[key], long):
                destination[key] = value
            elif isinstance(source[key], IP):
                destination[key] = value
            elif isinstance(source[key], str):
                destination[key] = value
            else:
                self.throw(
                    'can not copy "%s" (as it is of type %s) and it exists in both the source and destination'
                    % (key, type(source[key]))
                )

    def get(self, name='', default=None):
        if name:
            return self._current.get(name, default)
        return self._current

    def pop(self, name='', default=None):
        if name == '':
            return dict((k, self._current.pop(k)) for k in list(self._current))
        return self._current.pop(name, default)

    def template(self, template, name):
        return self._all['template'].get(template, {}).get(name, {})
