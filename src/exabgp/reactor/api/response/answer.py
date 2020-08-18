class Answer:
    error = 'error'
    done = 'done'
    shutdown = 'shutdown'

    buffer_size = max(len(error), len(done), len(shutdown))
