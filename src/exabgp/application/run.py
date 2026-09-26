#!/usr/bin/env python3

"""Non-interactive command execution for ExaBGP"""

from __future__ import annotations

import argparse
import contextlib
import errno
import os
import select
import signal
import sys
import time

import socket as sock

from exabgp.application.pipe import check_fifo, named_pipe
from exabgp.application.shortcuts import CommandShortcuts
from exabgp.application.unixsocket import unix_socket
from exabgp.environment import ROOT, getenv
from exabgp.reactor.api.response.answer import Answer
from exabgp.reactor.network.error import error
from exabgp.util.errstr import errstr

# Timeout and buffer size constants
PIPE_OPEN_TIMEOUT = 5  # Seconds to wait for pipe open
COMMAND_TIMEOUT = 5  # Seconds to wait for command send
PIPE_CLEAR_TIMEOUT = 1.5  # Seconds to clear pipe before command
COMMAND_RESPONSE_TIMEOUT = 5.0  # Seconds to wait for command response
DONE_TIME_DIFF = 0.5  # Time difference for done detection
SELECT_TIMEOUT = 0.01  # Select timeout in seconds
SELECT_WAIT_INCREMENT = 0.01  # Wait increment per select iteration

errno_block = set(
    (
        errno.EINPROGRESS,
        errno.EALREADY,
        errno.EAGAIN,
        errno.EWOULDBLOCK,
        errno.EINTR,
        errno.EDEADLK,
        errno.EBUSY,
        errno.ENOBUFS,
        errno.ENOMEM,
    ),
)


class AnswerStream:
    text_done = f'\n{Answer.text_done}\n'
    text_error = f'\n{Answer.text_error}\n'
    text_shutdown = f'\n{Answer.text_error}\n'
    json_done = f'\n{Answer.json_done}\n'
    json_error = f'\n{Answer.json_error}\n'
    json_shutdown = f'\n{Answer.json_error}\n'
    buffer_size = Answer.buffer_size + 2


def open_reader(recv: str) -> int:
    def open_timeout(signum: int, frame: object) -> None:
        sys.stderr.write('could not connect to read response from ExaBGP\n')
        sys.stderr.flush()
        sys.exit(1)

    signal.signal(signal.SIGALRM, open_timeout)
    signal.alarm(PIPE_OPEN_TIMEOUT)

    done = False
    while not done:
        try:
            reader = os.open(recv, os.O_RDONLY | os.O_NONBLOCK)
            done = True
        except OSError as exc:
            if exc.args[0] in errno_block:
                signal.signal(signal.SIGALRM, open_timeout)
                signal.alarm(PIPE_OPEN_TIMEOUT)
                continue
            sys.stdout.write('could not read answer from ExaBGP')
            sys.stdout.flush()
            sys.exit(1)
    signal.alarm(0)
    return reader


def open_writer(send: str) -> int:
    def write_timeout(signum: int, frame: object) -> None:
        sys.stderr.write('could not send command to ExaBGP (command timeout)')
        sys.stderr.flush()
        sys.exit(1)

    signal.signal(signal.SIGALRM, write_timeout)
    signal.alarm(COMMAND_TIMEOUT)

    try:
        writer = os.open(send, os.O_WRONLY)
    except OSError as exc:
        # One handler, not two. Python takes the first clause which matches, so the second
        # `except OSError` below this was unreachable, and it was the one carrying the reason:
        # the reachable one printed 'could not communicate with ExaBGP' with the exception
        # discarded, so a pipe we may not open read exactly like one which had gone away.
        if exc.errno == errno.ENXIO:
            sys.stderr.write('ExaBGP is not running / using the configured named pipe\n')
            sys.stderr.flush()
            sys.exit(1)
        sys.stderr.write(f'could not communicate with ExaBGP ({exc})\n')
        sys.stderr.flush()
        sys.exit(1)

    signal.alarm(0)
    return writer


def setargs(sub: argparse.ArgumentParser) -> None:
    # fmt:off
    sub.add_argument('--pipename', dest='pipename', help='Name of the pipe', required=False)
    transport_group = sub.add_mutually_exclusive_group()
    transport_group.add_argument('--pipe', dest='use_pipe', action='store_true', help='Use named pipe transport (default: Unix socket)')
    transport_group.add_argument('--socket', dest='use_socket', action='store_true', help='Use Unix socket transport (default)')
    sub.add_argument('--batch', dest='batch_file', metavar='FILE', help='Execute commands from file (or stdin if "-")')
    sub.add_argument('--no-color', dest='no_color', action='store_true', help='Disable colored output')
    sub.add_argument('command', nargs='*', help='command to run (omit for interactive mode)')
    # fmt:on


