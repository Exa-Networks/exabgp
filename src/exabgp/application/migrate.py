"""Migrate ExaBGP configuration and API formats between versions.

Subcommands:
  conf  - Migrate configuration files
  api   - Migrate API commands/JSON (stdin/stdout bridge)

Examples:
  exabgp migrate conf -f 3.4 -t main config.conf
  echo '{"type":"update",...}' | exabgp migrate api -f 4 -t main
"""

from __future__ import annotations

import json
import re
import sys
import argparse
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from typing import Any


CONF_VERSIONS = ('3.4', '4', '5', 'main')
API_VERSIONS = ('4', '5', 'main')


@dataclass
class MigrationResult:
    """Result of a migration operation."""

    content: str
    changes: list[str]
    version_from: str
    version_to: str


# =============================================================================
# Configuration file migrations
# =============================================================================


def find_balanced_braces(text: str, start: int) -> int:
    """Find the position of the closing brace that balances the opening brace at start.

    Args:
        text: The text to search
        start: Position of the opening brace

    Returns:
        Position of the matching closing brace, or -1 if not found
    """
    if start >= len(text) or text[start] != '{':
        return -1

    depth = 0
    i = start
    while i < len(text):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def migrate_conf_3_4_to_4(content: str, verbose: bool = False) -> MigrationResult:
    """Migrate configuration from 3.4 to 4.x format.

    Changes:
    - Process reference: 'process <name>;' -> 'api { processes [ <name> ]; }'
    - Add 'encoder text;' to process blocks if missing
    - 'route-refresh;' -> 'route-refresh enable;'
    """
    changes: list[str] = []
    result = content

    # Find and update process blocks (handles nested braces)
    # Pattern: process <name> { ... }
    # Process names can contain hyphens, underscores, alphanumeric
    process_pattern = re.compile(r'process\s+([\w-]+)\s*\{')

    offset = 0
    for match in process_pattern.finditer(content):
        brace_start = match.end() - 1 + offset
        brace_end = find_balanced_braces(result, brace_start)

        if brace_end == -1:
            continue

        block_content = result[brace_start + 1 : brace_end]

        if 'encoder' not in block_content:
            # Insert encoder after opening brace, preserving indentation
            new_block = '{\n    encoder text;' + block_content
            result = result[:brace_start] + new_block + result[brace_end:]
            offset += len('{\n    encoder text;') - 1
            changes.append(f"Added 'encoder text;' to process '{match.group(1)}'")

    # Replace standalone 'process <name>;' inside neighbor blocks with api wrapper
    # Process names can contain hyphens, underscores, alphanumeric
    def wrap_process_ref(match: re.Match[str]) -> str:
        indent = match.group(1)
        name = match.group(2)
        changes.append(f"Wrapped 'process {name};' with api block")
        return f'{indent}api {{\n{indent}    processes [ {name} ];\n{indent}}}'

    result = re.sub(
        r'^(\s+)process\s+([\w-]+)\s*;\s*$',
        wrap_process_ref,
        result,
        flags=re.MULTILINE,
    )

    # route-refresh; -> route-refresh enable;
    if re.search(r'route-refresh\s*;', result):
        result = re.sub(r'route-refresh\s*;', 'route-refresh enable;', result)
        changes.append("Changed 'route-refresh;' to 'route-refresh enable;'")

    return MigrationResult(result, changes, '3.4', '4')


def migrate_conf_4_to_5(content: str, verbose: bool = False) -> MigrationResult:
    """Migrate configuration from 4.x to 5.x format.

    Changes:
    - 'route refresh' -> 'route-refresh' (hyphenation)
    - 'tcp.once true' -> 'tcp.attempts 1'
    - 'tcp.once false' -> 'tcp.attempts 0'
    - 'fragment not-a-fragment' -> 'fragment !is-fragment'
    - 'facility syslog' -> 'facility daemon'
    """
    changes: list[str] = []
    result = content

    if re.search(r'\broute\s+refresh\b', result):
        result = re.sub(r'\broute\s+refresh\b', 'route-refresh', result)
        changes.append("Changed 'route refresh' to 'route-refresh'")

    if re.search(r'tcp\.once\s+true', result, re.IGNORECASE):
        result = re.sub(r'tcp\.once\s+true', 'tcp.attempts 1', result, flags=re.IGNORECASE)
        changes.append("Changed 'tcp.once true' to 'tcp.attempts 1'")

    if re.search(r'tcp\.once\s+false', result, re.IGNORECASE):
        result = re.sub(r'tcp\.once\s+false', 'tcp.attempts 0', result, flags=re.IGNORECASE)
        changes.append("Changed 'tcp.once false' to 'tcp.attempts 0'")

    if 'not-a-fragment' in result:
        result = result.replace('not-a-fragment', '!is-fragment')
        changes.append("Changed 'not-a-fragment' to '!is-fragment'")

    if re.search(r'facility\s+syslog\b', result):
        result = re.sub(r'facility\s+syslog\b', 'facility daemon', result)
        changes.append("Changed 'facility syslog' to 'facility daemon'")

    return MigrationResult(result, changes, '4', '5')


