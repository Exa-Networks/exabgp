from __future__ import annotations

from typing import ClassVar

# module constants, so the sizes below are computed from names mypyc can read: a compiled
# class body does not see the attributes defined above it in the same body
_TEXT_ERROR = 'error'
_JSON_ERROR = '{ "answer": "error", "message": "this command does not support json output" }'
_TEXT_DONE = 'done'
_JSON_DONE = '{ "answer": "done", "message": "command completed" }'
_TEXT_SHUTDOWN = 'shutdown'
_JSON_SHUTDOWN = '{ "answer": "shutdown", "message": "exbgp exited" }'

_TEXT_BUFFER_SIZE = max(len(_TEXT_ERROR), len(_TEXT_DONE), len(_TEXT_SHUTDOWN))
_JSON_BUFFER_SIZE = max(len(_JSON_ERROR), len(_JSON_DONE), len(_JSON_SHUTDOWN))


class Answer:
    text_error: ClassVar[str] = _TEXT_ERROR
    json_error: ClassVar[str] = _JSON_ERROR
    text_done: ClassVar[str] = _TEXT_DONE
    json_done: ClassVar[str] = _JSON_DONE
    text_shutdown: ClassVar[str] = _TEXT_SHUTDOWN
    json_shutdown: ClassVar[str] = _JSON_SHUTDOWN

    text_buffer_size: ClassVar[int] = _TEXT_BUFFER_SIZE
    json_buffer_size: ClassVar[int] = _JSON_BUFFER_SIZE
    buffer_size: ClassVar[int] = max(_TEXT_BUFFER_SIZE, _JSON_BUFFER_SIZE)
