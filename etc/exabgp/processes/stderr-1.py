#!/usr/bin/env python

import os
import sys
import time


def _prefixed (level, message):
	now = time.strftime('%a, %d %b %Y %H:%M:%S',time.localtime())
	return "%s %-8s %-6d %s" % (now,level,os.getpid(),message)


# When the parent dies we are seeing continual newlines, so we only access so many before stopping
counter = 0


while True:
	try:
		line = sys.stdin.readline().strip()
		# print >> sys.stderr, "GOT A LINE"
		sys.stdout.flush()
		if line == "":
			counter += 1
			if counter > 100:
				break
			continue

		counter = 0

		print >> sys.stderr, _prefixed(sys.argv[1] if len(sys.argv) >= 2 else 'EXABGP PROCESS',line)
	except KeyboardInterrupt:
		pass
	except IOError:
		# most likely a signal during readline
		pass
