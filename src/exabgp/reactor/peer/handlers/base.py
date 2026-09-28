"""Base class for message handlers.

MessageHandler is the abstract base class for all inbound message handlers.
Each handler processes a specific BGP message type.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Generator

if TYPE_CHECKING:
    from exabgp.bgp.message import Message
    from exabgp.reactor.peer.context import PeerContext


class MessageHandler(ABC):
    """Abstract base class for BGP message handlers.

    Handlers process inbound BGP messages.
    Each handler declares which message types it can process via can_handle().
    """

    @abstractmethod
    def can_handle(self, message: Message) -> bool:
        """Check if this handler can process the given message.

        Args:
            message: The BGP message to check

        Returns:
            True if this handler can process the message
        """
        ...

    @abstractmethod
    def handle(self, ctx: PeerContext, message: Message) -> Generator[Message, None, None]:
        """Process the message synchronously.

        Args:
            ctx: The peer context with protocol and neighbor state
            message: The BGP message to process

        Yields:
            Nothing: the generator form is what the synchronous callers iterate
        """
        ...

    @abstractmethod
    async def handle_async(self, ctx: PeerContext, message: Message) -> None:
        """Process the message asynchronously.

        Args:
            ctx: The peer context with protocol and neighbor state
            message: The BGP message to process
        """
        ...
