"""Read-only checks for the course-specific overlay (CSO)."""

import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import cast


def check_command(label: str, executable: str) -> bool:
    """Print an installed CLI's version and return whether it is available."""
    path = shutil.which(executable)
    if not path:
        print(f"MISSING  {label} ({executable})")
        return False

    try:
        result = subprocess.run(
            [path, "--version"], capture_output=True, text=True, timeout=15
        )
    except OSError as exc:
        print(f"ERROR    {label}: {exc}")
        return False
    except subprocess.TimeoutExpired:
        print(f"ERROR    {label}: version check timed out")
        return False

    if result.returncode:
        print(f"ERROR    {label}: unable to retrieve version")
        return False

    version = result.stdout.strip().splitlines()
    print(f"OK       {label}: {version[0] if version else 'installed'}")
    return True


def check_extensions() -> bool:
    """Check installed extensions against workspace recommendations."""
    config = Path(__file__).resolve().parents[2] / ".vscode" / "extensions.json"

    try:
        data = json.loads(config.read_text(encoding="utf-8"))
        recommended = data.get("recommendations", [])
        unwanted = data.get("unwantedRecommendations", [])

        for name, items in (
            ("recommendations", recommended),
            ("unwantedRecommendations", unwanted),
        ):
            if not isinstance(items, list) or not all(
                isinstance(item, str) and item
                for item in cast(list[object], items)
            ):
                raise ValueError(f"{name} must be an array of extension IDs")

        overlap = (
            {item.casefold() for item in recommended}
            & {item.casefold() for item in unwanted}
        )
        if overlap:
            raise ValueError(
                f"Extensions appear in both lists: {', '.join(sorted(overlap))}"
            )

    except (OSError, ValueError) as exc:
        print(f"ERROR    Cannot read {config.name}: {exc}")
        return False

    cli = shutil.which("code")
    if not cli:
        print("SKIPPED  Extension check (VS Code CLI not on PATH)")
        return True

    try:
        result = subprocess.run(
            [cli, "--list-extensions"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"SKIPPED  Extension check: {exc}")
        return True

    if result.returncode:
        print("SKIPPED  Extension check (VS Code CLI error)")
        return True

    installed = {
        line.strip().casefold()
        for line in result.stdout.splitlines()
    }

    missing = [
        item for item in recommended
        if item.casefold() not in installed
    ]
    unwanted_installed = [
        item for item in unwanted
        if item.casefold() in installed
    ]

    print(
        f"Recommended extensions: "
        f"{len(recommended) - len(missing)}/{len(recommended)} installed"
    )

    for item in missing:
        print(f"OPTIONAL {item} (not installed)")

    for item in unwanted_installed:
        print(f"WARNING  {item} (unwanted extension installed)")

    if not missing and not unwanted_installed:
        print("OK       Extension recommendations satisfied")

    return True


def main() -> int:
    print("Course-specific overlay readiness check\n")

    if (
        sys.version_info[:2] != (3, 12)
        or platform.python_implementation() != "CPython"
    ):
        print(
            f"INCOMPATIBLE  {platform.python_implementation()} "
            f"{sys.version.split()[0]}; requires CPython 3.12.x"
        )
        print("Select a Python 3.12 interpreter and rerun this check.")
        return 1

    print(f"OK       Python: {sys.version.split()[0]}")

    ready = all([
        check_command("GNU Bash", "bash"),
        check_command("Git", "git"),
        check_command("GitHub CLI", "gh"),
    ])

    print()
    valid_extensions = check_extensions()

    print(
        "\nRESULT:", "READY" if ready and valid_extensions else "ACTION NEEDED"
    )
    return 0 if ready and valid_extensions else 1


if __name__ == "__main__":
    sys.exit(main())