def migrate_conf_5_to_main(content: str, verbose: bool = False) -> MigrationResult:
    """Migrate configuration from 5.x to main (6.0) format.

    Changes:
    - 'nlri-mpls' -> 'labeled-unicast' (optional, both work)
    """
    changes: list[str] = []
    result = content

    if re.search(r'\bnlri-mpls\b', result):
        result = re.sub(r'\bnlri-mpls\b', 'labeled-unicast', result)
        changes.append("Changed 'nlri-mpls' to 'labeled-unicast' (RFC 8277 terminology)")

    return MigrationResult(result, changes, '5', 'main')


def wrap_run_commands(content: str, from_version: str) -> tuple[str, list[str]]:
    """Wrap 'run' commands in process blocks with API migration wrapper.

    Transforms:
        run /path/to/script.py;
    Into:
        run exabgp migrate api -f <from_version> -t main --exec /path/to/script.py;

    Args:
        content: Configuration content
        from_version: Original API version (4 or 5)

    Returns:
        Tuple of (new_content, list_of_changes)
    """
    changes: list[str] = []

    # Map config version to API version
    api_version = '4' if from_version in ('3.4', '4') else '5'

    def replace_run(match: re.Match[str]) -> str:
        indent = match.group(1)
        command = match.group(2).strip()

        # Skip if already wrapped with migrate
        if 'exabgp migrate api' in command:
            return match.group(0)

        truncated = f'{command[:50]}...' if len(command) > 50 else command
        changes.append(f'Wrapped run command with API migration: {truncated}')
        return f'{indent}run exabgp migrate api -f {api_version} -t main --exec {command};'

    # Match: run <command>; within process blocks
    # This regex matches 'run' followed by anything until semicolon
    result = re.sub(
        r'^(\s+)run\s+(.+?);',
        replace_run,
        content,
        flags=re.MULTILINE,
    )

    return result, changes


def get_conf_migration_chain(from_version: str, to_version: str) -> list[tuple[str, str]]:
    """Get the chain of config migrations needed."""
    if from_version not in CONF_VERSIONS:
        raise ValueError(f'Unknown source version: {from_version}. Valid: {CONF_VERSIONS}')
    if to_version not in CONF_VERSIONS:
        raise ValueError(f'Unknown target version: {to_version}. Valid: {CONF_VERSIONS}')

    from_idx = CONF_VERSIONS.index(from_version)
    to_idx = CONF_VERSIONS.index(to_version)

    if from_idx >= to_idx:
        raise ValueError(f'Cannot migrate backwards from {from_version} to {to_version}')

    chain = []
    for i in range(from_idx, to_idx):
        chain.append((CONF_VERSIONS[i], CONF_VERSIONS[i + 1]))
    return chain


def migrate_conf(
    content: str, from_version: str, to_version: str, verbose: bool = False, wrap_api: bool = False
) -> MigrationResult:
    """Migrate config content through version chain.

    Args:
        content: Configuration file content
        from_version: Source version
        to_version: Target version
        verbose: Show migration steps
        wrap_api: Wrap 'run' commands with API migration bridge for scripts
    """
    migrations = {
        ('3.4', '4'): migrate_conf_3_4_to_4,
        ('4', '5'): migrate_conf_4_to_5,
        ('5', 'main'): migrate_conf_5_to_main,
    }

    chain = get_conf_migration_chain(from_version, to_version)
    all_changes: list[str] = []
    result = content

    for step_from, step_to in chain:
        if verbose:
            sys.stderr.write(f'Migrating config {step_from} -> {step_to}...\n')

        migrator = migrations[(step_from, step_to)]
        step_result = migrator(result, verbose)
        result = step_result.content
        all_changes.extend(step_result.changes)

    # Wrap run commands with API migration if requested and target is main
    if wrap_api and to_version == 'main':
        result, wrap_changes = wrap_run_commands(result, from_version)
        all_changes.extend(wrap_changes)

    return MigrationResult(result, all_changes, from_version, to_version)


