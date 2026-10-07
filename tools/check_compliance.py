"""Validate deployment resources against the local infrastructure conventions."""

import json
import re
import sys
from pathlib import Path
from typing import Any


APPROVED_REGIONS = {'westeurope', 'germanywestcentral'}
PARAMETER_EXPRESSION = re.compile(r"^\[parameters\('([^']+)'\)\]$", re.IGNORECASE)


def resolve_parameter(value: Any, parameters: dict[str, Any]) -> Any:
    """Resolve a simple ARM parameter expression from a template default value."""
    if not isinstance(value, str):
        return value

    match = PARAMETER_EXPRESSION.fullmatch(value)
    if not match:
        return value

    parameter = parameters.get(match.group(1), {})
    return parameter.get('defaultValue') if isinstance(parameter, dict) else None


def validate_resource(resource: dict[str, Any], parameters: dict[str, Any]) -> list[str]:
    """Return violations for a resource and its nested resources."""
    violations: list[str] = []
    name = resource.get('name', '<unnamed resource>')
    location = resolve_parameter(resource.get('location'), parameters)
    tags = resource.get('tags')
    cost_center = (
        resolve_parameter(tags.get('CostCenter'), parameters)
        if isinstance(tags, dict)
        else None
    )

    if not isinstance(location, str) or location.lower() not in APPROVED_REGIONS:
        violations.append(f'{name}: location {location!r} is not approved')
    if not cost_center:
        violations.append(f'{name}: CostCenter tag is required')

    for child in resource.get('resources', []):
        if isinstance(child, dict):
            violations.extend(validate_resource(child, parameters))
    return violations


def validate_template(template: dict[str, Any]) -> list[str]:
    """Return all compliance violations in an ARM template."""
    parameters = template.get('parameters', {})
    resources = template.get('resources', [])
    if not isinstance(parameters, dict) or not isinstance(resources, list):
        return ['Template must define object parameters and an array of resources']

    violations: list[str] = []
    for resource in resources:
        if isinstance(resource, dict):
            violations.extend(validate_resource(resource, parameters))
    return violations


def main() -> int:
    if len(sys.argv) != 2:
        print(f'Usage: {Path(sys.argv[0]).name} TEMPLATE_PATH', file=sys.stderr)
        return 2

    try:
        with Path(sys.argv[1]).open(encoding='utf-8') as template_file:
            template = json.load(template_file)
    except (OSError, json.JSONDecodeError) as error:
        print(f'Unable to read template: {error}', file=sys.stderr)
        return 2

    if not isinstance(template, dict):
        print('Template root must be a JSON object', file=sys.stderr)
        return 2

    violations = validate_template(template)
    if violations:
        print('\n'.join(violations), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
