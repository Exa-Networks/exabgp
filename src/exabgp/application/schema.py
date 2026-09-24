"""Export ExaBGP configuration schema as JSON Schema.

This command outputs the configuration schema in JSON Schema format,
useful for IDE integration, validation tools, and documentation.

Usage:
    exabgp schema export              # Output full schema to stdout
    exabgp schema export --compact    # Minified JSON output
    exabgp schema export neighbor     # Export specific section
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys

from exabgp.configuration.schema import Container, SchemaElement, schema_to_json_schema


def setargs(sub: argparse.ArgumentParser) -> None:
    sub.add_argument(
        'action',
        nargs='?',
        default='export',
        choices=['export'],
        help='Action to perform (default: export)',
    )
    sub.add_argument(
        'section',
        nargs='?',
        default=None,
        help='Specific section to export (neighbor, process, template, etc.)',
    )
    sub.add_argument(
        '--compact',
        action='store_true',
        help='Output minified JSON (no indentation)',
    )


def _get_root_schema() -> Container:
    """Build the root configuration schema from all section schemas.

    Returns:
        Combined Container representing the full ExaBGP config schema.
    """
    from exabgp.configuration.neighbor import ParseNeighbor
    from exabgp.configuration.process import ParseProcess
    from exabgp.configuration.template import ParseTemplate
    from exabgp.configuration.capability import ParseCapability
    from exabgp.configuration.neighbor.family import ParseFamily
    from exabgp.configuration.static import ParseStatic
    from exabgp.configuration.flow import ParseFlow
    from exabgp.configuration.l2vpn import ParseL2VPN
    from exabgp.configuration.operational import ParseOperational
    from exabgp.configuration.role import ParseRole

    # Build root schema from section schemas
    children: dict[str, SchemaElement] = {}

    # Main sections with schemas
    schema = getattr(ParseNeighbor, 'schema', None)
    if schema:
        children['neighbor'] = schema

    schema = getattr(ParseProcess, 'schema', None)
    if schema:
        children['process'] = schema

    schema = getattr(ParseTemplate, 'schema', None)
    if schema:
        children['template'] = schema

    schema = getattr(ParseCapability, 'schema', None)
    if schema:
        children['capability'] = schema

    schema = getattr(ParseFamily, 'schema', None)
    if schema:
        children['family'] = schema

    schema = getattr(ParseStatic, 'schema', None)
    if schema:
        children['static'] = schema

    schema = getattr(ParseFlow, 'schema', None)
    if schema:
        children['flow'] = schema

    schema = getattr(ParseL2VPN, 'schema', None)
    if schema:
        children['l2vpn'] = schema

    schema = getattr(ParseOperational, 'schema', None)
    if schema:
        children['operational'] = schema

    children['role'] = ParseRole.schema

    return Container(
        description='ExaBGP configuration schema',
        children=children,
    )


# Where each configuration section's parser lives, as (module, class name).
#
# This was ten copies of the same try/import/assign/except ImportError: pass block, which
# is 91 lines saying one thing ten times and ten swallowed errors for check_exa_style to
# count. The data is the part which differs, so it is the only part written out.
SECTION_PARSERS: dict[str, tuple[str, str]] = {
    'neighbor': ('exabgp.configuration.neighbor', 'ParseNeighbor'),
    'process': ('exabgp.configuration.process', 'ParseProcess'),
    'template': ('exabgp.configuration.template', 'ParseTemplate'),
    'capability': ('exabgp.configuration.capability', 'ParseCapability'),
    'family': ('exabgp.configuration.neighbor.family', 'ParseFamily'),
    'static': ('exabgp.configuration.static', 'ParseStatic'),
    'flow': ('exabgp.configuration.flow', 'ParseFlow'),
    'l2vpn': ('exabgp.configuration.l2vpn', 'ParseL2VPN'),
    'operational': ('exabgp.configuration.operational', 'ParseOperational'),
    'role': ('exabgp.configuration.role', 'ParseRole'),
}


def _get_section_schema(section: str) -> Container | None:
    """Get schema for a specific section.

    Args:
        section: Section name (neighbor, process, template, etc.)

    Returns:
        Container schema for the section, or None if not found.
    """
    located = SECTION_PARSERS.get(section)
    if located is None:
        return None

    module_name, class_name = located
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        # Every section parser ships with exabgp, so an ImportError here means a partial or
        # vendored install rather than an optional dependency. The caller's None reads as
        # 'no such section', which would send the operator looking for a typo instead.
        sys.stderr.write(f'cannot load the schema of section {section}: {exc}\n')
        return None

    parser_class = getattr(module, class_name, None)
    if parser_class is None:
        return None

    schema = getattr(parser_class, 'schema', None)
    if isinstance(schema, Container):
        return schema

    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__)
    setargs(parser)
    return cmdline(parser.parse_args())


def cmdline(cmdarg: argparse.Namespace) -> int:
    action = cmdarg.action
    section = cmdarg.section
    compact = cmdarg.compact

    if action != 'export':
        sys.stderr.write(f'Unknown action: {action}\n')
        return 1

    # Get the schema to export
    if section:
        schema = _get_section_schema(section)
        if schema is None:
            sys.stderr.write(f'Unknown section: {section}\n')
            sys.stderr.write(
                'Available sections: neighbor, process, template, capability, family, static, flow, l2vpn, operational, role\n'
            )
            return 1
    else:
        schema = _get_root_schema()

    # Convert to JSON Schema
    json_schema = schema_to_json_schema(schema)

    # Add JSON Schema metadata
    json_schema['$schema'] = 'http://json-schema.org/draft-07/schema#'
    json_schema['$id'] = 'https://github.com/Exa-Networks/exabgp/schema/config.json'
    if section:
        json_schema['title'] = f'ExaBGP {section} configuration'
    else:
        json_schema['title'] = 'ExaBGP configuration'

    # Output
    if compact:
        output = json.dumps(json_schema, separators=(',', ':'))
    else:
        output = json.dumps(json_schema, indent=2)

    sys.stdout.write(output)
    sys.stdout.write('\n')
    sys.stdout.flush()

    return 0


if __name__ == '__main__':
    sys.exit(main())
