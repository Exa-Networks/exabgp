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

    return Container(
        description='ExaBGP configuration schema',
        children=children,
    )


def _get_section_schema(section: str) -> Container | None:
    """Get schema for a specific section.

    Args:
        section: Section name (neighbor, process, template, etc.)

    Returns:
        Container schema for the section, or None if not found.
    """
    section_map: dict[str, type] = {}

    try:
        from exabgp.configuration.neighbor import ParseNeighbor

        section_map['neighbor'] = ParseNeighbor
    except ImportError:
        pass

    try:
        from exabgp.configuration.process import ParseProcess

        section_map['process'] = ParseProcess
    except ImportError:
        pass

    try:
        from exabgp.configuration.template import ParseTemplate

        section_map['template'] = ParseTemplate
    except ImportError:
        pass

    try:
        from exabgp.configuration.capability import ParseCapability

        section_map['capability'] = ParseCapability
    except ImportError:
        pass

    try:
        from exabgp.configuration.neighbor.family import ParseFamily

        section_map['family'] = ParseFamily
    except ImportError:
        pass

    try:
        from exabgp.configuration.static import ParseStatic

        section_map['static'] = ParseStatic
    except ImportError:
        pass

    try:
        from exabgp.configuration.flow import ParseFlow

        section_map['flow'] = ParseFlow
    except ImportError:
        pass

    try:
        from exabgp.configuration.l2vpn import ParseL2VPN

        section_map['l2vpn'] = ParseL2VPN
    except ImportError:
        pass

    try:
        from exabgp.configuration.operational import ParseOperational

        section_map['operational'] = ParseOperational
    except ImportError:
        pass

    parser_class = section_map.get(section)
    if parser_class is None:
        return None

    schema = getattr(parser_class, 'schema', None)
    if schema:
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
                'Available sections: neighbor, process, template, capability, family, static, flow, l2vpn, operational\n'
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
