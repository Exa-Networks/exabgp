#!/usr/bin/env python3

"""Non-interactive command execution for ExaBGP"""

from __future__ import annotations

import argparse
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


def open_reader(recv):
    def open_timeout(signum, frame):
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


def open_writer(send):
    def write_timeout(signum, frame):
        sys.stderr.write('could not send command to ExaBGP (command timeout)')
        sys.stderr.flush()
        sys.exit(1)

    signal.signal(signal.SIGALRM, write_timeout)
    signal.alarm(COMMAND_TIMEOUT)

    try:
        writer = os.open(send, os.O_WRONLY)
    except OSError as exc:
        if exc.errno == errno.ENXIO:
            sys.stdout.write('ExaBGP is not running / using the configured named pipe')
            sys.stdout.flush()
            sys.exit(1)
        sys.stdout.write('could not communicate with ExaBGP')
        sys.stdout.flush()
        sys.exit(1)
    except OSError as exc:
        sys.stdout.write(f'could not communicate with ExaBGP ({exc})')
        sys.stdout.flush()
        sys.exit(1)

    signal.alarm(0)
    return writer


def setargs(sub):
    # fmt:off
    sub.add_argument('--pipename', dest='pipename', help='Name of the pipe', required=False)
    transport_group = sub.add_mutually_exclusive_group()
    transport_group.add_argument('--pipe', dest='use_pipe', action='store_true', help='Use named pipe transport (default: Unix socket)')
    transport_group.add_argument('--socket', dest='use_socket', action='store_true', help='Use Unix socket transport (default)')
    sub.add_argument('--batch', dest='batch_file', metavar='FILE', help='Execute commands from file (or stdin if "-")')
    sub.add_argument('--no-color', dest='no_color', action='store_true', help='Disable colored output')
    sub.add_argument('command', nargs='*', help='command to run (omit for interactive mode)')
    # fmt:on


def send_command_socket(socket_path, command_str, return_output=False):
    """
    Send command via Unix socket and receive response.

    Args:
        socket_path: Path to Unix socket
        command_str: Command to send
        return_output: If True, return output as string instead of printing

    Returns:
        Output string if return_output=True, None otherwise
    """
    output_lines = []

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
                    # Connection closed by server
                    break

                buf += chunk
                while b'\n' in buf:
                    line, buf = buf.split(b'\n', 1)
                    string = line.decode()

                    if string == Answer.text_done or string == Answer.json_done:
                        done = True
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
        try:
            client.close()
        except OSError:
            pass

    if return_output:
        return '\n'.join(output_lines)


def main():
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__)
    setargs(parser)
    cmdline(parser.parse_args())


def cmdline(cmdarg):
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
        # For reset command, just exit (no response expected)
        if use_pipe_transport:
            pipes = named_pipe(ROOT, pipename)
            if len(pipes) == 1:
                send = pipes[0] + pipename + '.in'
                if check_fifo(send):
                    writer = open_writer(send)
                    try:
                        os.write(writer, sending.encode('utf-8') + b'\n')
                        os.close(writer)
                    except OSError:
                        pass
        else:
            sockets = unix_socket(ROOT, socketname)
            if len(sockets) == 1:
                socket_path = sockets[0] + socketname + '.sock'
                try:
                    client = sock.socket(sock.AF_UNIX, sock.SOCK_STREAM)
                    client.settimeout(COMMAND_TIMEOUT)
                    client.connect(socket_path)
                    client.sendall(sending.encode('utf-8') + b'\n')
                    client.close()
                except OSError:
                    pass
        sys.exit(0)

    # Route to appropriate transport
    if use_pipe_transport:
        # Use named pipe transport
        cmdline_pipe(pipename, sending)
    else:
        # Use Unix socket transport
        cmdline_socket(socketname, sending)


def cmdline_batch(batch_file, pipename, socketname, use_pipe_transport, cmdarg):
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

            # Execute via transport (don't exit on error, continue with next command)
            try:
                if use_pipe_transport:
                    cmdline_pipe(pipename, sending, exit_on_completion=False)
                else:
                    cmdline_socket(socketname, sending, exit_on_completion=False)
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


