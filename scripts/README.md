# Local Ubuntu SOE/CSO deployments

These experimental launchers use the **shared** GC-STEM SOE manifest and each
course's own CSO manifest. They do not change the Codio reference environment
or the existing Codespaces, Docker, Windows Sandbox, or Vagrant launchers.

The SOE provisioning script supports **Ubuntu 24.04 LTS / Python 3.12**, with
AMD64 and ARM64 guest profiles. Guest setups are **headless**: IDE integration
is provided separately by the host. Do not claim qualification until an actual
VM launch and verification have passed on the intended hardware.

## Windows students: WSL2

**Requirements:** supported Windows 11/10, virtualization enabled, permissions
to install WSL, and Windows VS Code with the Microsoft WSL extension.

From **Windows PowerShell 5.1 or PowerShell 7+**, in your local SOE checkout:

```powershell
& "$HOME/Repos/_shared/SOE/scripts/powershell/setup_wsl2.ps1" -CourseRepo 'GC-STEM/crs000'
```

If WSL or Ubuntu is not yet installed, the command installs Ubuntu 24.04.
Restart Windows and create your Linux user when prompted, then rerun the same
command. The second run clones SOE to `~/Repos/_shared/SOE` *inside Ubuntu*,
clones the selected public course to `~/Repos/<course>` there, installs the
headless SOE/CSO packages and checks the resulting environment. Use `-SoeOnly` instead of `-CourseRepo` to install just the SOE. A private
course requires a separately authenticated checkout in WSL and direct use of
the Linux setup script with `--course-root`.

To open your course in VS Code, open Ubuntu and run:

```bash
cd ~/Repos/crs000 && code .
```

Replace `crs000` with the actual course repo directory. The host's VS Code
and WSL extension are prerequisites; VS Code is not installed inside the
Ubuntu guest. Keep Linux course files in the WSL filesystem for performance.

## Faculty: Multipass

**Requirements:** Canonical Multipass on the host, Python 3.10+, Git, enabled
virtualization, and sufficient memory and disk space. On macOS Apple Silicon,
Multipass creates an ARM64 Ubuntu image; on AMD64 hosts it uses AMD64.

From the local SOE checkout, use one command on Windows, macOS, or Linux:

```bash
python scripts/python/launch_multipass.py --course-repo GC-STEM/crs000
```

On Windows, `python` must resolve to Python 3.10+; on macOS/Linux you may
need `python3` instead. The launcher pins the guest SOE checkout to the host SOE commit; **commit
and push SOE first**. The launcher creates an Ubuntu 24.04 guest using
`scripts/cloud-init/multipass.yaml`, clones the pinned SOE revision and the selected public
course into the guest, runs the same SOE/CSO resolver, and verifies the tools.

To provision only the SOE, use `--soe-only` in place of `--course-repo`.

For a **private faculty checkout**, avoid placing GitHub credentials in the VM.
Instead mount an existing local course checkout:

```bash
python scripts/python/launch_multipass.py --course-path /path/to/course
```

The `--course-path` option requires the host path to contain
`.config/cso_manifest.json`. On Windows, supply the Windows path. The VM mount
shares a live working tree: use a clean, dedicated verification checkout
rather than a directory containing unrelated student files.

Manage the VM from the host:

```text
multipass shell gc-stem-faculty
multipass stop gc-stem-faculty
multipass start gc-stem-faculty
```

Use `--reuse` with the launcher to re-check an existing VM. You can instead
launch additional instances with a distinct `--name`. Removing a VM with
`multipass delete`/`purge` permanently discards its guest-local data; mounted
host files are not disposable VM storage.

## Shared Linux provisioner

The guest bootstrap script is:

```text
SOE/scripts/bash/setup_ubuntu_runtime.sh
```

It supports `--deployment wsl2|multipass`, plus one of `--course-repo OWNER/REPO`,
`--course-root /path/to/course`, or `--soe-only`. It uses the canonical SOE
resolver for capability selection, package installation, CSO composition,
verification, and protected course environments. It does **not** perform
interactive `gh auth login`, change Git user identity, or upgrade the Ubuntu
release/Python minor.

### Deployment scope

| Platform | Status | GUI/editor |
| --- | --- | --- |
| WSL2 Ubuntu 24.04 | Experimental, needs host test | VS Code + WSL extension on Windows |
| Multipass Ubuntu 24.04 AMD64 | Experimental, needs host test | Headless CLI |
| Multipass Ubuntu 24.04 ARM64 | Experimental, needs Apple Silicon test | Headless CLI |
| Windows Sandbox | Existing separate Windows test profile | Native Windows desktop |
| Vagrant | Placeholder, intentionally unimplemented | None |

The canonical schema is `GC-STEM/.github/schemas/manifest.schema.json`. New
Ubuntu deployment profiles are declared in `.config/soe_manifest.json` and
selected by `soe.py --deployment`; no duplicate package list is maintained.
