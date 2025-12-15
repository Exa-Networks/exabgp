#!/usr/bin/env python3
"""Migrate data: bytes -> data: Buffer in unpack methods.

This script safely migrates function signatures from using `bytes` to `Buffer`
for the `data` parameter in unpack methods, enabling zero-copy buffer operations.

Usage:
    # Dry run (shows what would change)
    python scripts/migrate_bytes_to_buffer.py --dry-run

    # Migrate specific files
    python scripts/migrate_bytes_to_buffer.py src/exabgp/bgp/message/open/capability/*.py

    # Migrate all files needing migration
    python scripts/migrate_bytes_to_buffer.py --all

    # Migrate by priority group
    python scripts/migrate_bytes_to_buffer.py --priority 1  # capabilities
    python scripts/migrate_bytes_to_buffer.py --priority 2  # communities
    python scripts/migrate_bytes_to_buffer.py --priority 3  # bgp-ls
    python scripts/migrate_bytes_to_buffer.py --priority 4  # sr/srv6
    python scripts/migrate_bytes_to_buffer.py --priority 5  # other
"""

import argparse
import re
import sys
from pathlib import Path

# Priority groups from the audit
PRIORITY_GROUPS: dict[int, list[str]] = {
    1: [  # Capabilities
        'src/exabgp/bgp/message/open/capability/capability.py',
        'src/exabgp/bgp/message/open/capability/mp.py',
        'src/exabgp/bgp/message/open/capability/addpath.py',
        'src/exabgp/bgp/message/open/capability/graceful.py',
        'src/exabgp/bgp/message/open/capability/asn4.py',
        'src/exabgp/bgp/message/open/capability/refresh.py',
        'src/exabgp/bgp/message/open/capability/extended.py',
        'src/exabgp/bgp/message/open/capability/nexthop.py',
        'src/exabgp/bgp/message/open/capability/hostname.py',
        'src/exabgp/bgp/message/open/capability/software.py',
        'src/exabgp/bgp/message/open/capability/ms.py',
        'src/exabgp/bgp/message/open/capability/operational.py',
        'src/exabgp/bgp/message/open/capability/unknown.py',
    ],
    2: [  # Communities
        'src/exabgp/bgp/message/update/attribute/community/initial/community.py',
        'src/exabgp/bgp/message/update/attribute/community/large/community.py',
        'src/exabgp/bgp/message/update/attribute/community/extended/community.py',
        'src/exabgp/bgp/message/update/attribute/community/extended/rt.py',
        'src/exabgp/bgp/message/update/attribute/community/extended/origin.py',
        'src/exabgp/bgp/message/update/attribute/community/extended/bandwidth.py',
        'src/exabgp/bgp/message/update/attribute/community/extended/traffic.py',
        'src/exabgp/bgp/message/update/attribute/community/extended/encapsulation.py',
        'src/exabgp/bgp/message/update/attribute/community/extended/l2info.py',
        'src/exabgp/bgp/message/update/attribute/community/extended/mac_mobility.py',
        'src/exabgp/bgp/message/update/attribute/community/extended/mup.py',
        'src/exabgp/bgp/message/update/attribute/community/extended/chso.py',
        'src/exabgp/bgp/message/update/attribute/community/extended/flowspec_scope.py',
    ],
    3: [  # BGP-LS
        'src/exabgp/bgp/message/update/nlri/bgpls/node.py',
        'src/exabgp/bgp/message/update/nlri/bgpls/link.py',
        'src/exabgp/bgp/message/update/nlri/bgpls/prefixv4.py',
        'src/exabgp/bgp/message/update/nlri/bgpls/prefixv6.py',
        'src/exabgp/bgp/message/update/nlri/bgpls/srv6sid.py',
        'src/exabgp/bgp/message/update/nlri/bgpls/tlvs/node.py',
        'src/exabgp/bgp/message/update/nlri/bgpls/tlvs/link.py',
        'src/exabgp/bgp/message/update/nlri/bgpls/tlvs/prefix.py',
        'src/exabgp/bgp/message/update/nlri/bgpls/tlvs/linkaddr.py',
        'src/exabgp/bgp/message/update/nlri/bgpls/tlvs/neighaddr.py',
        'src/exabgp/bgp/message/update/nlri/bgpls/tlvs/multitopology.py',
        'src/exabgp/bgp/message/update/nlri/bgpls/tlvs/ospfarea.py',
        'src/exabgp/bgp/message/update/nlri/bgpls/tlvs/ospfroute.py',
        'src/exabgp/bgp/message/update/nlri/bgpls/tlvs/sids.py',
        'src/exabgp/bgp/message/update/attribute/bgpls/linkstate.py',
        'src/exabgp/bgp/message/update/attribute/bgpls/node/name.py',
        'src/exabgp/bgp/message/update/attribute/bgpls/node/isisarea.py',
        'src/exabgp/bgp/message/update/attribute/bgpls/node/nodeopaque.py',
        'src/exabgp/bgp/message/update/attribute/bgpls/node/localrouterid.py',
        'src/exabgp/bgp/message/update/attribute/bgpls/node/srcap.py',
        'src/exabgp/bgp/message/update/attribute/bgpls/node/sralgo.py',
        'src/exabgp/bgp/message/update/attribute/bgpls/link/admingroup.py',
        'src/exabgp/bgp/message/update/attribute/bgpls/link/localremote.py',
        'src/exabgp/bgp/message/update/attribute/bgpls/link/igpmetric.py',
        'src/exabgp/bgp/message/update/attribute/bgpls/link/sharedrisklinkgroup.py',
        'src/exabgp/bgp/message/update/attribute/bgpls/link/opaque.py',
        'src/exabgp/bgp/message/update/attribute/bgpls/link/name.py',
        'src/exabgp/bgp/message/update/attribute/bgpls/link/mplsmask.py',
        'src/exabgp/bgp/message/update/attribute/bgpls/link/remoteasn.py',
        'src/exabgp/bgp/message/update/attribute/bgpls/link/bandwidth.py',
        'src/exabgp/bgp/message/update/attribute/bgpls/link/temetric.py',
        'src/exabgp/bgp/message/update/attribute/bgpls/link/protection.py',
        'src/exabgp/bgp/message/update/attribute/bgpls/link/adjsid.py',
        'src/exabgp/bgp/message/update/attribute/bgpls/link/lanadjsid.py',
        'src/exabgp/bgp/message/update/attribute/bgpls/link/peernodeasn.py',
        'src/exabgp/bgp/message/update/attribute/bgpls/link/peersid.py',
        'src/exabgp/bgp/message/update/attribute/bgpls/prefix/igpflags.py',
        'src/exabgp/bgp/message/update/attribute/bgpls/prefix/igproutetag.py',
        'src/exabgp/bgp/message/update/attribute/bgpls/prefix/igpextroutetag.py',
        'src/exabgp/bgp/message/update/attribute/bgpls/prefix/metric.py',
        'src/exabgp/bgp/message/update/attribute/bgpls/prefix/ospfforwardaddr.py',
        'src/exabgp/bgp/message/update/attribute/bgpls/prefix/opaque.py',
        'src/exabgp/bgp/message/update/attribute/bgpls/prefix/prefixsid.py',
    ],
    4: [  # SR/SRv6
        'src/exabgp/bgp/message/update/attribute/sr/prefixsid.py',
        'src/exabgp/bgp/message/update/attribute/sr/labelindex.py',
        'src/exabgp/bgp/message/update/attribute/sr/srgb.py',
        'src/exabgp/bgp/message/update/attribute/sr/srv6/generic.py',
        'src/exabgp/bgp/message/update/attribute/sr/srv6/sidinformation.py',
        'src/exabgp/bgp/message/update/attribute/sr/srv6/sidstructure.py',
        'src/exabgp/bgp/message/update/attribute/sr/srv6/l3service.py',
        'src/exabgp/bgp/message/update/attribute/sr/srv6/l2service.py',
    ],
    5: [  # Other
        'src/exabgp/bgp/message/update/nlri/mvpn/nlri.py',
        'src/exabgp/protocol/iso/__init__.py',
    ],
}

