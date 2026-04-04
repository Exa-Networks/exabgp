#!/usr/bin/env python3

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
            sys.stdout.write('announce route 10.0.%d.%d next-hop 1.2.3.4\n' % (counter >> 8, counter % 256))
            sys.stdout.flush()
            time.sleep(1)
            sys.stdout.write('withdraw route 10.0.%d.%d next-hop 1.2.3.4\n' % (counter >> 8, counter % 256))
            sys.stdout.flush()
        else:
            sys.stdout.write('announce route 2001:%d:: next-hop ::1\n' % counter)
            sys.stdout.flush()
            time.sleep(1)
            sys.stdout.write('withdraw route 2001:%d:: next-hop ::1\n' % counter)
            sys.stdout.flush()

        counter += 1
    except KeyboardInterrupt:
        pass
    except OSError:
        break
