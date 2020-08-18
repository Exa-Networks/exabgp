# 'FATAL CRITICAL ERROR WARNING INFO DEBUG NOTSET'
_RECORD = {
    'FATAL': '\033[00;31m',  # Strong Red
    'CRITICAL': '\033[00;31m',  # Strong Red
    'ERROR': '\033[01;31m',  # Red
    'WARNING': '\033[01;33m',  # Yellow
    'INFO': '\033[01;32m',  # Green
    'DEBUG': '',
    'NOTSET': '\033[01;34m',  # Blue
}

_MESSAGE = {
    'FATAL': '\033[1m',
    'CRITICAL': '',
    'ERROR': '\033[1m',
    'WARNING': '\033[1m',
    'INFO': '\033[1m',
    'DEBUG': '',
    'NOTSET': '',
}

_END = '\033[0m'


def source(level, message):
    color = _RECORD.get(level, '')
    if color:
        return f'{color}{message:<13}{_END}'
    return message


def message(level, message):
    color = _MESSAGE.get(level, '')
    if color:
        return f'{color}{message:<8}{_END}'
    return message
