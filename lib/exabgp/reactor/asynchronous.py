# encoding: utf-8
"""
reactor/async.py

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from collections import deque

from exabgp.logger import Logger
from exabgp.vendoring import six


class ASYNC(object):
    LIMIT = 50

    def __init__(self):
        self.logger = Logger()
        self._async = deque()

    def ready(self):
        return not self._async

    def schedule(self, uid, command, callback):
        self.logger.debug('async | %s | %s' % (uid, command), 'reactor')
        self._async.append((uid, callback))

    def clear(self, deluid=None):
        if not self._async:
            return
        if deluid is None:
            # We could delete all the generators just to be safe
            self._async = deque()
            return
        running = deque()
        for (uid, generator) in self._async:
            if uid != deluid:
                running.append((uid, generator))
        self._async = running

    def run(self):
        if not self._async:
            return False

        # length = range(min(len(self._async),self.LIMIT))
        length = range(self.LIMIT)
        uid, generator = self._async.popleft()

        for _ in length:
            try:
                six.next(generator)
            except KeyboardInterrupt:
                raise
            except StopIteration:
                if not self._async:
                    return False
                uid, generator = self._async.popleft()
            except Exception as exc:
                self.logger.error('async | %s | problem with function' % uid, 'reactor')
                for line in str(exc).split('\n'):
                    self.logger.error('async | %s | %s' % (uid, line), 'reactor')

        self._async.appendleft((uid, generator))
        return True
