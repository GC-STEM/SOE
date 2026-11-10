"""Resolve and provision the headless Codespaces SOE and course overlays."""

from __future__ import annotations

import argparse
import copy
import json
import os
import platform as host_platform
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any, TypedDict, cast
from urllib.request import urlopen

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError
from packaging.specifiers import SpecifierSet
from packaging.version import Version

CATALOGS = (
    "capabilities",
    "products",
    "software_sources",
    "provider_profiles",
    "platforms",
    "deployment_profiles",
    "lifecycle_workflows",
    "managed_settings",
    "managed_assets",
    "obsolete_components",
    "box_artifacts",
    "launch_profiles",
)
PACKAGE = re.compile(r"[a-z0-9][a-z0-9+.-]*(?::(?:amd64|arm64))?\Z")
EXTENSION = re.compile(r"[A-Za-z0-9-]+\.[A-Za-z0-9._-]+\Z")
PIP_PACKAGE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
CANONICAL_SCHEMA_URI = (
    "https://raw.githubusercontent.com/GC-STEM/.github/"
    "refs/heads/main/schemas/manifest.schema.json"
)
SOURCES = {
    "ubuntu_archive": "https://archive.ubuntu.com/ubuntu",
    "github_cli_packages": "https://cli.github.com/packages",
    "pypi": "https://pypi.org/simple",
    "vscode_marketplace": "https://marketplace.visualstudio.com",
    "github_codespaces": "https://github.com/features/codespaces",
}


JsonObject = dict[str, Any]


class Plan(TypedDict):
    """Stable outputs of the schema-validated SOE/CSO resolver."""

    configuration_kind: str
    workspace: str
    deployment: str
    platform: str
    profile: JsonObject
    packages: list[str]
    extensions: list[str]
    bindings: dict[str, JsonObject]
    environments: dict[str, str]
    settings: list[JsonObject]
    resolved: JsonObject


class LoadedPlan(Plan):
    """A plan with the selected schema source recorded by load_plan."""

    schema_path: str | None


class ConfigurationError(ValueError):
    """A configuration cannot be executed safely or completely."""


def require(condition: object, message: str) -> None:
    if not condition:
        raise ConfigurationError(message)


def unique_object(pairs: list[tuple[str, Any]]) -> JsonObject:
    result: JsonObject = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: str | Path) -> Any:
    return json.loads(
        Path(path).read_text(encoding="utf-8-sig"),
        object_pairs_hook=unique_object,
    )


@lru_cache(maxsize=1)
def read_published_schema() -> Any:
    """Read the canonical published schema once per invocation."""
    try:
        with urlopen(CANONICAL_SCHEMA_URI, timeout=60) as response:
            return json.loads(
                response.read().decode("utf-8-sig"),
                object_pairs_hook=unique_object,
            )
    except (OSError, ValueError) as error:
        raise ConfigurationError(
            "Cannot read the canonical schema. Use --schema or "
            "SOE_SCHEMA_PATH to select its file in the .github checkout."
        ) from error


def load_schema(schema_path: str | Path | None = None) -> JsonObject:
    """Use an explicitly selected canonical file or its published URL."""
    source = schema_path or os.environ.get("SOE_SCHEMA_PATH")
    schema = (
        read_json(source) if source else copy.deepcopy(read_published_schema())
    )
    require(
        isinstance(schema, dict)
        and cast(JsonObject, schema).get("$id") == CANONICAL_SCHEMA_URI,
        "Expected the canonical GC-STEM/.github manifest schema",
    )
    try:
        check_schema: Callable[[JsonObject], None] = getattr(
            Draft202012Validator, "check_schema"
        )
        check_schema(cast(JsonObject, schema))
    except SchemaError as error:
        raise ConfigurationError(
            f"Invalid canonical schema: {error.message}"
        ) from error
    return cast(JsonObject, schema)


