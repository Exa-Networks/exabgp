"""command.py

Created by Thomas Mangin on 2015-12-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any, Callable, ClassVar, Dict, List, Optional


class Command:
    callback: ClassVar[Dict[str, Dict[str, Any]]] = {'text': {}, 'json': {}, 'neighbor': {}, 'options': {}}

    functions: ClassVar[List[str]] = []

    @classmethod
    def register(
        cls, name: str, neighbor: bool = True, options: Optional[Any] = None, json_support: bool = False
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        if name not in cls.functions:
            cls.functions.append(name)
            cls.functions.sort(reverse=True)
            cls.callback['options'][name] = options

        def register(function: Callable[..., Any]) -> Callable[..., Any]:
            cls.callback['neighbor'][name] = neighbor
            cls.callback['text'][name] = function
            if json_support:
                cls.callback['json'][name] = function
            function.func_name = name.replace(' ', '_')  # type: ignore[attr-defined]
            return function

        return register
