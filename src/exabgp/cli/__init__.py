class msg(dict):
    command = '[command]'
    help = '[help]'
    validation = '[validation]'

    _keys = [command, help, validation]

    def __init__(self):
        self[self.help] = ''
        self[self.command] = ''
        self[self.validation] = ''

    def __str__(self):
        return ' '.join(f'{k}:{self[k]}' for k in self._keys if self[k])
