"""lexer.py

Turn configuration text into statements of positioned tokens.

A statement is the words up to and including one of `;`, `{` or `}`. The words are the
ones the legacy tokeniser produces, byte for byte, so both parsers see the same input:
the same quoting, the same escapes, the same refusal of a statement which does not end
on its own line. What this lexer adds is where each word came from, as the physical line
and column in the source, so an error can point at it.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator

from exabgp.configuration.grammar.error import ConfigError

TERMINATORS = (';', '{', '}')
SEPARATORS = (',', '[', ']')
SPACES = (' ', '\t', '\r', '\n')
QUOTES = ('"', "'")
COMMENT = '#'

UNICODE_ESCAPE_DIGITS = 4  # \uXXXX, as many hexadecimal digits as JSON asks for
_ESCAPES = {'b': '\b', 'f': '\f', 'n': '\n', 'r': '\r', 't': '\t'}

# a configuration line longer than this is not something anyone wrote by hand
MAX_LINE_CHARACTERS = 1024 * 1024


@dataclass(frozen=True, slots=True)
class Token:
    word: str
    source: str  # the file name, or '' for text given directly
    line: int  # 1 based physical line
    column: int  # 1 based

    def where(self) -> str:
        prefix = f'{self.source}:' if self.source else 'line '
        return f'{prefix}{self.line}:{self.column}'


@dataclass(frozen=True, slots=True)
class Statement:
    tokens: tuple[Token, ...]  # the last one is the terminator

    def __post_init__(self) -> None:
        assert self.tokens and self.tokens[-1].word in TERMINATORS, 'a statement ends with its terminator'

    @property
    def end(self) -> str:
        return self.tokens[-1].word

    @property
    def words(self) -> tuple[Token, ...]:
        """The tokens before the terminator."""
        return self.tokens[:-1]


def _characters(text: str) -> Iterator[tuple[int, int, str]]:
    """Each character of the text as the lexer reads it (escapes resolved), with where it starts and ends."""
    position = 0
    while position < len(text):
        start = position
        if text[position] != '\\' or position + 1 >= len(text):
            position += 1
            yield start, position, text[start]
            continue
        escape = text[position + 1]
        if escape == 'u':
            digits = text[position + 2 : position + 2 + UNICODE_ESCAPE_DIGITS]
            position += 2 + len(digits)
            # a malformed escape is no quote nor terminator: the command which holds it is refused when read
            valid = len(digits) == UNICODE_ESCAPE_DIGITS and _hexadecimal(digits)
            yield start, position, chr(int(digits, 16)) if valid else ''
            continue
        position += 2
        yield start, position, _ESCAPES.get(escape, escape)


def _hexadecimal(digits: str) -> bool:
    return all(char in '0123456789abcdefABCDEF' for char in digits)


def split_commands(text: str) -> list[str]:
    """The commands of a `group` line, at each `;` the lexer would end a statement with.

    A `;` inside quotes is part of a word and one inside braces ends a statement of a block:
    neither ends a command. It was split on every `;`, so a quoted word of a command, a
    name a peer chose for its SR policy and `exabgp decode --command` printed, could hold
    a command of its own: `policy-name "x ; withdraw route 10.0.0.0/8 ; y"`.
    """
    commands: list[str] = []
    start = 0
    quote = ''
    depth = 0
    for begin, end, char in _characters(text):
        if quote:
            quote = '' if char == quote else quote
        elif char in QUOTES:
            quote = char
        elif char == '{':
            depth += 1
        elif char == '}':
            depth = max(depth - 1, 0)
        elif char == ';' and not depth:
            commands.append(text[start:begin])
            start = end
    commands.append(text[start:])
    return [each.strip() for each in commands if each.strip()]


@dataclass(frozen=True, slots=True)
class _Line:
    text: str
    source: str
    starts: tuple[tuple[int, int], ...]  # (offset in text, physical line) of each joined piece


def unescape(text: str, where: str) -> str:
    """Resolve the backslash escapes of a line, as the legacy tokeniser does before splitting it."""
    result: list[str] = []
    position = 0
    while position < len(text):
        found = text.find('\\', position)
        if found == -1:
            result.append(text[position:])
            break
        result.append(text[position:found])
        found += 1
        if found >= len(text):
            result.append('\\')
            break
        escape = text[found]
        if escape == 'u':
            digits = text[found + 1 : found + 1 + UNICODE_ESCAPE_DIGITS]
            if len(digits) != UNICODE_ESCAPE_DIGITS:
                raise ConfigError(where, f'unicode escape \\u{digits} needs {UNICODE_ESCAPE_DIGITS} hexadecimal digits')
            try:
                result.append(chr(int(digits, 16)))
            except ValueError:
                raise ConfigError(where, f'unicode escape \\u{digits} is not hexadecimal') from None
            found += UNICODE_ESCAPE_DIGITS
        else:
            result.append(_ESCAPES.get(escape, escape))
        position = found + 1
    return ''.join(result)


class _Splitter:
    """Split one line into statements, the legacy way, remembering positions."""

    def __init__(self, line: _Line) -> None:
        self.line = line
        self.text = unescape(line.text, self._where(0))
        self.tokens: list[Token] = []
        self.word = ''
        self.word_at = 0
        self.quoted = ''

    def _where(self, offset: int) -> str:
        line, column = self._position(offset)
        return Token('', self.line.source, line, column).where()

    def _position(self, offset: int) -> tuple[int, int]:
        piece_offset, physical = self.line.starts[0]
        for start, line_number in self.line.starts:
            if start > offset:
                break
            piece_offset, physical = start, line_number
        return physical, offset - piece_offset + 1

    def _token(self, word: str, offset: int) -> Token:
        line, column = self._position(offset)
        return Token(word, self.line.source, line, column)

    def _flush(self) -> None:
        if self.word:
            self.tokens.append(self._token(self.word, self.word_at))
            self.word = ''

    def _add(self, char: str, offset: int) -> None:
        if not self.word:
            self.word_at = offset
        self.word += char

    def split(self) -> Iterator[Statement]:
        for offset, char in enumerate(self.text):
            if char in QUOTES:
                self._quote(char, offset)
                continue
            if self.quoted:
                self._add(char, offset)
                continue
            if char == COMMENT:
                if self.word or self.tokens:
                    raise ConfigError(self._where(offset), f'invalid syntax, unterminated statement before {COMMENT!r}')
                return
            if char in TERMINATORS:
                self._flush()
                self.tokens.append(self._token(char, offset))
                yield Statement(tuple(self.tokens))
                self.tokens = []
            elif char in SEPARATORS:
                self._flush()
                self.tokens.append(self._token(char, offset))
            elif char in SPACES:
                self._flush()
            else:
                self._add(char, offset)
        self._close()

    def _quote(self, char: str, offset: int) -> None:
        """A quote character, with the legacy rules.

        An opening quote does not end the word before it (`ab"cd"` is `abcd`). A closing quote
        ends the word even when it is empty (`""` is a word). Inside quotes, the other quote
        character does not close: it becomes the quote to close with, and is dropped.
        """
        if self.quoted == char:
            self.tokens.append(self._token(self.word, self.word_at))
            self.word = ''
            self.quoted = ''
            return
        if not self.quoted and not self.word:
            self.word_at = offset + 1
        self.quoted = char

    def _close(self) -> None:
        if self.word:
            raise ConfigError(self._where(self.word_at), f'invalid syntax, "{self.word}" is not followed by ;')
        if self.tokens:
            words = ' '.join(token.word for token in self.tokens)
            raise ConfigError(self.tokens[0].where(), f'invalid syntax, "{words}" is not followed by ;')


def _file_lines(lines: Iterable[str], source: str) -> Iterator[_Line]:
    """Lines of a file, a trailing backslash joining a line to the next one."""
    pending = ''
    starts: list[tuple[int, int]] = []
    number = 0
    for number, current in enumerate(lines, start=1):
        current = current.rstrip()
        if len(current) > MAX_LINE_CHARACTERS:
            raise ConfigError(f'{source}:{number}:1', f'line longer than {MAX_LINE_CHARACTERS} characters')
        starts.append((len(pending), number))
        if current.endswith('\\'):
            pending += current[:-1]
            continue
        yield _Line(pending + current, source, tuple(starts))
        pending = ''
        starts = []
    if pending:
        # the legacy reader repeats the last piece when the file ends on a continuation
        last = pending[starts[-1][0] :]
        yield _Line(pending + last, source, tuple(starts))


def _statements(lines: Iterable[_Line]) -> Iterator[Statement]:
    for line in lines:
        yield from _Splitter(line).split()


def lex_file(path: str) -> list[Statement]:
    with open(path, 'r') as handle:
        return list(_statements(_file_lines(handle, path)))


def lex_text(text: str) -> list[Statement]:
    """Text given directly: every line stands alone, there is no continuation."""
    lines = (_Line(line, '', ((0, number),)) for number, line in enumerate(text.split('\n'), start=1))
    return list(_statements(lines))


def lex_command(command: str) -> list[Statement]:
    """One API command, given as a single line."""
    return list(_statements([_Line(command, '', ((0, 1),))]))
