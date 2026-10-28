#!/usr/bin/env python3

import os
import sys
import syslog
import time


def _prefixed(level, message):
    now = time.strftime('%a, %d %b %Y %H:%M:%S', time.localtime())
    return f'{now} {level:<8} {os.getpid():<6d} {message}'


syslog.openlog('ExaBGP')

# When the parent dies we are seeing continual newlines, so we only access so many before stopping
counter = 0

while True:
    try:
        line = sys.stdin.readline().strip()
        if line == '':
            counter += 1
            if counter > 100:
                break
            continue

        counter = 0

        syslog.syslog(syslog.LOG_ALERT, _prefixed('INFO', line))
    except KeyboardInterrupt:
        pass
    except OSError:
        # most likely a signal during readline
        pass
