# encoding: utf-8
"""
timer.py

Created by Thomas Mangin on 2012-07-21.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import time

from exabgp.logger import Logger
from exabgp.bgp.message import _NOP
from exabgp.bgp.message import KeepAlive
from exabgp.bgp.message import Notify

# ================================================================ ReceiveTimer
# Track the time for keepalive updates


class ReceiveTimer(object):
    def __init__(self, session, holdtime, code, subcode, message=''):
        self.logger = Logger()
        self.session = session

        self.holdtime = holdtime
        self.last_print = 0
        self.last_read = int(time.time())

        self.code = code
        self.subcode = subcode
        self.message = message
        self.single = False

    def check_ka_timer(self, message=_NOP, ignore=_NOP.TYPE):
        if self.holdtime == 0:
            return message.TYPE != KeepAlive.TYPE
        now = int(time.time())
        if message.TYPE != ignore:
            self.last_read = now
        elapsed = now - self.last_read
        if elapsed > self.holdtime:
            raise Notify(self.code, self.subcode, self.message)
        if self.last_print != now:
            left = self.holdtime - elapsed
            self.logger.debug('receive-timer %d second(s) left' % left, source='ka-' + self.session())
            self.last_print = now
        return True

    def check_ka(self, message=_NOP, ignore=_NOP.TYPE):
        if self.check_ka_timer(message, ignore):
            return
        if self.single:
            raise Notify(2, 6, 'Negotiated holdtime was zero, it was invalid to send us a keepalive messages')
        self.single = True


class SendTimer(object):
    def __init__(self, session, holdtime):
        self.logger = Logger()
        self.session = session

        self.keepalive = holdtime.keepalive()
        self.last_print = int(time.time())
        self.last_sent = int(time.time())

    def need_ka(self):
        if not self.keepalive:
            return False

        now = int(time.time())
        left = self.last_sent + self.keepalive - now

        if now != self.last_print:
            self.logger.debug('send-timer %d second(s) left' % left, source='ka-' + self.session())
            self.last_print = now

        if left <= 0:
            self.last_sent = now
            return True
        return False
