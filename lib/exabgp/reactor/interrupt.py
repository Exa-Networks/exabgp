# encoding: utf-8
"""
reactor/interrupt.py

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import signal

from exabgp.logger import Logger


class Signal(object):
    NONE = 0
    SHUTDOWN = 1
    RESTART = 2
    RELOAD = 4
    FULL_RELOAD = 8

    def __init__(self):
        self.logger = Logger()
        self.received = self.NONE
        self.number = 0
        self.rearm()

    def rearm(self):
        self.received = Signal.NONE
        self.number = 0

        signal.signal(signal.SIGTERM, self.sigterm)
        signal.signal(signal.SIGHUP, self.sighup)
        signal.signal(signal.SIGALRM, self.sigalrm)
        signal.signal(signal.SIGUSR1, self.sigusr1)
        signal.signal(signal.SIGUSR2, self.sigusr2)

    def sigterm(self, signum, frame):
        self.logger.critical('SIGTERM received', 'reactor')
        if self.received:
            self.logger.critical('ignoring - still handling previous signal', 'reactor')
            return
        self.logger.critical('scheduling shutdown', 'reactor')
        self.received = self.SHUTDOWN
        self.number = signum

    def sighup(self, signum, frame):
        self.logger.critical('SIGHUP received', 'reactor')
        if self.received:
            self.logger.critical('ignoring - still handling previous signal', 'reactor')
            return
        self.logger.critical('scheduling shutdown', 'reactor')
        self.received = self.SHUTDOWN
        self.number = signum

    def sigalrm(self, signum, frame):
        self.logger.critical('SIGALRM received', 'reactor')
        if self.received:
            self.logger.critical('ignoring - still handling previous signal', 'reactor')
            return
        self.logger.critical('scheduling restart', 'reactor')
        self.received = self.RESTART
        self.number = signum

    def sigusr1(self, signum, frame):
        self.logger.critical('SIGUSR1 received', 'reactor')
        if self.received:
            self.logger.critical('ignoring - still handling previous signal', 'reactor')
            return
        self.logger.critical('scheduling reload of configuration', 'reactor')
        self.received = self.RELOAD
        self.number = signum

    def sigusr2(self, signum, frame):
        self.logger.critical('SIGUSR2 received', 'reactor')
        if self.received:
            self.logger.critical('ignoring - still handling previous signal', 'reactor')
            return
        self.logger.critical('scheduling reload of configuration and processes', 'reactor')
        self.received = self.FULL_RELOAD
        self.number = signum