def validate(
    data: JsonObject, schema: JsonObject, definition: str | None = None
) -> None:
    contract = schema
    if definition:
        contract = {"$ref": f"#/$defs/{definition}", "$defs": schema["$defs"]}
    errors = sorted(
        Draft202012Validator(
            contract, format_checker=FormatChecker()
        ).iter_errors(data),
        key=lambda error: str(error.json_path),
    )
    require(
        not errors,
        "Schema validation failed: "
        + "; ".join(
            f"{error.json_path}: {error.message}" for error in errors[:4]
        ),
    )


def inside(root: Path, path: str | Path) -> Path:
    resolved = Path(path).resolve()
    require(
        resolved.is_relative_to(root.resolve()),
        f"Path escapes workspace: {path}",
    )
    return resolved


def merge_new(target: JsonObject, additions: JsonObject, label: str) -> None:
    for key, value in additions.items():
        require(key not in target, f"Duplicate catalog ID: {label}/{key}")
        target[key] = copy.deepcopy(value)


def pointer_parent(
    document: JsonObject, pointer: str
) -> tuple[JsonObject, str]:
    keys = pointer.lstrip("/").split("/")
    node: Any = document
    for key in keys[:-1]:
        require(
            isinstance(node, dict) and key in node,
            f"Missing override target: {pointer}",
        )
        node = cast(JsonObject, node)[key]
    require(keys[-1] in node, f"Missing override target: {pointer}")
    return cast(JsonObject, node), keys[-1]


def compose(
    soe: JsonObject, course: JsonObject | None, schema: JsonObject
) -> JsonObject:
    validate(soe, schema)
    require(soe["manifest_type"] == "soe", "Expected an SOE manifest")
    resolved = copy.deepcopy(soe)
    resolved.pop("$schema", None)
    permissions = resolved.pop("override_permissions")
    resolved["manifest_type"] = "resolved"
    resolved["configuration_kind"] = "soe"
    if course is None:
        return resolved
    validate(course, schema)
    require(
        course["manifest_type"] == "course", "Expected a CSO course manifest"
    )
    require(
        course["baseline"]["baseline_id"] == soe["baseline"]["baseline_id"],
        "CSO baseline identity mismatch",
    )
    additions = course["additions"]
    for catalog in CATALOGS:
        merge_new(
            resolved.setdefault(catalog, {}),
            additions.get(catalog, {}),
            catalog,
        )
    for platform_id, extension in additions.get(
        "platform_extensions", {}
    ).items():
        require(
            platform_id in resolved["platforms"],
            f"Unknown platform: {platform_id}",
        )
        for catalog, entries in extension.items():
            merge_new(
                resolved["platforms"][platform_id][catalog],
                entries,
                f"platforms/{platform_id}/{catalog}",
            )
    targets: list[str] = []
    for override in course["overrides"]:
        target = override["target"]
        require(
            not any(
                target == old
                or target.startswith(old + "/")
                or old.startswith(target + "/")
                for old in targets
            ),
            "Overlapping CSO overrides",
        )
        permission = permissions.get(override["permission_id"])
        require(
            permission and permission["target"] == target,
            f"Unauthorized CSO override: {target}",
        )
        require(
            soe["control"]["status"] == "approved",
            "Draft SOE cannot authorize CSO overrides",
        )
        allowlist = permission.get("allowed_course_ids")
        require(
            allowlist is None or course["course"]["course_id"] in allowlist,
            "Course is not eligible for override",
        )
        pointer_parent(soe, target)
        parts = target.lstrip("/").split("/")
        if len(parts) >= 2:
            require(
                parts[1] not in additions.get(parts[0], {}),
                "CSO addition overlaps override",
            )
        if len(parts) == 4 and parts[0] == "platforms":
            require(
                parts[3]
                not in additions.get("platform_extensions", {})
                .get(parts[1], {})
                .get(parts[2], {}),
                "CSO platform extension overlaps override",
            )
        parent, key = pointer_parent(resolved, target)
        parent[key] = copy.deepcopy(override["value"])
        targets.append(target)
    resolved["configuration_kind"] = "cso"
    resolved["course"] = copy.deepcopy(course["course"])
    resolved["baseline_release"] = copy.deepcopy(soe["baseline"])
    resolved["baseline"] = copy.deepcopy(course["baseline"])
    resolved["baseline_control"] = copy.deepcopy(soe["control"])
    resolved["control"] = copy.deepcopy(course["control"])
    resolved["course_environments"] = copy.deepcopy(
        course.get("course_environments", {})
    )
    if "student_distribution" in course:
        resolved["student_distribution"] = copy.deepcopy(
            course["student_distribution"]
        )
    return resolved