def send_command_socket(socket_path: str, command_str: str, return_output: bool = False) -> str | bool:  # noqa: C901
    """Send one command over a Unix socket.

    Returns captured output when `return_output` is true; otherwise returns
    whether a completion marker confirmed success.
    """
    output_lines = []
    successful = False

    try:
        client = sock.socket(sock.AF_UNIX, sock.SOCK_STREAM)
        client.settimeout(COMMAND_TIMEOUT)
        client.connect(socket_path)
    except sock.error as exc:
        error_msg = ''
        if exc.errno == errno.ENOENT:
            error_msg = 'ExaBGP is not running / Unix socket not found\n'
        elif exc.errno == errno.ECONNREFUSED:
            error_msg = 'ExaBGP is not accepting connections on Unix socket\n'
        else:
            error_msg = f'could not connect to ExaBGP Unix socket ({exc})\n'

        if return_output:
            raise ConnectionError(error_msg.strip())
        else:
            sys.stdout.write(error_msg)
            sys.stdout.flush()
            sys.exit(1)

    try:
        # Send command
        client.sendall(command_str.encode('utf-8') + b'\n')

        # Receive response
        client.settimeout(COMMAND_RESPONSE_TIMEOUT)
        buf = b''
        done = False

        while not done:
            try:
                chunk = client.recv(4096)
                if not chunk:
                    # Closing before a completion marker is a failed command,
                    # including a partial unterminated response.
                    break

                buf += chunk
                while b'\n' in buf:
                    line, buf = buf.split(b'\n', 1)
                    string = line.decode()

                    if string == Answer.text_done or string == Answer.json_done:
                        done = True
                        successful = True
                        break
                    if string == Answer.text_shutdown or string == Answer.json_shutdown:
                        error_msg = 'ExaBGP is shutting down, command aborted\n'
                        if return_output:
                            raise RuntimeError(error_msg.strip())
                        else:
                            sys.stderr.write(error_msg)
                            sys.stderr.flush()
                        done = True
                        break
                    if string == Answer.text_error or string == Answer.json_error:
                        done = True
                        error_msg = "ExaBGP returns an error (see ExaBGP's logs for more information)\n"
                        if return_output:
                            raise RuntimeError(error_msg.strip())
                        else:
                            sys.stderr.write(error_msg)
                            sys.stderr.write('use help for a list of available commands\n')
                            sys.stderr.flush()
                        break

                    if return_output:
                        output_lines.append(string)
                    else:
                        sys.stdout.write(f'{string}\n')
                        sys.stdout.flush()

            except sock.timeout:
                warning_msg = '\nwarning: no end of command message received\nwarning: normal if exabgp.api.ack is set to false otherwise some data may get stuck\n'
                if return_output:
                    # Don't raise for timeout in interactive mode, just return what we got
                    pass
                else:
                    sys.stderr.write(warning_msg)
                    sys.stderr.flush()
                successful = not getenv().api.ack
                break
            except sock.error as exc:
                if exc.errno in errno_block:
                    continue
                error_msg = f'could not read response from ExaBGP ({exc})\n'
                if return_output:
                    raise IOError(error_msg.strip())
                else:
                    sys.stdout.write(error_msg)
                    sys.stdout.flush()
                    sys.exit(1)

    finally:
        # The answer is already read or already lost, and the caller is told which by the
        # return value below; a socket which will not close cleanly adds nothing to that.
        with contextlib.suppress(OSError):
            client.close()

    if return_output:
        if not successful:
            raise RuntimeError('connection closed before ExaBGP completed the command')
        return '\n'.join(output_lines)
    return successful


def main() -> None:
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__)
    setargs(parser)
    cmdline(parser.parse_args())


def _reset_over_pipe(sending: str, pipename: str) -> int:
    """Hand `reset` to the named pipe. Zero only if it was written."""
    pipes = named_pipe(ROOT, pipename)
    if len(pipes) != 1:
        found = 'none' if not pipes else f'{len(pipes)} candidates'
        sys.stderr.write(f'error: reset not sent, no single named pipe to send it to ({found})\n')
        return 1

    send = pipes[0] + pipename + '.in'
    if not check_fifo(send):
        sys.stderr.write(f'error: reset not sent, {send} is not a usable named pipe\n')
        return 1

    writer = open_writer(send)
    try:
        os.write(writer, sending.encode('utf-8') + b'\n')
    except OSError as exc:
        sys.stderr.write(f'error: reset not sent, could not write to {send} ({errstr(exc)})\n')
        return 1
    finally:
        # in a finally because the write failure path used to skip the close and leak the
        # descriptor for the remaining life of the call
        os.close(writer)
    return 0


