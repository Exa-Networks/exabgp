
"""command.py

Created by Thomas Mangin on 2015-12-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from typing import Dict, List

class Command:
    callback: Dict[str, dict] = {'text': {}, 'json': {}, 'neighbor': {}, 'options': {}}

    functions: List[str] = []

    @classmethod
    def register(cls, name, neighbor=True, options=None, json_support=False):
        if name not in cls.functions:
            cls.functions.append(name)
            cls.functions.sort(reverse=True)
            cls.callback['options'][name] = options

        def register(function):
            cls.callback['neighbor'][name] = neighbor
            cls.callback['text'][name] = function
            if json_support:
                cls.callback['json'][name] = function
            function.func_name = name.replace(' ', '_')
            return function

        return register