def applies(
    entry: JsonObject,
    profile_id: str,
    profile: JsonObject,
    platform_id: str,
) -> bool:
    if "platform_ids" in entry and platform_id not in entry["platform_ids"]:
        return False
    selector = entry.get("applies_to", {})
    return all(
        actual in selector[key]
        for key, actual in (
            ("deployment_profile_ids", profile_id),
            ("deployment_kinds", profile["deployment_kind"]),
            ("session_types", profile["session_type"]),
        )
        if key in selector
    )


def scan_selectors(node: object, profiles: JsonObject) -> None:
    if isinstance(node, dict):
        for profile_id in cast(JsonObject, node).get("applies_to", {}).get(
            "deployment_profile_ids", []
        ):
            require(
                profile_id in profiles,
                f"Unknown applicability profile: {profile_id}",
            )
        for value in cast(JsonObject, node).values():
            scan_selectors(value, profiles)
    elif isinstance(node, list):
        for value in cast(list[object], node):
            scan_selectors(value, profiles)


def version_ok(version: str, rule: JsonObject) -> bool:
    comparison = rule.get("comparison", "presence_only")
    if comparison in {"presence_only", "managed_latest"}:
        return True
    value = rule["value"]
    if comparison == "exact":
        value = "==" + value
    elif comparison == "minimum":
        value = ">=" + value
    return Version(version) in SpecifierSet(value)


def version_rules(product: JsonObject, binding: JsonObject) -> list[JsonObject]:
    return [
        rule
        for rule in (
            product.get("version_rule"),
            binding.get("version_rule_override"),
            binding.get("verification", {}).get("version_rule"),
        )
        if rule
    ]


def environment_path(workspace: Path, definition: JsonObject) -> Path:
    template = definition["path"]
    require(
        template.startswith("${COURSE_ROOT}/"),
        "Course environment requires COURSE_ROOT",
    )
    result = inside(
        workspace, workspace / template.removeprefix("${COURSE_ROOT}/")
    )
    require(
        result != workspace.resolve(),
        "Course environment cannot replace workspace",
    )
    return result


