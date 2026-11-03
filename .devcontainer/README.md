# Codespaces SOE

GitHub Codespaces is the default devcontainer for emergency student access
and faculty verification of course code. The image follows current Ubuntu
LTS − 1 and that release's default CPython minor version, the approved target
for Codio Boxes and VMs. It includes manifest-selected command-line tools
and provider-managed VS Code extensions. It does not run a Linux desktop.
The Codio deployment remains the primary overall reference.

SOE extension identifiers match the `recommendations` list in
`.vscode/extensions.json` on every platform. CI checks that alignment
and the generated Codespaces configuration. CSOs may add course extensions.

Current Ubuntu LTS − 1 means the Ubuntu LTS immediately preceding the
latest LTS, paired with its default Python minor version. The SOE manifest
records the concrete releases. Patch updates are allowed within those
lines. A different LTS or Python minor requires a reviewed, qualified SOE
release; moving `latest` tags do not select the baseline.

Rebuild existing local containers and Codespaces to use the new image.
Recreate course virtual environments with the manifest-selected Python
interpreter and reinstall their declared packages when they were created
using another Python minor.
The image update does not migrate existing Codio provider environments.

## Open the environment

Push the implementation and its configuration to the branch you intend to
use. On GitHub, select that branch, choose **Code > Codespaces**, and create
a codespace using the default configuration. GitHub confirms repository
access, available machines, and the account responsible for usage. The
repository does not grant access or promise unlimited free usage.

For a local launcher, select the CPython interpreter required by the SOE
manifest and make sure `python` invokes it. Install the shared automation
dependencies into an isolated environment, then run from the selected
checkout:

```bash
python -m venv .venv
.venv/bin/python -m pip install -r .config/requirements-automation.txt
.venv/bin/python scripts/python/launch_codespaces.py --print-url
```

On Windows, use `.venv\Scripts\python.exe` in place of `.venv/bin/python`.
Omit `--print-url` to open the creation page. The launcher derives the
owner/repository from this checkout's GitHub `origin` and uses its current
branch. A detached checkout requires `--branch`. Local uncommitted or
unpushed changes are not transferred to GitHub by this command.

The launcher never creates a billable codespace without GitHub's creation
page. It never signs in, changes repositories, or pushes local changes.

## Lifecycle and verification

The Dockerfile installs the SOE from the bundled manifest. Image provisioning
uses root; the editor, terminal, course setup, and course virtual environments
use the `vscode` development account. Course system-package additions use
noninteractive sudo. Credentials and personal Git identity are not baked in.

Creation runs course setup once. Startup runs read-only runtime verification.
Editor attachment additionally verifies the managed VS Code extension list.
Starting the environment does not upgrade packages or launch authentication.

Run an explicit check inside the container:

```bash
/opt/gc-stem/runtime/bin/python /opt/gc-stem/atlas/scripts/python/soe.py verify
/opt/gc-stem/runtime/bin/python /opt/gc-stem/atlas/scripts/python/soe.py verify --editor
```

The editor check requires an attached VS Code session. The runtime check does
not claim to verify editor extensions. Faculty should use the assignment's
CSO and run its actual tests in addition to environment verification.

The image contains a build-time SOE snapshot and matching automation under
`/opt/gc-stem/atlas`. Rebuild after changing shared SOE requirements; setup
does not fetch a different Atlas checkout or silently change that snapshot.

## Course overlays

Schema 3.2 uses `.config/soe_manifest.json` in Atlas and
`.config/cso_manifest.json` in each course. It uses `manifest_type: "soe"`,
`configuration_kind: "soe"` or `"cso"`, and `capability_bindings`. Legacy
manifest shapes must be migrated explicitly before using this resolver.

Every course, including an SOE-only course, declares a CSO manifest:

```json
{
  "schema_version": "3.2",
  "manifest_type": "course",
  "course": {
    "course_id": "CS-101",
    "course_title": "Example course",
    "environment_name": "Example CSO",
    "repository_name": "example-course"
  },
  "baseline": {
    "path": "${ATLAS_ROOT}/.config/soe_manifest.json",
    "baseline_id": "stem_computing_baseline"
  },
  "control": {
    "status": "draft",
    "source_repository": "https://github.com/GC-STEM/example-course"
  },
  "additions": {},
  "overrides": []
}
```

