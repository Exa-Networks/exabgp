from __future__ import annotations

import time
from typing import Callable, ClassVar, TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.environment.config import Environment

from exabgp.logger.option import option
from exabgp.logger.handler import get_logger  # noqa: F401,E261,E501
from exabgp.logger.format import formater  # noqa: F401,E261,E501

from exabgp.logger.format import lazyformat  # noqa: F401,E261,E501
from exabgp.logger.format import lazyattribute  # noqa: F401,E261,E501
from exabgp.logger.format import lazynlri  # noqa: F401,E261,E501
from exabgp.logger.format import lazymsg  # noqa: F401,E261,E501
from exabgp.logger.format import lazyexc  # noqa: F401,E261,E501

from exabgp.logger.history import history  # noqa: F401,E261,E501
from exabgp.logger.history import record  # noqa: F401,E261,E501

__all__ = [
    'get_logger',
    'formater',
    'lazyformat',
    'lazyattribute',
    'lazynlri',
    'lazymsg',
    'lazyexc',
    'history',
    'option',
    'record',
    'LogMessage',
    'log',
]

# Type for log messages - must be callable returning string (use lazymsg or lambda)
LogMessage = Callable[..., str]


def _noop_logger(logger: Callable[[str], None], message: LogMessage, source: str, level: str) -> None:
    """No-op logger used when logging is disabled"""
    pass


class _log:
    # Logger function that writes formatted log messages
    # Using Callable[..., None] to allow both the static method and _noop_logger
    logger: ClassVar[Callable[..., None]] = _noop_logger

    @staticmethod
    def init(env: 'Environment') -> None:
        option.setup(env)

    @classmethod
    def disable(cls) -> None:
        cls.logger = _noop_logger
        # Also disable the option.logger to prevent any calls
        option.logger = None

    @classmethod
    def silence(cls) -> None:
        # Silence keeps critical/fatal but disables debug through error
        original_logger = cls.logger

        def silenced_logger(logger_func: Callable[[str], None], message: LogMessage, source: str, level: str) -> None:
            if level in ('CRITICAL', 'FATAL'):
                original_logger(logger_func, message, source, level)

        cls.logger = silenced_logger

    @classmethod
    def debug(cls, message: LogMessage, source: str = '', level: str = 'DEBUG') -> None:
        if option.logger is not None:
            cls.logger(option.logger.debug, message, source, level)

    @classmethod
    def info(cls, message: LogMessage, source: str = '', level: str = 'INFO') -> None:
        if option.logger is not None:
            cls.logger(option.logger.info, message, source, level)

    @classmethod
    def warning(cls, message: LogMessage, source: str = '', level: str = 'WARNING') -> None:
        if option.logger is not None:
            cls.logger(option.logger.warning, message, source, level)

    @classmethod
    def error(cls, message: LogMessage, source: str = '', level: str = 'ERROR') -> None:
        if option.logger is not None:
            cls.logger(option.logger.error, message, source, level)

    @classmethod
    def critical(cls, message: LogMessage, source: str = '', level: str = 'CRITICAL') -> None:
        if option.logger is not None:
            cls.logger(option.logger.critical, message, source, level)

    @classmethod
    def fatal(cls, message: LogMessage, source: str = '', level: str = 'FATAL') -> None:
        if option.logger is not None:
            cls.logger(option.logger.fatal, message, source, level)


class log(_log):
    @staticmethod
    def logger(logger: Callable[[str], None], message: LogMessage, source: str, level: str) -> None:
        # Early exit if logging is disabled
        if not option.log_enabled(source, level):
            return

        # Call the lazy message function
        msg_str: str = message()

        timestamp_struct = time.localtime()
        timestamp_float = time.time()
        for line in msg_str.split('\n'):
            logger(option.formater(line, source, level, timestamp_struct))
            record(line, source, level, timestamp_float)
