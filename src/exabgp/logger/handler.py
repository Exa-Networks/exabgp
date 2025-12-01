# A wrapper class around logging to make it easier to use
# Uses logging.config.dictConfig for cleaner configuration

from __future__ import annotations

import os
import sys
import logging
import logging.config
from typing import Any

TIMED: str = '%(asctime)s: %(message)s'
SHORT: str = '%(filename)s: %(message)s'
CLEAR: str = '%(levelname) %(asctime)s %(filename)s: %(message)s'

levels: dict[str, int] = {
    'FATAL': logging.FATAL,
    'CRITICAL': logging.CRITICAL,
    'ERROR': logging.ERROR,
    'WARNING': logging.WARNING,
    'INFO': logging.INFO,
    'DEBUG': logging.DEBUG,
    'NOTSET': logging.NOTSET,
}

# prevent recreation of already created logger
_created: dict[str | None, logging.Logger] = {}


def _get_syslog_address() -> str:
    """Get platform-specific syslog socket path.

    Returns the appropriate syslog socket path for the current platform.
    Logs a warning to stderr if the socket does not exist.
    """
    if sys.platform == 'darwin':
        path = '/var/run/syslog'
    elif sys.platform.startswith('freebsd'):
        path = '/var/run/log'
    elif sys.platform.startswith('netbsd'):
        path = '/var/run/log'
    else:
        path = '/dev/log'

    if not os.path.exists(path):
        # Use stderr directly since logging may not be configured yet
        # Format matches ExaBGP's structured logging style
        import time

        now = time.strftime('%H:%M:%S')
        pid = os.getpid()
        print(
            f'{now} {pid:<6} {"startup":<15} ' f'syslog socket {path} does not exist - syslog logging may not work',
            file=sys.stderr,
        )
    return path


def _build_config(
    name: str,
    level: str = 'DEBUG',
    format_str: str = CLEAR,
    stream: Any = None,
    address: str | None = None,
    syslog: bool = False,
    filename: str | None = None,
    max_bytes: int = 1048576,
    backup_count: int = 3,
    facility: str = 'daemon',
) -> dict[str, Any]:
    """Build a dictConfig-compatible configuration dictionary."""
    config: dict[str, Any] = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'default': {
                'format': format_str,
            },
        },
        'handlers': {},
        'loggers': {
            name: {
                'level': level,
                'handlers': [],
                'propagate': False,
            },
        },
    }

    handlers_list: list[str] = []

    # Stream handler
    if stream is not None:
        stream_name = 'stderr' if stream is sys.stderr else 'stdout'
        handler_name = f'{name}_stream_{stream_name}'
        config['handlers'][handler_name] = {
            'class': 'logging.StreamHandler',
            'level': level,
            'formatter': 'default',
            'stream': f'ext://sys.{stream_name}',
        }
        handlers_list.append(handler_name)

    # Syslog handler
    if address is not None or syslog:
        syslog_address = address if address else _get_syslog_address()
        handler_name = f'{name}_syslog'
        config['handlers'][handler_name] = {
            'class': 'logging.handlers.SysLogHandler',
            'level': level,
            'formatter': 'default',
            'address': syslog_address,
            'facility': facility,
        }
        handlers_list.append(handler_name)

    # File handler
    if filename is not None:
        handler_name = f'{name}_file'
        config['handlers'][handler_name] = {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': level,
            'formatter': 'default',
            'filename': filename,
            'maxBytes': max_bytes,
            'backupCount': backup_count,
        }
        handlers_list.append(handler_name)

    config['loggers'][name]['handlers'] = handlers_list
    return config


def get_logger(name: str | None = None, **kwargs: Any) -> logging.Logger:
    """Get or create a logger with the specified configuration.

    Args:
        name: Logger name. If None, returns root logger.
        **kwargs: Configuration options:
            - level: Log level (default: 'DEBUG')
            - format: Log format string (default: CLEAR)
            - stream: Stream for StreamHandler (sys.stdout or sys.stderr)
            - syslog: If True, add SysLogHandler with default address
            - address: Syslog address (implies syslog=True)
            - filename: File path for RotatingFileHandler
            - maxBytes: Max file size before rotation (default: 1048576)
            - backupCount: Number of backup files (default: 3)
            - facility: Syslog facility (default: 'daemon')

    Returns:
        Configured logging.Logger instance.
    """
    if name in _created:
        if len(kwargs) == 0:
            return _created[name]
        raise ValueError(f'a logger with the name "{name}" already exists')

    if name is None:
        # For root logger, use basic configuration
        logger = logging.getLogger()
        logger.setLevel(kwargs.get('level', 'DEBUG'))
        _created[name] = logger
        return logger

    # Build and apply dictConfig
    config = _build_config(
        name=name,
        level=kwargs.get('level', 'DEBUG'),
        format_str=kwargs.get('format', CLEAR),
        stream=kwargs.get('stream'),
        address=kwargs.get('address'),
        syslog=kwargs.get('syslog', False),
        filename=kwargs.get('filename'),
        max_bytes=kwargs.get('maxBytes', 1048576),
        backup_count=kwargs.get('backupCount', 3),
        facility=kwargs.get('facility', 'daemon'),
    )

    logging.config.dictConfig(config)
    logger = logging.getLogger(name)

    _created[name] = logger
    return logger


# testing
if __name__ == '__main__':
    formating = '%(asctime)s (%(filename)s) %(levelname)s: %(message)s'

    # syslog logger
    # syslog=True if no 'address' field is provided
    syslog_logger = get_logger(__name__ + '.1', syslog=True, format=formating)
    syslog_logger.info('syslog test')

    # stream logger
    stream_logger = get_logger(__name__ + '.2', stream=sys.stdout, level='ERROR')
    stream_logger.info('stream test')

    # file logger
    filelog = get_logger(__name__ + '.3', filename='/tmp/test')
    filelog.info('file test')

    # create a combined logger
    get_logger('ExaBGP', syslog=True, stream=sys.stdout, filename='/tmp/test')

    # recover the created logger from name
    combined = get_logger('ExaBGP')
    combined.info('combined test')