# Pattern to match function signatures with data: bytes
# Matches: data: bytes, data:bytes, data : bytes
DATA_BYTES_PATTERN = re.compile(r'\bdata\s*:\s*bytes\b')

# Pattern to match packed: bytes (parameters and storage)
# Matches: packed: bytes, _packed: bytes
PACKED_BYTES_PATTERN = re.compile(r'\b(packed|_packed)\s*:\s*bytes\b')

# Import line to add
BUFFER_IMPORT = 'from exabgp.util.types import Buffer'

# Pattern to check if Buffer is already imported
BUFFER_IMPORT_PATTERN = re.compile(r'from exabgp\.util\.types import .*\bBuffer\b')


def has_buffer_import(content: str) -> bool:
    """Check if the file already imports Buffer."""
    return bool(BUFFER_IMPORT_PATTERN.search(content))


def needs_migration(content: str) -> bool:
    """Check if the file has data: bytes or packed: bytes that needs migration."""
    return bool(DATA_BYTES_PATTERN.search(content) or PACKED_BYTES_PATTERN.search(content))


def find_import_insertion_point(lines: list[str]) -> int:
    """Find the best line to insert the Buffer import.

    Strategy:
    1. Look for existing exabgp imports and insert after last one
    2. Otherwise, insert after the last import from exabgp
    3. Otherwise, insert after the last from/import line
    4. Otherwise, insert after __future__ imports
    """
    last_exabgp_import = -1
    last_import = -1
    last_future = -1

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('from __future__'):
            last_future = i
        elif stripped.startswith('from exabgp.') or stripped.startswith('import exabgp.'):
            last_exabgp_import = i
        elif stripped.startswith('from ') or stripped.startswith('import '):
            last_import = i

    # Prefer inserting after existing exabgp imports
    if last_exabgp_import >= 0:
        return last_exabgp_import + 1
    # Otherwise after any imports
    if last_import >= 0:
        return last_import + 1
    # Otherwise after __future__
    if last_future >= 0:
        return last_future + 1
    # Fallback: after any docstring/comments at the top
    return 0


