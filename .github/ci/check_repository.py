"""Validate shared configuration using a repository requirements manifest."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import editorconfig
import json5
import yaml

ROOT = Path(__file__).resolve().parents[2]


def tracked_files(root: Path) -> list[Path]:
    """Include hidden files without scanning virtual environments or .git."""
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True
    )
    return [
        root / name
        for name in result.stdout.decode("utf-8").split("\0")
        if name
    ]


def git_eol(root: Path, names: list[str]) -> dict[str, str]:
    """Ask Git to resolve attributes, including ordered filename exceptions."""
    result = subprocess.run(
        ["git", "check-attr", "-z", "--stdin", "eol"],
        input="\0".join(names).encode(),
        cwd=root,
        capture_output=True,
        check=True,
    )
    fields = result.stdout.decode().split("\0")
    return dict(zip(fields[0::3], fields[2::3]))


def eol_samples(root: Path) -> list[str]:
    """Cover each explicit EoL rule and the current tracked text files."""
    names = set()
    for line in (root / ".gitattributes").read_text().splitlines():
        parts = line.split()
        if not parts or parts[0].startswith("#"):
            continue
        if any(part.startswith("eol=") for part in parts[1:]):
            pattern = parts[0]
            if re.search(r"[?\[\]]", pattern):
                raise ValueError(
                    f"Add representative samples for complex pattern: {pattern}"
                )
            # Current baseline uses extension patterns and exact filenames.
            names.add(pattern.replace("*", "example"))
            names.add("nested/" + pattern.replace("*", "example"))
    names.update(
        path.relative_to(root).as_posix() for path in tracked_files(root)
    )
    return sorted(names)


def check_eol(
    root: Path, policy: dict, settings: dict
) -> tuple[list[str], list[str]]:
    """Check policy agreement, not working-tree bytes normalized by Git."""
    errors, warnings = [], []
    samples = eol_samples(root)
    attributes = git_eol(root, samples)
    for name in samples:
        expected = attributes[name]
        actual = editorconfig.get_properties(str(root / name)).get(
            "end_of_line"
        )
        if expected in {"lf", "crlf"} and actual != expected:
            errors.append(
                f"EoL policy mismatch: {name}: Git={expected}, "
                f"EditorConfig={actual or 'unset'}."
            )

    missing = []
    for language, name in policy.get("ide_samples", {}).items():
        expected = editorconfig.get_properties(str(root / name)).get(
            "end_of_line"
        )
        # VS Code supports single and compound language override keys.
        values = {
            value["files.eol"]
            for key, value in settings.items()
            if f"[{language}]" in key
            and isinstance(value, dict)
            and "files.eol" in value
        }
        if not values:
            values = {settings.get("files.eol", "auto")}
        desired = {"lf": "\n", "crlf": "\r\n"}.get(expected)
        if desired is None:
            continue
        if "auto" in values:
            missing.append(language)
        for value in values - {"auto"}:
            if value != desired:
                errors.append(
                    f"VS Code EoL conflicts with EditorConfig: {language}."
                )
    if missing:
        warnings.append(
            "VS Code files.eol safeguard is unset/auto for: "
            + ", ".join(missing)
            + ". Review .vscode/settings.json separately."
        )
    return errors, warnings


def validate(root: Path, policy: dict) -> tuple[list[str], list[str]]:
    """Parse repository configuration and validate reusable Core safeguards."""
    errors, warnings = [], []
    for name in policy["required_files"]:
        path = root / name
        if not path.is_file() or not path.stat().st_size:
            errors.append(f"Required file is missing or empty: {name}")

    settings = {}
    for path in tracked_files(root):
        if not path.is_file():
            continue
        name = path.relative_to(root).as_posix()
        try:
            source = path.read_text(encoding="utf-8")
            if path.suffix in {".json", ".jsonc", ".code-workspace"}:
                # VS Code accepts comments and trailing commas.
                if name.startswith(".vscode/") or path.suffix != ".json":
                    data = json5.loads(source, allow_duplicate_keys=False)
                else:
                    data = json.loads(source)
                if name == ".vscode/settings.json":
                    settings = data
            elif path.suffix == ".toml":
                tomllib.loads(source)
            elif path.suffix in {".yml", ".yaml"}:
                # BaseLoader keeps Actions' 'on' from becoming YAML 1.1 True.
                data = yaml.load(source, Loader=yaml.BaseLoader)
                if name.startswith(".github/workflows/"):
                    if not isinstance(data, dict):
                        errors.append(f"Empty/invalid workflow: {name}")
                        continue
                    for key in ("name", "on", "jobs", "permissions"):
                        if not data.get(key):
                            errors.append(f"{name}: missing {key}.")
                    if data.get("permissions") != {"contents": "read"}:
                        errors.append(f"{name}: use contents: read only.")
                    if "pull_request_target" in data.get("on", {}):
                        errors.append(
                            f"{name}: privileged PR event disallowed."
                        )
                    for job in data.get("jobs", {}).values():
                        for step in job.get("steps", []):
                            uses = step.get("uses", "")
                            if uses and not uses.startswith("./"):
                                if not re.search(r"@[a-f0-9]{40}$", uses):
                                    errors.append(
                                        f"{name}: pin action to full SHA: "
                                        f"{uses}"
                                    )
                            if (
                                step.get("with", {}).get("persist-credentials")
                                == "true"
                            ):
                                errors.append(
                                    f"{name}: credentials must not persist."
                                )
                elif data is None:
                    warnings.append(
                        f"Empty configuration awaits review: {name}"
                    )
        except UnicodeDecodeError:
            # Binary assets are not text configuration.
            continue
        except (ValueError, yaml.YAMLError) as error:
            errors.append(f"{name}: invalid configuration: {error}")

    try:
        eol_errors, eol_warnings = check_eol(root, policy, settings)
        errors.extend(eol_errors)
        warnings.extend(eol_warnings)
    except (OSError, ValueError, editorconfig.EditorConfigError) as error:
        errors.append(f"Cannot validate EoL policy: {error}")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--policy", type=Path, default=ROOT / ".github/ci/core-policy.json"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat existing review warnings as failures.",
    )
    args = parser.parse_args()
    errors, warnings = validate(
        args.root.resolve(), json.loads(args.policy.read_text(encoding="utf-8"))
    )
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    print(
        f"Repository validation: {len(errors)} error(s), "
        f"{len(warnings)} warning(s)."
    )
    return int(bool(errors or (args.strict and warnings)))


if __name__ == "__main__":
    raise SystemExit(main())
