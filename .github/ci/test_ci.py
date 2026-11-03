"""Regression tests for CI failure detection and safe documentation checks."""

from __future__ import annotations

import functools
import http.server
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

from check_readme_commands import blocks, syntax_check
from check_repository import ROOT, check_eol, validate

LYCHEE = os.environ.get("LYCHEE_TEST_EXECUTABLE") or shutil.which("lychee")


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        subprocess.run(
            ["git", "init", "-q", str(self.root)],
            check=True,
            capture_output=True,
        )
        self.write(".gitattributes", "*.py text eol=crlf\n*.json text eol=lf\n")
        self.write(
            ".editorconfig",
            "root = true\n[*.py]\nend_of_line = crlf\n"
            "[*.json]\nend_of_line = lf\n",
        )
        self.write(
            ".vscode/settings.json", '{"[python]": {"files.eol": "\\r\\n"}}'
        )
        self.policy = {
            "required_files": [".gitattributes", ".editorconfig"],
            "ide_samples": {"python": "example.py"},
        }
        self.stage()

    def write(self, name, source):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
        return path

    def stage(self):
        subprocess.run(
            ["git", "add", "."], cwd=self.root, check=True, capture_output=True
        )

    def test_valid_baseline(self):
        self.assertEqual(validate(self.root, self.policy), ([], []))

    def test_missing_required_file(self):
        self.policy["required_files"].append("LICENSE")
        errors, _ = validate(self.root, self.policy)
        self.assertTrue(any("LICENSE" in error for error in errors))

    def test_editor_policy_drift(self):
        self.write(".editorconfig", "root = true\n[*]\nend_of_line = lf\n")
        errors, _ = validate(self.root, self.policy)
        self.assertTrue(any("EoL policy mismatch" in error for error in errors))

    def test_ide_policy_conflict(self):
        errors, _ = check_eol(
            self.root, self.policy, {"[python]": {"files.eol": "\n"}}
        )
        self.assertTrue(
            any("VS Code EoL conflicts" in error for error in errors)
        )

    def test_ide_defaults_warn(self):
        errors, warnings = check_eol(self.root, self.policy, {})
        self.assertFalse(errors)
        self.assertTrue(any("safeguard" in warning for warning in warnings))

    def test_compound_override_conflict(self):
        errors, _ = check_eol(
            self.root, self.policy, {"[python][markdown]": {"files.eol": "\n"}}
        )
        self.assertTrue(errors)

    def test_exact_git_exception_overrides_extension(self):
        self.write(
            ".gitattributes",
            "*.py text eol=crlf\n*.json text eol=lf\nspecial.py text eol=lf\n",
        )
        self.write(
            ".editorconfig",
            "root = true\n[*.py]\nend_of_line = crlf\n"
            "[*.json]\nend_of_line = lf\n[special.py]\nend_of_line = lf\n",
        )
        self.stage()
        self.assertEqual(validate(self.root, self.policy), ([], []))

    def test_jsonc_comments_and_trailing_comma(self):
        self.write(
            ".vscode/settings.json",
            '// comment\n{"[python]": {"files.eol": "\\r\\n"},}\n',
        )
        self.assertEqual(validate(self.root, self.policy), ([], []))

    def test_invalid_json_is_error(self):
        self.write(".vscode/settings.json", '{"unterminated": ')
        errors, _ = validate(self.root, self.policy)
        self.assertTrue(
            any("invalid configuration" in error for error in errors)
        )

    def test_empty_workflow_is_error(self):
        self.write(".github/workflows/empty.yml", "")
        self.stage()
        errors, _ = validate(self.root, self.policy)
        self.assertTrue(
            any("Empty/invalid workflow" in error for error in errors)
        )

    def test_write_permissions_are_error(self):
        self.write(
            ".github/workflows/unsafe.yml",
            "name: Unsafe\non: push\npermissions: write-all\n"
            "jobs:\n  test:\n    runs-on: ubuntu-latest\n    steps: []\n",
        )
        self.stage()
        errors, _ = validate(self.root, self.policy)
        self.assertTrue(any("contents: read" in error for error in errors))

    def test_action_requires_sha(self):
        self.write(
            ".github/workflows/unsafe.yml",
            "name: Unsafe\non: push\npermissions:\n  contents: read\n"
            "jobs:\n  test:\n    runs-on: ubuntu-latest\n"
            "    steps:\n      - uses: actions/checkout@v7\n",
        )
        self.stage()
        errors, _ = validate(self.root, self.policy)
        self.assertTrue(any("full SHA" in error for error in errors))

    def test_empty_issue_config_warns(self):
        self.write(".github/ISSUE_TEMPLATE/config.yml", "")
        self.stage()
        errors, warnings = validate(self.root, self.policy)
        self.assertFalse(errors)
        self.assertTrue(any("Empty configuration" in item for item in warnings))