def _reset_over_socket(sending: str, socketname: str) -> int:
    """Hand `reset` to the unix socket. Zero only if it was sent."""
    sockets = unix_socket(ROOT, socketname)
    if len(sockets) != 1:
        found = 'none' if not sockets else f'{len(sockets)} candidates'
        sys.stderr.write(f'error: reset not sent, no single socket to send it to ({found})\n')
        return 1

    socket_path = sockets[0] + socketname + '.sock'
    client = sock.socket(sock.AF_UNIX, sock.SOCK_STREAM)
    try:
        client.settimeout(COMMAND_TIMEOUT)
        client.connect(socket_path)
        client.sendall(sending.encode('utf-8') + b'\n')
    except OSError as exc:
        sys.stderr.write(f'error: reset not sent, could not reach {socket_path} ({errstr(exc)})\n')
        return 1
    finally:
        client.close()
    return 0


def _send_reset(sending: str, pipename: str, socketname: str, use_pipe_transport: bool) -> int:
    """The exit status `reset` should leave with."""
    if use_pipe_transport:
        return _reset_over_pipe(sending, pipename)
    return _reset_over_socket(sending, socketname)


def cmdline(cmdarg: argparse.Namespace) -> None:
    # Determine transport: command-line flag > environment variable > default (socket)
    # Priority: 1. Command-line flags, 2. Environment variable, 3. Default
    if hasattr(cmdarg, 'use_pipe') and cmdarg.use_pipe:
        use_pipe_transport = True
    elif hasattr(cmdarg, 'use_socket') and cmdarg.use_socket:
        use_pipe_transport = False
    else:
        # Check environment variable
        env_transport = os.environ.get('exabgp_cli_transport', '').lower()
        if env_transport == 'pipe':
            use_pipe_transport = True
        elif env_transport == 'socket':
            use_pipe_transport = False
        else:
            # Default to socket transport
            use_pipe_transport = False

    pipename = cmdarg.pipename if cmdarg.pipename else getenv().api.pipename
    socketname = getenv().api.socketname

    # Check for batch mode (batch_file should be a string)
    batch_file = getattr(cmdarg, 'batch_file', None)
    if batch_file and isinstance(batch_file, str):
        cmdline_batch(batch_file, pipename, socketname, use_pipe_transport, cmdarg)
        sys.exit(0)

    command = cmdarg.command

    # Require command for non-interactive run mode
    if command == []:
        sys.stderr.write('error: no command provided\n')
        sys.stderr.write('usage: exabgp run <command>\n')
        sys.stderr.write('       exabgp cli           (for interactive mode)\n')
        sys.stderr.write('       exabgp run --batch <file>\n')
        sys.stderr.flush()
        sys.exit(1)

    # Process command shortcuts/nicknames using shared module
    command_str = ' '.join(command)
    sending = CommandShortcuts.expand_shortcuts(command_str)

    # Show expanded command if shortcuts were used
    if sending != command_str:
        sys.stdout.write(f'command: {sending}\n')

    if sending == 'reset':
        # reset is the one command which expects no answer from the daemon, and that used
        # to be read as "nothing here can fail": every path below ended at the same
        # unconditional sys.exit(0), including the ones where no byte had left the process.
        # A script checking the status was told a reset had happened when there was no
        # socket, no fifo, no daemon listening, or a write which failed part way through.
        #
        # There is no acknowledgement to wait for, so zero here can only mean "the command
        # was handed to the transport". That is still worth distinguishing from "there was
        # no transport to hand it to".
        sys.exit(_send_reset(sending, pipename, socketname, use_pipe_transport))

    # Route to appropriate transport
    if use_pipe_transport:
        # Use named pipe transport
        cmdline_pipe(pipename, sending)
    else:
        # Use Unix socket transport
        cmdline_socket(socketname, sending)


