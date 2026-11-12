#!/usr/bin/env bash
# Provision a headless Ubuntu 24.04 WSL2/Multipass SOE or course CSO.
# Shared installer and resolver are owned by GC-STEM/SOE.
set -Eeuo pipefail

usage() {
  printf 'Usage: %s --deployment wsl2|multipass [--course-repo OWNER/REPO | --course-root DIRECTORY | --soe-only]\n' "$0" >&2
  exit 2
}

deployment=''
course_repo=''
course_root=''
soe_only=false
while (($#)); do
  case "$1" in
    --deployment) (($# >= 2)) || usage; deployment=$2; shift 2 ;;
    --course-repo) (($# >= 2)) || usage; course_repo=$2; shift 2 ;;
    --course-root) (($# >= 2)) || usage; course_root=$2; shift 2 ;;
    --soe-only) soe_only=true; shift ;;
    *) usage ;;
  esac
done
[[ $deployment == wsl2 || $deployment == multipass ]] || usage
if [[ $soe_only == true ]]; then
  [[ -z $course_repo && -z $course_root ]] || usage
else
  [[ -n $course_repo && -z $course_root || -z $course_repo && -n $course_root ]] || usage
fi
if [[ -n $course_repo && ! $course_repo =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
  echo 'Invalid course repository (expected OWNER/REPO).' >&2
  exit 2
fi

[[ $(id -u) -ne 0 ]] || { echo 'Run as the default Ubuntu user, not root.' >&2; exit 2; }
[[ -f /etc/os-release ]] || { echo 'Missing /etc/os-release' >&2; exit 1; }
# shellcheck disable=SC1091
source /etc/os-release
[[ ${ID:-} == ubuntu && ${VERSION_ID:-} == 24.04 ]] || {
  echo 'This deployment requires Ubuntu 24.04 LTS.' >&2; exit 1;
}
case "$(uname -m)" in
  x86_64) architecture=amd64 ;;
  aarch64|arm64) architecture=arm64 ;;
  *) echo 'Unsupported CPU architecture.' >&2; exit 1 ;;
esac
profile="ubuntu_${deployment}_${architecture}"
soe_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
[[ -f "$soe_root/.config/soe_manifest.json" ]] || {
  echo 'SOE manifest is missing.' >&2; exit 1;
}
# A standalone guest may not have Git yet; WSL/Multipass normally bootstrap it.
if ! command -v git >/dev/null 2>&1; then
  sudo apt-get update
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y git
fi

if [[ $soe_only == true ]]; then
  workspace=$soe_root
  mode=soe
elif [[ -n $course_root ]]; then
  workspace=$(cd "$course_root" && pwd -P)
  mode=cso
else
  course_name=${course_repo#*/}
  workspace="$HOME/Repos/$course_name"
  mode=cso
  mkdir -p "$HOME/Repos"
  if [[ ! -e $workspace ]]; then
    git clone --origin upstream "https://github.com/$course_repo.git" "$workspace"
  fi
fi
if [[ $mode == cso && ! -f $workspace/.config/cso_manifest.json ]]; then
  echo "Missing course CSO manifest: $workspace/.config/cso_manifest.json" >&2
  exit 1
fi

# Bootstrap only: package selection and CSO resolution belong to soe.py.
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  ca-certificates curl gpg git python3 python3-venv python3-pip sudo
sudo install -d -m 0755 /etc/apt/keyrings
if [[ ! -s /etc/apt/keyrings/githubcli.gpg ]]; then
  curl --fail --location --retry 3 --max-time 60 \
    https://cli.github.com/packages/githubcli-archive-keyring.gpg \
    | sudo tee /etc/apt/keyrings/githubcli.gpg >/dev/null
  sudo chmod 0644 /etc/apt/keyrings/githubcli.gpg
fi
printf 'deb [arch=%s signed-by=/etc/apt/keyrings/githubcli.gpg] https://cli.github.com/packages stable main\n' \
  "$architecture" | sudo tee /etc/apt/sources.list.d/github-cli.list >/dev/null

runtime="$HOME/.cache/gc-stem/automation"
if [[ ! -x $runtime/bin/python ]]; then
  mkdir -p "$(dirname "$runtime")"
  python3 -m venv "$runtime"
fi
"$runtime/bin/python" -m pip install --disable-pip-version-check \
  -r "$soe_root/.config/requirements-automation.txt"
"$runtime/bin/python" "$soe_root/scripts/python/soe.py" setup \
  --soe-root "$soe_root" --workspace "$workspace" \
  --deployment "$profile" --mode "$mode"
"$runtime/bin/python" "$soe_root/scripts/python/soe.py" verify \
  --soe-root "$soe_root" --workspace "$workspace" \
  --deployment "$profile" --mode "$mode"
printf '\nREADY: %s (%s)\nSOE: %s\nWorkspace: %s\n' \
  "$deployment" "$architecture" "$soe_root" "$workspace"
