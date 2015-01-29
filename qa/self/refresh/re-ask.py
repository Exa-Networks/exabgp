#!/usr/bin/env python

import sys
import signal

class TimeError (Exception): pass

def handler (signum, frame):
	raise TimeError()

count = 0

while True:
	try:
		signal.signal(signal.SIGALRM, handler)
		signal.alarm(4)

		line = sys.stdin.readline()
		sys.stderr.write('received %s\n' % line.strip())
		sys.stderr.flush()
	except TimeError:
		print 'announce route-refresh ipv4 unicast'
		sys.stdout.flush()
		print >> sys.stderr, 'announce route-refresh ipv4 unicast'
		sys.stderr.flush()
