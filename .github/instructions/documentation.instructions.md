---
applyTo: "README.md,docs/**,scripts/README.md,.devcontainer/README.md,.github/ci/README.md"
---

# Atlas documentation

Supplement the [root agent guide](../../AGENTS.md) and
[repository instructions](../copilot-instructions.md) with these practices
for Atlas's technical references, setup guidance, and educational materials.

## Accuracy and ownership

- Describe Atlas as the shared STEM Standard Operating Environment (SOE),
  shared automation, and related libraries. Course-specific overlays (CSOs),
  assignments, grading requirements, and student work belong to their
  respective repositories and official learning environment.
- Use [README.md](../../README.md), the selected manifest, actual CLI behavior,
  and relevant workflow definitions to verify claims. Explain material
  inconsistencies without silently inventing a policy or implementation.
- Keep supported functionality distinct from plans and placeholders.
  Preserve readiness and provisional notices until their documented
  conditions are met. A lifecycle script name or example command does not
  prove that a platform adapter has been implemented.
- Distinguish checked-out source, built image snapshots, published artifacts,
  and running environments. A documentation edit or new Git branch does not
  rebuild an existing environment or publish an image.
- Reference centrally owned community policies and manifest schemas with
  appropriate absolute links. Do not imply those files or workflows are
  automatically copied into Atlas or course repositories.

## Explain the environment clearly

- Expand SOE and CSO on first use and explain unfamiliar terms when useful.
  Identify whether instructions are for maintainers, faculty verification,
  course authors, or students; keep the next step appropriate to that role.
- Explain the documented baseline selection rule, while obtaining concrete
  OS and Python release values from the current manifest. Avoid changing a
  runtime target simply because a newer release exists.
- Distinguish the Atlas checkout from the selected course checkout.
  Identify where a command runs, which interpreter it uses, and which
  files or environment it can change.
- Preserve course-environment isolation and destination-specific settings.
  Explain runtime verification separately from editor-extension verification
  and assignment correctness.
- Keep account access, authentication, image publication, and Codespaces
  usage/cost decisions tied to their actual provider processes. Do not
  invent entitlements, promise unlimited free use, or describe a launcher
  as creating an environment when it only opens a creation page.

## Commands and examples

- State prerequisites, operating system, shell, working directory, selected
  repository, and expected result where relevant. Separate read-only
  planning/verification from setup, installation, updates, and other writes.
- Provide selectable commands and code with accurate language labels.
  Keep commands separate from transcripts and output; avoid copied shell
  prompts in runnable examples.
- Use visibly synthetic placeholders for unpublished images and example
  repositories. Explain what must be replaced and avoid presenting those
  examples as existing releases or verified destinations.
- Use platform-appropriate paths and interpreter names. Document Windows
  alternatives where Unix virtual-environment paths would be misleading.
- Keep examples aligned with the current schema and supported adapters.
  Schema acceptance alone does not prove provisioning, authorization,
  external-resource availability, or readiness for a required assignment.
- Protect credentials, personal identity, private course content, and student
  records in screenshots, logs, examples, and troubleshooting requests.

## Accessibility and review

- Use descriptive headings and links, readable paragraphs, and simple data
  tables with headers. Explain essential information without relying solely
  on color, emoji, screenshots, or an optional wiki.
- Provide meaningful alternative text and textual explanations for diagrams.
  Keep required instructions usable without Copilot or an AI subscription.
- Preserve current repository formatting and line endings. Technical
  documentation work does not authorize an infrastructure EOL migration or
  changes to the tested course-submission policy.
- Update affected navigation, anchors, examples, and cross-references
  together. Review rendered Markdown and relevant UI behavior when available.
- Use the documentation, shell-syntax, configuration, and link checks in the
  root guide and CI documentation. A syntax check does not execute a command;
  link success does not prove the remote content's accuracy or accessibility.
- Report actual checks and remaining limitations. Keep temporary findings
  in the completion report rather than permanent instruction text.
