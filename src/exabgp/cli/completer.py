import os

from prompt_toolkit.completion import Completer
from prompt_toolkit.completion import Completion

from vyos import util
from vyos.ifconfig.section import Section

from vyos.xml import kw
from vyos.cli import command
from vyos.cli import msg

DEBUG = False

TAB = '     '

# TODO ..
paths = {
    'vyos_completion_dir' : os.environ.get('vyos_completion_dir', './src/conf_mode')
}


class VyOSCompleter(Completer):
    # debug
    counter = 0

    def __init__(self, xml, message):
        self.xml = xml
        self.ignore_case = True
        self.message = message

    def get_completions(self, document, complete_event):
        cmd = document.text.lstrip()
        while '  ' in cmd:
            cmd = cmd.replace('  ', ' ')

        yield from self._completions(cmd)

    def _completions(self, cmd):
        # update the buffers as we may have added ' '
        self.message[msg.command] = cmd

        order = cmd.split(' ')[0]

        # provide the root cmd completion
        if order not in command.public or ' ' not in cmd:
            yield from self._root_complete(cmd)
            self.root_help(cmd)
            return

        # provide completion for set
        if order == 'set':
            yield from self._set_complete(cmd)
            self.edit_help()
            return

        # provide completion for set
        if order == 'delete':
            yield from self._delete_complete(cmd)
            self.edit_help()
            return

    # DEBUG

    def _debug(self):
        if not DEBUG:
            return
        self.counter += 1
        for data in (
            ('debug', f'counter: {self.counter}', ''),
            ('debug', f'inside: {self.xml.inside}', ''),
            ('debug', f'node: {self.xml.tree.get(kw.node,"not a node")}', ''),
            ('debug', f'check: {self.xml.check}', ''),
            ('debug', f'typing: {self.xml.filling}', ''),
            ('debug', f'options: {self.xml.options}', ''),
            ('debug', f'last: {self.xml.word}', ''),
        ):
            yield data

    # ROOT

    def _root_complete(self, cmd):
        # we have a perfect match, look ahead to the next word
        matches = [order for order in command.public if order.startswith(cmd)]
        if len(matches) == 1:
            if matches[0] == cmd:
                yield Completion(' ')
                return
            yield Completion(matches[0][len(cmd):])
            return

        for option in command.public.keys():
            if option.startswith(cmd):
                yield Completion(option + ' ', -len(cmd))

    def root_help(self, cmd):
        r = self.format(self._root_help(cmd))
        self.message[msg.help] = r
        return r

    def _root_help(self, cmd):
        yield ('', '', 'Possible completions:')
        word = cmd.strip()
        for k, v in command.public.items():
            if k.startswith(word):
                yield (k, v, '')

    def _completions_options(self, word, options):
        if word in options:
            yield Completion(' ')
            return

        for option in options:
            if option.startswith(word):
                # yield Completion(option[len(words[-1]):])
                yield Completion(option[len(word):])
            elif not word:
                yield Completion(option)

    # SET
    def _set_complete(self, cmd):
        yield from self._search_complete(cmd)

    # DELETE
    def _delete_complete(self, cmd):
        # TODO: this should only show what exists
        yield from self._search_complete(cmd)

    def _search_complete(self, cmd):
        if cmd.startswith('set'):
            cmd = cmd[3:].lstrip()
        self.xml.traverse(cmd)

        # we have found a known word, let move to the next
        if not self.xml.filling and not cmd.endswith(' '):
            yield Completion(' ')
            return

        # only one incomplete answer possible, we complete it
        if len(self.xml.options) == 1:
            yield Completion(self.xml.options[0][len(self.xml.word):])
            return

        # XXX: This should not be hardcoded !

        # using split(' ') intead of split() to not eats the final ' '
        words = cmd.split(' ')
        # hardcoded search for words
        if len(words) == 3 and words[0] == 'interfaces' and words[1] in Section.sections():
            word = words[2] if len(words) == 3 else ''

            options = []
            prefixes = Section.interface_prefixes(words[1])
            interfaces = util.cmd('/usr/libexec/vyos/completion/list_interfaces.py').split()
            for ifname in interfaces:
                for prefix in prefixes:
                    if ifname.startswith(prefix):
                        options.append(ifname)

            yield from self._completions_options(word, options)
            return

        # completion options

        if kw.completion in self.xml.tree:
            completion_dir = os.environ.get('vyos_completion_dir','/usr/libexec/vyos/completion/')
            completion = self.xml.tree[kw.completion]
            if kw.script in completion:
                script = completion[kw.script].replace('${vyos_completion_dir}', completion_dir)
                options = cmd(script).split()
            elif kw.list in completion:
                # XXX: untested
                options = completion[kw.list]
            elif kw.path in completion:
                # XXX: untested
                path = completion[kw.path]
                self.xml.traverse(path)
                if self.xml.inside != path.split():
                    return
                options = [option for option in self.xml.tree.keys() if not kw.found(option)]

            yield from self._completions_options(words[-1], options)
            return

        # tab mid-word
        options = [option for option in self.xml.options if not kw.found(option)]
        yield from self._completions_options(words[-1], options)

    def format(self, generator):
        r = ''
        for option in generator:
            if not DEBUG:
                if option[0] in ('enter', 'skip', 'debug'):
                    continue
            if option[2]:
                r += f'{option[0]} {option[1]} {option[2]}\n'
            else:
                r += f'{TAB}{option[0]:<23} {option[1]} {option[2]}\n'
        return r

    def edit_help(self):
        r = self.format(self._debug())
        r += self.format(self.xml.listing())
        r += self.format(self.xml.summary())
        self.xml.speculate()
        r += self.format(self.xml.constraint())

        self.message[msg.help] = r
        return r
