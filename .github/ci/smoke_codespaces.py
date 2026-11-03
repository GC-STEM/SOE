"""Exercise real SOE and CSO setup inside the built non-root container."""

import json
import os
import platform
import subprocess
import tempfile
from pathlib import Path

from test_soe import python_overlay

ATLAS = Path(os.environ.get("ATLAS_ROOT", "/opt/gc-stem/atlas"))


def execute(*args):
    subprocess.run([str(arg) for arg in args], check=True)


def main():
    assert os.geteuid() != 0, "Smoke test must exercise the development user"
    assert platform.python_implementation() == "CPython"
    assert platform.python_version_tuple()[:2] == ("3", "12")
    runtime = "/opt/gc-stem/runtime/bin/python"
    script = ATLAS / "scripts/python/soe.py"
    execute(runtime, script, "verify", "--workspace", ATLAS, "--mode", "soe")
    with tempfile.TemporaryDirectory() as directory:
        workspace = Path(directory)
        (workspace / ".config").mkdir()
        course = python_overlay()
        course["additions"]["platform_extensions"]["ubuntu_headless"][
            "os_packages"
        ] = {
            "course_jq": {
                "display_name": "jq",
                "purpose": "Exercise course APT additions.",
                "package_identifier": "jq",
                "required": True,
                "source_id": "ubuntu_archive",
                "verification": {
                    "adapter_id": "apt_package",
                    "package_identifiers": ["jq"],
                },
            },
        }
        course["additions"]["managed_settings"] = {
            "course_editor": {
                "display_name": "Course settings",
                "target_capability_role": "source_code_ide",
                "scope": "workspace",
                "settings_adapter_id": "vscode_workspace_settings",
                "target_path": "${WORKSPACE_ROOT}/.vscode/settings.json",
                "merge_policy": "merge_preserve_unmanaged",
                "values": {"editor.formatOnSave": True},
            },
        }
        (workspace / ".vscode").mkdir()
        settings = workspace / ".vscode/settings.json"
        settings.write_text('{"custom.userSetting": true}')
        (workspace / ".config/cso_manifest.json").write_text(json.dumps(course))
        for _ in range(2):
            execute(runtime, script, "setup", "--workspace", workspace)
        execute(runtime, script, "verify", "--workspace", workspace)
        assert json.loads(settings.read_text()) == {
            "custom.userSetting": True,
            "editor.formatOnSave": True,
        }
        execute("jq", "--version")
        execute(
            workspace / ".venv/bin/python",
            "-c",
            "import platform,sys,pytest; "
            "assert sys.version_info[:2] == (3,12); "
            "assert platform.python_implementation() == 'CPython'; "
            "assert pytest.__version__ == '8.4.2'",
        )
        execute(
            "/usr/bin/python3",
            "-c",
            "import importlib.util; "
            "assert importlib.util.find_spec('pytest') is None",
        )
    print("SOE and isolated CSO provisioning passed, including repeated setup.")


if __name__ == "__main__":
    main()