# =============================================================================
# API/JSON migrations
# =============================================================================

# API v4 -> v6 command mappings (action-first -> target-first)
API_COMMAND_MIGRATIONS: dict[str, str] = {
    # Daemon commands
    'shutdown': 'daemon shutdown',
    'reload': 'daemon reload',
    'restart': 'daemon restart',
    'status': 'daemon status',
    # Session commands
    'enable-ack': 'session ack enable',
    'disable-ack': 'session ack disable',
    'ping': 'session ping',
    # Show commands -> rib/peer commands
    'show adj-rib in': 'rib show in',
    'show adj-rib out': 'rib show out',
    'show neighbor': 'peer show',
    'show neighbor summary': 'peer show summary',
    # Teardown
    'teardown': 'peer * teardown',
}

# JSON key renames across versions
# Format: (old_key, new_key, context_key or None for any context, version_step)
# context_key: only rename if this key exists in same dict or parent
# version_step: which version transition this applies to
JSON_KEY_MIGRATIONS: list[tuple[str, str, str | None, str]] = [
    # BGP-LS specific (4 -> 5)
    ('sr_capability_flags', 'sr-capability-flags', 'bgp-ls', '4->5'),
    ('interface-address', 'interface-addresses', 'bgp-ls', '4->5'),
    ('neighbor-address', 'neighbor-addresses', 'bgp-ls', '4->5'),
    # BGP-LS ip-reachability-tlv (5 -> main) - only in ip-reachability context
    ('ip', 'prefix', 'ip-reachability-tlv', '5->main'),
]


def migrate_api_command(command: str, from_version: str, to_version: str) -> tuple[str, list[str]]:
    """Migrate a single API command between versions.

    Returns (new_command, list_of_changes).
    """
    changes: list[str] = []
    result = command.strip()

    # Only apply command migrations when going to 'main' (v6 API)
    if to_version != 'main':
        return result, changes

    # Check for direct command mappings
    for old, new in API_COMMAND_MIGRATIONS.items():
        if result == old or result.startswith(old + ' '):
            suffix = result[len(old) :]
            result = new + suffix
            changes.append(f"Changed '{old}' to '{new}'")
            return result, changes

    # Handle announce/withdraw without peer prefix
    if result.startswith('announce ') and not result.startswith('peer '):
        result = 'peer * ' + result
        changes.append("Added 'peer *' prefix to announce command")
    elif result.startswith('withdraw ') and not result.startswith('peer '):
        result = 'peer * ' + result
        changes.append("Added 'peer *' prefix to withdraw command")

    # Handle neighbor <ip> commands -> peer <ip> commands
    match = re.match(r'^neighbor\s+(\S+)\s+(.+)$', result)
    if match:
        peer_ip = match.group(1)
        rest = match.group(2)
        result = f'peer {peer_ip} {rest}'
        changes.append(f"Changed 'neighbor {peer_ip}' to 'peer {peer_ip}'")

    return result, changes


def has_context_key(obj: dict[str, Any], context: str, parent_keys: list[str]) -> bool:
    """Check if context key exists in current dict or parent path."""
    # Check current dict keys
    for key in obj.keys():
        if context in str(key).lower():
            return True
    # Check parent path
    for key in parent_keys:
        if context in str(key).lower():
            return True
    return False


def _get_applicable_renames(
    from_version: str, to_version: str, reverse: bool = False
) -> list[tuple[str, str, str | None]]:
    """Get applicable key renames for a version transition.

    Args:
        from_version: Source version (script's expected format for reverse)
        to_version: Target version (ExaBGP's format for reverse)
        reverse: If True, swap old/new keys for reverse transformation

    Returns:
        List of (old_key, new_key, context) tuples

    For reverse migration (NEW -> OLD):
        from_version = script's expected (old) format
        to_version = ExaBGP's (new) format
        We apply migrations that cross the version boundaries between from and to.
    """
    applicable: list[tuple[str, str, str | None]] = []

    for old_key, new_key, context, version_step in JSON_KEY_MIGRATIONS:
        apply = False
        if version_step == '4->5':
            # Apply when crossing the 4->5 boundary
            # Forward: from_version is 4
            # Reverse: from_version is 4 (we need to get back to v4)
            apply = from_version == '4'
        elif version_step == '5->main':
            # Apply when crossing the 5->main boundary
            # Forward: to_version is main
            # Reverse: to_version is main (we're coming from main)
            apply = to_version == 'main'

        if apply:
            if reverse:
                applicable.append((new_key, old_key, context))  # Swap direction
            else:
                applicable.append((old_key, new_key, context))

    return applicable