def make_plan(
    resolved: JsonObject, schema: JsonObject, workspace: Path, profile_id: str
) -> Plan:
    profiles = resolved["deployment_profiles"]
    scan_selectors(resolved, profiles)
    require(profile_id in profiles, f"Unknown deployment: {profile_id}")
    profile = profiles[profile_id]
    platform_id = profile["platform_id"]
    require(platform_id in resolved["platforms"], "Unknown deployment platform")
    platform = resolved["platforms"][platform_id]
    for source_id, expected_uri in SOURCES.items():
        source = resolved["software_sources"].get(source_id)
        require(
            source and source["base_uri"].rstrip("/") == expected_uri,
            f"Unsupported source configuration: {source_id}",
        )
    require(
        profile["enabled"] and platform["enabled"],
        "Deployment or platform is disabled",
    )
    require(
        profile_id == "github_codespaces"
        and profile.get("profile_adapter_id") == "codespaces_devcontainer",
        "This adapter implements the Codespaces deployment only",
    )
    require(
        profile["deployment_kind"] == "container"
        and platform["os"]["family"] == "linux",
        "Expected Linux container deployment",
    )
    references = [
        p for p in profiles.values() if p["enabled"] and p["reference_profile"]
    ]
    require(
        len(references) == 1,
        "Exactly one primary reference deployment is required",
    )
    reference_platforms = [
        key
        for key, p in resolved["platforms"].items()
        if p["enabled"] and p["reference_platform"]
    ]
    require(
        reference_platforms == [references[0]["platform_id"]],
        "Reference platform/deployment mismatch",
    )
    for workflow_id in profile["allowed_workflow_ids"]:
        workflow = resolved["lifecycle_workflows"].get(workflow_id)
        require(
            workflow and profile_id in workflow["deployment_profile_ids"],
            "Workflow authorization mismatch",
        )
        require(
            workflow.get("interaction_mode") == "noninteractive",
            "Codespaces lifecycle must be noninteractive",
        )
    for action in ("runtime_initial_install", "runtime_verify"):
        require(
            action in profile["allowed_workflow_ids"],
            f"Missing workflow: {action}",
        )
    resolved["selected_deployment_profile_id"] = profile_id
    validate(resolved, schema, "resolvedConfiguration")

    def selected(entry: JsonObject) -> bool:
        return applies(entry, profile_id, profile, platform_id)

    capabilities: dict[str, JsonObject] = {
        key: value
        for key, value in resolved["capabilities"].items()
        if selected(value)
    }
    bindings: dict[str, JsonObject] = {}
    for key, binding in platform["capability_bindings"].items():
        require(
            key in resolved["capabilities"],
            f"Unknown capability binding: {key}",
        )
        if (
            key in capabilities
            and selected(binding)
            and (binding["required"] or capabilities[key]["required"])
        ):
            require(
                binding["required"],
                f"Required capability disabled by binding: {key}",
            )
            bindings[key] = binding
    for key, capability in capabilities.items():
        require(
            not capability["required"] or key in bindings,
            f"Missing required capability: {key}",
        )
    packages: list[str] = []
    extensions: list[str] = []
    environments: dict[str, str] = {}
    for key, definition in platform["os_packages"].items():
        if definition["required"] and selected(definition):
            require(
                definition["source_id"] == "ubuntu_archive",
                f"Unsupported OS package source: {key}",
            )
            require(
                PACKAGE.fullmatch(definition["package_identifier"]),
                f"Invalid APT identifier: {key}",
            )
            require(
                definition.get("version_rule", {}).get(
                    "comparison", "presence_only"
                )
                in {"presence_only", "managed_latest"},
                "Versioned support packages need an implementation",
            )
            packages.append(definition["package_identifier"])
    for key, binding in bindings.items():
        for dependency in set(
            capabilities[key].get("depends_on", [])
            + binding.get("dependencies", [])
        ):
            require(
                dependency in bindings,
                f"Missing applicable dependency: {key} -> {dependency}",
            )
        require(
            binding["product_id"] in resolved["products"],
            f"Unknown product: {key}",
        )
        product = resolved["products"][binding["product_id"]]
        for rule in version_rules(product, binding):
            version_ok("0", rule)
        require(
            key in product["capability_roles"],
            f"Product does not implement capability: {key}",
        )
        require(
            binding["source_id"] in resolved["software_sources"],
            f"Unknown source: {key}",
        )
        if "provider_profile_id" in binding:
            require(
                binding["provider_profile_id"] in resolved["provider_profiles"],
                f"Unknown provider: {key}",
            )
            authentication = resolved["provider_profiles"][
                binding["provider_profile_id"]
            ]["authentication"]
            require(
                not authentication["interactive"],
                "Codespaces provisioning cannot initiate interactive login",
            )
        for setting_id in binding.get("settings_profile_ids", []):
            require(
                setting_id in resolved["managed_settings"],
                f"Unknown settings profile: {setting_id}",
            )
        adapter = binding["installer_adapter_id"]
        if adapter == "apt_package":
            require(
                binding["product_id"] == "python"
                or all(
                    rule["comparison"] in {"presence_only", "managed_latest"}
                    for rule in version_rules(product, binding)
                ),
                f"Unsupported versioned APT component: {key}",
            )
            require(
                binding["source_id"]
                in platform["package_manager"]["source_ids"],
                f"APT source not enabled: {key}",
            )
            require(
                binding["source_id"]
                in {"ubuntu_archive", "github_cli_packages"},
                f"Unsupported APT source: {key}",
            )
            require(
                PACKAGE.fullmatch(binding["package_identifier"]),
                f"Invalid APT identifier: {key}",
            )
            packages.append(binding["package_identifier"])
        elif adapter == "devcontainer_extension":
            extension = binding["package_identifier"]
            require(
                binding["source_id"] == "vscode_marketplace"
                and EXTENSION.fullmatch(extension),
                "Invalid extension source or ID",
            )
            require(
                all(
                    rule["comparison"] == "presence_only"
                    for rule in version_rules(product, binding)
                ),
                "Versioned editor extensions need a supported adapter",
            )
            extensions.append(extension)
        elif adapter == "codespaces_editor":
            require(
                binding["installation_scope"] == "provider_managed"
                and binding["source_id"] == "github_codespaces",
                "Invalid managed editor binding",
            )
        elif adapter == "python_venv_package":
            require(
                binding["source_id"] == "pypi"
                and PIP_PACKAGE.fullmatch(binding["package_identifier"]),
                "Only named PyPI packages are supported",
            )
            environment_id = binding["environment_id"]
            definition = resolved.get("course_environments", {}).get(
                environment_id
            )
            require(
                definition and selected(definition),
                f"Missing applicable course environment: {environment_id}",
            )
            require(
                definition["runtime_capability_id"]
                == "programming_language_runtime",
                "Course environments require the selected Python runtime",
            )
            require(
                definition["runtime_capability_id"] in bindings,
                "Missing course interpreter capability",
            )
            environments[environment_id] = str(
                environment_path(workspace, definition)
            )
        else:
            raise ConfigurationError(
                f"Unsupported Codespaces installer: {adapter}"
            )
    require(
        len(set(environments.values())) == len(environments),
        "Course environments cannot share directories",
    )
    for asset in resolved["managed_assets"].values():
        require(
            not selected(asset),
            "Applicable managed assets need a supported Codespaces adapter",
        )
    require(
        not any(
            selected(item) for item in resolved["obsolete_components"].values()
        ),
        "Applicable removal operations need a supported Codespaces adapter",
    )
    settings: list[JsonObject] = []
    setting_keys: set[tuple[str, str]] = set()
    for setting in resolved["managed_settings"].values():
        if selected(setting) and setting["scope"] == "workspace":
            require(
                setting["settings_adapter_id"] == "vscode_workspace_settings",
                "Unsupported workspace settings adapter",
            )
            require(
                setting["target_path"].startswith("${WORKSPACE_ROOT}/"),
                "Invalid workspace settings path",
            )
            destination_path = inside(
                workspace,
                workspace
                / setting["target_path"].removeprefix("${WORKSPACE_ROOT}/"),
            )
            for key in setting["values"]:
                destination = (str(destination_path), key)
                require(
                    destination not in setting_keys,
                    "Conflicting managed workspace settings",
                )
                setting_keys.add(destination)
            settings.append(setting)
    return {
        "configuration_kind": resolved["configuration_kind"],
        "workspace": str(workspace.resolve()),
        "deployment": profile_id,
        "platform": platform_id,
        "profile": profile,
        "packages": sorted(set(packages)),
        "extensions": sorted(set(extensions)),
        "bindings": bindings,
        "environments": environments,
        "settings": settings,
        "resolved": resolved,
    }


