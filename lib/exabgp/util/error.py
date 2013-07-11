# encoding: utf-8
"""
errno.py

Created by Thomas Mangin on 2013-07-11.
Copyright (c) 2013-2013 Exa Networks. All rights reserved.
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
