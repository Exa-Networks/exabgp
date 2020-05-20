# encoding: utf-8
"""
command.py

Created by Thomas Mangin on 2015-12-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""


class Command(object):
    callback = {'text': {}, 'json': {}, 'neighbor': {}, 'options': {}}

    functions = []

    @classmethod
    def register(cls, encoding, name, neighbor=True, options=None):
        if name not in cls.functions:
            cls.functions.append(name)
            cls.functions.sort(reverse=True)
            cls.callback['options'][name] = options

        def register(function):
            cls.callback['neighbor'][name] = neighbor
            cls.callback[encoding][name] = function
            function.func_name = name.replace(' ', '_')
            return function

        return register
