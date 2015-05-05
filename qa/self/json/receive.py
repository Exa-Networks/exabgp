#!/usr/bin/env python

import sys
import json
import pprint

exit = False

while True:
	line = sys.stdin.readline().strip()

	if not line:
		if exit:
			sys.exit(0)
		exit = True
	else:
		exit = False
		

	print >> sys.stderr, '\n=====\n'
	print >> sys.stderr, line
	print >> sys.stderr, '\n---\n'
	print >> sys.stderr, pprint.pformat(json.loads(line),indent=3).replace("u'","'")
	sys.stderr.flush()
