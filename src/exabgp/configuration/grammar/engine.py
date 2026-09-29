"""engine.py

Read statements against a tree of nodes and build what it declares.

The engine keeps the legacy parser's behaviour, accidents included, until each accident
is decided on (plan/done-config-grammar.md, section 6). Those it reproduces are marked
`legacy:` below.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from exabgp.configuration.grammar.context import ReadContext
from exabgp.configuration.grammar.error import ConfigError, suggest
from exabgp.configuration.grammar.lexer import Statement, Token
from exabgp.configuration.grammar.nodes import MISSING, Block, Keep
from exabgp.configuration.grammar.words import Words

# sections nest a handful deep (neighbor, flow, route, match); this is far past any real one
MAX_DEPTH = 32


@dataclass
class _Frame:
    block: Block
    name: Any
    opened: Token | None
    values: dict[str, Any] = field(default_factory=dict)

    def where(self) -> str:
        return self.opened.where() if self.opened else ''


class Engine:
    def __init__(self, root: Block, context: ReadContext | None = None) -> None:
        self.root = root
        # shared by the builders of one read: templates, names already used, ...
        self.context = context if context is not None else ReadContext()

    def read(self, statements: list[Statement]) -> Any:
        if not statements:
            raise ConfigError('', 'the configuration is empty')
        stack = [_Frame(self.root, '', None)]
        for statement in statements:
            if statement.end == ';':
                self._leaf(stack[-1], statement)
            elif statement.end == '{':
                stack.append(self._open(stack, statement))
            elif len(stack) == 1:
                # legacy: a `}` with nothing open ends the configuration, what follows is ignored
                break
            else:
                # legacy: words before a `}` are ignored, `hold-time 30 }` sets nothing
                self._close(stack)
        # legacy: sections still open when the text ends are closed as if it said so
        while len(stack) > 1:
            self._close(stack)
        return self._build(stack[0])

    def _leaf(self, frame: _Frame, statement: Statement) -> None:
        words = statement.words
        keyword = words[0] if words else statement.tokens[-1]
        child = frame.block.leaf(keyword.word) if words else None
        if child is None:
            raise self._unknown(frame.block, keyword, [leaf.keyword for leaf in frame.block.leaves()])
        # legacy: the words a value does not use are ignored, `respawn false extra;` is `respawn false;`
        value = child.type.parse(self._words(statement, 1))
        try:
            child.keep(frame.values, value, self.context)
        except ValueError as exc:
            raise ConfigError(keyword.where(), str(exc)) from None

    def _open(self, stack: list[_Frame], statement: Statement) -> _Frame:
        frame = stack[-1]
        keyword = statement.tokens[0]
        child = frame.block.block(keyword.word) if statement.words else None
        if child is None:
            raise self._unknown(frame.block, keyword, [block.keyword for block in frame.block.blocks()], 'section')
        if len(stack) >= MAX_DEPTH:
            raise ConfigError(keyword.where(), f'sections nested more than {MAX_DEPTH} deep')
        name = child.name.parse(self._words(statement, 1)) if child.name else ''
        if child.keep == Keep.NAMED and name in frame.values.get(child.field, {}):
            raise ConfigError(keyword.where(), f'a {child.keyword} section called "{name}" already exists')
        child.section.opened(self.context)
        opened = _Frame(child, name, keyword)
        existing = frame.values.get(child.field)
        if child.keep == Keep.SINGLE and isinstance(existing, dict):
            # legacy: a section opened twice continues the first one, its values are shared
            opened.values = existing
        return opened

    def _words(self, statement: Statement, start: int) -> Words:
        """The words of a statement from `start`, sharing the context of the read.

        The context lasts across statements, as the legacy tokeniser's state did: the address
        family of `route <prefix> {` is what `next-hop self;` inside the block refers to.
        """
        self.context.statement = statement.words
        return Words(statement.words[start:], statement.tokens[-1], self.context)

    def _close(self, stack: list[_Frame]) -> None:
        frame = stack.pop()
        built = self._build(frame)
        parent = stack[-1]
        assert parent.block.block(frame.block.keyword) is frame.block
        if frame.block.keep == Keep.NAMED:
            parent.values.setdefault(frame.block.field, {})[frame.name] = built
        elif frame.block.keep == Keep.LIST:
            parent.values.setdefault(frame.block.field, []).append(built)
        elif frame.block.keep == Keep.EXTEND:
            parent.values.setdefault(frame.block.field, []).extend(built)
        else:
            parent.values[frame.block.field] = built

    def _build(self, frame: _Frame) -> Any:
        values = frame.values
        for leaf in frame.block.leaves():
            if leaf.field not in values and leaf.default is not MISSING:
                values[leaf.field] = leaf.default
        missing = [leaf.keyword for leaf in frame.block.leaves() if leaf.mandatory and leaf.field not in values]
        if missing:
            raise ConfigError(frame.where(), frame.block.missing.format(names=', '.join(missing)))
        try:
            frame.block.section.finish(values)
            return frame.block.section.build(frame.name, values, self.context)
        except ConfigError:
            raise
        except ValueError as exc:
            raise ConfigError(frame.where(), str(exc)) from None

    @staticmethod
    def _unknown(block: Block, keyword: Token, candidates: list[str], kind: str = 'keyword') -> ConfigError:
        where = f' in {block.keyword}' if block.keyword else ''
        return ConfigError(
            keyword.where(),
            f"unknown {kind} '{keyword.word}'{where}",
            expected=sorted(candidates),
            suggestions=suggest(keyword.word, candidates),
        )
