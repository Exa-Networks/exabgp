from __future__ import annotations


class Answer:
    text_error = 'error'
    json_error = '{ "answer": "error", "message": "this command does not support json output" }'
    text_done = 'done'
    json_done = '{ "answer": "done", "message": "command completed" }'
    text_shutdown = 'shutdown'
    json_shutdown = '{ "answer": "shutdown", "message": "exbgp exited" }'

    text_buffer_size = max(len(text_error), len(text_done), len(text_shutdown))
    json_buffer_size = max(len(json_error), len(json_done), len(json_shutdown))
    buffer_size = max(text_buffer_size, json_buffer_size)
