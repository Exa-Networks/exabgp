from __future__ import annotations

import time
from typing import Callable, ClassVar, Optional, Type, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.environment.environment import Env

from exabgp.logger.option import option
from exabgp.logger.handler import get_logger  # noqa: F401,E261,E501
from exabgp.logger.format import formater  # noqa: F401,E261,E501

from exabgp.logger.format import lazyformat  # noqa: F401,E261,E501
from exabgp.logger.format import lazyattribute  # noqa: F401,E261,E501
from exabgp.logger.format import lazynlri  # noqa: F401,E261,E501

from exabgp.logger.history import history  # noqa: F401,E261,E501
from exabgp.logger.history import record  # noqa: F401,E261,E501

# Type for log messages - can be string or callable returning string
LogMessage = Union[str, Callable[[], str]]


class _log:
    # Logger function that writes formatted log messages
    logger: ClassVar[Optional[Callable[[Callable[[str], None], LogMessage, str, str], None]]] = None

    @staticmethod
    def init(env: 'Env') -> None:
        option.setup(env)

    @classmethod
    def disable(cls) -> None:
        def eat(cls: Type['_log'], message: LogMessage, source: str = '', level: str = '') -> None:
            pass

        cls.debug = eat  # type: ignore[assignment]
        cls.info = eat  # type: ignore[assignment]
        cls.warning = eat  # type: ignore[assignment]
        cls.error = eat  # type: ignore[assignment]
        cls.critical = eat  # type: ignore[assignment]
        cls.fatal = eat  # type: ignore[assignment]

    @classmethod
    def silence(cls) -> None:
        def eat(cls: Type['_log'], message: LogMessage, source: str = '', level: str = '') -> None:
            pass

        cls.debug = eat  # type: ignore[assignment]
        cls.info = eat  # type: ignore[assignment]
        cls.warning = eat  # type: ignore[assignment]
        cls.error = eat  # type: ignore[assignment]

    @classmethod
    def debug(cls, message: LogMessage, source: str = '', level: str = 'DEBUG') -> None:
        cls.logger(option.logger.debug, message, source, level)  # type: ignore[misc,union-attr]

    @classmethod
    def info(cls, message: LogMessage, source: str = '', level: str = 'INFO') -> None:
        cls.logger(option.logger.info, message, source, level)  # type: ignore[misc,union-attr]

    @classmethod
    def warning(cls, message: LogMessage, source: str = '', level: str = 'WARNING') -> None:
        cls.logger(option.logger.warning, message, source, level)  # type: ignore[misc,union-attr]

    @classmethod
    def error(cls, message: LogMessage, source: str = '', level: str = 'ERROR') -> None:
        cls.logger(option.logger.error, message, source, level)  # type: ignore[misc,union-attr]

    @classmethod
    def critical(cls, message: LogMessage, source: str = '', level: str = 'CRITICAL') -> None:
        cls.logger(option.logger.critical, message, source, level)  # type: ignore[misc,union-attr]

    @classmethod
    def fatal(cls, message: LogMessage, source: str = '', level: str = 'FATAL') -> None:
        cls.logger(option.logger.fatal, message, source, level)  # type: ignore[misc,union-attr]


class log(_log):
    @staticmethod
    def logger(logger: Callable[[str], None], message: LogMessage, source: str, level: str) -> None:  # type: ignore[override]
        # DEVELOPER WARNING: Log messages must always be callable (lambda) for lazy evaluation
        if not callable(message):
            import sys

            warning = (
                f'\n'
                f'================================================================================\n'
                f'WARNING: Non-callable log message detected!\n'
                f'================================================================================\n'
                f'Source: {source}\n'
                f'Level: {level}\n'
                f'Message type: {type(message).__name__}\n'
                f'Message preview: {str(message)[:100]}...\n'
                f'\n'
                f'All log messages MUST be wrapped in lambda for lazy evaluation:\n'
                f'  WRONG: log.{level.lower()}("message", "{source}")\n'
                f'  RIGHT: log.{level.lower()}(lambda: "message", "{source}")\n'
                f'================================================================================\n'
            )
            sys.stderr.write(warning)
            sys.stderr.flush()

        # Early exit if logging is disabled
        if not option.log_enabled(source, level):
            return

        # If message is callable, call it now
        msg_str: str
        if callable(message):
            msg_str = message()
        else:
            msg_str = message

        timestamp_struct = time.localtime()
        timestamp_float = time.time()
        for line in msg_str.split('\n'):
            logger(option.formater(line, source, level, timestamp_struct))  # type: ignore[call-arg]
            record(line, source, level, timestamp_float)
