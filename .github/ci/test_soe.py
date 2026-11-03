"""Regression tests for SOE/CSO resolution and Codespaces launch identity."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "python"))

from check_dev_env import check_extensions  # noqa: E402
from devcontainer_config import configuration  # noqa: E402
from launch_codespaces import github_identity, launch_url  # noqa: E402
from launch_codespaces import main as launch_main  # noqa: E402
from soe import (  # noqa: E402
    CANONICAL_SCHEMA_URI,
    ConfigurationError,
    compose,
    environment_path,
    load_plan,
    load_schema,
    make_plan,
    read_json,
    validate,
    verify,
    version_ok,
)
from soe import main as soe_main  # noqa: E402


def course_manifest():
    return {
        "schema_version": "3.2",
        "manifest_type": "course",
        "course": {
            "course_id": "CS-101",
            "course_title": "Test Course",
            "environment_name": "Test CSO",
            "repository_name": "test-course",
        },
        "baseline": {
            "path": "${ATLAS_ROOT}/.config/soe_manifest.json",
            "baseline_id": "stem_computing_baseline",
        },
        "control": {
            "status": "draft",
            "source_repository": "https://github.com/GC-STEM/test-course",
        },
        "additions": {},
        "overrides": [],
    }


def python_overlay():
    course = course_manifest()
    course["course_environments"] = {
        "course_python": {
            "kind": "python_venv",
            "path": "${COURSE_ROOT}/.venv",
            "runtime_capability_id": "programming_language_runtime",
        },
    }
    course["additions"] = {
        "platform_extensions": {
            "ubuntu_headless": {
                "capability_bindings": {
                    "test_runner": {
                        "product_id": "pytest",
                        "required": True,
                        "installation_scope": "course_environment",
                        "installer_adapter_id": "python_venv_package",
                        "source_id": "pypi",
                        "package_identifier": "pytest",
                        "environment_id": "course_python",
                        "version_rule_override": {
                            "comparison": "exact",
                            "value": "8.4.2",
                        },
                        "verification": {
                            "adapter_id": "python_venv_package",
                            "package_identifiers": ["pytest"],
                        },
                    }
                },
            }
        }
    }
    return course


class ResolverTests(unittest.TestCase):
    def setUp(self):
        self.soe = read_json(ROOT / ".config/soe_manifest.json")
        self.schema = load_schema()

    def plan(self, course=None, soe=None):
        return make_plan(
            compose(soe or self.soe, course, self.schema),
            self.schema,
            ROOT,
            "github_codespaces",
        )

    def test_headless_soe_excludes_desktop_and_vagrant(self):
        plan = self.plan()
        self.assertEqual(plan["configuration_kind"], "soe")
        self.assertEqual(plan["profile"]["os_release_id"], "24.04")
        self.assertTrue({"git", "gh", "python3-venv"} <= set(plan["packages"]))
        self.assertFalse(
            {"code", "vagrant", "xfce4", "xclip"} & set(plan["packages"])
        )

    def test_schema_is_valid(self):
        Draft202012Validator.check_schema(self.schema)

    def test_changed_source_configuration_is_not_ignored(self):
        self.soe["software_sources"]["pypi"]["base_uri"] = (
            "https://example.com/simple"
        )
        with self.assertRaisesRegex(ConfigurationError, "source configuration"):
            self.plan()

    def test_baseline_only_course(self):
        self.assertEqual(
            self.plan(course_manifest())["configuration_kind"], "cso"
        )

    def test_course_venv_binding(self):
        plan = self.plan(python_overlay())
        self.assertIn("course_python", plan["environments"])
        self.assertNotIn("pytest", plan["packages"])
        generated = configuration(plan, image="example/soe:test")
        self.assertEqual(
            generated["customizations"]["vscode"]["settings"][
                "python.defaultInterpreterPath"
            ],
            "${workspaceFolder}/.venv/bin/python",
        )

    def test_missing_course_manifest_is_not_silently_soe(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ConfigurationError):
                load_plan(ROOT, Path(directory))

    def test_duplicate_addition_rejected(self):
        course = course_manifest()
        course["additions"] = {
            "products": {"git": copy.deepcopy(self.soe["products"]["git"])}
        }
        with self.assertRaisesRegex(ConfigurationError, "Duplicate catalog"):
            self.plan(course)

    def test_unauthorized_override_rejected(self):
        course = course_manifest()
        course["overrides"] = [
            {
                "permission_id": "not_granted",
                "target": "/products/git",
                "reason": "Test override",
                "value": self.soe["products"]["git"],
            }
        ]
        with self.assertRaisesRegex(ConfigurationError, "Unauthorized"):
            self.plan(course)

    def test_filtered_dependency_rejected(self):
        self.soe["capabilities"]["version_control_system"]["applies_to"] = {
            "session_types": ["headless"]
        }
        with self.assertRaisesRegex(ConfigurationError, "dependency"):
            self.plan()

    def test_unknown_selector_rejected(self):
        self.soe["capabilities"]["vm_orchestration"]["applies_to"] = {
            "deployment_profile_ids": ["missing_profile"]
        }
        with self.assertRaisesRegex(
            ConfigurationError, "Unknown applicability"
        ):
            self.plan()

    def test_disabled_deployment_rejected(self):
        self.soe["deployment_profiles"]["github_codespaces"]["enabled"] = False
        with self.assertRaisesRegex(ConfigurationError, "disabled"):
            self.plan()

    def test_unknown_installer_rejected_before_execution(self):
        self.soe["platforms"]["ubuntu_headless"]["capability_bindings"][
            "version_control_system"
        ]["installer_adapter_id"] = "arbitrary_shell"
        with self.assertRaisesRegex(ConfigurationError, "Unsupported"):
            self.plan()

    def test_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"schema_version":"3.2","schema_version":"3.1"}')
            with self.assertRaisesRegex(ConfigurationError, "Duplicate JSON"):
                read_json(path)

    def test_legacy_schema_is_explicitly_rejected(self):
        self.soe["schema_version"] = "3.1"
        with self.assertRaises(ConfigurationError):
            validate(self.soe, self.schema)

    def test_environment_cannot_escape_workspace(self):
        with self.assertRaises(ConfigurationError):
            environment_path(ROOT, {"path": "${COURSE_ROOT}/../../outside"})

    def test_python_312_series_is_required_on_every_platform(self):
        rules = {"product": self.soe["products"]["python"]["version_rule"]}
        rules.update(
            {
                name: platform["capability_bindings"][
                    "programming_language_runtime"
                ]["verification"]["version_rule"]
                for name, platform in self.soe["platforms"].items()
            }
        )
        for name, rule in rules.items():
            with self.subTest(platform=name):
                for version in ("3.12.0", "3.12.3", "3.12.99"):
                    self.assertTrue(version_ok(version, rule))
                for version in ("3.10.12", "3.11.9", "3.13.0", "3.14.4"):
                    self.assertFalse(version_ok(version, rule))

    def test_all_linux_targets_use_ubuntu_2404(self):
        for name, platform in self.soe["platforms"].items():
            if platform["os"]["family"] == "linux":
                with self.subTest(platform=name):
                    self.assertEqual(
                        [
                            release["release_id"]
                            for release in platform["os"]["releases"]
                        ],
                        ["24.04"],
                    )
        for name, profile in self.soe["deployment_profiles"].items():
            platform = self.soe["platforms"][profile["platform_id"]]
            if platform["os"]["family"] == "linux":
                with self.subTest(deployment=name):
                    self.assertEqual(profile["os_release_id"], "24.04")

    def test_soe_extensions_match_workspace_recommendations(self):
        recommendations = read_json(ROOT / ".vscode/extensions.json")[
            "recommendations"
        ]
        self.assertEqual(len(recommendations), len(set(recommendations)))
        for platform_id, platform in self.soe["platforms"].items():
            with self.subTest(platform=platform_id):
                bindings = {
                    key: binding
                    for key, binding in platform["capability_bindings"].items()
                    if binding["installer_adapter_id"]
                    in {"vscode_extension", "devcontainer_extension"}
                }
                self.assertCountEqual(
                    [
                        binding["package_identifier"]
                        for binding in bindings.values()
                    ],
                    recommendations,
                )
                for key, binding in bindings.items():
                    self.assertTrue(binding["required"])
                    self.assertTrue(self.soe["capabilities"][key]["required"])

    def test_generated_configuration_matches_manifest(self):
        generated = configuration(self.plan())
        self.assertEqual(
            read_json(ROOT / ".devcontainer/devcontainer.json"),
            generated,
        )
        for hook in (
            "postCreateCommand", "postStartCommand", "postAttachCommand"
        ):
            with self.subTest(hook=hook):
                script = Path(generated[hook][1]).relative_to(
                    "/opt/gc-stem/atlas"
                )
                self.assertTrue((ROOT / script).is_file())

    def test_verify_is_read_only(self):
        plan = self.plan()
        with (
            patch("soe.check_host"),
            patch("soe.apt_installed", return_value=True),
            patch("soe.shutil.which", return_value="/usr/bin/python3"),
            patch("soe.run") as execute,
        ):
            execute.return_value.stdout = json.dumps(
                {
                    "version": "3.12.3",
                    "implementation": "CPython",
                }
            )
            verify(plan)
            for call in execute.call_args_list:
                command = call.args[0]
                self.assertNotIn("install", command)
                self.assertNotIn("sudo", command)

    def test_matching_version_from_other_interpreter_is_rejected(self):
        with (
            patch("soe.check_host"),
            patch("soe.apt_installed", return_value=True),
            patch("soe.shutil.which", return_value="/usr/bin/python3"),
            patch("soe.run") as execute,
        ):
            execute.return_value.stdout = json.dumps(
                {
                    "version": "3.12.3",
                    "implementation": "PyPy",
                }
            )
            with self.assertRaisesRegex(ConfigurationError, "CPython"):
                verify(self.plan())


class SchemaSourceTests(unittest.TestCase):
    def schema(self):
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": CANONICAL_SCHEMA_URI,
            "type": "object",
        }

    def test_explicit_canonical_file_takes_precedence(self):
        source = Path("selected/.github/schemas/manifest.schema.json")
        with (
            patch.dict(os.environ, {"SOE_SCHEMA_PATH": "other/schema.json"}),
            patch("soe.read_json", return_value=self.schema()) as read,
            patch("soe.read_published_schema") as fetch,
        ):
            self.assertEqual(load_schema(source), self.schema())
            read.assert_called_once_with(source)
            fetch.assert_not_called()

    def test_default_uses_published_canonical_schema(self):
        with (
            patch.dict(os.environ),
            patch(
                "soe.read_published_schema", return_value=self.schema()
            ) as fetch,
        ):
            os.environ.pop("SOE_SCHEMA_PATH", None)
            self.assertEqual(load_schema(), self.schema())
            fetch.assert_called_once_with()

    def test_missing_selected_file_does_not_fall_back_to_network(self):
        with (
            patch("soe.read_json", side_effect=FileNotFoundError),
            patch("soe.read_published_schema") as fetch,
        ):
            with self.assertRaises(FileNotFoundError):
                load_schema(Path("missing/schema.json"))
            fetch.assert_not_called()

    def test_other_schema_identity_is_rejected(self):
        with patch("soe.read_json", return_value={"$id": "other"}):
            with self.assertRaisesRegex(ConfigurationError, "canonical"):
                load_schema(Path("other/schema.json"))

    def test_atlas_has_no_repository_schema_copy(self):
        self.assertFalse((ROOT / ".config/manifest.schema.json").exists())


class EntryPointTests(unittest.TestCase):
    def test_resolver_defaults_to_atlas_root(self):
        with (
            patch.dict(os.environ),
            patch("soe.load_plan", return_value={}) as load,
            patch("sys.stdout"),
        ):
            os.environ.pop("ATLAS_ROOT", None)
            self.assertEqual(soe_main(["plan"]), 0)
            self.assertEqual(load.call_args.args[0], ROOT)

    def test_resolver_honors_configured_atlas_root(self):
        selected = ROOT / "selected-atlas"
        with (
            patch.dict(os.environ, {"ATLAS_ROOT": str(selected)}),
            patch("soe.load_plan", return_value={}) as load,
            patch("sys.stdout"),
        ):
            self.assertEqual(soe_main(["plan"]), 0)
            self.assertEqual(load.call_args.args[0], selected)

    def test_launcher_defaults_to_atlas_root(self):
        with (
            patch("launch_codespaces.launch_url") as launch,
            patch("launch_codespaces.webbrowser.open") as browser,
            patch("sys.stdout"),
            patch("sys.stderr"),
        ):
            launch.return_value = "https://codespaces.new/GC-STEM/atlas"
            self.assertEqual(launch_main(["--print-url"]), 0)
            self.assertEqual(launch.call_args.args[1], ROOT)
            browser.assert_not_called()

    def test_extensions_resolve_from_repository_configuration(self):
        with (
            patch("check_dev_env.shutil.which", return_value=None) as which,
            patch("sys.stdout"),
        ):
            self.assertTrue(check_extensions())
            which.assert_called_once_with("code")


class LauncherTests(unittest.TestCase):
    def test_github_remote_forms(self):
        for remote in (
            "https://github.com/GC-STEM/atlas.git",
            "git@github.com:GC-STEM/atlas.git",
            "ssh://git@github.com/GC-STEM/atlas.git",
        ):
            self.assertEqual(github_identity(remote), "GC-STEM/atlas")

    def test_credentials_and_other_hosts_rejected(self):
        for remote in (
            "https://github.com.evil.test/a/b",
            "https://secret@github.com/a/b",
            "https://github.com/a/b?token=secret",
            "git@gitlab.com:a/b",
        ):
            with self.assertRaises(ConfigurationError):
                github_identity(remote)

    def test_launch_uses_selected_repository_and_branch(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            (workspace / ".config").mkdir()
            (workspace / ".devcontainer").mkdir()
            (workspace / ".config/soe_manifest.json").write_text("{}")
            (workspace / ".devcontainer/devcontainer.json").write_text(
                (ROOT / ".devcontainer/devcontainer.json").read_text()
            )
            (workspace / ".devcontainer/Dockerfile").write_text(
                "FROM ubuntu:24.04\n"
            )
            for command in (
                ("init",),
                (
                    "remote",
                    "add",
                    "origin",
                    "git@github.com:student/assignment.git",
                ),
                ("symbolic-ref", "HEAD", "refs/heads/course/topic"),
            ):
                subprocess.run(
                    ["git", "-C", str(workspace), *command],
                    check=True,
                    capture_output=True,
                )
            self.assertEqual(
                launch_url(workspace, ROOT),
                "https://codespaces.new/student/assignment/tree/course%2Ftopic",
            )


if __name__ == "__main__":
    unittest.main()
