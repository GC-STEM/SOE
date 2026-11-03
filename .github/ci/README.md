# GC-STEM Core Continuous Integration

Continuous integration (CI) checks proposed repository changes automatically.
These checks protect shared standards and Core automation. Course assignment
tests and student assessment logic belong in the applicable course repository.

## Workflows

| Workflow | Checks | Runs |
| -------- | ------ | ---- |
| Core Validation | Required files, configuration syntax, EoL policy agreement, Python automation, regression tests, and GitHub Actions syntax | Push, pull request, or manual |
| Codespaces SOE | Current Ubuntu LTS − 1/default Python image build, resolver tests, and non-root course setup/isolation | Push, pull request, or manual |
| Documentation Command Syntax | Bash code-block syntax on Linux, macOS, and Windows Git Bash | Push, pull request, or manual |
| Internal Links | Local file, image, directory, and heading links | Push, pull request, manual, and weekly |
| External Links | HTTP/HTTPS destinations and supported heading anchors | Manual and weekly |

Both link workflows are scheduled for **Monday at 11:17 UTC**
(07:17 Eastern Daylight Time / 06:17 Eastern Standard Time).
Schedules use the default branch. Push these files to that branch and enable
GitHub Actions to activate the weekly checks. Scheduled runs may be delayed;
GitHub can disable public-repository schedules after 60 days without activity.

These workflows run only in GC-STEM/_core. Reusable scripts can support other
repositories, but course workflows require an intentional configuration review.

## Files and Responsibilities

* **core-policy.json:** Core's required-file manifest and representative IDE
  language samples. Keep repository-specific requirements here.
* **check_repository.py:** Reusable configuration and policy validator.
* **check_readme_commands.py:** Checks explicitly labeled Bash, sh, or zsh
  fenced blocks in tracked Markdown. The workflow checks Bash.
* **check_links.py:** Runs Lychee on tracked Markdown and HTML, including hidden
  directories. It also checks URLs and Markdown text in issue-template YAML.
* **lychee.toml:** Common link-check configuration and reviewed exceptions.
* **requirements.txt:** Pinned Core CI dependencies.
* **test_ci.py:** Regression tests for the validators, safe command syntax
  checking, and link failure detection.
* **test_soe.py:** SOE/CSO composition and Codespaces launcher regression tests.
* **smoke_codespaces.py:** Real container provisioning, course isolation,
  workspace-setting preservation, and repeated-setup qualification.

The former assignment starter checker and empty synchronization workflow have
been removed. Downstream synchronization remains unimplemented. Add it after
the approved exact-copy, managed-merge, and selected-copy rules are configured
and tested.

## What the Checks Verify

Repository validation parses JSON/JSONC, TOML, and YAML configuration.
GitHub Actions syntax receives a separate actionlint check. Workflow actions
must use full commit SHAs, read-only permissions, and checkout without
persisted credentials.

EoL checks compare resolved Git attributes with EditorConfig rules for each
explicit EoL pattern and tracked file. Recognized VS Code language settings
must agree when explicitly configured. Missing IDE defaults produce visible
warnings while the separate IDE configuration review remains pending.

The authority policy is .gitattributes, then .editorconfig, then compatible
IDE safeguards. It is not a runtime override chain. CI neither rewrites those
files nor establishes Brightspace or Turnitin compatibility by itself.

Shell checks validate syntax without executing documented commands. They do
not prove installation commands work or commands behave correctly. Transcript
blocks labeled console or shell, PowerShell examples, and indented or
nested fenced examples are outside this syntax check.

## Link Coverage and Results

The internal job makes no network requests. It checks relative and root-relative
repository paths and Markdown/HTML anchors. Wiki pages and absolute GitHub URLs
are remote destinations and are checked by the external job.

The external job makes fresh HTTP/HTTPS requests each run. It follows redirects,
retries failures twice, checks supported anchor fragments, and requires a
successful HTTP response. It does not accept timeouts, 403, 404, 429, or server
errors as successful verification.

Both jobs publish a report in the Actions run summary and retain a downloadable
report artifact for 14 days. Findings include their source files. YAML text is
temporarily converted beside its source for correct relative-link resolution;
temporary files are removed after the check.

Email addresses, example URLs inside code blocks, and the contents of linked
remote pages are not recursively checked. Authentication redirects can reach a
successful login page without verifying the protected content. JavaScript-built
anchors, bot protection, rate limits, and sign-in requirements may require
manual review.

There are **no initial URL exclusions**. Do not exempt all GitHub or SNHU links
or accept error status codes just to produce a green run. If a link cannot be
checked automatically, verify it manually, add a precise exception with its
reason in lychee.toml, and document how it will be reviewed.

## Run Locally

Use the Python interpreter selected by the SOE manifest for current Ubuntu LTS − 1, and Git, from the repository root. Ensure `python` invokes that interpreter:

```bash
python -m pip install -r .github/ci/requirements.txt
python .github/ci/check_repository.py
python .github/ci/check_readme_commands.py --shell bash
python -m ruff check --isolated --select E,F,I --line-length 80 .github/ci
python -m unittest discover -s .github/ci -p 'test_*.py' -v
```

Install Lychee **v0.24.2** to run the same link checks and integration tests:

```bash
python .github/ci/check_links.py --mode internal --output /tmp/internal-links.md
python .github/ci/check_links.py --mode external --output /tmp/external-links.md
```

Choose another report path on Windows. The scripts use Git's tracked-file list,
so stage newly added documentation before checking it. Link integration tests
run when Lychee is on PATH; other tests run without it.

Use the validator's --strict flag to treat review warnings as failures.
The standard workflow leaves those warnings visible without blocking unrelated
CI repairs.

## Maintaining CI

Propose shared-policy changes in _core. Keep approved legal text and branding
under their institutional approval processes. Do not distribute Core's required
file manifest or repository-specific workflow guards to courses unchanged.

Update dependency and action pins deliberately, run the regression tests, and
review the Actions results after pushing. Correct real broken links at their
sources. Existing community-documentation defects may cause the new link checks
to fail until those documents are repaired.

## References

* [GitHub Actions workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
* [Scheduled workflow events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
* [Lychee](https://github.com/lycheeverse/lychee)
* [actionlint](https://github.com/rhysd/actionlint)
* [EditorConfig](https://editorconfig.org/)