def cmdline_batch(
    batch_file: str, pipename: str, socketname: str, use_pipe_transport: bool, cmdarg: argparse.Namespace
) -> None:
    """Execute commands from file or stdin."""
    # Read commands from file or stdin
    if batch_file == '-':
        # Read from stdin
        command_source = sys.stdin
        source_name = 'stdin'
    else:
        # Read from file
        if not os.path.exists(batch_file):
            sys.stderr.write(f'Batch file not found: {batch_file}\n')
            sys.exit(1)
        try:
            command_source = open(batch_file, 'r')
            source_name = batch_file
        except IOError as exc:
            sys.stderr.write(f'Could not open batch file: {exc}\n')
            sys.exit(1)

    sys.stdout.write(f'Executing commands from {source_name}...\n')
    sys.stdout.flush()

    # Process commands line by line
    line_num = 0
    errors = 0

    try:
        for line in command_source:
            line_num += 1
            command = line.strip()

            # Skip empty lines and comments
            if not command or command.startswith('#'):
                continue

            sys.stdout.write(f'\n[{line_num}] {command}\n')
            sys.stdout.flush()

            # Execute command - apply shortcut expansion using shared module
            sending = CommandShortcuts.expand_shortcuts(command)

            # Execute via transport and count a daemon-side refusal as an error.
            try:
                if use_pipe_transport:
                    successful = cmdline_pipe(pipename, sending, exit_on_completion=False)
                else:
                    successful = cmdline_socket(socketname, sending, exit_on_completion=False)
                if not successful:
                    errors += 1
            except Exception as exc:
                sys.stderr.write(f'Error executing command: {exc}\n')
                errors += 1

    finally:
        if batch_file != '-':
            command_source.close()

    # Summary
    sys.stdout.write(f'\nBatch execution complete: {line_num} commands, {errors} errors\n')
    sys.stdout.flush()

    if errors > 0:
        sys.exit(1)


def cmdline_socket(socketname: str, sending: str, exit_on_completion: bool = True) -> bool:
    """Execute command via Unix socket transport."""
    sockets = unix_socket(ROOT, socketname)
    if len(sockets) != 1:
        sys.stdout.write(f"could not find ExaBGP's Unix socket ({socketname}.sock) for the cli\n")
        sys.stdout.write('we scanned the following folders (the number is your PID):\n - ')
        sys.stdout.write('\n - '.join(sockets))
        sys.stdout.flush()
        if exit_on_completion:
            sys.exit(1)
        raise RuntimeError('Socket not found')

    socket_path = sockets[0] + socketname + '.sock'
    if not os.path.exists(socket_path):
        sys.stdout.write(f'could not find Unix socket to connect to ExaBGP: {socket_path}\n')
        sys.stdout.flush()
        if exit_on_completion:
            sys.exit(1)
        raise RuntimeError('Socket not found')

    successful = bool(send_command_socket(socket_path, sending, return_output=False))
    if exit_on_completion:
        sys.exit(0 if successful else 1)
    return successful


