"""render.py

Print Settings back as configuration text, walking the same tree the engine reads with.

What is printed reads back to equal Settings, with either parser.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any

from exabgp.configuration.grammar.context import PrintContext
from exabgp.configuration.grammar.lexer import COMMENT, QUOTES, SEPARATORS, SPACES, TERMINATORS
from exabgp.configuration.grammar.nodes import Block, Keep, Leaf
from exabgp.configuration.grammar.types.base import Printed, Syntax, WordOrSyntax

INDENT = '\t'
# the statements of a block whose order matters across keywords, as (keyword, value) pairs,
# printed before the fields, which are printed in the order the block declares its children
STATEMENTS = '_statements'
_PLAIN_BREAKERS = set(SPACES + TERMINATORS + SEPARATORS + QUOTES + (COMMENT, '\\'))
_ESCAPED = {'\\': '\\\\', '\b': '\\b', '\f': '\\f', '\n': '\\n', '\r': '\\r', '\t': '\\t'}


def quote(word: WordOrSyntax) -> str:
    """A word as the lexer will read it back."""
    if isinstance(word, Syntax):
        return word.word
    if word and not any(char in _PLAIN_BREAKERS for char in word):
        return word
    # the lexer resolves escapes before it looks for quotes, and inside quotes the other quote
    # character changes which one closes: a word holding either can not be written at all
    if any(char in QUOTES for char in word):
        raise ValueError(f'{word!r} holds a quote character and can not be written in a configuration')
    escaped = ''.join(_ESCAPED.get(char, char) for char in word)
    return f'"{escaped}"'


def _leaf(leaf: Leaf, value: Any) -> str:
    rendered = list(value.words) if isinstance(value, Printed) else leaf.type.render(value)
    words = ' '.join(quote(word) for word in rendered)
    return f'{leaf.keyword} {words};' if words else f'{leaf.keyword};'


def _block(block: Block, name: Any, built: Any, depth: int, context: PrintContext) -> list[str]:
    name, values = block.section.unbuild(name, built, context)
    indent = INDENT * depth
    words = [quote(word) for word in block.name.render(name)] if block.name is not None else []
    lines = [indent + ' '.join([block.keyword, *words, '{'])] if block.keyword else []
    inner = depth + 1 if block.keyword else depth
    lines.extend(_children(block, values, inner, context))
    if block.keyword:
        lines.append(indent + '}')
    return lines


def _children(block: Block, values: dict[str, Any], depth: int, context: PrintContext) -> list[str]:
    leaves = {child.keyword: child for child in block.children if isinstance(child, Leaf)}
    lines = [INDENT * depth + _leaf(leaves[keyword], value) for keyword, value in values.get(STATEMENTS, [])]
    for child in block.children:
        value = values.get(child.field)
        if value is None:
            continue
        if isinstance(child, Leaf) and child.repeated:
            lines.extend(INDENT * depth + _leaf(child, each) for each in value)
        elif isinstance(child, Leaf):
            lines.append(INDENT * depth + _leaf(child, value))
        elif child.keep != Keep.SINGLE and not value:
            continue
        elif child.keep == Keep.NAMED:
            for name, built in value.items():
                lines.extend(_block(child, name, built, depth, context))
        elif child.keep in (Keep.LIST, Keep.EXTEND):
            for built in value:
                lines.extend(_block(child, '', built, depth, context))
        else:
            lines.extend(_block(child, '', value, depth, context))
    return lines


def render(root: Block, settings: Any) -> str:
    return '\n'.join(_block(root, '', settings, 0, PrintContext())) + '\n'


def one_line(block: Block, built: Any) -> str:
    """One block on one line, as an API command gives it: `route { match { ... } ... }`."""
    return ' '.join(line.strip() for line in _block(block, '', built, 0, PrintContext()))
