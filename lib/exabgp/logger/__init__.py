import sys
import time
import logging

from exabgp.logger.option import option
from exabgp.logger.handler import getLogger
from exabgp.logger.format import formater

from exabgp.logger.format import lazyformat
from exabgp.logger.format import lazyattribute
from exabgp.logger.format import lazynlri

from exabgp.logger.history import history
from exabgp.logger.history import record


class _log(object):
    logger = None

    @staticmethod
    def init(env):
        option.setup(env)

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
        timestamp = time.localtime()
        for line in message.split('\n'):
            logger(option.formater(line, source, level, timestamp))
            record(line, source, level, timestamp)


class logfunc(_log):
    def logger(logger, message, source, level):
        if not option.log_enabled(source, level):
            return
        log.logger(logger, message(), source, level)
