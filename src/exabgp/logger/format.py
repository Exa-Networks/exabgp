import os
import time

from exabgp.logger import color
from exabgp.logger.tty import istty
from exabgp.util.od import od


def _short_formater(message, source, level, timestamp):
    return f'{source:<15} {message}'


def _long_formater(message, source, level, timestamp):
    now = time.strftime('%H:%M:%S', timestamp)
    return f'{now} {os.getpid():<6} {source:<15} {message}'


def _short_color_formater(message, source, level, timestamp):
    source = color.source(level, source)
    message = color.message(level, message)
    return f'\r{source:<15} {message}'


def _long_color_formater(message, source, level, timestamp):
    now = time.strftime('%H:%M:%S', timestamp)
    source = color.source(level, source)
    message = color.message(level, message)
    return f'\r{now} {os.getpid():<6} {source:<15} {message}'


def formater(short, destination):
    # service, short, tty
    # fmt: off
    _formater = {
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


def lazyformat(prefix, message, formater=od):
    def _lazy():
        formated = formater(message)
        return '%s (%4d) %s' % (prefix, len(message), formated)

    return _lazy


def lazyattribute(flag, aid, length, data):
    def _lazy():
        return 'attribute %-18s flag 0x%02x type 0x%02x len 0x%02x%s' % (
            str(aid),
            flag,
            int(aid),
            length,
            ' payload %s' % od(data) if data else '',
        )

    return _lazy


def lazynlri(afi, safi, addpath, data):
    def _lazy():
        family = '%s %s' % (afi, safi)
        path = 'with path-information' if addpath else 'without path-information'
        payload = od(data) if data else 'none'
        return 'NLRI      %-18s %-28s payload %s' % (family, path, payload)

    return _lazy
