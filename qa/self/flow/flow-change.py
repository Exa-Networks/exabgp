#!/usr/bin/env python

import os
import sys
import time

flow="flow route { match { source 10.0.0.1/32; destination 10.0.0.2/32; destination-port =3128; protocol tcp; } then { discard; } }"

# When the parent dies we are seeing continual newlines, so we only access so many before stopping
counter = 1

# sleep a little bit or we will never see the asm in the configuration file
# and the message received just before we go to the established loop will be printed twice
time.sleep(1)

while True:
	try:
		time.sleep(1)
		if counter % 2:
			print 'announce', flow
			sys.stdout.flush()
		else:
			print 'withdraw', flow
			sys.stdout.flush()

		counter += 1
	except KeyboardInterrupt:
		pass
	except IOError:
		break
