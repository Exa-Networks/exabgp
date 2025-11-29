"""message_type.py

Created by Thomas Mangin on 2024-01-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from enum import Enum


class MessageType(Enum):
    """BGP message types for JSON API transcoding."""

    STATE = 'state'
    OPEN = 'open'
    KEEPALIVE = 'keepalive'
    NOTIFICATION = 'notification'
    UPDATE = 'update'
    EOR = 'eor'
    REFRESH = 'refresh'
    OPERATIONAL = 'operational'

    @classmethod
    def from_str(cls, value: str) -> 'MessageType':
        """Convert string to MessageType, raises ValueError if invalid."""
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(f'invalid message type: {value}')
