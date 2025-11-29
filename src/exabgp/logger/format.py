from __future__ import annotations

import os
import time
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.protocol.family import AFI, SAFI

from exabgp.logger import color
from exabgp.logger.tty import istty
from exabgp.util.od import od

# Type alias for formatter functions - timestamp is time.struct_time
FormatterFunc = Callable[[str, str, str, time.struct_time], str]


def _short_formater(message: str, source: str, level: str, timestamp: time.struct_time) -> str:
    return f'{source:<15} {message}'


def _long_formater(message: str, source: str, level: str, timestamp: time.struct_time) -> str:
    now = time.strftime('%H:%M:%S', timestamp)
    return f'{now} {os.getpid():<6} {source:<15} {message}'


def _short_color_formater(message: str, source: str, level: str, timestamp: time.struct_time) -> str:
    source = color.source(level, source)
    message = color.message(level, message)
    return f'\r{source:<15} {message}'


def _long_color_formater(message: str, source: str, level: str, timestamp: time.struct_time) -> str:
    now = time.strftime('%H:%M:%S', timestamp)
    source = color.source(level, source)
    message = color.message(level, message)
    return f'\r{now} {os.getpid():<6} {source:<15} {message}'


def formater(short: bool, destination: str) -> FormatterFunc | None:
    # service, short, tty
    # fmt: off
    _formater: dict[tuple[str, bool, bool], FormatterFunc] = {
        ('stdout', True, True): _short_color_formater,
        ('stdout', True, False): _short_formater,
        ('stdout', False, True): _long_color_formater,
        ('stdout', False, False): _long_formater,

        ('stderr', True, True): _short_color_formater,
        ('stderr', True, False): _short_formater,
        ('stderr', False, True): _long_color_formater,
        ('stderr', False, False): _long_formater,

        ('syslog', True, True): _short_formater,
        ('syslog', True, False): _short_formater,
        ('syslog', False, True): _short_formater,
        ('syslog', False, False): _short_formater,

        ('file', True, True): _long_formater,
        ('file', True, False): _long_formater,
        ('file', False, True): _long_formater,
        ('file', False, False): _long_formater,
    }
    # fmt: on
    return _formater.get((destination, short, istty(destination)), None)


# NOTE: Do not convert these functions to use f-strings!
# These lazy formatting functions are called during logging and using f-strings
# causes infinite recursion when the logger tries to format the log message.
# The % formatting is intentionally used here to avoid this issue.
def lazyformat(prefix: str, message: bytes, formater: Callable[[bytes], str] = od) -> Callable[[], str]:
    def _lazy() -> str:
        formated = formater(message)
        return '%s (%4d) %s' % (prefix, len(message), formated)

    return _lazy


def lazyattribute(flag: int, aid: int, length: int, data: bytes) -> Callable[[], str]:
    def _lazy() -> str:
        return 'attribute %-18s flag 0x%02x type 0x%02x len 0x%02x%s' % (
            str(aid),
            flag,
            int(aid),
            length,
            ' payload {}'.format(od(data)) if data else '',
        )

    return _lazy


def lazynlri(afi: 'AFI', safi: 'SAFI', addpath: bool, data: bytes) -> Callable[[], str]:
    def _lazy() -> str:
        family = '{} {}'.format(afi, safi)
        path = 'with path-information' if addpath else 'without path-information'
        payload = od(data) if data else 'none'
        return 'NLRI      %-18s %-28s payload %s' % (family, path, payload)

    return _lazy


def lazymsg(template: str, **kwargs: object) -> Callable[[], str]:
    """Create a lazy log message from a format string template.

    Usage:
        log.debug(lazymsg('duplicate AFI/SAFI: {afi}/{safi}', afi=afi, safi=safi), 'parser')
    """

    def _format() -> str:
        return template.format(**kwargs)

    return _format
