#!/usr/bin/env python3

import sys
import time

# When the parent dies we are seeing continual newlines, so we only access so many before stopping
counter = 1

# sleep a little bit or we will never see the asm in the configuration file
# and the message received just before we go to the established loop will be printed twice
time.sleep(1)

sys.stdout.write(f'announce operational rpcq afi ipv4 safi unicast sequence {counter:d}\n')
sys.stdout.write(f'announce operational rpcp afi ipv4 safi unicast sequence {counter:d} counter 200\n')
time.sleep(1)

counter += 1

sys.stdout.write(f'announce operational apcq afi ipv4 safi unicast sequence {counter:d}\n')
sys.stdout.write(f'announce operational apcp afi ipv4 safi unicast sequence {counter:d} counter 150\n')
time.sleep(1)

counter += 1

sys.stdout.write(f'announce operational lpcq afi ipv4 safi unicast sequence {counter:d}\n')
sys.stdout.write(f'announce operational lpcp afi ipv4 safi unicast sequence {counter:d} counter 250\n')
time.sleep(1)

while True:
    try:
        time.sleep(1)
        if counter % 2:
            sys.stdout.write(
                f'announce operational adm afi ipv4 safi unicast advisory "this is dynamic message #{counter:d}"\n'
            )
            sys.stdout.flush()
        else:
            sys.stdout.write(
                'announce operational asm afi ipv4 safi unicast advisory "we SHOULD not send asm from the API"\n'
            )
            sys.stdout.flush()

        counter += 1
    except KeyboardInterrupt:
        pass
    except OSError:
        break
