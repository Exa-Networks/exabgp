"""command.py

Created by Thomas Mangin on 2015-12-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Callable, ClassVar, Dict, List, Optional, TypeVar, Union


# TypeVar for the decorator pattern - preserves the function signature
F = TypeVar('F', bound=Callable)


class Command:
    # Callback dictionary stores different types per key:
    # - 'text' and 'json': store command handler functions
    # - 'neighbor': stores bool flags
    # - 'options': stores optional configuration (could be None, dict, list, etc.)
    callback: ClassVar[Dict[str, Dict[str, Union[Callable, bool, None, Dict, List]]]] = {
        'text': {},
        'json': {},
        'neighbor': {},
        'options': {},
    }

    functions: ClassVar[List[str]] = []

    @classmethod
    def register(
        cls, name: str, neighbor: bool = True, options: Optional[Union[Dict, List]] = None, json_support: bool = False
    ) -> Callable[[F], F]:
        if name not in cls.functions:
            cls.functions.append(name)
            cls.functions.sort(reverse=True)
            cls.callback['options'][name] = options

        def register(function: F) -> F:
            cls.callback['neighbor'][name] = neighbor
            cls.callback['text'][name] = function
            if json_support:
                cls.callback['json'][name] = function
            function.func_name = name.replace(' ', '_')  # type: ignore[attr-defined]
            return function

        return register
