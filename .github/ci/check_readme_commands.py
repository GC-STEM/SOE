"""Check documented shell syntax without executing documentation commands."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from check_repository import ROOT, tracked_files


def blocks(source: str) -> list[tuple[int, str, str]]:
    """Extract top-level fenced blocks; preserve their language and line."""
    found = []
    opening = None
    body = []
    for line_number, line in enumerate(source.splitlines(), 1):
        if opening is None:
            match = re.match(r"^ {0,3}(`{3,}|~{3,})([^\s]*)[^\n]*$", line)
            if match:
                opening = (match[1], match[2].lower(), line_number + 1)
                body = []
        elif re.fullmatch(
            r" {0,3}"
            + re.escape(opening[0][0])
            + r"{"
            + str(len(opening[0]))
            + r",}\s*",
            line,
        ):
            found.append((opening[2], opening[1], "\n".join(body) + "\n"))
            opening = None
        else:
            body.append(line)
    if opening is not None:
        raise ValueError(f"Unclosed code fence at line {opening[2] - 1}.")
    return found


def syntax_check(shell: str, source: str) -> str | None:
    """Use -n: shell commands, substitutions, and redirects are not executed."""
    executable = os.environ.get("CI_TEST_SHELL") or shutil.which(shell)
    if not executable:
        raise ValueError(f"Cannot locate {shell}.")
    result = subprocess.run(
        [executable, "-n"],
        input=source,
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )
    if result.returncode:
        return (result.stderr or result.stdout).strip()
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--shell", choices=("bash", "sh", "zsh"), default="bash"
    )
    args = parser.parse_args()
    errors, checked = [], 0
    # 'shell'/'console' blocks can contain transcripts; require a precise label.
    languages = {"bash": {"bash"}, "sh": {"sh"}, "zsh": {"zsh"}}[args.shell]
    for path in tracked_files(args.root):
        if path.suffix.lower() != ".md" or not path.is_file():
            continue
        try:
            for line, language, source in blocks(
                path.read_text(encoding="utf-8")
            ):
                if language not in languages:
                    continue
                checked += 1
                error = syntax_check(args.shell, source)
                if error:
                    errors.append(
                        f"{path.relative_to(args.root)}:{line}: {error}"
                    )
        except (ValueError, subprocess.TimeoutExpired) as error:
            errors.append(f"{path.relative_to(args.root)}: {error}")
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    print(f"Checked {checked} {args.shell} block(s); {len(errors)} error(s).")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