def _transform_json(
    data: Any, renames: list[tuple[str, str, str | None]], changes: list[str], parent_keys: list[str]
) -> Any:
    """Recursively transform JSON data with key renames."""
    if isinstance(data, dict):
        new_dict: dict[str, Any] = {}
        for key, value in data.items():
            str_key = str(key)
            final_key = str_key

            for old, new, context in renames:
                if str_key == old:
                    if context is None or has_context_key(data, context, parent_keys):
                        final_key = new
                        changes.append(f"Renamed '{old}' to '{new}'")
                        break

            new_dict[final_key] = _transform_json(value, renames, changes, parent_keys + [str_key])
        return new_dict
    elif isinstance(data, list):
        return [_transform_json(item, renames, changes, parent_keys) for item in data]
    else:
        return data


def migrate_api_json(data: dict[str, Any], from_version: str, to_version: str) -> tuple[dict[str, Any], list[str]]:
    """Migrate JSON data between versions (forward: OLD -> NEW).

    Returns (new_data, list_of_changes).
    """
    changes: list[str] = []
    renames = _get_applicable_renames(from_version, to_version, reverse=False)
    return _transform_json(data, renames, changes, []), changes


def reverse_migrate_api_json(
    data: dict[str, Any], from_version: str, to_version: str
) -> tuple[dict[str, Any], list[str]]:
    """Reverse migrate JSON data between versions (reverse: NEW -> OLD).

    Used for stdin transformation in exec mode - transforms new ExaBGP JSON
    to old format that legacy scripts expect.

    Returns (new_data, list_of_changes).
    """
    changes: list[str] = []
    renames = _get_applicable_renames(from_version, to_version, reverse=True)
    return _transform_json(data, renames, changes, []), changes


def migrate_api_line(line: str, from_version: str, to_version: str, verbose: bool = False) -> tuple[str, list[str]]:
    """Migrate a single API line (command or JSON) forward: OLD -> NEW.

    Returns (new_line, list_of_changes).
    """
    line = line.strip()
    if not line:
        return line, []

    # Try to parse as JSON
    if line.startswith('{'):
        try:
            data = json.loads(line)
            new_data, changes = migrate_api_json(data, from_version, to_version)
            return json.dumps(new_data, separators=(',', ':')), changes
        except json.JSONDecodeError:
            pass  # Not valid JSON, treat as command

    # Treat as text command
    return migrate_api_command(line, from_version, to_version)


def reverse_migrate_api_line(
    line: str, from_version: str, to_version: str, verbose: bool = False
) -> tuple[str, list[str]]:
    """Reverse migrate a single API line (JSON only) reverse: NEW -> OLD.

    Used for stdin transformation - transforms new ExaBGP JSON events
    to old format that legacy scripts expect.

    Note: Only JSON is transformed. Text commands from ExaBGP to scripts
    are not common, so we pass them through unchanged.

    Returns (new_line, list_of_changes).
    """
    line = line.strip()
    if not line:
        return line, []

    # Try to parse as JSON
    if line.startswith('{'):
        try:
            data = json.loads(line)
            new_data, changes = reverse_migrate_api_json(data, from_version, to_version)
            return json.dumps(new_data, separators=(',', ':')), changes
        except json.JSONDecodeError:
            pass  # Not valid JSON, pass through

    # Pass through non-JSON (commands from ExaBGP to script are rare)
    return line, []


def migrate_api(content: str, from_version: str, to_version: str, verbose: bool = False) -> MigrationResult:
    """Migrate API content (commands or JSON) between versions."""
    if from_version not in API_VERSIONS:
        raise ValueError(f'Unknown API source version: {from_version}. Valid: {API_VERSIONS}')
    if to_version not in API_VERSIONS:
        raise ValueError(f'Unknown API target version: {to_version}. Valid: {API_VERSIONS}')

    from_idx = API_VERSIONS.index(from_version)
    to_idx = API_VERSIONS.index(to_version)

    if from_idx >= to_idx:
        raise ValueError(f'Cannot migrate backwards from {from_version} to {to_version}')

    all_changes: list[str] = []
    lines = content.splitlines()
    result_lines: list[str] = []

    for line in lines:
        new_line, changes = migrate_api_line(line, from_version, to_version, verbose)
        all_changes.extend(changes)
        result_lines.append(new_line)

    return MigrationResult('\n'.join(result_lines), all_changes, from_version, to_version)


