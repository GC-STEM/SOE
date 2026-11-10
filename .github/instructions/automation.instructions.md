---
applyTo: ".github/ci/**,.github/workflows/**,.config/requirements-automation.txt"
---

# SOE validation and CI

Supplement the [root agent guide](../../AGENTS.md) and
[repository instructions](../copilot-instructions.md) with these practices
for SOE validation, tests, workflows, and shared resolver dependencies.

## Scope and sources

- Read the affected scripts, tests, calling workflows, and
  [CI guide](../ci/README.md) before changing behavior. Use actual workflow
  definitions to establish triggers, guards, runtimes, and tool versions;
  report relevant stale documentation separately.
- SOE maintains SOE automation and its qualification. Course assignment
  tests and assessment rules belong to their course repositories.
  Organization community defaults belong to `GC-STEM/.github`.
- Keep repository-specific required files and IDE samples in
  `core-policy.json`. Keep CI dependencies and shared resolver dependencies
  consistent with their respective requirements files; avoid unrelated
  upgrades or importing course dependency requirements into the tooling.
- EOL agreement checks are active in the SOE validator. Preserve resolved
  Git attributes, EditorConfig, and applicable explicit IDE settings rather
  than copying `.github` repository's disabled EOL-check policy.
  Policy agreement does not establish final student submission bytes.

## Python and configuration checks

- Preserve strict JSON versus intended JSONC handling, TOML parsing, and
  safe YAML handling. Workflow YAML must keep `on` as a key; the current
  validator uses `BaseLoader` for that purpose. Avoid a blanket parser
  replacement that changes scalar or key interpretation.
- Treat configuration and documentation as data. Do not execute embedded
  expressions or documented commands to validate syntax.
- Reuse tracked-file discovery and explicit repository-root handling.
  Preserve hidden-file coverage and NUL-delimited Git output. Avoid broad
  scans through `.git`, virtual environments, generated files, or other
  checkouts.
- Use UTF-8, `pathlib`, subprocess argument lists, and explicit working
  directories. Preserve CLI options, useful diagnostics, failure status,
  warning/error distinctions, and the documented `--strict` behavior.
- Obtain effective EOL attributes through Git and editor properties through
  EditorConfig. Preserve exact-path and ordered pattern exceptions.
  Follow current formatting rules without an incidental EOL migration.

## Documentation and link validation

- Keep documented-command validation syntax-only: invoke the selected
  shell with `-n` without executing commands, substitutions, or redirections.
  Preserve precise language labels, supported fences, source line numbers,
  unclosed-fence errors, and bounded subprocess execution.
- Preserve `CI_TEST_SHELL` resolution and the Linux, macOS, and Windows Git
  Bash matrix. A syntax pass does not establish example functionality.
- Keep internal link checks offline and external checks limited to HTTP/HTTPS.
  Preserve tracked documentation and issue-template YAML coverage, correct
  source-relative resolution, temporary-file cleanup, and original source
  names in reports.
- Propagate Lychee failures. Preserve TLS verification, successful-response
  requirements, bounded requests and retries, and fresh results.
  Add only precise, documented exceptions after manual verification;
  maintain existing reviewed exceptions deliberately.
- Preserve useful Actions summaries and report artifacts on failure.
  Distinguish inaccessible authenticated content, rate limits, and bot
  protection from verified working or broken destinations.

## Workflow safeguards

- Preserve `permissions: {contents: read}`, full commit SHA pins for external
  actions, and `persist-credentials: false` for checkout. Do not introduce
  `pull_request_target`.
- Preserve intentional owner/repository guards, event coverage, concurrency,
  bounded job timeouts, and failure diagnostics. Do not substitute another
  repository's guard merely because it appears in a shared example.
- Treat pull-request content as untrusted data. Pass values as arguments or
  environment data instead of constructing executable shell text from them.
  Keep credentials and personal identity out of logs and build artifacts.
- Update associated checksums, compatible action inputs, version comments,
  and relevant documentation when a task changes pinned tools or actions.
- Keep the external-link workflow's manual/scheduled coverage explicit;
  an ordinary PR does not automatically receive that check.

## Tests and qualification

- Use the manifest/workflow-selected Python and pinned CI dependencies.
  SOE's configured Python checks cover both `.github/ci` and `scripts`;
  use the isolated Ruff settings from the workflows.
- Add focused behavioral regression coverage for changed code, including
  relevant rejection paths. Use temporary repositories, controlled fixtures,
  and local HTTP servers instead of live public sites where practical.
  Prose-only edits do not require new Python tests.
- Ensure Bash and workflow-pinned Lychee are available before claiming full
  corresponding regression coverage. Inspect and report skipped tests.
- Resolver tests also require the canonical schema. Use the documented
  published source or an explicitly selected canonical file through
  `SOE_SCHEMA_PATH`; record the source. Preserve tests proving that an
  explicitly missing selected file does not silently fall back to network.
- Distinguish unit/regression checks from container qualification.
  `smoke_codespaces.py` provisions real environments and checks isolation;
  run it through the container workflow for relevant runtime changes,
  rather than treating it as a harmless local documentation check.
- Follow the exact commands in current workflows and the root guide for
  repository validation, compile checks, Ruff, `unittest`, links, and
  actionlint. Include newly added files in tracked-file scans by staging
  only intended files when necessary, preserving existing work.
- Report passed, failed, skipped, and unavailable checks, distinguishing
  pre-existing defects and environmental limitations. Preserve validation
  coverage rather than disabling checks to obtain a passing result.
