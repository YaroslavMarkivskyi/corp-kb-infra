import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).parents[1]
ENTRYPOINT = REPOSITORY_ROOT / "main.bicep"
COMPLIANCE_CHECK = REPOSITORY_ROOT / "tools" / "check_compliance.py"


def build_template(tmp_path: Path) -> dict:
    """Build the deployable entry point and return the generated ARM template."""
    assert ENTRYPOINT.is_file(), "The infrastructure entry point must be main.bicep"

    output_path = tmp_path / "main.json"
    result = subprocess.run(
        [
            "az",
            "bicep",
            "build",
            "--file",
            str(ENTRYPOINT),
            "--outfile",
            str(output_path),
            "--no-restore",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=os.environ
        | {
            "AZURE_CONFIG_DIR": str(tmp_path / "azure-config"),
            "DOTNET_BUNDLE_EXTRACT_BASE_DIR": str(tmp_path / "dotnet-bundle"),
        },
    )

    assert result.returncode == 0, result.stderr
    assert output_path.is_file(), "Bicep build did not create an ARM template"
    return json.loads(output_path.read_text(encoding="utf-8"))


def run_compliance_check(template_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(COMPLIANCE_CHECK), str(template_path)],
        check=False,
        capture_output=True,
        text=True,
    )


def write_template(tmp_path: Path, resources: list[dict]) -> Path:
    template_path = tmp_path / "template.json"
    template_path.write_text(
        json.dumps({"$schema": "https://schema.management.azure.com/", "resources": resources}),
        encoding="utf-8",
    )
    return template_path


def compliant_resource() -> dict:
    return {
        "type": "Contoso.Example/resources",
        "apiVersion": "2026-01-01",
        "name": "compliant",
        "location": "westeurope",
        "tags": {"CostCenter": "CC-1234"},
    }


def test_compliance_check_accepts_resources_in_approved_regions_with_cost_center(
    tmp_path: Path,
) -> None:
    template = write_template(tmp_path, [compliant_resource()])

    result = run_compliance_check(template)

    assert result.returncode == 0, result.stderr


def test_compliance_check_rejects_a_resource_in_an_unapproved_region(
    tmp_path: Path,
) -> None:
    resource = compliant_resource() | {"location": "northeurope"}
    template = write_template(tmp_path, [resource])

    result = run_compliance_check(template)

    assert result.returncode != 0
    assert "northeurope" in result.stderr


def test_compliance_check_rejects_a_resource_without_a_cost_center_tag(
    tmp_path: Path,
) -> None:
    resource = compliant_resource() | {"tags": {}}
    template = write_template(tmp_path, [resource])

    result = run_compliance_check(template)

    assert result.returncode != 0
    assert "CostCenter" in result.stderr


def test_built_template_is_resource_group_scoped_policy_free_and_compliant(
    tmp_path: Path,
) -> None:
    template = build_template(tmp_path)

    assert template["$schema"].endswith("/deploymentTemplate.json#")
    assert template["resources"], "The skeleton must contain resources to check"
    policy_resources = {
        "microsoft.authorization/policydefinitions",
        "microsoft.authorization/policyassignments",
    }
    assert not any(
        resource["type"].lower() in policy_resources
        for resource in template.get("resources", [])
    )
    assert not any(
        resource["type"].lower() == "microsoft.storage/storageaccounts"
        for resource in template.get("resources", [])
    ), "The template must not create a placeholder storage account"

    template_path = tmp_path / "built-main.json"
    template_path.write_text(json.dumps(template), encoding="utf-8")
    result = run_compliance_check(template_path)

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("parameter_file", "location"),
    [
        (REPOSITORY_ROOT / "dev.bicepparam", "westeurope"),
        (REPOSITORY_ROOT / "prod.bicepparam", "germanywestcentral"),
    ],
)
def test_environment_parameters_define_an_approved_location_and_cost_center(
    parameter_file: Path, location: str
) -> None:
    assert parameter_file.is_file()

    contents = parameter_file.read_text(encoding="utf-8")
    assert f"param location = '{location}'" in contents
    assert "param costCenter = 'CC-1000'" in contents
    assert "param budgetAmount = 200" in contents
    assert "param budgetStartDate = '" in contents
    assert "utcNow" not in contents
