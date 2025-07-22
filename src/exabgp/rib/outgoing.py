# encoding: utf-8
"""
store.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from copy import deepcopy
from exabgp.logger import log

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message import Action
from exabgp.bgp.message import Update
from exabgp.bgp.message.refresh import RouteRefresh

from exabgp.rib.cache import Cache

# This is needs to be an ordered dict
RIBdict = dict


class OutgoingRIB(Cache):
    def __init__(self, cache, families):
        Cache.__init__(self, cache, families)

        self._watchdog = {}
        self.families = families
        self.micro_route_tables = {}

        # using change-inde and not nlri-index as it is cached as same us memory
        # even if it is a few bytes longer
        self._new_nlri = {}  # self._new_nlri[change-index] = change
        self._new_attr_af_nlri = {}  # self._new_attr_af_nlri[attr-index][family][change-index] = change
        self._new_attribute = {}  # self._new_attribute[attr-index] = attributes

        # _new_nlri: we are modifying this nlri
        # this is useful to iterate and find nlri currently handled

        # _new_attr_af_nlri: add or remove the nlri
        # this is the best way to iterate over NLRI when generating updates
        # sharing attributes, then family

        # _new_attribute: attributes of one of the changes
        # makes our life easier, but could be removed

        self._refresh_families = set()
        self._refresh_changes = []

        self.reset()

    # will resend all the routes once we reconnect
    def reset(self):
        # WARNING : this function can run while we are in the updates() loop too !
        self._refresh_families = set()
        self._refresh_changes = []
        for _ in self.updates(True):
            pass

    # back to square one, all the routes are removed
    def clear(self):
        self.clear_cache()
        self._new_nlri = {}
        self._new_attr_af_nlri = {}
        self._new_attribute = {}
        self.reset()

    def pending(self):
        return len(self._new_nlri) != 0 or len(self._refresh_changes) != 0

    def resend(self, enhanced_refresh, family=None):
        requested_families = set(self.families)

        if family is not None:
            requested_families = set(self.families).intersection([family])

        if enhanced_refresh:
            for family in requested_families:
                self._refresh_families.add(family)

        for change in self.cached_changes(requested_families):
            self._refresh_changes.append(change)

    def withdraw(self, families=None):
        if not families:
            families = self.families
        requested_families = set(families).intersection(self.families)

        changes = list(self.cached_changes(requested_families, [Action.ANNOUNCE, Action.WITHDRAW]))
        for change in changes:
            self.del_from_rib(change)

    def queued_changes(self):
        for change in self._new_nlri.values():
            yield change

    def replace_restart(self, previous, new):
        # this requires that all changes are announcements
        indexed = {}

        for change in previous:
            indexed[change.index()] = change

        for change in new:
            indexed.pop(change.index(), None)

        for change in self.cached_changes(self.families):
            self.add_to_rib(change, True)

        for index in list(indexed):
            self.del_from_rib(indexed.pop(index))

    def replace_reload(self, previous, new):
        # this requires that all changes are announcements
        indexed = {}

        for change in previous:
            indexed[change.index()] = change

        for change in new:
            if indexed.pop(change.index(), None) is None:
                self.add_to_rib(change, True)
                continue

        for index in list(indexed):
            self.del_from_rib(indexed.pop(index))

    def add_to_rib_watchdog(self, change):
        watchdog = change.attributes.watchdog()
        withdraw = change.attributes.withdraw()
        if watchdog:
            if withdraw:
                self._watchdog.setdefault(watchdog, {}).setdefault('-', {})[change.index()] = change
                return True
            self._watchdog.setdefault(watchdog, {}).setdefault('+', {})[change.index()] = change
        self.add_to_rib(change)
        return True

    def announce_watchdog(self, watchdog):
        if watchdog in self._watchdog:
            for change in list(self._watchdog[watchdog].get('-', {}).values()):
                change.nlri.action = Action.ANNOUNCE  # pylint: disable=E1101
                self.add_to_rib(change)
                self._watchdog[watchdog].setdefault('+', {})[change.index()] = change
                self._watchdog[watchdog]['-'].pop(change.index())

    def withdraw_watchdog(self, watchdog):
        if watchdog in self._watchdog:
            for change in list(self._watchdog[watchdog].get('+', {}).values()):
                self.del_from_rib(change)
                self._watchdog[watchdog].setdefault('-', {})[change.index()] = change
                self._watchdog[watchdog]['+'].pop(change.index())

    def del_from_rib(self, change, device_id=None):
        log.debug('remove %s from rib for device %s' % (change, device_id), 'rib')

        if device_id:
            if device_id in self.micro_route_tables:
                self.micro_route_tables[device_id].del_from_rib(change)
            return

        change_index = change.index()
        change_family = change.nlri.family().afi_safi()

        attr_af_nlri = self._new_attr_af_nlri
        new_nlri = self._new_nlri

        # remove previous announcement if cancelled/replaced before being sent
        prev_change = new_nlri.get(change_index, None)
        if prev_change:
            prev_change_index = prev_change.index()
            prev_change_attr_index = prev_change.attributes.index()
            attr_af_nlri.setdefault(prev_change_attr_index, {}).setdefault(change_family, RIBdict({})).pop(
                prev_change_index, None
            )

        change = deepcopy(change)
        change.nlri.action = Action.WITHDRAW
        return self._update_rib(change)

    def add_to_resend(self, change):
        self._refresh_changes.append(change)

    def add_to_rib(self, change, force=False, device_id=None):
        log.debug('insert %s into rib for device %s' % (change, device_id), 'rib')

        if device_id:
            if device_id not in self.micro_route_tables:
                self.micro_route_tables[device_id] = OutgoingRIB(self.cache, self.families)
            self.micro_route_tables[device_id].add_to_rib(change, force)
            return

        if not force and self.in_cache(change):
            return

        return self._update_rib(change)

    def _update_rib(self, change):
        # change.nlri.index does not prepend the family
        change_index = change.index()
        change_family = change.nlri.family().afi_safi()
        change_attr_index = change.attributes.index()

        attr_af_nlri = self._new_attr_af_nlri
        new_nlri = self._new_nlri
        new_attr = self._new_attribute

        # add the route to the list to be announced/withdrawn
        attr_af_nlri.setdefault(change_attr_index, {}).setdefault(change_family, RIBdict({}))[change_index] = change
        new_nlri[change_index] = change
        new_attr[change_attr_index] = change.attributes
        self.update_cache(change)

    def updates(self, grouped, device_id=None):
        if device_id:
            if device_id in self.micro_route_tables:
                for update in self.micro_route_tables[device_id].updates(grouped):
                    yield update
            return

        attr_af_nlri = self._new_attr_af_nlri
        new_attr = self._new_attribute

        # Get ready to accept more data
        self._new_nlri = {}
        self._new_attr_af_nlri = {}
        self._new_attribute = {}

        # generating Updates from what is in the RIB
        for attr_index, per_family in attr_af_nlri.items():
            for family, changes in per_family.items():
                if not changes:
                    continue

                attributes = new_attr[attr_index]

                if family == (AFI.ipv4, SAFI.unicast) and grouped:
                    nlris = [change.nlri for change in changes.values()]
                    yield Update(nlris, attributes)
                    continue

                if family == (AFI.ipv4, SAFI.mcast_vpn) and grouped:
                    nlris = [change.nlri for change in changes.values()]
                    yield Update(nlris, attributes)
                    continue
                if family == (AFI.ipv6, SAFI.mcast_vpn) and grouped:
                    nlris = [change.nlri for change in changes.values()]
                    yield Update(nlris, attributes)
                    continue

                for change in changes.values():
                    yield Update([change.nlri], attributes)

        # Route Refresh

        for afi, safi in self._refresh_families:
            yield RouteRefresh(afi, safi, RouteRefresh.start)

        for change in self._refresh_changes:
            yield Update([change.nlri], change.attributes)
        self._refresh_changes = []

        for afi, safi in self._refresh_families:
            yield RouteRefresh(afi, safi, RouteRefresh.end)
        self._refresh_families = set()
