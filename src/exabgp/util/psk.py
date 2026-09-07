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
import re


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


# The heuristic which existed before 6.0: a key made only of lowercase hexadecimal
# characters was assumed to be base64 which had lost its padding.
_HEX_ONLY = re.compile(r'[a-f0-9]+')

# The padding the heuristic tried, in the order it tried it.
_GUESSED_PADDING = ('==', '=', '')


def guessed_as_base64(value: str) -> bool:
    """Report whether the heuristic removed in 6.0 would have decoded this key.

    Hexadecimal is a subset of the base64 alphabet, so a key from `openssl rand
    -hex 16` decoded cleanly into a different key and the session authenticated
    with bytes the operator never wrote (#1423).  Reading such a key literally
    is the fix, but it also changes the key on the wire for anyone whose session
    worked before, and they have to ask for base64 explicitly to keep it up.

    Args:
        value: The key as it was written in the configuration

    Returns:
        True if earlier releases would have decoded this key as base64
    """
    if not _HEX_ONLY.fullmatch(value):
        return False

    for padding in _GUESSED_PADDING:
        try:
            decode_base64(value + padding)
        except PSKError:
            continue
        return True

    return False
