# encoding: utf-8
"""
format.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.util import character
from exabgp.util import coroutine


def formated(line):
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


@coroutine.join
def unescape(string):
    start = 0
    while start < len(string):
        pos = string.find('\\', start)
        if pos == -1:
            yield string[start:]
            break
        yield string[start:pos]
        pos += 1
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
            yield character(int(string[pos + 1 : pos + 5], 16))
            pos += 4
        else:
            yield esc
        start = pos + 1


# A coroutine which return the producer token, or string if quoted from the stream


def tokens(stream):
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

        if parsed:
            raise ValueError('invalid syntax')