# =============================================================================
# CLI interface
# =============================================================================


def setargs_conf(sub: argparse.ArgumentParser) -> None:
    """Define CLI arguments for conf subcommand."""
    sub.add_argument('config', help='configuration file to migrate', type=str)
    sub.add_argument(
        '-f', '--from', dest='from_version', required=True, choices=CONF_VERSIONS[:-1], help='source version'
    )
    sub.add_argument('-t', '--to', dest='to_version', required=True, choices=CONF_VERSIONS[1:], help='target version')
    sub.add_argument('-o', '--output', help='output file (default: stdout)', type=str)
    sub.add_argument('-i', '--inplace', action='store_true', help='modify file in place (creates timestamped backup)')
    sub.add_argument('-n', '--dry-run', action='store_true', dest='dry_run', help='show changes without applying')
    sub.add_argument('-v', '--verbose', action='store_true', help='show each transformation applied')
    sub.add_argument(
        '-w', '--wrap-api', action='store_true', dest='wrap_api', help='wrap run commands with API migration bridge'
    )


def setargs_api(sub: argparse.ArgumentParser) -> None:
    """Define CLI arguments for api subcommand."""
    sub.add_argument(
        '-f', '--from', dest='from_version', required=True, choices=API_VERSIONS[:-1], help='source API version'
    )
    sub.add_argument(
        '-t', '--to', dest='to_version', required=True, choices=API_VERSIONS[1:], help='target API version'
    )
    sub.add_argument('-v', '--verbose', action='store_true', help='show each transformation applied')
    sub.add_argument(
        '-e',
        '--exec',
        dest='exec_cmd',
        nargs=argparse.REMAINDER,
        help='execute command and transform its output (use as: --exec /path/to/script args...)',
    )
    sub.add_argument('input', nargs='?', help='input (default: stdin)', type=str)


def cmdline_conf(cmdarg: argparse.Namespace) -> int:
    """Handle conf subcommand."""
    config_path = Path(cmdarg.config)

    if not config_path.exists():
        sys.stderr.write(f'Error: file not found: {cmdarg.config}\n')
        return 1

    try:
        content = config_path.read_text()
    except Exception as e:
        sys.stderr.write(f'Error reading file: {e}\n')
        return 1

    try:
        result = migrate_conf(content, cmdarg.from_version, cmdarg.to_version, cmdarg.verbose, cmdarg.wrap_api)
    except ValueError as e:
        sys.stderr.write(f'Error: {e}\n')
        return 1

    if cmdarg.dry_run:
        sys.stdout.write(f'Migration: {result.version_from} -> {result.version_to}\n')
        if result.changes:
            sys.stdout.write(f'Changes ({len(result.changes)}):\n')
            for change in result.changes:
                sys.stdout.write(f'  - {change}\n')
        else:
            sys.stdout.write('No changes needed.\n')
        return 0

    if cmdarg.verbose and result.changes:
        sys.stderr.write(f'Applied {len(result.changes)} changes:\n')
        for change in result.changes:
            sys.stderr.write(f'  - {change}\n')

    if cmdarg.inplace:
        # Timestamped backup to avoid overwriting previous backups
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        backup_path = config_path.with_suffix(f'{config_path.suffix}.{timestamp}.bak')
        backup_path.write_text(content)
        config_path.write_text(result.content)
        sys.stderr.write(f'Migrated {cmdarg.config} (backup: {backup_path})\n')
    elif cmdarg.output:
        output_path = Path(cmdarg.output)
        output_path.write_text(result.content)
        sys.stderr.write(f'Migrated config written to {cmdarg.output}\n')
    else:
        sys.stdout.write(result.content)

    return 0


