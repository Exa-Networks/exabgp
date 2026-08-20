"""psk.py

Strict decoding of the pre-shared keys used by TCP MD5 (RFC 2385) and
TCP-AO (RFC 5925).

Both the configuration validation and the socket setup must reach the same
verdict on a key, otherwise a key rejected at one layer and accepted at the
other leaves a session silently unauthenticated.

Created by Thomas Mangin on 2026-08-20.
Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import base64


class PSKError(ValueError):
    """Raised when a pre-shared key can not be decoded."""


def decode_base64(value: str) -> bytes:
    """Decode a base64 encoded pre-shared key.

    Unlike a bare base64.b64decode() call this rejects any character outside the
    base64 alphabet instead of discarding it, so a mistyped key fails loudly
    instead of yielding a key different from the one which was intended.

    Args:
        value: The base64 text to decode

    Returns:
        The decoded key

    Raises:
        PSKError: If the text is not valid base64 or decodes to nothing
    """
    try:
        # binascii.Error, raised on a bad alphabet or bad padding, is a ValueError
        decoded = base64.b64decode(value, validate=True)
    except (TypeError, ValueError) as exc:
        raise PSKError(f'not valid base64 ({exc})') from None

    if not decoded:
        raise PSKError('decodes to an empty key')

    return decoded
