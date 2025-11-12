from __future__ import annotations

from typing import ClassVar, List


class msg(dict):
    command: ClassVar[str] = '[command]'
    help: ClassVar[str] = '[help]'
    validation: ClassVar[str] = '[validation]'

    _keys: ClassVar[List[str]] = [command, help, validation]

    def __init__(self) -> None:
        self[self.help] = ''
        self[self.command] = ''
        self[self.validation] = ''

    def __str__(self) -> str:
        return ' '.join(f'{k}:{self[k]}' for k in self._keys if self[k])
