import json
import os
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).parents[1]
ENTRYPOINT = REPOSITORY_ROOT / "main.bicep"
COMPLIANCE_CHECK = REPOSITORY_ROOT / "tools" / "check_compliance.py"
PARAMETER_FILES = (
    REPOSITORY_ROOT / "dev.bicepparam",
    REPOSITORY_ROOT / "prod.bicepparam",
)


def build_template(tmp_path: Path) -> dict[str, Any]:
    """Build the deployable entry point and return the generated ARM template."""
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
    return json.loads(output_path.read_text(encoding="utf-8"))


def deployment_resources(resources: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    """Yield resources, including resources emitted by Bicep modules."""
    for resource in resources:
        yield resource
        yield from deployment_resources(resource.get("resources", []))

        properties = resource.get("properties", {})
        template = properties.get("template", {}) if isinstance(properties, dict) else {}
        nested_resources = template.get("resources", []) if isinstance(template, dict) else []
        yield from deployment_resources(nested_resources)


def test_built_template_defines_a_compliant_monthly_resource_group_budget(
    tmp_path: Path,
) -> None:
    template = build_template(tmp_path)
    budgets = [
        resource
        for resource in deployment_resources(template["resources"])
        if resource.get("type", "").lower() == "microsoft.consumption/budgets"
    ]

    assert len(budgets) == 1, "The resource group must have one monthly Cost Management budget"
    budget = budgets[0]
    properties = budget["properties"]

    assert budget["location"] == "[parameters('location')]"
    assert budget["tags"]["CostCenter"] == "[parameters('costCenter')]"
    assert properties["category"] == "Cost"
    assert properties["amount"] == "[parameters('monthlyBudget')]"
    assert properties["timeGrain"] == "Monthly"

    notifications = properties["notifications"]
    for threshold in (80, 100):
        notification = next(
            (
                value
                for value in notifications.values()
                if value["threshold"] == threshold
            ),
            None,
        )
        assert notification is not None, f"Missing the {threshold}% budget alert"
        assert notification["enabled"] is True
        assert notification["operator"] == "GreaterThanOrEqualTo"
        assert set(notification["contactEmails"]) == {
            "it-ops@company.com",
            "[parameters('pmEmail')]",
        }

    template_path = tmp_path / "built-main.json"
    template_path.write_text(json.dumps(template), encoding="utf-8")
    result = subprocess.run(
        ["python", str(COMPLIANCE_CHECK), str(template_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_budget_module_is_composed_by_the_entrypoint() -> None:
    budget_module = REPOSITORY_ROOT / "modules" / "budget.bicep"

    assert budget_module.is_file(), "The budget must be declared in modules/budget.bicep"
    assert "modules/budget.bicep" in ENTRYPOINT.read_text(encoding="utf-8")


def test_pm_email_is_a_required_main_template_parameter(tmp_path: Path) -> None:
    template = build_template(tmp_path)

    pm_email = template["parameters"]["pmEmail"]
    assert pm_email["type"] == "string"
    assert "defaultValue" not in pm_email


def test_environment_parameters_provide_the_monthly_budget_and_pm_placeholder() -> None:
    for parameter_file in PARAMETER_FILES:
        contents = parameter_file.read_text(encoding="utf-8")

        assert "param monthlyBudget = 200" in contents
        assert "param pmEmail = 'REPLACE-WITH-PM-EMAIL@company.invalid'" in contents
