"""format.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Iterable, Iterator

from exabgp.util import coroutine


def formated(line: str) -> str:
    changed_line = '#'
    new_line = (
        line.strip()
        .replace('\t', ' ')
        .replace(']', ' ]')
        .replace('[', '[ ')
        .replace(')', ' )')
        .replace('(', '( ')
        .replace(',', ' , ')
    )
    while new_line != changed_line:
        changed_line = new_line
        new_line = new_line.replace('  ', ' ')
    return new_line


# convert special caracters


UNICODE_ESCAPE_DIGITS = 4  # \\uXXXX, as many hexadecimal digits as JSON asks for


@coroutine.join
def unescape(string: str) -> Iterator[str]:
    start = 0
    while start < len(string):
        pos = string.find('\\', start)
        if pos == -1:
            yield string[start:]
            break
        yield string[start:pos]
        pos += 1
        if pos >= len(string):
            # a backslash with nothing after it read one character past the end.  An
            # unknown escape yields the character itself below, so a backslash which
            # escapes nothing yields the backslash, rather than raising IndexError out
            # of a helper whose callers only expect the configuration ValueError
            yield '\\'
            break
        esc = string[pos]
        if esc == 'b':
            yield '\b'
        elif esc == 'f':
            yield '\f'
        elif esc == 'n':
            yield '\n'
        elif esc == 'r':
            yield '\r'
        elif esc == 't':
            yield '\t'
        elif esc == 'u':
            digits = string[pos + 1 : pos + 1 + UNICODE_ESCAPE_DIGITS]
            # a truncated escape used to be read as however many digits were there, so
            # "\\u12" quietly became chr(0x12) rather than being reported: a wrong
            # character in the configuration is worse than a refused one
            if len(digits) != UNICODE_ESCAPE_DIGITS:
                raise ValueError(f'unicode escape \\u{digits} needs {UNICODE_ESCAPE_DIGITS} hexadecimal digits')
            try:
                yield chr(int(digits, 16))
            except ValueError:
                raise ValueError(f'unicode escape \\u{digits} is not hexadecimal')
            pos += UNICODE_ESCAPE_DIGITS
        else:
            yield esc
        start = pos + 1


# A coroutine which return the producer token, or string if quoted from the stream


def tokens(stream: Iterable[str]) -> Iterator[list[tuple[int, int, str]]]:  # noqa: C901
    spaces = [' ', '\t', '\r', '\n']
    strings = ['"', "'"]
    syntax = [',', '[', ']']
    eol = [';', '{', '}']
    comment = [
        '#',
    ]

    nb_lines = 0

    for letters in stream:
        line = unescape(letters)
        parsed = []
        nb_chars = 0
        nb_lines += 1
        quoted = ''
        word = ''
        for char in line:
            if char in comment:
                if quoted:
                    word += char
                    nb_chars += 1
                else:
                    if word:
                        parsed.append((nb_lines, nb_chars, char))
                        word = ''
                    break

            elif char in eol:
                if quoted:
                    word += char
                    nb_chars += 1
                else:
                    if word:
                        parsed.append((nb_lines, nb_chars - len(word), word))
                        word = ''
                    parsed.append((nb_lines, nb_chars, char))
                    nb_chars += 1
                    yield parsed
                    parsed = []

            elif char in syntax:
                if quoted:
                    word += char
                else:
                    if word:
                        parsed.append((nb_lines, nb_chars - len(word), word))
                        word = ''
                    parsed.append((nb_lines, nb_chars, char))
                nb_chars += 1

            elif char in spaces:
                if quoted:
                    word += char
                elif word:
                    parsed.append((nb_lines, nb_chars - len(word), word))
                    word = ''
                nb_chars += 1

            elif char in strings:
                # word += char
                if quoted == char:
                    quoted = ''
                    parsed.append((nb_lines, nb_chars - len(word), word))
                    word = ''
                else:
                    quoted = char
                nb_chars += 1

            else:
                word += char
                nb_chars += 1

        if word:
            raise ValueError(f'invalid syntax line {nb_lines}: "{word}"')

        if parsed:
            raise ValueError(f'invalid syntax line {nb_lines}: "{parsed}"')
