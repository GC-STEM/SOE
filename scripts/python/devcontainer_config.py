"""Generate editor declarations from resolved SOE/CSO requirements."""

from collections.abc import Mapping
from typing import Any


def configuration(
    plan: Mapping[str, Any], image: str | None = None
) -> dict[str, Any]:
    if plan["configuration_kind"] == "cso" and not image:
        raise ValueError(
            "Course generation requires --image with a published SOE image"
        )
    common = [
        "/opt/gc-stem/runtime/bin/python",
        "/opt/gc-stem/atlas/scripts/python/soe.py",
    ]
    result: dict[str, Any] = {
        "name": "GC-STEM SOE - Ubuntu 24.04 / Python 3.12",
        "remoteUser": "vscode",
        "containerUser": "vscode",
        "init": True,
        "updateRemoteUserUID": True,
        "overrideCommand": True,
        "containerEnv": {"ATLAS_ROOT": "/opt/gc-stem/atlas"},
        "postCreateCommand": common
        + ["setup", "--workspace", "${containerWorkspaceFolder}"],
        "postStartCommand": common
        + ["verify", "--workspace", "${containerWorkspaceFolder}"],
        "postAttachCommand": common
        + ["verify", "--editor", "--workspace", "${containerWorkspaceFolder}"],
        "waitFor": "postCreateCommand",
        "customizations": {
            "vscode": {
                "extensions": plan["extensions"],
                "settings": {
                    "python.defaultInterpreterPath": "/usr/bin/python3",
                    "editor.formatOnSave": True,
                    "[python]": {
                        "editor.defaultFormatter": "charliermarsh.ruff"
                    },
                    "terminal.integrated.defaultProfile.linux": "bash",
                },
            }
        },
    }
    if plan["environments"]:
        environment_id = next(iter(plan["environments"]))
        definition = plan["resolved"]["course_environments"][environment_id]
        result["customizations"]["vscode"]["settings"][
            "python.defaultInterpreterPath"
        ] = (
            definition["path"].replace("${COURSE_ROOT}", "${workspaceFolder}")
            + "/bin/python"
        )
    if image:
        result["image"] = image
    else:
        result["build"] = {"dockerfile": "Dockerfile", "context": ".."}
    return result