def cmdline_socket(socketname, sending, exit_on_completion=True):
    """Execute command via Unix socket transport."""
    sockets = unix_socket(ROOT, socketname)
    if len(sockets) != 1:
        sys.stdout.write(f"could not find ExaBGP's Unix socket ({socketname}.sock) for the cli\n")
        sys.stdout.write('we scanned the following folders (the number is your PID):\n - ')
        sys.stdout.write('\n - '.join(sockets))
        sys.stdout.flush()
        if exit_on_completion:
            sys.exit(1)
        else:
            raise RuntimeError('Socket not found')

    socket_path = sockets[0] + socketname + '.sock'

    # Check if socket exists and is actually a socket
    if not os.path.exists(socket_path):
        sys.stdout.write(f'could not find Unix socket to connect to ExaBGP: {socket_path}\n')
        sys.stdout.flush()
        if exit_on_completion:
            sys.exit(1)
        else:
            raise RuntimeError('Socket not found')

    send_command_socket(socket_path, sending, return_output=False)
    if exit_on_completion:
        sys.exit(0)


def cmdline_pipe(pipename, sending, exit_on_completion=True):
    """Execute command via named pipe transport."""
    pipes = named_pipe(ROOT, pipename)
    if len(pipes) != 1:
        sys.stdout.write(f"could not find ExaBGP's named pipes ({pipename}.in and {pipename}.out) for the cli\n")
        sys.stdout.write('we scanned the following folders (the number is your PID):\n - ')
        sys.stdout.write('\n - '.join(pipes))
        sys.stdout.flush()
        if exit_on_completion:
            sys.exit(1)
        else:
            raise RuntimeError('Pipe not found')

    send = pipes[0] + pipename + '.in'
    recv = pipes[0] + pipename + '.out'

    if not check_fifo(send):
        sys.stdout.write('could not find write named pipe to connect to ExaBGP')
        sys.stdout.flush()
        sys.exit(1)

    if not check_fifo(recv):
        sys.stdout.write('could not find read named pipe to connect to ExaBGP')
        sys.stdout.flush()
        sys.exit(1)

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
            sys.stdout.write(f'could not clear named pipe from potential previous command data ({exc!s})')
            sys.stdout.flush()
            sys.exit(1)
        except OSError as exc:
            if exc.errno in error.block:
                continue
            sys.stdout.write(f'could not clear named pipe from potential previous command data ({exc!s})')
            sys.stdout.write(str(exc))
            sys.stdout.flush()
            sys.exit(1)

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
        sys.stdout.write(f'could not send command to ExaBGP ({exc!s})')
        sys.stdout.flush()
        sys.exit(1)

    waited = 0.0
    buf = b''
    done = False
    done_time_diff = DONE_TIME_DIFF
    while not done:
        try:
            r, _, _ = select.select([reader], [], [], SELECT_TIMEOUT)
        except OSError as exc:
            if exc.errno in error.block:
                continue
            sys.stdout.write(f'could not get answer from ExaBGP ({exc!s})')
            sys.stdout.flush()
            sys.exit(1)
        except OSError as exc:
            if exc.errno in error.block:
                continue
            sys.stdout.write(f'could not get answer from ExaBGP ({exc!s})')
            sys.stdout.flush()
            sys.exit(1)

        if waited > COMMAND_RESPONSE_TIMEOUT:
            sys.stderr.write('\n')
            sys.stderr.write('warning: no end of command message received\n')
            sys.stderr.write(
                'warning: normal if exabgp.api.ack is set to false otherwise some data may get stuck on the pipe\n',
            )
            sys.stderr.write('warning: otherwise it may cause exabgp reactor to block\n')
            sys.exit(0)
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
            sys.stdout.write(f'could not read answer from ExaBGP ({exc!s})')
            sys.stdout.flush()
            sys.exit(1)
        except OSError as exc:
            if exc.errno in error.block:
                continue
            sys.stdout.write(f'could not read answer from ExaBGP ({exc!s})')
            sys.stdout.flush()
            sys.exit(1)

        buf += raw
        while b'\n' in buf:
            line, buf = buf.split(b'\n', 1)
            string = line.decode()
            if string == Answer.text_done or string == Answer.json_done:
                done = True
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
                done = True

    try:
        os.close(reader)
    except OSError:
        pass

    if exit_on_completion:
        sys.exit(0)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
