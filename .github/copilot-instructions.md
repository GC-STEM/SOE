# Working in GC-STEM/atlas

Atlas maintains GC-STEM's Standard Operating Environment (SOE), shared
automation, and course-specific overlay (CSO) support. Its implemented
Codespaces path is a headless Linux environment. Preserve the documented
development status; implemented code is not proof of a qualified release,
institutional approval, or support for every platform described by the schema.

## Start with the owning resource

- Read [README.md](../README.md), [AGENTS.md](../AGENTS.md), and guidance
  relevant to the change. Use the applicable files under `instructions/`
  for runtime, devcontainer, CI, or documentation work.
- `.config/soe_manifest.json` owns the concrete shared environment declaration.
  `scripts/python/soe.py` resolves and provisions supported SOE/CSO plans;
  `devcontainer_config.py` generates editor configuration;
  `launch_codespaces.py` derives launch identity from the selected checkout.
- `.devcontainer/` defines the image, lifecycle, and local Compose behavior.
  `.github/ci/` and `.github/workflows/` own checks. `.vscode/` contains
  workspace settings, extension recommendations, and optional MCP configuration.
- Inspect scripts before treating them as implemented entry points. Platform
  lifecycle placeholders and software-lifecycle documents under `docs/` do
  not establish working features or approved requirements.
- The canonical manifest schema belongs to
  `GC-STEM/.github/schemas/manifest.schema.json`. Atlas owns its SOE and
  implementation; selected courses own their CSO manifests and coursework.
  `crs000` owns master course templates. Wikis are maintained separately.

## Runtime and configuration boundaries

- Use the SOE manifest's concrete Ubuntu/Python selections and documented
  release policy. Do not advance the baseline from the date or a moving tag.
  Keep compatible-version rules and course grading-runtime constraints intact.
- Keep Atlas root and the selected workspace distinct. Course operations use
  the actual course checkout, not an inherited template identity or an assumed
  home-directory layout. Every course declares its own CSO, including SOE-only
  courses; Atlas SOE-only resolution does not require a course manifest.
- Preserve schema validation, duplicate-key rejection, composition before
  filtering, approved override boundaries, reference and dependency checks,
  path containment, and isolated course environments.
- Use an explicit `--schema` or `SOE_SCHEMA_PATH` for offline or unpublished
  schema work. A missing explicit source must fail without network fallback.
  Do not add a maintained schema copy to Atlas; an image's generated schema
  dependency is separate from the source of truth.
- Distinguish inspection from mutation. Planning and verification do not
  provision packages; setup, system installation, generated-file writes,
  image builds, and smoke qualification can change their targets.
  Perform those effects only within the task's scope. Schema lookup may
  require network access even during inspection.
- Install course packages only through their declared isolated environments.
  Preserve unrelated workspace settings, credentials, personal Git identity,
  and global editor settings. Runtime startup must not silently update
  packages, switch Atlas revisions, or initiate authentication.

## Changes and communication

- Keep changes focused and preserve existing work. Verify discrepancies
  against current scripts, manifests, and workflows; report temporary
  findings separately from permanent instructions.
- Use clear language and accessible examples for maintainers, faculty, and
  students. Preserve official course authority and alternatives to GitHub.
  Do not invent academic rules, access, funding, or institutional approvals.
- Follow applicable shared community guidance in
  [GC-STEM/.github](https://github.com/GC-STEM/.github). These defaults are
  not physically included in clones. Agent instructions, workflows, licenses,
  and editor configuration require intentional adoption in each repository.
- Follow `.gitattributes`, `.editorconfig`, and relevant formatter settings.
  Markdown/Python currently use CRLF; JSON/YAML and Unix scripts use LF.
  Preserve the tested course-submission policy and destination-specific
  output rules. EOL migration is separately scoped work.
- Optional GitHub MCP tools provide read-only context and documentation
  through the signed-in account. They do not provision the SOE, grant access,
  or make AI tools a course requirement.

## Validation and completion

Use [CI guidance](ci/README.md), actual workflows, and the root agent guide
for commands and prerequisites. Use the manifest-selected interpreter;
current hosted CI uses Python 3.12. Install pinned CI dependencies into the
intended test environment before checks.

- Configuration: run `python .github/ci/check_repository.py`. Atlas checks
  Git/EditorConfig/IDE EOL agreement; do not copy another repository's policy.
- Documentation: check relevant Bash fences and internal links; verify
  changed external destinations when available. Syntax is not functionality.
- Runtime/CI code: run configured lint and behavioral tests. Full
  `test_*.py` discovery includes SOE tests and needs an intentional canonical
  schema source. Ensure Bash/Lychee prerequisites before claiming their
  corresponding coverage; report skipped tests.
- Container changes: use the documented Docker qualification when in scope.
  Mocked tests do not establish real container or editor-attachment results.
- Preserve workflow permissions, action SHA pins, checkout credential
  controls, and intended guards. Avoid weakening checks to obtain a pass.

Scans use `git ls-files`; stage only intended new files when needed, preserving
existing staged work. Inspect the final diff. Report changed behavior, checks
passed/failed/skipped/unavailable, pre-existing failures, and consumer impact.
