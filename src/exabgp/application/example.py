"""Generate documented ExaBGP configuration example from schema.

This command outputs a complete, documented configuration example
with all available options and their metadata (type, default, range, etc.).

The output is generated from the schema definitions, not from a static file,
ensuring it's always up-to-date with the current codebase.

Usage:
    exabgp example                    # Output full example to stdout
    exabgp example > example.conf     # Save to file
    exabgp example neighbor           # Output specific section
"""

from __future__ import annotations

import argparse
import sys

from exabgp.configuration.example import generate_full_example, generate_neighbor_example


def setargs(sub: argparse.ArgumentParser) -> None:
    """Configure command-line arguments for the example command.

    Args:
        sub: ArgumentParser subparser to configure
    """
    sub.add_argument(
        'section',
        nargs='?',
        default=None,
        choices=[None, 'neighbor', 'full'],
        help='Specific section to generate (default: full)',
    )


def main() -> int:
    """Entry point when run as standalone script."""
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__)
    setargs(parser)
    return cmdline(parser.parse_args())


def cmdline(cmdarg: argparse.Namespace) -> int:
    """Execute the example command.

    Args:
        cmdarg: Parsed command-line arguments

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    section = cmdarg.section

    # Generate the appropriate section
    if section == 'neighbor':
        output = generate_neighbor_example()
    else:
        # Default: full example
        output = generate_full_example()

    # Output to stdout
    sys.stdout.write(output)
    if not output.endswith('\n'):
        sys.stdout.write('\n')
    sys.stdout.flush()

    return 0


if __name__ == '__main__':
    sys.exit(main())
