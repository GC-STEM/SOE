---
applyTo: "scripts/**,.config/**"
---

# SOE and CSO runtime automation

Supplement the repository-wide guidance with these practices for the shared
environment manifest, resolver, launchers, and platform scripts. Read
[script guidance](../../scripts/README.md) and the
[Codespaces guide](../../.devcontainer/README.md) before changing behavior.

## Implemented behavior and ownership

- SOE owns the SOE manifest and shared runtime implementation. The canonical
  manifest schema belongs to `GC-STEM/.github/schemas/manifest.schema.json`;
  each selected course owns its `.config/cso_manifest.json` and coursework.
- Inspect actual entry points before using an apparent lifecycle script.
  `scripts/python/soe.py` implements resolution and the headless Codespaces
  adapter. The platform lifecycle files described as placeholders are not
  alternative working provisioning paths.
- Treat the schema's general capabilities separately from implemented
  adapters. The current resolver implements the selected Codespaces Linux
  container deployment; a declaration does not implement another platform,
  installer, managed asset, removal operation, or VM launcher.
- Preserve the manifest-selected Ubuntu and Python release policy. Do not
  recalculate or advance the concrete SOE target merely because a newer
  release exists. Major baseline changes require the documented qualification
  process; compatible installed versions must not be replaced incidentally.

## Resolution and schema handling

- Keep SOE root, selected workspace, and course root distinct. Use actual
  selected checkouts and explicit CLI arguments where ambiguity is possible.
  Avoid assumptions about home directories, clone names, or a faculty remote.
- Preserve SOE-only resolution without a course manifest and the requirement
  for a CSO manifest in a course workspace, including baseline-only courses.
  Keep explicit migration requirements for legacy manifest shapes.
- Preserve duplicate-JSON-key rejection, schema identity checks, meta-schema
  validation, instance validation, and useful error paths.
- Use `--schema` or `SOE_SCHEMA_PATH` with the actual canonical file for
  offline or unpublished-schema checks. An invalid explicit path must fail;
  do not silently fall back to a different source or maintain a second schema
  inside SOE. Default resolution can fetch the canonical published schema.
- Preserve deep-copy composition before deployment filtering. Duplicate IDs,
  unknown references, unauthorized or overlapping overrides, unsupported
  applicable adapters, and missing applicable dependencies are failures.
  Keep baseline override permissions and course eligibility checks intact.
- Keep requiredness conditional on applicability and preserve dependency
  closure. Filtering is not authorization to remove installed components.
- Preserve path containment, resolved-path and symlink checks, distinct course
  environment directories, and conflict detection for managed settings.

## Mutation and isolation

- Use `plan`, verification, and `devcontainer --check` for inspection where
  appropriate. They do not provision packages, although schema resolution may
  require network access unless an explicit local schema is selected.
- `install-system`, `setup`, and devcontainer generation without `--check`
  change their targets. Execute them only when those effects are within the
  task. Preserve preflight validation before package or workspace mutation.
- Keep system installation root-only and course setup under the development
  user. Preserve noninteractive sudo, provider authentication boundaries,
  and argument-list subprocess calls. Startup must not initiate login.
- Keep shared automation dependencies isolated from course dependencies.
  Install course Python packages through the declared course environment's
  interpreter, never global pip or another course's environment.
- Preserve declared sources, package identifier validation, compatible-version
  checks, and explicit failures for incompatible existing packages or
  interpreters. Do not delete environments or force upgrades as a generic fix.
- Modify only selected managed workspace settings, respecting merge policies
  and unrelated user values. Avoid personal Git identity and global editor
  configuration changes. Keep credentials out of manifests and logs.
- Preserve destination formatting and the tested course-submission EOL policy
  when producing course-bound files; configuration metadata alone does not
  establish the bytes of a submitted artifact.

## Verification

- Install the declared automation and CI dependencies into the intended test
  environment. Run the relevant resolver tests with
  `python -m unittest discover -s .github/ci -p test_soe.py -v`.
  Set `SOE_SCHEMA_PATH` to the selected canonical file for reproducible offline
  tests. Use synthetic course fixtures and mocked external effects.
- `python scripts/python/soe.py plan --mode soe` inspects the SOE plan;
  `python scripts/python/soe.py devcontainer --mode soe --check` checks generated
  configuration drift. Run from the SOE root with dependencies and the
  intended schema source available.
- Add behavior tests for changed composition, selectors, override permissions,
  paths, isolation, versions, and failure handling. Documentation-only changes
  do not require new resolver tests.
- Separate mocked resolver results from real container qualification, editor
  attachment, and assignment tests. Report skipped or unavailable checks and
  avoid claiming support or institutional approval from schema validity alone.
