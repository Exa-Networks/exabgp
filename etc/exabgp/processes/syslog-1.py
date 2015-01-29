#!/usr/bin/env python

import os
import sys
import time
import syslog

def _prefixed (level, message):
	now = time.strftime('%a, %d %b %Y %H:%M:%S',time.localtime())
	return "%s %-8s %-6d %s" % (now,level,os.getpid(),message)

syslog.openlog("ExaBGP")

# When the parent dies we are seeing continual newlines, so we only access so many before stopping
counter = 0

while True:
	try:
		line = sys.stdin.readline().strip()
		if line == "":
			counter += 1
			if counter > 100:
				break
			continue

		counter = 0

		syslog.syslog(syslog.LOG_ALERT, _prefixed('INFO',line))
	except KeyboardInterrupt:
		pass
	except IOError:
		# most likely a signal during readline
		pass
