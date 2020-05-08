# encoding: utf-8
"""
store.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""
import sys

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message import OUT
from exabgp.bgp.message import Update
from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.bgp.message.update.attribute import Attributes

from exabgp.rib.cache import Cache

if sys.version_info[0] >= 3 and sys.version_info[1] >= 6:
    RIBdict = dict
else:
    from exabgp.vendoring.ordereddict import OrderedDict as RIBdict


class OutgoingRIB(Cache):
    def __init__(self, cache, families):
        Cache.__init__(self, cache, families)

        self._watchdog = {}
        self.families = families

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

        self._enhanced_refresh_start = []
        self._enhanced_refresh_delay = []

        self.reset()

    # will resend all the routes once we reconnect
    def reset(self):
        # WARNING : this function can run while we are in the updates() loop too !
        self._enhanced_refresh_start = []
        self._enhanced_refresh_delay = []
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
        return len(self._new_nlri) != 0

    def resend(self, families, enhanced_refresh):
        # families can be None or []
        requested_families = self.families if not families else set(families).intersection(self.families)

        if enhanced_refresh:
            for family in requested_families:
                if family not in self._enhanced_refresh_start:
                    self._enhanced_refresh_start.append(family)

        for change in self.cached_changes(requested_families):
            self.add_to_rib(change, True)

    def withdraw(self, families, enhanced_refresh):
        requested_families = self.families if not families else set(families).intersection(self.families)

        if enhanced_refresh:
            for family in requested_families:
                if family not in self._enhanced_refresh_start:
                    self._enhanced_refresh_start.append(family)

        changes = list(self.cached_changes(requested_families))
        for change in changes:
            self.del_from_rib(change)

    def queued_changes(self):
        for change in self._new_nlri.values():
            yield change

    def replace(self, previous, changes):
        for change in previous:
            change.nlri.action = OUT.WITHDRAW
            self.add_to_rib(change, True)

        for change in changes:
            self.add_to_rib(change, True)

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
                change.nlri.action = OUT.ANNOUNCE  # pylint: disable=E1101
                self.add_to_rib(change)
                self._watchdog[watchdog].setdefault('+', {})[change.index()] = change
                self._watchdog[watchdog]['-'].pop(change.index())

    def withdraw_watchdog(self, watchdog):
        if watchdog in self._watchdog:
            for change in list(self._watchdog[watchdog].get('+', {}).values()):
                change.nlri.action = OUT.WITHDRAW
                self.add_to_rib(change)
                self._watchdog[watchdog].setdefault('-', {})[change.index()] = change
                self._watchdog[watchdog]['+'].pop(change.index())

    def del_from_rib(self, change, force=False):
        return self.add_to_rib(change, force, True)

    # _withdraw should only be used by del_from_rib
    def add_to_rib(self, change, force=False, _withdraw=False):
        # WARNING: do not call change.nlri.index as it does not prepend the family
        # WARNING : this function can run while we are in the updates() loop

        # import traceback
        # traceback.print_stack()
        # print("\n\n\n")
        # print("%s %s" % ('inserting' if change.nlri.action == OUT.ANNOUNCE else 'withdrawing', change.extensive()))
        # print("\n\n\n")

        if not force and self._enhanced_refresh_start:
            self._enhanced_refresh_delay.append(change)
            return

        change_index = change.index()
        change_family = change.nlri.family()
        change_attr_index = change.attributes.index()

        attr_af_nlri = self._new_attr_af_nlri
        new_nlri = self._new_nlri
        new_attr = self._new_attribute

        in_cache, same_in_cache = self.in_cache(change)

        if same_in_cache:
            if not force and not _withdraw:
                return

        # withdrawal of a route before we had time to announce it ?

        # this optimisation require much calculation when announcing routes
        # and an extra withdrawal is harmless.
        # Also, just having the data in new_nlri, does not mean we should not
        # send the withdraw (as you can have chain announced and need to
        # cancel a announcement done a long time ago)
        # So to work correctly, you need to track sent changes (which costs)
        # And the yield makes it very cpu/memory intensive ..

        if _withdraw:
            change.nlri.action = OUT.WITHDRAW

        # always remove previous announcement if cancelled or replaced before being sent
        if change.nlri.action == OUT.WITHDRAW:
            prev_change = new_nlri.get(change_index, None)
            if prev_change:
                prev_change_index = prev_change.index()
                prev_change_attr_index = prev_change.attributes.index()
                attr_af_nlri.setdefault(prev_change_attr_index, {}).setdefault(change_family, RIBdict({})).pop(
                    prev_change_index, None
                )
            # then issue the normal withdrawal

        # add the route to the list to be announced/withdrawn
        attr_af_nlri.setdefault(change_attr_index, {}).setdefault(change_family, RIBdict({}))[change_index] = change
        new_nlri[change_index] = change
        new_attr[change_attr_index] = change.attributes
        self.update_cache(change)

    def updates(self, grouped):
        attr_af_nlri = self._new_attr_af_nlri
        new_attr = self._new_attribute

        # Get ready to accept more data
        self._new_nlri = {}
        self._new_attr_af_nlri = {}
        self._new_attribute = {}

        # if we need to perform a route-refresh, sending the message
        # to indicate the start of the announcements

        rr_announced = []

        for afi, safi in self._enhanced_refresh_start:
            rr_announced.append((afi, safi))
            yield Update(RouteRefresh(afi, safi, RouteRefresh.start), Attributes())

        # generating Updates from what is in the RIB

        for attr_index, per_family in attr_af_nlri.items():
            for family, changes in per_family.items():
                if not changes:
                    continue

                # only yield once we have a consistent state, otherwise it will go wrong
                # as we will try to modify things we are iterating over and using

                attributes = new_attr[attr_index]

                if family == (AFI.ipv4, SAFI.unicast) and grouped:
                    yield Update([change.nlri for change in changes.values()], attributes)
                else:
                    for change in changes.values():
                        yield Update([change.nlri,], attributes)

        # If we are performing a route-refresh, indicating that the
        # update were all sent

        if rr_announced:
            for afi, safi in rr_announced:
                self._enhanced_refresh_start.remove((afi, safi))
                yield Update(RouteRefresh(afi, safi, RouteRefresh.end), Attributes())

            for change in self._enhanced_refresh_delay:
                self.add_to_rib(change, True)
            self._enhanced_refresh_delay = []

            for update in self.updates(grouped):
                yield update
