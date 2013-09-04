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
			print 'operational adm "this is dynamic message #%d"' % counter
			sys.stdout.flush()
			print >> sys.stderr, 'operational adm "this is dynamic message #%d"' % counter
			sys.stderr.flush()
		else:
			print 'operational asm "we SHOULD not send asm from the API"'
			sys.stdout.flush()
			print >> sys.stderr, 'operational asm "we SHOULD not send asm from the API"'
			sys.stderr.flush()

		counter += 1
	except KeyboardInterrupt:
		pass
	except IOError:
		break
