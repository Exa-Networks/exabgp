#!/usr/bin/env python3
"""No `try` in the application entry points may catch one exception type twice.

Python takes the first handler which matches, so a second `except OSError` on the same
`try` is code which can never run.  `cli.py` carried four such pairs and
`pipe.check_fifo` three clauses where only the first could run, and the messages in the
dead ones had never once been printed.  They were written when `IOError` and
`socket.error` were their own types; both have been aliases of `OSError` since Python 3.3,
so the rename in 2c806ac62 did not create the deadness, it only made it visible.

The same scan over all of `src/exabgp` was clean when this test was written, so the scope
here is the package the defect was recorded against rather than the tree.
"""

from __future__ import annotations

import ast
from pathlib import Path

APPLICATION = Path(__file__).parent.parent.parent / 'src' / 'exabgp' / 'application'

# a file with no try/except at all would make this test pass by walking nothing
MINIMUM_HANDLERS = 20


def caught_names(handler: ast.ExceptHandler) -> list[str]:
    """Every exception name this one clause catches, a bare except included."""
    if handler.type is None:
        return ['<bare>']
    if isinstance(handler.type, ast.Tuple):
        return [ast.unparse(element) for element in handler.type.elts]
    return [ast.unparse(handler.type)]


def test_no_handler_is_shadowed_by_an_earlier_one():
    sources = sorted(APPLICATION.rglob('*.py'))
    assert sources, f'walked nothing under {APPLICATION}'

    handlers = 0
    dead = []
    for source in sources:
        tree = ast.parse(source.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            first_seen: dict[str, int] = {}
            for handler in node.handlers:
                handlers += 1
                for name in caught_names(handler):
                    if name in first_seen:
                        dead.append(f'{source.name}:{handler.lineno}: {name} already caught on line {first_seen[name]}')
                    else:
                        first_seen[name] = handler.lineno

    assert handlers >= MINIMUM_HANDLERS, f'only {handlers} handlers walked, the scan is not looking at the code'
    assert dead == [], 'handlers which can never run:\n' + '\n'.join(dead)
