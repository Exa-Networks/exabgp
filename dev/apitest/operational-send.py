#!/usr/bin/env python

import os
import sys
import time

# When the parent dies we are seeing continual newlines, so we only access so many before stopping
counter = 1

# sleep a little bit or we will never see the asm in the configuration file
# and the message received just before we go to the established loop will be printed twice
time.sleep(4)

while True:
	try:
		time.sleep(1)
		if counter % 2:
			print 'operational adm afi ipv4 safi unicast "this is dynamic message #%d"' % counter
			sys.stdout.flush()
		else:
			print 'operational asm afi ipv4 safi unicast "we SHOULD not send asm from the API"'
			sys.stdout.flush()

		#if counter % 3:
		#	print 'operational rpcq afi ipv4 safi unicast sequence %d' % counter

		counter += 1
	except KeyboardInterrupt:
		pass
	except IOError:
		break
