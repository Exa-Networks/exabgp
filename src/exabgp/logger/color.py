from __future__ import annotations


# 'FATAL CRITICAL ERROR WARNING INFO DEBUG NOTSET'
_RECORD: dict[str, str] = {
    'FATAL': '\033[00;31m',  # Strong Red
    'CRITICAL': '\033[00;31m',  # Strong Red
    'ERROR': '\033[01;31m',  # Red
    'WARNING': '\033[01;33m',  # Yellow
    'INFO': '\033[01;32m',  # Green
    'DEBUG': '',
    'NOTSET': '\033[01;34m',  # Blue
}

_MESSAGE: dict[str, str] = {
    'FATAL': '\033[1m',
    'CRITICAL': '',
    'ERROR': '\033[1m',
    'WARNING': '\033[1m',
    'INFO': '\033[1m',
    'DEBUG': '',
    'NOTSET': '',
}

_END: str = '\033[0m'


def source(level: str, message: str) -> str:
    color = _RECORD.get(level, '')
    if color:
        return f'{color}{message:<15}{_END}'
    return message


def message(level: str, message: str) -> str:
    color = _MESSAGE.get(level, '')
    if color:
        return f'{color}{message:<8}{_END}'
    return message
