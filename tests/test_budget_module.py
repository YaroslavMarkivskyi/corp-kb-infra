import json
import os
import re
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).parents[1]
ENTRYPOINT = REPOSITORY_ROOT / "main.bicep"
BUDGET_MODULE = REPOSITORY_ROOT / "modules" / "budget.bicep"
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


def test_entrypoint_composes_the_budget_module_without_an_inline_budget() -> None:
    contents = ENTRYPOINT.read_text(encoding="utf-8")

    assert BUDGET_MODULE.is_file(), "The monthly budget must live in modules/budget.bicep"
    assert re.search(
        r"module\s+budget\s+'\./modules/budget\.bicep'\s*=\s*{",
        contents,
    ), "main.bicep must compose the budget module"
    assert "Microsoft.Consumption/budgets" not in contents


def test_budget_module_declares_budget_and_notification_inputs() -> None:
    assert BUDGET_MODULE.is_file(), "The monthly budget must live in modules/budget.bicep"
    contents = BUDGET_MODULE.read_text(encoding="utf-8")

    for declaration in (
        "param budgetAmount int",
        "param itOpsEmail string",
        "param pmEmail string",
        "param budgetStartDate string",
    ):
        assert declaration in contents


def test_environment_parameters_provide_a_fixed_monthly_budget_and_start_date() -> None:
    for parameter_file in PARAMETER_FILES:
        contents = parameter_file.read_text(encoding="utf-8")

        assert "param budgetAmount = 200" in contents
        assert re.search(
            r"param\s+budgetStartDate\s*=\s+'\d{4}-\d{2}-01T00:00:00Z'",
            contents,
        )
        assert "utcNow" not in contents
        assert "param pmEmail = 'REPLACE-WITH-PM-EMAIL@company.invalid'" in contents


def test_monthly_budget_alerts_at_80_and_100_percent_reach_it_ops_and_the_pm(
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

    assert properties["amount"] == "[parameters('budgetAmount')]"
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
            "[parameters('itOpsEmail')]",
            "[parameters('pmEmail')]",
        }
