import sys
import argparse
import os

from vyos.xml import kw
from vyos.util import call
from vyos.util import popen

if sys.version_info[:3] < (3, 7):

    def breakpoint():
        import pdb

        pdb.set_trace()
        pass


def _nop(config, path):
    order = path[0]
    print(f'command {order} not implemented ({path})')


def _run(config, path):
    order, more = path.split(' ', 1) if ' ' in path else (path, '')

    command, ret = popen(f'which {order}')
    if ret == 0:
        if more:
            command += ' ' + more
        return call(command)

    command = f'/bin/vbash -c "source /opt/vyatta/etc/functions/script-template; _vyatta_op_run {path}"'
    ret = call(command)
    if ret != 0:
        print('failed')
        return False
    return True


def _debug(config, path):
    breakpoint()
    pass


def xml(config, path):
    config.xml.traverse(path)
    print()
    print(f'path  : {path}')
    print(f'inside: {config.xml.inside}')
    print()
    for key, value in config.xml.tree.items():
        if isinstance(value, dict) and not kw.found(key):
            print(f'{key}: ' + '{...}')
        else:
            print(f'{key}: {value}')


public = {
    'confirm': 'Confirm prior commit-confirm',
    'comment': 'Add comment to this configuration element',
    'commit': 'Commit the current set of changes',
    'commit-confirm': 'Commit the current set of changes with confirm required',
    'compare': 'Compare configuration revisions',
    'copy': 'Copy a configuration element',
    'delete': 'Delete a configuration element',
    'discard': 'Discard uncommitted changes',
    'edit': 'Edit a sub-element',
    'exit': 'Exit from this configuration level',
    'load': 'Load configuration from a file and replace running configuration',
    'loadkey': 'Load user SSH key from a file',
    'merge': 'Load configuration from a file and merge running configuration',
    'rename': 'Rename a configuration element',
    'rollback': 'Rollback to a prior config revision (requires reboot)',
    'run': 'Run an operational-mode command',
    'save': 'Save configuration to a file',
    'set': 'Set the value of a parameter or create a new element',
    'show': 'Show the configuration (default values may be suppressed)',
}


private = {
    'q': 'Exit from this configuration level',
    'xml': 'look into the xml tree',
    'commnands': 'show configuration commands',
    'commit-memory': 'commit change to memory',
}

_dispatch = {
    'confirm': _nop,
    'comment': _nop,
    'commit': lambda config, path: config.commit(),
    'commit-confirm': _nop,
    'memory': lambda config, path: config.commit(memory_only=True),
    'compare': _nop,
    'copy': _nop,
    'delete': lambda config, path: config.delete(path.split()),
    'discard': lambda config, path: config.discard(path.split()),
    'edit': lambda config, path: config.edit(path.split()),
    'exit': lambda config, path: sys.exit(),
    'load': lambda config, path: config.load_config(path),
    'loadkey': _nop,
    'merge': _nop,
    'rename': _nop,
    'rollback': _nop,
    'run': _run,
    'save': lambda config, path: config.save_config('/config/vyos.conf'),
    'set': lambda config, path: config.set(path.split()),
    'show': lambda config, path: print(config.show(path.split())),
    'debug': _debug,
    # private
    'q': lambda config, path: sys.exit(),
    'xml': lambda config, path: xml(config, path),
    'commands': lambda config, path: print(config.commands([])),
}


def run(config, cmd):
    while '  ' in cmd:
        cmd = cmd.replace('  ', ' ')
    order, more = cmd.split(' ', 1) if ' ' in cmd else (cmd, '')
    if order not in _dispatch:
        print(f'unimplemented command: {cmd}')
        return False
    return _dispatch[order](config, more)