def cmdline_pipe(pipename: str, sending: str, exit_on_completion: bool = True) -> bool:
    """Execute command via named pipe transport."""
    pipes = named_pipe(ROOT, pipename)
    if len(pipes) != 1:
        sys.stdout.write(f"could not find ExaBGP's named pipes ({pipename}.in and {pipename}.out) for the cli\n")
        sys.stdout.write('we scanned the following folders (the number is your PID):\n - ')
        sys.stdout.write('\n - '.join(pipes))
        sys.stdout.flush()
        if exit_on_completion:
            sys.exit(1)
        raise RuntimeError('Pipe not found')

    send = pipes[0] + pipename + '.in'
    recv = pipes[0] + pipename + '.out'

    if not check_fifo(send):
        message = 'could not find write named pipe to connect to ExaBGP'
        sys.stderr.write(message + '\n')
        sys.stderr.flush()
        if exit_on_completion:
            sys.exit(1)
        raise RuntimeError(message)

    if not check_fifo(recv):
        message = 'could not find read named pipe to connect to ExaBGP'
        sys.stderr.write(message + '\n')
        sys.stderr.flush()
        if exit_on_completion:
            sys.exit(1)
        raise RuntimeError(message)

    reader = open_reader(recv)

    rbuffer = b''
    start = time.time()
    while True:
        try:
            while select.select([reader], [], [], 0) != ([], [], []):
                rbuffer += os.read(reader, 4096)
                rbuffer = rbuffer[-AnswerStream.buffer_size :]
        except OSError as exc:
            if exc.errno in error.block:
                continue
            message = f'could not clear named pipe from potential previous command data ({exc!s})'
            sys.stdout.write(message)
            sys.stdout.flush()
            if exit_on_completion:
                sys.exit(1)
            raise RuntimeError(message) from exc

        # we are not ack'ing the command and probably have read all there is
        if time.time() > start + PIPE_CLEAR_TIMEOUT:
            break

        # we read nothing, nothing to do
        if not rbuffer:
            break

        # we read some data but it is not ending by a new line (ie: not a command completion)
        if rbuffer[-1] != ord('\n'):
            continue

        if AnswerStream.text_done.endswith(rbuffer.decode()[-len(AnswerStream.text_done) :]):
            break
        if AnswerStream.text_error.endswith(rbuffer.decode()[-len(AnswerStream.text_error) :]):
            break
        if AnswerStream.text_shutdown.endswith(rbuffer.decode()[-len(AnswerStream.text_shutdown) :]):
            break

        if AnswerStream.json_done.endswith(rbuffer.decode()[-len(AnswerStream.json_done) :]):
            break
        if AnswerStream.json_error.endswith(rbuffer.decode()[-len(AnswerStream.json_error) :]):
            break
        if AnswerStream.json_shutdown.endswith(rbuffer.decode()[-len(AnswerStream.json_shutdown) :]):
            break

    writer = open_writer(send)
    try:
        os.write(writer, sending.encode('utf-8') + b'\n')
        os.close(writer)
    except OSError as exc:
        message = f'could not send command to ExaBGP ({exc!s})'
        sys.stdout.write(message)
        sys.stdout.flush()
        if exit_on_completion:
            sys.exit(1)
        raise RuntimeError(message) from exc

    waited = 0.0
    buf = b''
    done = False
    done_time_diff = DONE_TIME_DIFF
    successful = False
    while not done:
        try:
            r, _, _ = select.select([reader], [], [], SELECT_TIMEOUT)
        except OSError as exc:
            if exc.errno in error.block:
                continue
            message = f'could not get answer from ExaBGP ({exc!s})'
            sys.stdout.write(message)
            sys.stdout.flush()
            if exit_on_completion:
                sys.exit(1)
            raise RuntimeError(message) from exc

        if waited > COMMAND_RESPONSE_TIMEOUT:
            sys.stderr.write('\n')
            sys.stderr.write('warning: no end of command message received\n')
            sys.stderr.write(
                'warning: normal if exabgp.api.ack is set to false otherwise some data may get stuck on the pipe\n',
            )
            sys.stderr.write('warning: otherwise it may cause exabgp reactor to block\n')
            successful = not getenv().api.ack
            break
        elif not r:
            waited += SELECT_WAIT_INCREMENT
            continue
        else:
            waited = 0.0

        try:
            raw = os.read(reader, 4096)
        except OSError as exc:
            if exc.errno in error.block:
                continue
            message = f'could not read answer from ExaBGP ({exc!s})'
            sys.stdout.write(message)
            sys.stdout.flush()
            if exit_on_completion:
                sys.exit(1)
            raise RuntimeError(message) from exc

        buf += raw
        while b'\n' in buf:
            line, buf = buf.split(b'\n', 1)
            string = line.decode()
            if string == Answer.text_done or string == Answer.json_done:
                done = True
                successful = True
                break
            if string == Answer.text_shutdown or string == Answer.json_shutdown:
                sys.stderr.write('ExaBGP is shutting down, command aborted\n')
                sys.stderr.flush()
                done = True
                break
            if string == Answer.text_error or string == Answer.json_error:
                done = True
                sys.stderr.write("ExaBGP returns an error (see ExaBGP's logs for more information)\n")
                sys.stderr.write('use help for a list of available commands\n')
                sys.stderr.flush()
                break
            sys.stdout.write(f'{string}\n')
            sys.stdout.flush()

        if not getenv().api.ack and not raw.decode():
            this_moment = time.time()
            recv_epoch_time = os.path.getmtime(recv)
            time_diff = this_moment - recv_epoch_time
            if time_diff >= done_time_diff:
                successful = True
                done = True

    # Everything we came for has been read, and the process exits a few lines below.
    with contextlib.suppress(OSError):
        os.close(reader)

    if exit_on_completion:
        sys.exit(0 if successful else 1)
    return successful


if __name__ == '__main__':
    # Ctrl+C at the command line is the user asking for this to stop, so stopping without a
    # traceback is the answer rather than a swallowed error.
    with contextlib.suppress(KeyboardInterrupt):
        main()