Add new platform support packages through `additions.platform_extensions`.
Add language packages with a declared `python_venv` course environment and
`python_venv_package` bindings. These install through the course environment's
interpreter, never global pip. Dependency resolution happens after SOE/CSO
composition and deployment filtering. Duplicate IDs, missing dependencies,
unauthorized overrides, and unsupported adapters are errors before setup.

The implementation supports APT packages from the configured Ubuntu/GitHub
CLI repositories, named PyPI packages in course virtual environments,
provider-managed editor/extensions, and workspace VS Code JSON settings.
Other assets, removal operations, sources, and installers require an explicit
adapter implementation; they are not silently skipped.

Course repositories need their own `.devcontainer/devcontainer.json`.
They do not inherit Atlas configuration automatically. After publishing an
SOE image to the chosen registry, generate a course configuration from its
resolved requirements, supplying that image's immutable reference:

```bash
python /path/to/atlas/scripts/python/soe.py devcontainer \
  --atlas-root /path/to/atlas --workspace /path/to/course \
  --image registry.example/soe@sha256:REPLACE_WITH_PUBLISHED_DIGEST
```

Commit the generated course configuration. Regenerate and rebuild after
changing course extensions. Image publication is separate from this
repository's Codespaces implementation; no DockerHub artifact is assumed.

## Local Docker build and launch

The local Compose configuration uses the headless SOE image and maps the
host's `$HOME/Repos` to `/home/vscode/Repos`, which is `~/Repos` for the
container's `vscode` user. The shell starts in that directory. Changes made
there are written to the host's repositories.

Create the host directory if needed:

```bash
mkdir -p "$HOME/Repos"
```

On the host, run this command from the Atlas checkout to build the image
and open an interactive container shell:

```bash
docker compose -f .devcontainer/compose.local.yaml run --build --rm soe bash
```

Compose uses the host's `HOME`, with `USERPROFILE` as the Windows fallback.
The source directory must already exist. On Windows PowerShell, create it
with `New-Item -ItemType Directory -Force "$HOME/Repos"` if needed, then use
the same Docker Compose command.

The Dockerfile prepares the container directory; the host bind mount is
applied when Compose starts the container. For a direct Docker launch after
building the local image:

```bash
docker run --rm -it \
  --mount "type=bind,source=$HOME/Repos,target=/home/vscode/Repos" \
  --workdir /home/vscode/Repos gc-stem-soe:local bash
```

## Local qualification

```bash
docker build -t gc-stem-soe:test -f .devcontainer/Dockerfile .
docker run --rm \
  --mount "type=bind,source=$PWD,target=/workspaces/atlas,readonly" \
  --workdir /workspaces/atlas gc-stem-soe:test \
  /opt/gc-stem/runtime/bin/python .github/ci/smoke_codespaces.py
```

The Codespaces workflow builds the image and checks SOE-only resolution,
course composition, approved Python compatibility, course package isolation,
repeated setup, and launcher identity. A GitHub-hosted editor attachment is
still needed to check the actual managed editor and extension installation.

The schema is maintained only in
`GC-STEM/.github/schemas/manifest.schema.json`. Atlas does not carry a
repository copy. The manifest's `$schema` reference points to that canonical
published file.

Local validation uses the published schema by default. To validate offline
or against unpublished schema changes, pass `--schema` with the actual file
in your selected `.github` checkout, or set `SOE_SCHEMA_PATH` to that file.
The resolver and launcher both support `--schema`; an invalid selected path
fails rather than silently switching to the network.

Image builds fetch the canonical published schema into
`/opt/gc-stem/schema/manifest.schema.json`, outside the Atlas checkout, and
set `SOE_SCHEMA_PATH` to it. This is a generated runtime dependency, not a
second maintained source. The built environment can validate offline.
Publish schema changes in `.github` before building a container that needs
them; rebuilding the image retrieves the current published schema.

The first qualified container architecture is Linux AMD64. Native ARM64 and
the optional Xfce Docker desktop remain separate work. VM launchers remain
disabled, and Vagrant is optional. Development status does not imply
institutional approval of a release or its funding arrangements.
