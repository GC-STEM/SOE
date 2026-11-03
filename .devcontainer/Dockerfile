# syntax=docker/dockerfile:1

# Headless emergency/reference SOE. Desktop Docker is a separate future profile.
FROM ubuntu:24.04

LABEL org.opencontainers.image.title="GC-STEM SOE (headless)" \
      org.opencontainers.image.source="https://github.com/GC-STEM/atlas" \
      org.opencontainers.image.description="Ubuntu 24.04 / Python 3.12 SOE for Codespaces"

ENV LANG=C.UTF-8 TZ=Etc/UTC ATLAS_ROOT=/opt/gc-stem/atlas \
    SOE_SCHEMA_PATH=/opt/gc-stem/schema/manifest.schema.json \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Installer and Dev Containers bootstrap prerequisites only.
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates curl gpg git openssh-client python3 python3-venv \
        sudo tar gzip procps libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

# Vendor-signed GitHub CLI repository; package signatures are checked by APT.
RUN mkdir -p /etc/apt/keyrings \
    && curl --fail --location --retry 3 --max-time 60 \
        https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        --output /etc/apt/keyrings/githubcli.gpg \
    && chmod 644 /etc/apt/keyrings/githubcli.gpg \
    && echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/githubcli.gpg] https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list

COPY .config/requirements-automation.txt /opt/gc-stem/requirements-automation.txt
RUN python3 -m venv /opt/gc-stem/runtime \
    && /opt/gc-stem/runtime/bin/python -m pip install --no-cache-dir \
        -r /opt/gc-stem/requirements-automation.txt

# Fetch the single schema source; keep the build artifact outside Atlas.
ADD --chmod=0444 https://raw.githubusercontent.com/GC-STEM/.github/refs/heads/main/schemas/manifest.schema.json /opt/gc-stem/schema/manifest.schema.json
COPY .config/soe_manifest.json /opt/gc-stem/atlas/.config/
COPY scripts/python/soe.py scripts/python/devcontainer_config.py scripts/python/launch_codespaces.py /opt/gc-stem/atlas/scripts/python/
RUN chmod 0755 /opt/gc-stem/schema \
    && /opt/gc-stem/runtime/bin/python /opt/gc-stem/atlas/scripts/python/soe.py \
        install-system --workspace /opt/gc-stem/atlas --mode soe \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && if getent group 1000 > /dev/null; then \
        groupmod --new-name vscode "$(getent group 1000 | cut -d: -f1)"; \
       else groupadd --gid 1000 vscode; fi \
    && if getent passwd 1000 > /dev/null; then \
        usermod --login vscode --gid 1000 --home /home/vscode \
            --move-home --shell /bin/bash \
            "$(getent passwd 1000 | cut -d: -f1)"; \
       else useradd --uid 1000 --gid 1000 --create-home \
            --shell /bin/bash vscode; fi \
    && echo 'vscode ALL=(root) NOPASSWD:ALL' > /etc/sudoers.d/vscode \
    && chmod 440 /etc/sudoers.d/vscode \
    && mkdir -p /workspaces /home/vscode/Repos \
    && chown vscode:vscode /workspaces /home/vscode/Repos

USER vscode
# Local Compose bind-mounts the host's Repos folder at /home/vscode/Repos.
# Codespaces supplies its workspace mount and working directory separately.
WORKDIR /workspaces
RUN /opt/gc-stem/runtime/bin/python /opt/gc-stem/atlas/scripts/python/soe.py \
    verify --workspace /opt/gc-stem/atlas --mode soe

# VS Code and extensions are provided by Codespaces at editor attachment.
CMD ["sleep", "infinity"]
