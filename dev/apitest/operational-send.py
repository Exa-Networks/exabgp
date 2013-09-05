#!/usr/bin/env python

import os
import sys
import time

# When the parent dies we are seeing continual newlines, so we only access so many before stopping
counter = 1

while True:
	try:
		time.sleep(1)
		if counter % 2:
			print 'operational adm afi ipv4 safi unicast "this is dynamic message #%d"' % counter
			sys.stdout.flush()
		else:
			print 'operational asm afi ipv4 safi unicast "we SHOULD not send asm from the API"'
			sys.stdout.flush()

		counter += 1
	except KeyboardInterrupt:
		pass
	except IOError:
		break
