#!/usr/bin/env python3

from __future__ import print_function
import os
import sys
import time

# When the parent dies we are seeing continual newlines, so we only access so many before stopping
counter = 1

# sleep a little bit or we will never see the asm in the configuration file
# and the message received just before we go to the established loop will be printed twice
time.sleep(1)


while True:
    try:
        if counter % 2:
            print('announce route 10.0.%d.%d next-hop 1.2.3.4' % (counter >> 8, counter % 256))
            sys.stdout.flush()
            time.sleep(1)
            print('withdraw route 10.0.%d.%d next-hop 1.2.3.4' % (counter >> 8, counter % 256))
            sys.stdout.flush()
        else:
            print('announce route 2001:%d:: next-hop ::1' % counter)
            sys.stdout.flush()
            time.sleep(1)
            print('withdraw route 2001:%d:: next-hop ::1' % counter)
            sys.stdout.flush()

        counter += 1
    except KeyboardInterrupt:
        pass
    except IOError:
        break
