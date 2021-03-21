import re
from copy import deepcopy

from prompt_toolkit.validation import ThreadedValidator as Validator

# from prompt_toolkit.validation import Validator
from prompt_toolkit.validation import ValidationError
from prompt_toolkit.document import Document

from vyos.modules import validation
from vyos.cli import msg
from vyos.xml import kw


def _unquote(value):
    if not value:
        return value
    if value.startswith("'"):
        value = value[1:]
    if value.endswith("'"):
        value = value[:-1]
    return value


class VyOSValidator(Validator):
    def __init__(self, xml, message):
        self.xml = xml
        self.regex = {}
        self.command = ''
        self.message = message

    def invalid(self, cmd, reason, data):
        cmd = self.command + cmd
        self.message[msg.validation] = (data, reason)
        end = len(cmd)
        raise ValidationError(message=reason, cursor_position=end)

    def validate(self, document):
        self.message[msg.validation] = ()
        self.validate_command(document.text)

    def validate_command(self, cmd):
        order = cmd.split(' ')[0]

        # provide completion for set
        if order == 'set':
            self.command = 'set '
            self._validate_set(cmd[3:].lstrip())

    def _validate_set(self, cmd):
        for data, constraint in self.xml.checks(cmd):
            if not data:
                continue

            if constraint is None:
                self.invalid(cmd, f'invalid keyword "{data}"', data)

            data = _unquote(data)

            # we are making a deepcopy to be able to pop()
            # and notice if we have some new/un-implemented
            # tests we need to deal implement
            constraint = deepcopy(constraint)
            reports = []

            while constraint:
                if kw.regex in constraint:
                    regexes = constraint.pop(kw.regex)
                    for regex in regexes:
                        # caching regex creation
                        if regex not in self.regex.values():
                            self.regex[regex] = re.compile(regex)
                            reports.append(f'failed regex {regex}')
                        if self.regex[regex].match(data):
                            reports = []
                            constraint = []
                            break
                elif kw.validator in constraint:
                    namedvalidators = constraint.pop(kw.validator)
                    for validator in namedvalidators:
                        name = validator[kw.name]
                        argument = validator.get(kw.argument, '')
                        if not validation.has(name):
                            raise ValidationError(message=f'Not implemented: {name}', cursor_position=0)
                        reports.append(f'failed validator {name}')
                        if validation.validate(name, argument, data):
                            reports = []
                            constraint = []
                            break
                else:
                    raise ValidationError(message=f'Not implemented: {name}', cursor_position=0)

            if reports:
                # we do not break, data is invalid
                self.invalid(cmd, f'"{data}" ' + ', '.join(reports), data)
