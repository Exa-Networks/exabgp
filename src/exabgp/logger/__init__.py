from __future__ import annotations

import time

from exabgp.logger.option import option
from exabgp.logger.handler import get_logger  # noqa: F401,E261,E501
from exabgp.logger.format import formater  # noqa: F401,E261,E501

from exabgp.logger.format import lazyformat  # noqa: F401,E261,E501
from exabgp.logger.format import lazyattribute  # noqa: F401,E261,E501
from exabgp.logger.format import lazynlri  # noqa: F401,E261,E501

from exabgp.logger.history import history  # noqa: F401,E261,E501
from exabgp.logger.history import record  # noqa: F401,E261,E501


class _log(object):
    logger = None

    @staticmethod
    def init(env):
        option.setup(env)

    @classmethod
    def disable(cls):
        def eat(cls, message, source='', level=''):
            pass

        cls.debug = eat
        cls.info = eat
        cls.warning = eat
        cls.error = eat
        cls.critical = eat
        cls.fatal = eat

    @classmethod
    def silence(cls):
        def eat(cls, message, source='', level=''):
            pass

        cls.debug = eat
        cls.info = eat
        cls.warning = eat
        cls.error = eat

    @classmethod
    def debug(cls, message, source='', level='DEBUG'):
        cls.logger(option.logger.debug, message, source, level)

    @classmethod
    def info(cls, message, source='', level='INFO'):
        cls.logger(option.logger.info, message, source, level)

    @classmethod
    def warning(cls, message, source='', level='WARNING'):
        cls.logger(option.logger.warning, message, source, level)

    @classmethod
    def error(cls, message, source='', level='ERROR'):
        cls.logger(option.logger.error, message, source, level)

    @classmethod
    def critical(cls, message, source='', level='CRITICAL'):
        cls.logger(option.logger.critical, message, source, level)

    @classmethod
    def fatal(cls, message, source='', level='FATAL'):
        cls.logger(option.logger.fatal, message, source, level)


class log(_log):
    def logger(logger, message, source, level):
        # Early exit if logging is disabled
        if not option.log_enabled(source, level):
            return

        # If message is callable, call it now
        if callable(message):
            message = message()

        timestamp = time.localtime()
        for line in message.split('\n'):
            logger(option.formater(line, source, level, timestamp))
            record(line, source, level, timestamp)
