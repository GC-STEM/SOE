<!-- To see this file in a clean, formatted view, select ▼ in the upper-right corner of the editor pane, then select "Markdown Preview".-->

# GC-STEM Atlas

---

> [!WARNING]
> This repository is under active development and may change frequently. It is not ready for student or faculty use

---

{{Welcome and overview}}

## Table of Contents <!-- omit from toc -->

1. [STEM Standard Operating Environment](#stem-standard-operating-environment)
2. [STEM Shared Libraries](#stem-shared-libraries)
3. [CSO Automation Scripts](#cso-automation-scripts)
4. [CSO Isolation](#cso-isolation)

## STEM Standard Operating Environment

The STEM Standard Operating Environment (SOE) follows **current Ubuntu LTS − 1**: the Ubuntu LTS release immediately preceding the latest LTS, together with that release's default CPython minor version. This target applies to Codio Boxes and VMs, Codespaces, local Docker, and native Ubuntu installations. Windows and macOS use the same CPython minor series on their native OS. The SOE manifest records the concrete release selections.

Patch updates within the manifest-selected Ubuntu release and Python minor series are allowed. Future LTS/Python-minor changes require a reviewed SOE release. Existing Codio environments must be migrated and qualified; this policy does not change provider images automatically. Course instructions and grading runtimes, including zyBooks where used, must be checked against the approved target.

GitHub Codespaces is the default development container for temporary student access and faculty verification. It provides a headless runtime with VS Code. See [Codespaces setup and launch](.devcontainer/README.md) for instructions, course-specific overlays (CSO), and verification.

Click to learn more [about the Standard Operating Environment](https://github.com/GC-STEM/atlas/wiki/About-the-SOE)

## STEM Shared Libraries

## CSO Automation Scripts

## CSO Isolation

### Course-Activity Environments

#### Python Virtual Environments

- [Python Virtual Environments (`venv`)](https://docs.python.org/3/tutorial/venv.html)

#### Java Toolchain and Dependency Management

- [Gradle Java Toolchains](https://docs.gradle.org/current/userguide/toolchains.html)
- [Apache Maven Dependency Management](https://maven.apache.org/guides/introduction/introduction-to-dependency-mechanism.html)

#### C/C++ Dependency and Build Configuration Management

- [vcpkg Manifest Mode](https://learn.microsoft.com/en-us/vcpkg/consume/manifest-mode)
- [Conan Package Management](https://docs.conan.io/2/tutorial/consuming_packages.html)
- [CMake Presets](https://cmake.org/cmake/help/latest/manual/cmake-presets.7.html)

#### JavaScript/TypeScript Runtime and Dependency Management

- [mise Runtime Version Management](https://mise.jdx.dev/dev-tools/)
- [npm Dependency Management (`package.json`)](https://docs.npmjs.com/cli/configuring-npm/package-json/)
- [npm Dependency Lockfiles (`package-lock.json`)](https://docs.npmjs.com/cli/configuring-npm/package-lock-json/)
- [npm Workspaces](https://docs.npmjs.com/cli/using-npm/workspaces/)
- [pnpm Workspaces](https://pnpm.io/workspaces)

### Development Containers

Cloud: [GitHub Codespaces](https://github.com/features/codespaces)

Remote: [Codio Boxes](https://www.codio.com/blog/codio-boxes-and-box-parts)

Local: [Docker Containers](https://www.docker.com/resources/what-container/)

### Virtual Machines

[**Codio Virtual Machines**](https://docs.codio.com/instructors/setupcourses/virtualmachine.html)

[**Oracle VirtualBox**](https://www.virtualbox.org/)

[**VBoxManage**](https://www.virtualbox.org/manual/ch08.html)

[**Vagrant**](https://developer.hashicorp.com/vagrant/install)

<!-- Repository Metadata
---
version: "{0.0.0}"
updated: "{YYYY-MM-DDTHH:MM:SS±HH:MM}"
tags: ["{Tag1}", "{Tag2}"]
---
-->
