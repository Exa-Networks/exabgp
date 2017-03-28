#!/usr/bin/env python

import os
import sys
import errno
import fcntl
import select


errno_block = set((
	errno.EINPROGRESS, errno.EALREADY,
	errno.EAGAIN, errno.EWOULDBLOCK,
	errno.EINTR, errno.EDEADLK,
	errno.EBUSY, errno.ENOBUFS,
	errno.ENOMEM,
))

errno_fatal = set((
	errno.ECONNABORTED, errno.EPIPE,
	errno.ECONNREFUSED, errno.EBADF,
	errno.ESHUTDOWN, errno.ENOTCONN,
	errno.ECONNRESET, errno.ETIMEDOUT,
	errno.EINVAL,
))

errno_unavailable = set((
	errno.ECONNREFUSED, errno.EHOSTUNREACH,
))


def async (fd):
	try:
		fcntl.fcntl(fd, fcntl.F_SETFL, os.O_NONBLOCK)
		return True
	except IOError:
		return False


def sync (fd):
	try:
		fcntl.fcntl(fd, fcntl.F_SETFL, os.O_NDELAY)
		return True
	except IOError:
		return False


if not async(sys.stdin):
	print >> sys.stderr, "could not set stdin/stdout non blocking"
	sys.stderr.flush()
	sys.exit(1)


def _reader ():
	received = ''

	while True:
		try:
			data = os.read(sys.stdin.fileno(),4096)
		except IOError as exc:
			if exc.args[0] in errno_block:
				yield ''
				continue
			elif exc.args[0] in errno_fatal:
				print >> sys.stderr, "fatal error while reading on stdin : %s" % str(exc)
				sys.exit(1)
			else:
				print >> sys.stderr, "unknown error while reading on stdin : %s" % str(exc)
				sys.exit(1)

		if not data:
			# we lost the pipe
			print >> sys.stderr, "the read pipe was closed by the other side : %s" % str(exc)
			sys.exit(1)

		received += data
		if '\n' in received:
			line,received = received.split('\n',1)
			yield line + '\n'
		else:
			yield ''

reader = _reader().next


def write (data='', left=''):
	left += data
	try:
		if left:
			number = os.write(sys.stdout.fileno(),left)
			left = left[number:]
			sys.stdout.flush()
	except IOError as exc:
		if exc.args[0] in errno_block:
			return not not left
		elif exc.args[0] in errno_fatal:
			# this may not send anything ...
			print >> sys.stderr, "fatal error while reading on stdin : %s" % str(exc)
			sys.stderr.flush()
			sys.exit(1)
		else:
			print >> sys.stderr, "unknown error while reading on stdin : %s" % str(exc)
			sys.stderr.flush()
			sys.exit(1)

	return not not left


def read (timeout):
	try:
		r, w, x = select.select([sys.stdin], [], [sys.stdin,], timeout)  # pylint: disable=W0612
	except IOError as exc:
		if exc.args[0] in errno_block:
			return ''
		elif exc.args[0] in errno_fatal:
			# this may not send anything ...
			print >> sys.stderr, "fatal error during select : %s" % str(exc)
			sys.stderr.flush()
			sys.exit(1)
		else:
			# this may not send anything ...
			print >> sys.stderr, "unexpected error during select : %s" % str(exc)
			sys.stderr.flush()
			sys.exit(1)

	if not r:
		return ''

	line = reader()
	if not line:
		return ''

	return line


announce = ['announce route 192.0.2.%d next-hop 10.0.0.1\n' % ip for ip in range(1,255)]

leftover  = False
try:
	while True:
		received = read(1.0)  # wait for a maximum of one second
		if received:
			# do something with the data received
			pass

		more,announce = announce[:10],announce[10:]

		if more:
			leftover = write(''.join(more))
		elif leftover:
			# echo back what we got
			leftover = write()
except Exception:
	sync(sys.stdin)