@unittest.skipUnless(shutil.which("bash"), "Bash is required.")
class CommandTests(unittest.TestCase):
    def test_invalid_shell_syntax(self):
        self.assertIsNotNone(
            syntax_check("bash", 'if true; then\necho "missing fi"\n')
        )

    def test_documentation_is_not_executed(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "must-not-exist"
            self.assertIsNone(syntax_check("bash", f'touch "{marker}"\n'))
            self.assertFalse(marker.exists())

    def test_tilde_fence_and_transcript_labels(self):
        result = blocks("~~~bash\necho ok\n~~~\n\n```console\n$ echo ok\n```\n")
        self.assertEqual([item[1] for item in result], ["bash", "console"])

    def test_unclosed_fence_fails(self):
        with self.assertRaises(ValueError):
            blocks("```bash\necho ok\n")


@unittest.skipUnless(LYCHEE, "Install Lychee to run link integration tests.")
class LinkTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        subprocess.run(
            ["git", "init", "-q", str(self.root)],
            check=True,
            capture_output=True,
        )
        (self.root / ".github/ci").mkdir(parents=True)
        (self.root / ".github/ci/lychee.toml").write_text(
            'hidden = true\ninclude_fragments = "anchor-only"\n'
            "no_progress = true\nmax_retries = 0\ntimeout = 2\n",
            encoding="utf-8",
        )
        self.readme = self.root / "README.md"
        self.readme.write_text("# Home\n", encoding="utf-8")
        (self.root / ".github/target.md").write_text(
            "# Existing Heading\n", encoding="utf-8"
        )

    def run_links(self, mode="internal"):
        subprocess.run(
            ["git", "add", "."], cwd=self.root, check=True, capture_output=True
        )
        result = subprocess.run(
            [
                sys_executable(),
                str(ROOT / ".github/ci/check_links.py"),
                "--root",
                str(self.root),
                "--mode",
                mode,
                "--output",
                str(self.root / "report.md"),
                "--lychee",
                str(LYCHEE),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode, result.stdout + result.stderr

    def test_hidden_file_encoded_path_and_heading(self):
        (self.root / ".github/with space.md").write_text(
            "# Target\n", encoding="utf-8"
        )
        self.readme.write_text(
            "[heading](.github/target.md#existing-heading)\n"
            "[space](.github/with%20space.md#target)\n",
            encoding="utf-8",
        )
        code, output = self.run_links()
        self.assertEqual(code, 0, output)

    def test_missing_file_and_heading_fail(self):
        self.readme.write_text(
            "[missing](missing.md)\n[heading](.github/target.md#missing)\n",
            encoding="utf-8",
        )
        code, output = self.run_links()
        self.assertNotEqual(code, 0, output)

    def test_yaml_markdown_link_is_checked_and_cleaned(self):
        templates = self.root / ".github/ISSUE_TEMPLATE"
        templates.mkdir()
        (templates / "config.yml").write_text(
            "contact_links:\n  - url: https://example.com\n"
            '    about: "See [missing](missing.md)"\n',
            encoding="utf-8",
        )
        code, output = self.run_links()
        self.assertNotEqual(code, 0, output)
        self.assertFalse(list(templates.glob(".ci-links-*")))

    def test_external_http_good_and_missing_are_distinguished(self):
        class Handler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *_):
                pass

        handler = functools.partial(Handler, directory=str(self.root))
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}"
        # Keep missing local file in both runs: external job must ignore it.
        self.readme.write_text(
            f"[good]({url}/.github/target.md)\n[local](missing.md)\n",
            encoding="utf-8",
        )
        code, output = self.run_links("external")
        self.assertEqual(code, 0, output)
        self.readme.write_text(f"[404]({url}/missing)\n", encoding="utf-8")
        code, output = self.run_links("external")
        self.assertNotEqual(code, 0, output)


def sys_executable():
    """Return the interpreter running these tests."""
    import sys

    return sys.executable


if __name__ == "__main__":
    unittest.main()
