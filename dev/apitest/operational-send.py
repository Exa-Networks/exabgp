#!/usr/bin/env python

import os
import sys
import time

# When the parent dies we are seeing continual newlines, so we only access so many before stopping
counter = 1

# sleep a little bit or we will never see the asm in the configuration file
# and the message received just before we go to the established loop will be printed twice
time.sleep(1)

print 'operational rpcq afi ipv4 safi unicast sequence %d' % counter
print 'operational rpcp afi ipv4 safi unicast sequence %d rxc 100 txc 200' % counter
time.sleep(1)

counter += 1

print 'operational apcq afi ipv4 safi unicast sequence %d' % counter
print 'operational apcp afi ipv4 safi unicast sequence %d counter 150' % counter
time.sleep(1)

counter += 1

print 'operational lpcq afi ipv4 safi unicast sequence %d' % counter
print 'operational lpcp afi ipv4 safi unicast sequence %d counter 250' % counter
time.sleep(1)

while True:
	try:
		time.sleep(1)
		if counter % 2:
			print 'operational adm afi ipv4 safi unicast advisory "this is dynamic message #%d"' % counter
			sys.stdout.flush()
		else:
			print 'operational asm afi ipv4 safi unicast advisory "we SHOULD not send asm from the API"'
			sys.stdout.flush()

		counter += 1
	except KeyboardInterrupt:
		pass
	except IOError:
		break
