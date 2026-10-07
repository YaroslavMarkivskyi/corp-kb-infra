import json
from pathlib import Path

from scripts.policy_check import check_template


def write_template(tmp_path: Path, resources: list[dict]) -> Path:
    template_path = tmp_path / "main.json"
    template_path.write_text(
        json.dumps({"$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#", "resources": resources}),
        encoding="utf-8",
    )
    return template_path


def resource(name: str, location: str, tags: dict[str, str]) -> dict:
    return {
        "type": "Microsoft.Storage/storageAccounts",
        "apiVersion": "2023-01-01",
        "name": name,
        "location": location,
        "tags": tags,
    }


def test_policy_check_accepts_allowed_region_with_cost_center_tag(tmp_path: Path) -> None:
    template_path = write_template(
        tmp_path,
        [resource("allowed", "westeurope", {"CostCenter": "engineering"})],
    )

    assert check_template(template_path) == []


def test_policy_check_rejects_resource_outside_allowed_regions(tmp_path: Path) -> None:
    template_path = write_template(
        tmp_path,
        [resource("disallowed", "northeurope", {"CostCenter": "engineering"})],
    )

    violations = check_template(template_path)

    assert any("northeurope" in violation for violation in violations)
    assert any("westeurope" in violation and "germanywestcentral" in violation for violation in violations)


def test_policy_check_rejects_resource_without_cost_center_tag(tmp_path: Path) -> None:
    template_path = write_template(
        tmp_path,
        [resource("untagged", "germanywestcentral", {"Environment": "dev"})],
    )

    violations = check_template(template_path)

    assert any("untagged" in violation and "CostCenter" in violation for violation in violations)
