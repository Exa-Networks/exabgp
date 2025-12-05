"""v4/json.py

API v4 JSON encoder - wraps v6 JSON and patches version string.

Created by Thomas Mangin on 2024-12-04.
Copyright (c) 2024 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from exabgp.reactor.api.response.json import JSON
from exabgp.version import json as json_version

if TYPE_CHECKING:
    from exabgp.bgp.neighbor import Neighbor
    from exabgp.bgp.message.open.capability.negotiated import Negotiated
    from exabgp.bgp.message.notification import Notification
    from exabgp.bgp.message.open import Open
    from exabgp.bgp.message.update import Update
    from exabgp.bgp.message.refresh import RouteRefresh
    from exabgp.bgp.message.operational import OperationalFamily
    from exabgp.bgp.fsm import FSM


class V4JSON:
    """API v4 JSON encoder - delegates to v6 and patches version string.

    This ensures all v4 JSON calls exercise the v6 code path, providing
    implicit testing of v6 through v4 functional tests.
    """

    def __init__(self, version: str) -> None:
        self._v6 = JSON(json_version)  # Delegate to v6 encoder
        self.version = version  # v4 version string to use in output

    def _patch_version(self, result: str | None) -> str | None:
        """Replace v6 version with v4 version in JSON output."""
        if result is None:
            return None
        return result.replace(f'"exabgp": "{json_version}"', f'"exabgp": "{self.version}"')

    def up(self, neighbor: 'Neighbor') -> str:
        result = self._v6.up(neighbor)
        return self._patch_version(result) or ''

    def connected(self, neighbor: 'Neighbor') -> str:
        result = self._v6.connected(neighbor)
        return self._patch_version(result) or ''

    def down(self, neighbor: 'Neighbor', reason: str = '') -> str:
        result = self._v6.down(neighbor, reason)
        return self._patch_version(result) or ''

    def shutdown(self) -> str:
        result = self._v6.shutdown()
        return self._patch_version(result) or ''

    def negotiated(self, neighbor: 'Neighbor', negotiated: 'Negotiated') -> str | None:
        result = self._v6.negotiated(neighbor, negotiated)
        return self._patch_version(result)

    def fsm(self, neighbor: 'Neighbor', fsm: 'FSM') -> str | None:
        result = self._v6.fsm(neighbor, fsm)
        return self._patch_version(result)

    def signal(self, neighbor: 'Neighbor', signal: int) -> str | None:
        result = self._v6.signal(neighbor, signal)
        return self._patch_version(result)

    def notification(
        self,
        neighbor: 'Neighbor',
        direction: str,
        message: 'Notification',
        header: bytes,
        body: bytes,
        negotiated: 'Negotiated',
    ) -> str:
        result = self._v6.notification(neighbor, direction, message, header, body, negotiated)
        return self._patch_version(result) or ''

    def packets(
        self,
        neighbor: 'Neighbor',
        direction: str,
        category: int,
        header: bytes,
        body: bytes,
        negotiated: 'Negotiated',
    ) -> str:
        result = self._v6.packets(neighbor, direction, category, header, body, negotiated)
        return self._patch_version(result) or ''

    def keepalive(
        self, neighbor: 'Neighbor', direction: str, header: bytes, body: bytes, negotiated: 'Negotiated'
    ) -> str:
        result = self._v6.keepalive(neighbor, direction, header, body, negotiated)
        return self._patch_version(result) or ''

    def open(
        self,
        neighbor: 'Neighbor',
        direction: str,
        sent_open: 'Open',
        header: bytes,
        body: bytes,
        negotiated: 'Negotiated',
    ) -> str:
        result = self._v6.open(neighbor, direction, sent_open, header, body, negotiated)
        return self._patch_version(result) or ''

    def update(
        self,
        neighbor: 'Neighbor',
        direction: str,
        update: 'Update',
        header: bytes,
        body: bytes,
        negotiated: 'Negotiated',
    ) -> str:
        result = self._v6.update(neighbor, direction, update, header, body, negotiated)
        return self._patch_version(result) or ''

    def refresh(
        self,
        neighbor: 'Neighbor',
        direction: str,
        refresh: 'RouteRefresh',
        header: bytes,
        body: bytes,
        negotiated: 'Negotiated',
    ) -> str:
        result = self._v6.refresh(neighbor, direction, refresh, header, body, negotiated)
        return self._patch_version(result) or ''

    def operational(
        self,
        neighbor: 'Neighbor',
        direction: str,
        what: str,
        operational: 'OperationalFamily',
        header: bytes,
        body: bytes,
        negotiated: 'Negotiated',
    ) -> str:
        result = self._v6.operational(neighbor, direction, what, operational, header, body, negotiated)
        return self._patch_version(result) or ''