def load_plan(
    atlas_root: Path,
    workspace: Path,
    mode: str = "auto",
    profile_id: str = "github_codespaces",
    schema_path: str | Path | None = None,
) -> LoadedPlan:
    atlas_root, workspace = atlas_root.resolve(), workspace.resolve()
    schema_path = schema_path or os.environ.get("SOE_SCHEMA_PATH")
    schema = load_schema(schema_path)
    soe = read_json(atlas_root / ".config/soe_manifest.json")
    course_path = workspace / ".config/cso_manifest.json"
    if mode == "auto":
        mode = "cso" if course_path.is_file() else "soe"
        require(
            mode == "cso"
            or (workspace / ".config/soe_manifest.json").is_file(),
            "Course checkout requires .config/cso_manifest.json; "
            "choose --mode soe explicitly for an SOE-only workspace",
        )
    course = read_json(course_path) if mode == "cso" else None
    plan = cast(
        LoadedPlan,
        make_plan(compose(soe, course, schema), schema, workspace, profile_id),
    )
    plan["schema_path"] = (
        str(Path(schema_path).resolve()) if schema_path else None
    )
    return plan


def run(
    args: Iterable[object], **kwargs: Any
) -> subprocess.CompletedProcess[Any]:
    return cast(
        subprocess.CompletedProcess[Any],
        subprocess.run([str(arg) for arg in args], check=True, **kwargs),
    )


