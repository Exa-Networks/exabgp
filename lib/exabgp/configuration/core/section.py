# encoding: utf-8
"""
section.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from string import ascii_letters
from string import digits

from exabgp.configuration.core.error import Error


class Section(Error):
    name = 'undefined'
    known = dict()  # command/section and code to handle it
    default = dict()  # command/section has a a defult value, use it if no data was provided
    action = {}  # how to handle this command ( append, add, assign, route )
    assign = {}  # configuration to class variable lookup for setattr

    def __init__(self, tokerniser, scope, error, logger):
        Error.__init__(self)
        self.tokeniser = tokerniser
        self.scope = scope
        self.error = error
        self.logger = logger
        self._names = []

    def clear(self):
        self._names = []

    @classmethod
    def register(cls, name, action, afi=''):
        def inner(function):
            identifier = (afi, name) if afi else name
            if identifier in cls.known:
                raise RuntimeError('more than one registration per command attempted')
            cls.known[identifier] = function
            cls.action[identifier] = action
            return function

        return inner

    def check_name(self, name):
        if any(False if c in ascii_letters + digits + '.-_' else True for c in name):
            self.throw('invalid character in name for %s ' % self.name)
        if name in self._names:
            self.throw('the name "%s" already exists in %s' % (name, self.name))
        self._names.append(name)

    def pre(self):
        return True

    def post(self):
        return True

    def parse(self, name, command):
        identifier = command if command in self.known else (self.name, command)
        if identifier not in self.known:
            return self.error.set(
                'unknown command %s options are %s' % (command, ', '.join([str(_) for _ in self.known]))
            )

        try:
            if command in self.default:
                insert = self.known[identifier](self.tokeniser.iterate, self.default[command])
            else:
                insert = self.known[identifier](self.tokeniser.iterate)

            action = self.action.get(identifier, '')

            if action == 'set-command':
                self.scope.set(command, insert)
            elif action == 'extend-name':
                self.scope.extend(name, insert)
            elif action == 'append-name':
                self.scope.append(name, insert)
            elif action == 'append-command':
                self.scope.append(command, insert)
            elif action == 'extend-command':
                self.scope.extend(command, insert)
            elif action == 'attribute-add':
                self.scope.attribute_add(name, insert)
            elif action == 'nlri-set':
                self.scope.nlri_assign(name, self.assign[command], insert)
            elif action == 'nlri-add':
                for adding in insert:
                    self.scope.nlri_add(name, command, adding)
            elif action == 'nlri-nexthop':
                self.scope.nlri_nexthop(name, insert)
            elif action == 'nexthop-and-attribute':
                ip, attribute = insert
                if ip:
                    self.scope.nlri_nexthop(name, ip)
                if attribute:
                    self.scope.attribute_add(name, attribute)
            elif action == 'append-route':
                self.scope.extend_routes(insert)
            elif action == 'nop':
                pass
            else:
                raise RuntimeError('name %s command %s has no action set' % (name, command))
            return True
        except ValueError as exc:
            return self.error.set(str(exc))

        return True
