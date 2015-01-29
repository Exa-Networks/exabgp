# encoding: utf-8
"""
error.py

Created by Thomas Mangin on 2013-07-11.
Copyright (c) 2013-2015 Exa Networks. All rights reserved.
"""

import errno


class error:
	block = set((
		errno.EINPROGRESS, errno.EALREADY,
		errno.EAGAIN, errno.EWOULDBLOCK,
		errno.EINTR, errno.EDEADLK,
		errno.EBUSY, errno.ENOBUFS,
		errno.ENOMEM,
	))

	fatal = set((
		errno.ECONNABORTED, errno.EPIPE,
		errno.ECONNREFUSED, errno.EBADF,
		errno.ESHUTDOWN, errno.ENOTCONN,
		errno.ECONNRESET, errno.ETIMEDOUT,
		errno.EINVAL,
	))

	unavailable = set((
		errno.ECONNREFUSED, errno.EHOSTUNREACH,
	))


class NetworkError   (Exception):
	pass


class BindingError   (NetworkError):
	pass


class AcceptError    (NetworkError):
	pass


class NotConnected   (NetworkError):
	pass


class LostConnection (NetworkError):
	pass


class MD5Error       (NetworkError):
	pass


class NagleError     (NetworkError):
	pass


class TTLError       (NetworkError):
	pass


class AsyncError     (NetworkError):
	pass


class TooSlowError   (NetworkError):
	pass


class SizeError      (NetworkError):
	pass


# not used atm - can not generate message due to size

class NotifyError    (Exception):
	def __init__ (self, code, subcode, msg):
		self.code = code
		self.subcode = subcode
		Exception.__init__(self,msg)
