#!/usr/bin/env python

import os
import sys
import time
import syslog

def _prefixed (level,message):
	now = time.strftime('%a, %d %b %Y %H:%M:%S',time.localtime())
	return "%s %-8s %-6d %s" % (now,level,os.getpid(),message)

syslog.openlog("ExaBPG")

while True:
	now = time.strftime('%a, %d %b %Y %H:%M:%S',time.localtime())

	line = sys.stdin.readline()
	syslog.syslog(syslog.LOG_ALERT, _prefixed('INFO',line))