def add_buffer_import(content: str) -> str:
    """Add the Buffer import to the file if not present."""
    if has_buffer_import(content):
        return content

    lines = content.split('\n')
    insert_point = find_import_insertion_point(lines)

    # Check if we're inserting after an exabgp import - if so, keep it grouped
    if insert_point > 0:
        prev_line = lines[insert_point - 1].strip()
        if prev_line.startswith('from exabgp.') or prev_line.startswith('import exabgp.'):
            # Insert right after the previous exabgp import
            lines.insert(insert_point, BUFFER_IMPORT)
        else:
            # Add blank line before if not grouped with other exabgp imports
            lines.insert(insert_point, '')
            lines.insert(insert_point + 1, BUFFER_IMPORT)
    else:
        lines.insert(insert_point, BUFFER_IMPORT)

    return '\n'.join(lines)


def migrate_data_bytes(content: str) -> str:
    """Replace data: bytes with data: Buffer in function signatures."""
    return DATA_BYTES_PATTERN.sub('data: Buffer', content)


def migrate_packed_bytes(content: str) -> str:
    """Replace packed: bytes and _packed: bytes with Buffer versions."""
    return PACKED_BYTES_PATTERN.sub(r'\1: Buffer', content)


def migrate_file(filepath: Path, dry_run: bool = False) -> tuple[bool, int]:
    """Migrate a single file.

    Returns: (changed, count) - whether file was changed and number of replacements
    """
    content = filepath.read_text()

    if not needs_migration(content):
        return False, 0

    # Count replacements (both data: bytes and packed: bytes)
    data_count = len(DATA_BYTES_PATTERN.findall(content))
    packed_count = len(PACKED_BYTES_PATTERN.findall(content))
    count = data_count + packed_count

    # Perform migrations
    new_content = add_buffer_import(content)
    new_content = migrate_data_bytes(new_content)
    new_content = migrate_packed_bytes(new_content)

    if dry_run:
        return True, count

    filepath.write_text(new_content)
    return True, count


