import json
import os
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).parents[1]
ENTRYPOINT = REPOSITORY_ROOT / "main.bicep"


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


def test_monthly_budget_alerts_at_80_and_100_percent_reach_it_ops_and_the_pm(
    tmp_path: Path,
) -> None:
    template = build_template(tmp_path)
    budgets = [
        resource
        for resource in deployment_resources(template["resources"])
        if resource.get("type", "").lower() == "microsoft.consumption/budgets"
    ]

    assert budgets, "Missing the Cost Management budget that defines the monthly alerts"
    budget = budgets[0]
    properties = budget["properties"]

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
