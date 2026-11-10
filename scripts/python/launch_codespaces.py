"""Open the Codespaces creation page for the selected GitHub checkout."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import webbrowser
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import quote, urlsplit

from soe import ConfigurationError, load_plan, read_json, require


def github_identity(remote: str) -> str:
    if remote.startswith("git@github.com:"):
        path = remote.removeprefix("git@github.com:")
    else:
        parsed = urlsplit(remote)
        require(
            parsed.hostname == "github.com"
            and parsed.scheme in {"https", "ssh"},
            "Origin must identify a GitHub.com repository",
        )
        require(
            not parsed.password
            and not parsed.query
            and not parsed.fragment
            and parsed.port is None,
            "Origin must not contain credentials, ports, or URL parameters",
        )
        require(
            (parsed.scheme == "https" and parsed.username is None)
            or (parsed.scheme == "ssh" and parsed.username == "git"),
            "Unsupported GitHub origin identity",
        )
        path = parsed.path.lstrip("/")
    path = path.removesuffix("/").removesuffix(".git")
    require(
        re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9][A-Za-z0-9._-]*", path
        ),
        "Invalid GitHub owner/repository",
    )
    return path


def git(workspace: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(workspace), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def launch_url(
    workspace: Path,
    atlas_root: Path,
    branch: str | None = None,
    schema_path: str | Path | None = None,
) -> str:
    plan = load_plan(atlas_root, workspace, schema_path=schema_path)
    launcher = plan["resolved"]["launch_profiles"].get("github_codespaces")
    require(
        launcher and launcher["enabled"] and launcher["kind"] == "codespaces",
        "Codespaces launcher is disabled",
    )
    require(
        launcher["deployment_profile_id"] == plan["deployment"],
        "Launcher deployment mismatch",
    )
    require(
        launcher["devcontainer_path"] == ".devcontainer/devcontainer.json",
        "This launcher uses the default devcontainer configuration",
    )
    configuration = read_json(workspace / launcher["devcontainer_path"])
    extensions = (
        configuration.get("customizations", {})
        .get("vscode", {})
        .get("extensions", [])
    )
    require(
        set(plan["extensions"]).issubset(extensions),
        "Missing SOE/CSO extensions; regenerate devcontainer before launch",
    )
    if "build" in configuration:
        dockerfile = configuration["build"].get("dockerfile", "Dockerfile")
        require(
            (workspace / ".devcontainer" / dockerfile).is_file(),
            "Devcontainer Dockerfile is missing",
        )
    else:
        require(
            configuration.get("image"),
            "Devcontainer needs an image or Dockerfile",
        )
    identity = github_identity(git(workspace, "remote", "get-url", "origin"))
    branch = branch or git(
        workspace, "symbolic-ref", "--quiet", "--short", "HEAD"
    )
    git(workspace, "check-ref-format", "--branch", branch)
    return f"https://codespaces.new/{identity}/tree/{quote(branch, safe='')}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument(
        "--atlas-root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument(
        "--branch", help="Explicit branch, including for a detached checkout"
    )
    parser.add_argument("--print-url", action="store_true")
    parser.add_argument(
        "--schema",
        type=Path,
        help="Canonical schema file in the .github checkout",
    )
    args = parser.parse_args(argv)
    try:
        url = launch_url(
            args.workspace.resolve(),
            args.atlas_root.resolve(),
            args.branch,
            schema_path=args.schema,
        )
        print(url)
        print(
            "Codespaces uses the pushed branch and its SOE/CSO configuration. "
            "GitHub confirms access and billing.",
            file=sys.stderr,
        )
        if not args.print_url:
            require(
                webbrowser.open(url),
                "Browser could not open; use the printed URL",
            )
    except (
        ConfigurationError,
        OSError,
        ValueError,
        KeyError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"Codespaces: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
