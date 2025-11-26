#!/usr/bin/env python3

from __future__ import annotations

import os
import sys
import socket
import getpass
import argparse

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

# from prompt_toolkit.completion import Completer
# from prompt_toolkit.completion import Completion
# from prompt_toolkit.validation import Validator
from prompt_toolkit.validation import ValidationError
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.key_binding import KeyBindings

# from prompt_toolkit import print_formatted_text
# from prompt_toolkit.formatted_text import to_formatted_text
# from prompt_toolkit import prompt

from exabgp.conf.yang.tree import Tree
from exabgp.cli.completer import VyOSCompleter  # type: ignore[attr-defined]
from exabgp.cli.validator import VyOSValidator
from exabgp.cli.command import run
from exabgp.cli import msg

from exabgp.conf import Config  # type: ignore[attr-defined]

corrections = {
    'neighbour': 'neighbor',
}


message = msg()

running = True


def main():
    parser = argparse.ArgumentParser(description='configure ExaBGP')
    parser.add_argument('--load', type=str, help='configuration file to load')
    parser.add_argument('--commit', action='store_true', help='commit the configuration on load')
    parser.add_argument('--show', action='store_true', help='show loaded configuration')
    parser.add_argument('--no-cli', action='store_true', help='do not start the cli')
    arg = parser.parse_args()

    # if True:
    #     init_modules()

    # if not (arg.load and arg.commit):
    #     airbag.enable()

    user = getpass.getuser()
    host = socket.gethostname()

    # boot mode, load config, apply it and exit
    config = Config(f'{user}@{host}')

    if arg.load:
        if not os.path.exists(arg.load):
            sys.exit(f'no configuration file: {arg.load}')
        sys.stdout.write(f'loading: {arg.load}\n')
        config.load_config(arg.load, verbose=arg.no_cli)

    if arg.show:
        sys.stdout.write(f'{config.show()}\n')
    if arg.load and arg.commit:
        sys.stdout.write('commiting\n')
        config.commit()
        sys.stdout.write('done.\n')
    if arg.no_cli:
        sys.exit(0)

    config.commit(memory_only=True)

    yang = Tree()
    completer = VyOSCompleter(yang, message)
    validator = VyOSValidator(yang, message)

    kb = KeyBindings()

    @kb.add('c-c', eager=True)
    def _(event):
        global running
        running = False
        event.app.exit()

    @kb.add('?')
    def _(event):
        b = event.app.current_buffer

        if b.complete_state:
            b.complete_next()
        else:
            b.start_completion(select_first=False)

        message[msg.command] = b.text
        event.app.exit()

    prompt_session = PromptSession(
        history=FileHistory('./myhistory'),
        # completer=FuzzyCompleter(completer),
        completer=completer,
        enable_history_search=True,
        complete_while_typing=True,
        complete_in_thread=True,
        auto_suggest=AutoSuggestFromHistory(),
        validator=validator,
        validate_while_typing=True,
        multiline=False,
        wrap_lines=True,
        enable_system_prompt=True,
        key_bindings=kb,
        mouse_support=False,
        vi_mode=True,
    )

    while running:
        level = ['edit'] + config.get_level()
        edit = ' '.join(level)
        sys.stdout.write(f'Python-cli [{edit}]\n')
        cmd = prompt_session.prompt(f'Python-cli {user}@{host}# ', default=message[msg.command])
        # '?' was pressed and we exited
        if not cmd:
            sys.stdout.write(f'{message[msg.help]}\n')
            continue

        if cmd.startswith('set '):
            yang.traverse(cmd[4:])
            if not yang.final:  # and xml.is_leaf(cmd[4:].split()):
                sys.stdout.write('command incomplete\n')
                message[msg.command] = cmd
                continue
            if yang.extra:
                sys.stdout.write('invalid extra data\n')
                continue

            # do not go any further if the last argument does not pass validation
            try:
                validator.validate_command(cmd)
            except ValidationError:
                msg.command = cmd
                continue

        run(config, cmd)
        message[msg.command] = ''
    sys.stdout.write('exit\n')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
    except EOFError:
        pass
