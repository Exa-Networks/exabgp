"""serializer.py

UpdateSerializer - Converts UpdateData to wire-format Update messages.

This class separates the generation logic from the container class,
following the principle that Update (wire container) and UpdateData
(semantic container) should have distinct responsibilities.

Created as part of the Update/Attributes refactoring.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Generator

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.update import Update, UpdateWire

# Type alias for the semantic container (current Update class)
UpdateData = Update


class UpdateSerializer:
    """Serializer for converting UpdateData to wire-format Update messages.

    Separates the serialization/generation logic from the data container.
    One UpdateData can produce multiple Update wire messages due to BGP
    message size limits.

    Usage:
        data = UpdateData(announces, withdraws, attributes)
        for update in UpdateSerializer.serialize(data, negotiated):
            send(update.to_bytes())
    """

    @staticmethod
    def serialize(
        data: UpdateData,
        negotiated: 'Negotiated',
        include_withdraw: bool = True,
    ) -> Generator[UpdateWire, None, None]:
        """Convert UpdateData to wire-format Update messages.

        One UpdateData can produce multiple Update messages due to BGP
        message size limits.

        Args:
            data: Semantic container with announces, withdraws, attributes.
            negotiated: BGP session negotiated parameters.
            include_withdraw: Whether to include withdrawals in output.

        Yields:
            UpdateWire objects containing serialized UPDATE payloads.
        """
        # Delegate to UpdateData.messages() for the actual serialization logic.
        # This approach avoids duplicating the complex message generation code
        # while providing the new interface.
        #
        # The messages() method yields complete BGP messages (with header).
        # We need to extract just the payload to create UpdateWire objects.
        for msg_bytes in data.messages(negotiated, include_withdraw):
            # BGP message format: marker(16) + length(2) + type(1) + payload
            # Extract payload by removing 19-byte header
            payload = msg_bytes[19:]
            yield UpdateWire(payload)

    @staticmethod
    def serialize_bytes(
        data: UpdateData,
        negotiated: 'Negotiated',
        include_withdraw: bool = True,
    ) -> Generator[bytes, None, None]:
        """Convenience: yield complete message bytes.

        This is equivalent to calling to_bytes() on each UpdateWire from
        serialize(), but slightly more efficient as it avoids creating
        intermediate UpdateWire objects.

        Args:
            data: Semantic container with announces, withdraws, attributes.
            negotiated: BGP session negotiated parameters.
            include_withdraw: Whether to include withdrawals in output.

        Yields:
            Complete BGP UPDATE message bytes (with header).
        """
        # Direct delegation - messages() already returns complete messages
        yield from data.messages(negotiated, include_withdraw)