def check_host(plan: Plan) -> None:
    require(sys.platform == "linux", "Provisioning requires a Linux container")
    facts = {
        key: value
        for line in Path("/etc/os-release").read_text().splitlines()
        if "=" in line
        for key, value in [line.split("=", 1)]
    }
    require(facts.get("ID", "").strip('"') == "ubuntu", "Expected Ubuntu")
    require(
        facts["VERSION_ID"].strip('"') == plan["profile"]["os_release_id"],
        "Ubuntu release does not match deployment",
    )
    architecture = {"amd64": "x86_64", "aarch64": "arm64"}.get(
        host_platform.machine(), host_platform.machine()
    )
    require(
        architecture == plan["profile"]["architecture"],
        "Architecture does not match deployment",
    )


def apt_installed(package: str) -> bool:
    result = subprocess.run(
        ["dpkg-query", "-W", "-f=${Status}", package],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout == "install ok installed"


def install_system(plan: Plan) -> None:
    check_host(plan)
    geteuid: Callable[[], int] = getattr(os, "geteuid")
    require(geteuid() == 0, "System installation requires root")
    missing = [
        package for package in plan["packages"] if not apt_installed(package)
    ]
    if missing:
        run(["apt-get", "update"])
        run(
            ["apt-get", "install", "-y", "--no-install-recommends", *missing],
            env={**os.environ, "DEBIAN_FRONTEND": "noninteractive"},
        )


def interpreter(environment: str | Path) -> Path:
    return Path(environment) / "bin/python"


def pip_requirement(plan: Plan, binding: JsonObject) -> str:
    requirements: list[str] = []
    product = plan["resolved"]["products"][binding["product_id"]]
    for rule in version_rules(product, binding):
        comparison = rule["comparison"]
        if comparison in {"presence_only", "managed_latest"}:
            continue
        value = rule["value"]
        requirements.append(
            {"minimum": ">=", "exact": "=="}.get(comparison, "") + value
        )
    return binding["package_identifier"] + ",".join(requirements)


def installed_package_version(
    python: str | Path, binding: JsonObject
) -> str | None:
    query = (
        "import importlib.metadata,sys; "
        "print(importlib.metadata.version(sys.argv[1]))"
    )
    result = subprocess.run(
        [str(python), "-c", query, binding["package_identifier"]],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        return None
    return result.stdout.strip()


def package_satisfied(
    python: str | Path, binding: JsonObject, plan: Plan
) -> bool:
    installed = installed_package_version(python, binding)
    if installed is None:
        return False
    product = plan["resolved"]["products"][binding["product_id"]]
    return all(
        version_ok(installed, rule) for rule in version_rules(product, binding)
    )


def merge_settings(target: JsonObject, values: JsonObject) -> None:
    for key, value in values.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            merge_settings(target[key], cast(JsonObject, value))
        else:
            target[key] = copy.deepcopy(cast(object, value))


def contains_settings(actual: object, expected: JsonObject) -> bool:
    return isinstance(actual, dict) and all(
        key in actual
        and (
            contains_settings(
                cast(JsonObject, actual)[key], cast(JsonObject, value)
            )
            if isinstance(value, dict)
            else cast(JsonObject, actual)[key] == value
        )
        for key, value in expected.items()
    )


def python_runtime_version(python: str | Path) -> str:
    result = run(
        [
            python,
            "-c",
            "import json, platform; print(json.dumps({"
            "'version': platform.python_version(), "
            "'implementation': platform.python_implementation()}))",
        ],
        capture_output=True,
        text=True,
    )
    facts = json.loads(result.stdout)
    require(
        facts["implementation"] == "CPython",
        "The approved SOE interpreter must be CPython",
    )
    return facts["version"]


def verify_course_interpreter(plan: Plan, environment: str | Path) -> None:
    python = interpreter(environment)
    require(python.is_file(), "Missing course environment")
    version = python_runtime_version(python)
    runtime = plan["bindings"]["programming_language_runtime"]
    product = plan["resolved"]["products"][runtime["product_id"]]
    require(
        all(
            version_ok(version, rule)
            for rule in version_rules(product, runtime)
        ),
        "Course interpreter is incompatible; rebuild its venv explicitly",
    )


def setup(
    plan: LoadedPlan, workspace: Path, atlas_root: Path, mode: str
) -> None:
    check_host(plan)
    geteuid: Callable[[], int] = getattr(os, "geteuid")
    require(geteuid() != 0, "Course setup must run as the development user")
    if any(not apt_installed(package) for package in plan["packages"]):
        run(
            [
                "sudo",
                "-n",
                sys.executable,
                Path(__file__).resolve(),
                "install-system",
                "--atlas-root",
                atlas_root,
                "--workspace",
                workspace,
                "--mode",
                mode,
            ]
            + (["--schema", plan["schema_path"]] if plan["schema_path"] else [])
        )
    verify(plan, editor=False, course_packages=False)
    for environment in plan["environments"].values():
        require(
            not Path(environment).is_symlink(),
            "Course environment cannot be a symlink",
        )
        if not interpreter(environment).exists():
            run(["/usr/bin/python3", "-m", "venv", environment])
        require(
            inside(workspace, environment) == Path(environment),
            "Invalid environment directory",
        )
        verify_course_interpreter(plan, environment)
    for binding in plan["bindings"].values():
        if binding["installer_adapter_id"] == "python_venv_package":
            python = interpreter(
                plan["environments"][binding["environment_id"]]
            )
            if not package_satisfied(python, binding, plan):
                require(
                    installed_package_version(python, binding) is None,
                    "Existing course package is incompatible; "
                    "resolve the conflict explicitly before setup",
                )
                run(
                    [
                        python,
                        "-m",
                        "pip",
                        "install",
                        "--disable-pip-version-check",
                        "--index-url",
                        "https://pypi.org/simple/",
                        pip_requirement(plan, binding),
                    ]
                )
    for setting in plan["settings"]:
        target = inside(
            workspace,
            workspace
            / setting["target_path"].removeprefix("${WORKSPACE_ROOT}/"),
        )
        if target.exists() and setting["merge_policy"] == "create_if_missing":
            continue
        values: JsonObject = read_json(target) if target.exists() else {}
        merge_settings(values, setting["values"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(values, indent=2) + "\n", encoding="utf-8")
    verify(plan, editor=False)


def verify(
    plan: Plan, editor: bool = False, course_packages: bool = True
) -> None:
    check_host(plan)
    verified_python = "not selected"
    if course_packages:
        for environment in plan["environments"].values():
            verify_course_interpreter(plan, environment)
    for setting in plan["settings"]:
        if not course_packages:
            continue
        workspace = Path(plan["workspace"])
        target = inside(
            workspace,
            workspace
            / setting["target_path"].removeprefix("${WORKSPACE_ROOT}/"),
        )
        require(target.is_file(), "Missing managed workspace settings")
        if setting["merge_policy"] != "create_if_missing":
            require(
                contains_settings(read_json(target), setting["values"]),
                "Managed workspace settings do not match requirements",
            )
    for package in plan["packages"]:
        require(apt_installed(package), f"Missing APT package: {package}")
    for key, binding in plan["bindings"].items():
        adapter = binding["installer_adapter_id"]
        product = plan["resolved"]["products"][binding["product_id"]]
        if adapter == "apt_package":
            commands: list[str] = binding["verification"].get(
                "executable_names", []
            )
            require(
                not commands
                or any(shutil.which(command) for command in commands),
                f"Missing executable: {key}",
            )
            if product["product_kind"] == "programming_runtime":
                require(
                    binding["product_id"] == "python",
                    "Unsupported runtime verification",
                )
                verified_python = python_runtime_version("/usr/bin/python3")
                require(
                    all(
                        version_ok(verified_python, rule)
                        for rule in version_rules(product, binding)
                    ),
                    "Python version does not satisfy the selected requirements",
                )
            else:
                require(
                    all(
                        rule["comparison"]
                        in {"presence_only", "managed_latest"}
                        for rule in version_rules(product, binding)
                    ),
                    f"Unsupported component version verification: {key}",
                )
        elif adapter == "python_venv_package" and course_packages:
            python = interpreter(
                plan["environments"][binding["environment_id"]]
            )
            require(python.is_file(), f"Missing course environment: {key}")
            require(
                package_satisfied(python, binding, plan),
                f"Missing/incompatible course package: {key}",
            )
    if editor:
        require(
            shutil.which("code"),
            "Managed VS Code CLI is not available; attach the editor first",
        )
        installed = (
            run(["code", "--list-extensions"], capture_output=True, text=True)
            .stdout.casefold()
            .splitlines()
        )
        for extension in plan["extensions"]:
            require(
                extension.casefold() in installed,
                f"Missing editor extension: {extension}; "
                "regenerate the devcontainer and rebuild",
            )
    print(
        f"Verified {plan['configuration_kind'].upper()} runtime: "
        f"Ubuntu {plan['profile']['os_release_id']}, "
        f"CPython {verified_python}; "
        + (
            "editor extensions verified."
            if editor
            else "editor extensions are checked separately after attachment."
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=("plan", "install-system", "setup", "verify", "devcontainer"),
    )
    parser.add_argument(
        "--atlas-root",
        type=Path,
        default=Path(
            os.environ.get("ATLAS_ROOT", Path(__file__).resolve().parents[2])
        ),
    )
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument(
        "--mode", choices=("auto", "soe", "cso"), default="auto"
    )
    parser.add_argument("--deployment", default="github_codespaces")
    parser.add_argument(
        "--schema",
        type=Path,
        help="Canonical schema file in the .github checkout; "
        "defaults to SOE_SCHEMA_PATH or the published canonical URL",
    )
    parser.add_argument("--editor", action="store_true")
    parser.add_argument(
        "--image", help="Published SOE image for a course devcontainer"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check generated devcontainer for drift",
    )
    args = parser.parse_args(argv)
    try:
        plan = load_plan(
            args.atlas_root,
            args.workspace,
            args.mode,
            args.deployment,
            schema_path=args.schema,
        )
        if args.action == "plan":
            print(
                json.dumps(
                    {
                        key: value
                        for key, value in plan.items()
                        if key != "resolved"
                    },
                    indent=2,
                )
            )
        elif args.action == "install-system":
            install_system(plan)
        elif args.action == "setup":
            setup(
                plan,
                args.workspace.resolve(),
                args.atlas_root.resolve(),
                plan["configuration_kind"],
            )
        elif args.action == "verify":
            verify(plan, args.editor)
        elif args.action == "devcontainer":
            from devcontainer_config import configuration

            generated = configuration(plan, image=args.image)
            target = args.workspace / ".devcontainer/devcontainer.json"
            if args.check:
                require(
                    read_json(target) == generated,
                    "devcontainer.json differs from SOE/CSO; regenerate it",
                )
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(
                    json.dumps(generated, indent=2) + "\n",
                    encoding="utf-8",
                    newline="\n",
                )
    except (
        ConfigurationError,
        OSError,
        ValueError,
        KeyError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"SOE: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