def get_files_for_priority(priority: int, base_path: Path) -> list[Path]:
    """Get files for a specific priority group."""
    if priority not in PRIORITY_GROUPS:
        return []
    return [base_path / f for f in PRIORITY_GROUPS[priority] if (base_path / f).exists()]


def find_all_files_needing_migration(base_path: Path) -> list[Path]:
    """Find all Python files that need migration."""
    files = []
    for py_file in base_path.rglob('*.py'):
        try:
            content = py_file.read_text()
            if needs_migration(content):
                files.append(py_file)
        except Exception:
            pass
    return sorted(files)


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Migrate data: bytes -> data: Buffer in unpack methods',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        'files',
        nargs='*',
        help='Specific files to migrate',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be changed without making changes',
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Migrate all files needing migration',
    )
    parser.add_argument(
        '--priority',
        type=int,
        choices=[1, 2, 3, 4, 5],
        help='Migrate files in a specific priority group',
    )
    parser.add_argument(
        '--list',
        action='store_true',
        dest='list_files',
        help='List files that need migration without changing them',
    )

    args = parser.parse_args()

    # Find the base path (repository root)
    script_path = Path(__file__).resolve()
    base_path = script_path.parent.parent  # scripts/ -> repo root

    # Determine which files to process
    files_to_process: list[Path] = []

    if args.list_files:
        files = find_all_files_needing_migration(base_path / 'src')
        print(f'Files needing migration ({len(files)}):')
        for f in files:
            content = f.read_text()
            data_count = len(DATA_BYTES_PATTERN.findall(content))
            packed_count = len(PACKED_BYTES_PATTERN.findall(content))
            count = data_count + packed_count
            print(f'  {f.relative_to(base_path)} ({count} occurrence{"s" if count > 1 else ""})')
        return 0

    if args.files:
        files_to_process = [Path(f) for f in args.files]
    elif args.all:
        files_to_process = find_all_files_needing_migration(base_path / 'src')
    elif args.priority:
        files_to_process = get_files_for_priority(args.priority, base_path)
    else:
        parser.print_help()
        return 1

    if not files_to_process:
        print('No files to process')
        return 0

    # Process files
    total_changed = 0
    total_replacements = 0

    mode = 'DRY RUN' if args.dry_run else 'Migrating'
    print(f'{mode}: {len(files_to_process)} file(s)')
    print()

    for filepath in files_to_process:
        if not filepath.exists():
            print(f'  SKIP (not found): {filepath}')
            continue

        changed, count = migrate_file(filepath, dry_run=args.dry_run)
        if changed:
            total_changed += 1
            total_replacements += count
            rel_path = filepath.relative_to(base_path) if filepath.is_relative_to(base_path) else filepath
            print(f'  {"Would change" if args.dry_run else "Changed"}: {rel_path} ({count} replacement{"s" if count > 1 else ""})')
        else:
            rel_path = filepath.relative_to(base_path) if filepath.is_relative_to(base_path) else filepath
            print(f'  Skip (no changes needed): {rel_path}')

    print()
    print(f'Summary: {total_changed} file(s) {"would be " if args.dry_run else ""}changed, {total_replacements} replacement{"s" if total_replacements != 1 else ""}')

    if args.dry_run and total_changed > 0:
        print()
        print('Run without --dry-run to apply changes')

    return 0


if __name__ == '__main__':
    sys.exit(main())
