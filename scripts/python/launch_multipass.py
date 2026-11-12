"""Launch an Ubuntu 24.04 Multipass guest and provision its SOE/CSO."""

from __future__ import annotations

import argparse
import platform
import re
import shutil
import subprocess
from pathlib import Path

REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,39}$")
GUEST_SOE = "/home/ubuntu/Repos/_shared/SOE"


def run(
    *parts: object, capture: bool = False
) -> subprocess.CompletedProcess[str]:
    command = [str(part) for part in parts]
    return subprocess.run(
        command, check=True, text=True, capture_output=capture
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    course = parser.add_mutually_exclusive_group(required=True)
    course.add_argument(
        "--course-repo", help="Public OWNER/REPO to clone into guest"
    )
    course.add_argument(
        "--course-path",
        type=Path,
        help="Mount a host course checkout (private repos supported)",
    )
    course.add_argument(
        "--soe-only", action="store_true", help="Provision SOE without a course"
    )
    parser.add_argument(
        "--name", default="gc-stem-faculty", help="Multipass instance name"
    )
    parser.add_argument("--cpus", type=int, default=2)
    parser.add_argument("--memory", default="4G")
    parser.add_argument("--disk", default="20G")
    parser.add_argument(
        "--reuse", action="store_true", help="Use an existing named VM"
    )
    args = parser.parse_args()

    if not NAME_PATTERN.fullmatch(args.name):
        parser.error("--name must be lowercase letters, numbers, or hyphens")
    if args.cpus < 1:
        parser.error("--cpus must be positive")
    if args.course_repo and not REPO_PATTERN.fullmatch(args.course_repo):
        parser.error("--course-repo must be OWNER/REPO")
    course_path = args.course_path.resolve() if args.course_path else None
    if course_path and not (
        course_path / ".config/cso_manifest.json"
    ).is_file():
        parser.error("--course-path must contain .config/cso_manifest.json")
    if not shutil.which("multipass"):
        parser.error("Install Canonical Multipass on the host first")
    if not shutil.which("git"):
        parser.error("Git is required on the host to pin the SOE revision")
    soe_root = Path(__file__).resolve().parents[2]
    revision = run(
        "git", "-C", soe_root, "rev-parse", "HEAD", capture=True
    ).stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        parser.error("Cannot determine the exact SOE checkout commit")

    host_arch = platform.machine().lower()
    if host_arch not in {"x86_64", "amd64", "aarch64", "arm64"}:
        parser.error(f"Unsupported host architecture: {host_arch}")

    if course_path and platform.system() == "Windows":
        mounts = subprocess.run(
            ["multipass", "get", "local.privileged-mounts"],
            capture_output=True,
            text=True,
        )
        if mounts.returncode or mounts.stdout.strip().lower() != "true":
            parser.error(
                "Multipass host mounts are disabled on Windows. "
                "Review the security implications of "
                "'multipass set local.privileged-mounts=true' "
                "or use --course-repo instead."
            )

    exists = subprocess.run(
        ["multipass", "info", args.name], capture_output=True, text=True
    ).returncode == 0
    if exists and not args.reuse:
        parser.error(
            f"VM {args.name!r} exists; use --reuse or a different --name"
        )
    if exists:
        # A running instance needs no start; a stopped instance does.
        status = run("multipass", "info", args.name, capture=True).stdout
        if not re.search(r"State:\s+Running", status, re.IGNORECASE):
            run("multipass", "start", args.name)
    else:
        cloud_init = soe_root / "scripts/cloud-init/multipass.yaml"
        if not cloud_init.is_file():
            parser.error(f"Missing cloud-init configuration: {cloud_init}")
        run(
            "multipass", "launch", "24.04", "--name", args.name,
            "--cpus", args.cpus, "--memory", args.memory,
            "--disk", args.disk, "--cloud-init", cloud_init,
        )
    run("multipass", "exec", args.name, "--", "cloud-init", "status", "--wait")

    # Clone SOE as a separate, course-independent shared checkout.
    script = (
        'set -Eeuo pipefail; mkdir -p "$HOME/Repos/_shared"; '
        'if [ ! -e "$HOME/Repos/_shared/SOE" ]; then '
        'git clone https://github.com/GC-STEM/SOE.git '
        '"$HOME/Repos/_shared/SOE"; fi; '
        'test -f "$HOME/Repos/_shared/SOE/scripts/bash/setup_ubuntu_runtime.sh"'
    )
    run("multipass", "exec", args.name, "--", "bash", "-lc", script)
    run(
        "multipass", "exec", args.name, "--", "git", "-C", GUEST_SOE,
        "fetch", "origin", "main",
    )
    run(
        "multipass", "exec", args.name, "--", "git", "-C", GUEST_SOE,
        "checkout", "--detach", revision,
    )

    setup: list[str] = [
        "multipass", "exec", args.name, "--", "bash",
        f"{GUEST_SOE}/scripts/bash/setup_ubuntu_runtime.sh",
        "--deployment", "multipass",
    ]
    if course_path:
        target = "/home/ubuntu/Repos/" + course_path.name
        run(
            "multipass", "exec", args.name, "--", "mkdir", "-p",
            "/home/ubuntu/Repos",
        )
        # A host mount avoids copying faculty content or Git credentials
        # into the VM.
        run("multipass", "mount", course_path, f"{args.name}:{target}")
        setup += ["--course-root", target]
    elif args.soe_only:
        setup.append("--soe-only")
    else:
        setup += ["--course-repo", args.course_repo]
    run(*setup)
    print(f"SOE/CSO verified in {args.name} using SOE commit {revision[:12]}.")
    print(f"To enter: multipass shell {args.name}")
    print(f"To stop: multipass stop {args.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
