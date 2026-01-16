"""Network error types and errno classification.

Provides exception classes for network operations and classifies
errno values into recoverable (block) vs fatal categories.

Key classes:
    error: Errno classification (block, fatal, default sets)
    NetworkError: Base network exception
    BindingError, AcceptError, LostConnection, etc.: Specific errors

Created by Thomas Mangin on 2013-07-11.
Copyright (c) 2013-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import errno as errno  # Re-export for type checkers
from typing import ClassVar

__all__ = [
    'errno',
    'error',
    'NetworkError',
    'BindingError',
    'AcceptError',
    'NotConnected',
    'LostConnection',
    'MD5Error',
    'TCPAOError',
    'NagleError',
    'TTLError',
    'AsyncError',
    'TooSlowError',
    'SizeError',
    'NotifyError',
]


class error:
    block: ClassVar[set[int]] = set(
        (
            errno.EINPROGRESS,
            errno.EALREADY,
            errno.EAGAIN,
            errno.EWOULDBLOCK,
            errno.EINTR,
            errno.EDEADLK,
            errno.EBUSY,
            errno.ENOBUFS,
            errno.ENOMEM,
            errno.ENOTCONN,
        ),
    )

    fatal: ClassVar[set[int]] = set(
        (
            errno.ECONNABORTED,
            errno.EPIPE,
            errno.ECONNREFUSED,
            errno.EBADF,
            errno.ESHUTDOWN,
            errno.ENOTCONN,
            errno.ECONNRESET,
            errno.ETIMEDOUT,
            errno.EINVAL,
        ),
    )

    unavailable: ClassVar[set[int]] = set(
        (
            errno.ECONNREFUSED,
            errno.EHOSTUNREACH,
        ),
    )


class NetworkError(Exception):
    pass


class BindingError(NetworkError):
    pass


class AcceptError(NetworkError):
    pass


class NotConnected(NetworkError):
    pass


class LostConnection(NetworkError):
    pass


class MD5Error(NetworkError):
    pass


class TCPAOError(NetworkError):
    pass


class NagleError(NetworkError):
    pass


class TTLError(NetworkError):
    pass


class AsyncError(NetworkError):
    pass


class TooSlowError(NetworkError):
    pass


class SizeError(NetworkError):
    pass


# not used atm - can not generate message due to size


class NotifyError(Exception):
    def __init__(self, code: int, subcode: int, msg: str) -> None:
        self.code: int = code
        self.subcode: int = subcode
        Exception.__init__(self, msg)
