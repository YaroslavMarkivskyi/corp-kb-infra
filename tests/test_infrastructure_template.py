import json
import os
import subprocess
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).parents[1]
ENTRYPOINT = REPOSITORY_ROOT / "main.bicep"
APPROVED_REGIONS = {"westeurope", "germanywestcentral"}


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


def policy_definitions(template: dict) -> list[dict]:
    return [
        resource
        for resource in template["resources"]
        if resource["type"].lower() == "microsoft.authorization/policydefinitions"
    ]


def policy_assignments(template: dict) -> list[dict]:
    return [
        resource
        for resource in template["resources"]
        if resource["type"].lower() == "microsoft.authorization/policyassignments"
    ]


def has_condition(
    condition: object, field: str, operator: str, expected_value: object = None
) -> bool:
    if isinstance(condition, dict):
        if condition.get("field") == field and operator in condition and (
            expected_value is None or condition[operator] == expected_value
        ):
            return True
        return any(
            has_condition(value, field, operator, expected_value)
            for value in condition.values()
        )
    if isinstance(condition, list):
        return any(
            has_condition(value, field, operator, expected_value) for value in condition
        )
    return False


def denies(policy: dict) -> bool:
    return policy["properties"]["policyRule"]["then"].get("effect") == "deny"


def assignment_targets(policy: dict, assignments: list[dict]) -> bool:
    policy_name = policy["name"]
    return any(
        policy_name in assignment["properties"].get("policyDefinitionId", "")
        for assignment in assignments
    )


def test_infrastructure_skeleton_builds_to_an_arm_template(tmp_path: Path) -> None:
    template = build_template(tmp_path)

    assert template["$schema"].startswith("https://schema.management.azure.com/")
    assert template["resources"], "The skeleton must contain deployable resources"


def test_deployment_defines_a_deny_policy_for_unapproved_regions(tmp_path: Path) -> None:
    template = build_template(tmp_path)

    region_policies = [
        policy
        for policy in policy_definitions(template)
        if denies(policy)
        and has_condition(
            policy["properties"]["policyRule"]["if"],
            "location",
            "notIn",
            sorted(APPROVED_REGIONS),
        )
    ]

    assert region_policies, (
        "A deny policy must reject locations outside exactly the approved-region set"
    )
    assert any(
        assignment_targets(policy, policy_assignments(template))
        for policy in region_policies
    ), "An assignment must enforce the approved-region deny policy"


def test_deployment_defines_a_deny_policy_for_missing_cost_center(tmp_path: Path) -> None:
    template = build_template(tmp_path)

    cost_center_policies = [
        policy
        for policy in policy_definitions(template)
        if denies(policy)
        and has_condition(
            policy["properties"]["policyRule"]["if"],
            "tags['CostCenter']",
            "exists",
            False,
        )
    ]

    assert cost_center_policies, "A deny policy must reject resources without the CostCenter tag"
    assert any(
        assignment_targets(policy, policy_assignments(template))
        for policy in cost_center_policies
    ), "An assignment must enforce the CostCenter deny policy"
