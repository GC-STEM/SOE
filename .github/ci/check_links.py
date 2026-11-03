"""Run Lychee against tracked documentation and issue-template link text."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from contextlib import ExitStack
from pathlib import Path

import yaml
from check_repository import ROOT, tracked_files


def text_values(value: object) -> list[str]:
    """Extract YAML URLs and Markdown description text."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [text for item in value for text in text_values(item)]
    if isinstance(value, dict):
        return [text for item in value.values() for text in text_values(item)]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--mode", choices=("internal", "external"), required=True
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--lychee", default="lychee")
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    executable = shutil.which(args.lychee)
    if not executable:
        parser.error("Lychee is required. See .github/ci/README.md.")
    executable = str(Path(executable).resolve())

    paths = tracked_files(root)
    documentation = [
        path
        for path in paths
        if path.suffix.lower() in {".md", ".markdown", ".html", ".htm"}
        and path.is_file()
    ]
    if not documentation:
        parser.error("No tracked documentation was found.")
    with ExitStack() as stack:
        aliases = {}
        for path in paths:
            relative = path.relative_to(root).as_posix()
            if not relative.startswith(".github/ISSUE_TEMPLATE/"):
                continue
            if path.suffix not in {".yml", ".yaml"} or not path.is_file():
                continue
            texts = text_values(
                yaml.safe_load(path.read_text(encoding="utf-8"))
            )
            if not texts:
                continue
            # Keep each synthetic Markdown file beside its YAML source so
            # relative links have the same base directory. Always clean it up.
            handle = stack.enter_context(
                tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    suffix=".md",
                    prefix=".ci-links-",
                    dir=path.parent,
                    delete=False,
                )
            )
            synthetic = Path(handle.name)
            stack.callback(synthetic.unlink, missing_ok=True)
            handle.write("\n\n".join(texts) + "\n")
            handle.close()
            documentation.append(synthetic)
            aliases[str(synthetic)] = str(path)

        command = [
            executable,
            "--config",
            str(root / ".github/ci/lychee.toml"),
            "--root-dir",
            str(root),
            "--files-from",
            "-",
            "--format",
            "markdown",
            "--output",
            str(output),
        ]
        if args.mode == "internal":
            command.append("--offline")
        else:
            # The internal job owns filesystem links.
            command.extend(["--scheme", "http", "--scheme", "https"])
        result = subprocess.run(
            command,
            input="\n".join(str(path) for path in documentation),
            cwd=root,
            text=True,
            check=False,
        )
        if output.exists():
            report = output.read_text(encoding="utf-8")
            for synthetic, original in aliases.items():
                report = report.replace(synthetic, original)
            output.write_text(report, encoding="utf-8")
            summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
            if summary_path:
                with open(summary_path, "a", encoding="utf-8") as summary:
                    summary.write(f"## {args.mode.title()} link checks\n\n")
                    summary.write(report + "\n")
        else:
            output.write_text(
                f"No link report was produced (exit {result.returncode}).\n",
                encoding="utf-8",
            )
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