def cmdline_api(cmdarg: argparse.Namespace) -> int:
    """Handle api subcommand - acts as a bridge for API commands/JSON.

    Supports three modes:
    1. Direct input: exabgp migrate api -f 4 -t main "command"
    2. Stdin pipe: echo "command" | exabgp migrate api -f 4 -t main
    3. Exec mode: exabgp migrate api -f 4 -t main --exec /path/to/script.py
       In exec mode, bidirectional transformation is performed:
       - stdin (ExaBGP -> script): NEW JSON -> OLD JSON (reverse transform)
       - stdout (script -> ExaBGP): OLD commands -> NEW commands (forward transform)
    """
    import subprocess
    import threading

    # Exec mode: run command with bidirectional transformation
    if cmdarg.exec_cmd:
        try:
            proc = subprocess.Popen(
                cmdarg.exec_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=sys.stderr,
                text=True,
                bufsize=1,  # Line buffered
            )
        except FileNotFoundError:
            sys.stderr.write(f'Error: command not found: {cmdarg.exec_cmd[0]}\n')
            return 1
        except PermissionError:
            sys.stderr.write(f'Error: permission denied: {cmdarg.exec_cmd[0]}\n')
            return 1

        # Thread to handle stdin: read from sys.stdin, reverse transform, write to proc.stdin
        def stdin_handler() -> None:
            assert proc.stdin is not None
            try:
                for line in sys.stdin:
                    # Reverse transform: NEW ExaBGP JSON -> OLD format for script
                    new_line, _ = reverse_migrate_api_line(line, cmdarg.from_version, cmdarg.to_version, cmdarg.verbose)
                    proc.stdin.write(new_line)
                    if not new_line.endswith('\n'):
                        proc.stdin.write('\n')
                    proc.stdin.flush()
            except (BrokenPipeError, OSError):
                pass  # Process exited
            finally:
                try:
                    proc.stdin.close()
                except (BrokenPipeError, OSError):
                    pass

        stdin_thread = threading.Thread(target=stdin_handler, daemon=True)
        stdin_thread.start()

        # Main thread: read from proc.stdout, forward transform, write to sys.stdout
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                # Forward transform: OLD script commands -> NEW format for ExaBGP
                new_line, _ = migrate_api_line(line, cmdarg.from_version, cmdarg.to_version, cmdarg.verbose)
                sys.stdout.write(new_line)
                if not new_line.endswith('\n'):
                    sys.stdout.write('\n')
                sys.stdout.flush()
        except KeyboardInterrupt:
            proc.terminate()
            return 130

        proc.wait()
        stdin_thread.join(timeout=1.0)
        return proc.returncode or 0

    # Read from stdin or argument
    if cmdarg.input:
        content = cmdarg.input
    elif sys.stdin.isatty():
        sys.stderr.write('Usage: exabgp migrate api -f <version> -t <version> [input]\n')
        sys.stderr.write('       or pipe input via stdin\n')
        sys.stderr.write('       or use --exec /path/to/script to wrap a command\n')
        return 1
    else:
        content = sys.stdin.read()

    try:
        result = migrate_api(content, cmdarg.from_version, cmdarg.to_version, cmdarg.verbose)
    except ValueError as e:
        sys.stderr.write(f'Error: {e}\n')
        return 1

    if cmdarg.verbose and result.changes:
        sys.stderr.write(f'Applied {len(result.changes)} changes:\n')
        for change in result.changes:
            sys.stderr.write(f'  - {change}\n')

    sys.stdout.write(result.content)
    if not result.content.endswith('\n'):
        sys.stdout.write('\n')
    sys.stdout.flush()

    return 0


def setargs(sub: argparse.ArgumentParser) -> None:
    """Define CLI arguments - creates subparsers for conf and api."""
    subparsers = sub.add_subparsers(dest='migrate_command')

    conf_parser = subparsers.add_parser('conf', help='migrate configuration files')
    setargs_conf(conf_parser)
    conf_parser.set_defaults(func=cmdline_conf)

    api_parser = subparsers.add_parser('api', help='migrate API commands/JSON (stdin/stdout bridge)')
    setargs_api(api_parser)
    api_parser.set_defaults(func=cmdline_api)


def cmdline(cmdarg: argparse.Namespace) -> int:
    """Main command handler."""
    if not hasattr(cmdarg, 'func') or cmdarg.func is None:
        sys.stderr.write('Usage: exabgp migrate {conf|api} [options]\n')
        sys.stderr.write('  conf  - migrate configuration files\n')
        sys.stderr.write('  api   - migrate API commands/JSON\n')
        return 1
    result: int = cmdarg.func(cmdarg)
    return result


def main() -> int:
    """Standalone entry point."""
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__)
    setargs(parser)
    return cmdline(parser.parse_args())


if __name__ == '__main__':
    try:
        code = main()
        sys.exit(code)
    except BrokenPipeError:
        sys.exit(1)
