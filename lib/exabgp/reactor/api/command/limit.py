# encoding: utf-8
"""
command/limit.py

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import re


def extract_neighbors(command):
    """Return a list of neighbor definition : the neighbor definition is a list of string which are in the neighbor indexing string"""
    # This function returns a list and a string
    # The first list contains parsed neighbor to match against our defined peers
    # The string is the command to be run for those peers
    # The parsed neighbor is a list of the element making the neighbor string so each part can be checked against the neighbor name

    returned = []

    neiremain = command.split(' ', 1)
    if len(neiremain) == 1:
        return [], command

    neighbor, remaining = neiremain
    if neighbor != 'neighbor':
        return [], command

    ipcmd = remaining.split(' ', 1)
    if len(ipcmd) == 1:
        return [], remaining
    ip, command = ipcmd
    definition = ['neighbor %s' % (ip)]

    if ' ' not in command:
        return definition, command

    while True:
        try:
            key, value, remaining = command.split(' ', 2)
        except ValueError:
            # single word command
            keyval = command.split(' ', 1)
            if len(keyval) == 1:
                return definition, command
            key, value = keyval
        # we have further filtering
        if key == ',':
            returned.append(definition)
            _, command = command.split(' ', 1)
            definition = []
            continue
        if key not in ['neighbor', 'local-ip', 'local-as', 'peer-as', 'router-id', 'family-allowed']:
            if definition:
                returned.append(definition)
            break
        definition.append('%s %s' % (key, value))
        command = remaining

    return returned, command


def match_neighbor(description, name):
    for string in description:
        if re.search(r'(^|\s)%s($|\s|,)' % re.escape(string), name) is None:
            return False
    return True


def match_neighbors(peers, descriptions):
    """Return the sublist of peers matching the description passed, or None if no description is given"""
    if not descriptions:
        return peers

    returned = []
    for peer_name in peers:
        for description in descriptions:
            if match_neighbor(description, peer_name):
                if peer_name not in returned:
                    returned.append(peer_name)
    return returned
