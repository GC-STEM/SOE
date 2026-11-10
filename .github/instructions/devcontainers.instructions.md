---
applyTo: ".devcontainer/**,scripts/python/devcontainer_config.py,scripts/python/launch_codespaces.py,.vscode/extensions.json"
---

# Devcontainers and Codespaces

Apply these practices to container definitions, generated editor configuration,
and Codespaces launch behavior. Read the
[Codespaces guide](../../.devcontainer/README.md) and applicable runtime
instructions before editing.

## Runtime model

- Preserve the headless SOE model. The current implemented container target is
  Linux AMD64; native ARM64, desktop Docker, VM launchers, and other planned
  deployments require their own implementation and qualification.
- Keep the concrete Ubuntu and Python selections aligned across the SOE
  manifest, Dockerfile, generated configuration, tests, and documentation.
  Moving tags and current release dates must not advance the baseline
  automatically. Distinguish patch maintenance from a reviewed baseline change.
- Keep the build-time SOE snapshot and automation under `/opt/gc-stem/soe`
  distinct from the selected workspace. Runtime setup must not silently fetch
  or switch SOE revisions. Rebuild when the bundled requirements change.
- Preserve the canonical schema source in `GC-STEM/.github`. The generated
  image dependency under `/opt/gc-stem/schema` is not a second maintained
  source. Publish schema changes before builds that require them; use the
  resolver's explicit schema selection for local unpublished-schema tests.

## Lifecycle and generated configuration

- Preserve root image provisioning followed by a non-root `vscode` development
  account. Keep shared automation in its dedicated runtime environment and
  course packages in their declared isolated course environments.
- Preserve the lifecycle distinction: creation performs setup, startup runs
  read-only runtime verification, and attachment additionally checks the
  managed editor extensions. Startup must not upgrade packages or launch login.
- Keep generated configuration consistent with `devcontainer_config.py` and
  resolved requirements. Check drift with
  `python scripts/python/soe.py devcontainer --mode soe --check` from SOE,
  using the intended schema source and installed automation dependencies.
- Course repositories need their own committed devcontainer configuration;
  they do not inherit SOE's files. Course generation requires the published
  SOE image reference documented by the project. Use an immutable image
  reference rather than inventing a registry artifact or publication workflow.
- Keep the SOE extension set aligned with `.vscode/extensions.json` and the
  manifest. Preserve legitimate CSO additions and the selected course
  interpreter path. Update generator expectations and tests with changes.
- Preserve workspace-scoped settings and provider-managed editor behavior.
  Avoid baking credentials, personal Git identity, or global user settings
  into images or generated configuration.

## Checkout identity and launch behavior

- Derive Codespaces owner/repository from the selected checkout's validated
  GitHub origin and use its selected branch. A detached checkout requires an
  explicit branch. Never substitute a template, faculty, or SOE identity
  for the destination course repository.
- Preserve origin validation, branch validation, required extension checks,
  and devcontainer availability checks before producing a launch URL.
- Use the launcher's `--print-url` option when inspecting behavior without
  opening a browser. Preserve the GitHub creation-page step: generating or
  opening a URL must not automatically create a billable codespace, sign in,
  push changes, or change repository permissions.
- Explain that launch uses published branch contents. Local uncommitted or
  unpushed work is not transferred by the launcher. Access, available machines,
  and usage funding remain subject to GitHub and institutional arrangements.

## Local mounts and builds

- Preserve the distinction between host paths, container paths, and Codespaces
  workspace mounts. Local Compose binds the host's `Repos` directory to
  `/home/vscode/Repos`; changes there affect host files.
- Keep the documented HOME/USERPROFILE resolution and explicit existing-host
  directory requirement. Do not assume the selected checkout lives there or
  automatically move repositories to satisfy a mount.
- Preserve the smoke-test checkout's read-only bind mount. Use temporary course
  fixtures for mutation tests rather than real student repositories.
- Follow current EOL and binary rules. A Linux image does not justify an
  unrelated repository-wide line-ending conversion.

## Qualification

- For generator or launcher logic, run the relevant `test_soe.py` tests with
  declared dependencies and an intentional schema source. Check generated
  configuration drift and SOE extension alignment.
- For Dockerfile or lifecycle changes, use the documented image-build and
  container smoke procedure when available. It performs real provisioning;
  distinguish those results from syntax checks and mocked unit tests.
- Keep coverage for SOE-only resolution, CSO composition, non-root operation,
  compatible Python, package isolation, preservation of user settings, repeated
  setup, and destination launch identity.
- Real editor-extension verification needs an attached editor. Runtime checks
  do not verify that installation, and environment checks do not replace the
  course's actual assignment tests.
- Report Docker, network, architecture, schema, or hosted-editor limitations
  honestly. Do not claim a container was built or a Codespace qualified from
  configuration parsing or generated-file comparison alone.
