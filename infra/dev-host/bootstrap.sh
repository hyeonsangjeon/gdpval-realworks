#!/usr/bin/env bash
# What to install on the development host, and what to measure once it is there.
#
# Run through `az vm run-command invoke`, which reaches the machine through the
# Azure agent rather than through a listening port. That is why main.bicep can
# create a machine with no public address and no inbound rule and still be
# usable: nothing here needs a session.
#
# Two halves, and they must not be confused with one another.
#
# The first half installs what the card lists — git, Docker, Python, Node,
# LibreOffice, the Noto fonts, and the pieces VS Code Remote SSH expects — plus
# bubblewrap, which is what Codex's sandbox is built on and what the whole
# execution-host question is about.
#
# The second half *measures* and does not fix. In particular it reads
# kernel.apparmor_restrict_unprivileged_userns and reports it. Ubuntu has
# shipped that at 1 since 23.10, and 1 is the setting under which Codex's
# sandbox fails on GitHub's ubuntu-24.04 runner — the namespace is created and
# then stripped of the capability needed to bring up the loopback interface of
# the network Codex unshares. This script does not set it to 0. Doing so would
# remove the restriction from every process on the machine, which is not a fix
# but the absence of one, and it is the fourth of the four shortcuts refused in
# tasks/0822_saturday/TASK_NATIVE_CODEX_RUN_PATH.md §3b.
#
# If the machine reports `user_namespaces_restricted_by_security_policy`, that
# is a finding about the card's chosen image, and the decision that follows —
# a targeted AppArmor profile for one binary, which is a security-policy change
# and needs asking for — belongs to a person.
#
# Idempotent: safe to run twice. It exits non-zero only when something it
# installed is not there afterwards, never because a measurement came back
# unwelcome.

set -euo pipefail

REPO_URL="${GDPVAL_REPO_URL:-https://github.com/hyeonsangjeon/gdpval-realworks.git}"
WORK_ROOT="${GDPVAL_WORK_ROOT:-/mnt/gdpval}"
PYTHON_VERSION="${GDPVAL_PYTHON_VERSION:-3.10.12}"
REPORT="${GDPVAL_BOOTSTRAP_REPORT:-/var/log/gdpval-bootstrap.json}"
MARKER="/etc/gdpval-dev-host"

log() { printf '[bootstrap] %s\n' "$*"; }

# ---------------------------------------------------------------------------
# 0. Say what this machine is, before anything else can be run on it.
#
# batch-runner/dev_host_boundary.py reads this file and refuses to start a
# GDPVal benchmark run on a machine that carries it. The card's boundary
# section — do not quietly substitute this VM for a pre-registered execution
# environment — is enforced by that refusal, and the refusal needs the marker to
# exist from the first minute rather than from whenever somebody remembers to
# write it.
# ---------------------------------------------------------------------------
if [ ! -f "${MARKER}" ]; then
  log "marking this machine as a development host"
  cat > "${MARKER}" <<'MARKERDOC'
# This machine is the gdpval-realworks development and test host.
#
# It is NOT a pre-registered GDPVal benchmark execution environment. The
# benchmark's Host subprocess, Docker and Azure Code Interpreter arms are
# defined elsewhere and pinned there; running one of them here would change
# the kernel, the image, the machine size and the region underneath a
# comparison whose entire claim is that only the run place changed.
#
# batch-runner/dev_host_boundary.py reads this file and refuses to start a
# benchmark run while it says no. Deleting the file is not how that is
# answered -- to run the benchmark on an Azure VM, register this machine as
# its own arm by setting benchmark_execution_environment=yes together with
# all of:
#
#   benchmark_arm=<name>
#   benchmark_arm_kernel=<uname -r at registration>
#   benchmark_arm_image=<publisher:offer:sku:version>
#   benchmark_arm_vm_size=<Standard_...>
#   benchmark_arm_region=<azure region>
#   benchmark_arm_task_manifest_sha256=<the fixed task list>
#
# A partial registration is refused, and so is a run on a kernel other than
# the one the arm was pinned to.
role=development
benchmark_execution_environment=no
defined_by=infra/dev-host/main.bicep
MARKERDOC
fi

# ---------------------------------------------------------------------------
# 1. The data disk. Docker layers, checkouts and test output go here, not on
#    the operating system disk.
# ---------------------------------------------------------------------------
DATA_DEV=""
for candidate in /dev/disk/azure/scsi1/lun0 /dev/sdc /dev/sdb; do
  if [ -b "${candidate}" ]; then DATA_DEV="${candidate}"; break; fi
done

if [ -n "${DATA_DEV}" ] && ! mountpoint -q "${WORK_ROOT}"; then
  log "preparing data disk ${DATA_DEV} at ${WORK_ROOT}"
  if ! blkid "${DATA_DEV}" > /dev/null 2>&1; then
    mkfs.ext4 -F -L gdpval "${DATA_DEV}"
  fi
  mkdir -p "${WORK_ROOT}"
  DATA_UUID="$(blkid -s UUID -o value "${DATA_DEV}")"
  if ! grep -q "${DATA_UUID}" /etc/fstab; then
    printf 'UUID=%s %s ext4 defaults,nofail 0 2\n' "${DATA_UUID}" "${WORK_ROOT}" >> /etc/fstab
  fi
  mount "${WORK_ROOT}"
elif [ -z "${DATA_DEV}" ]; then
  log "NOTE: no data disk found; using ${WORK_ROOT} on the OS disk"
  mkdir -p "${WORK_ROOT}"
fi

# ---------------------------------------------------------------------------
# 2. Packages. The card's list, plus bubblewrap.
# ---------------------------------------------------------------------------
export DEBIAN_FRONTEND=noninteractive
log "apt update"
apt-get update -qq

log "installing base tooling"
apt-get install -y -qq \
  build-essential ca-certificates curl git gnupg jq lsb-release unzip \
  pkg-config libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev \
  libffi-dev liblzma-dev tk-dev uuid-dev \
  bubblewrap \
  libreoffice \
  fonts-noto fonts-noto-cjk fonts-noto-color-emoji \
  ffmpeg poppler-utils

# VS Code Remote SSH wants a working sshd, a writable home and tar/gzip. It
# does not need an inbound rule to be *installed*; it needs one to be *used*,
# and that is main.bicep's sshAllowedSourcePrefixes, left empty on purpose.
log "installing VS Code Remote SSH prerequisites"
apt-get install -y -qq openssh-server tar gzip

# Docker from Docker's own repository. The card's condition 1 names "current
# Docker" among the things the development box cannot provide: 20.10.3 there
# against 24.0 as the bar.
if ! command -v docker > /dev/null 2>&1; then
  log "installing Docker"
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  printf 'deb [arch=%s signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu %s stable\n' \
    "$(dpkg --print-architecture)" "$(. /etc/os-release && echo "${VERSION_CODENAME}")" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker

# Node from NodeSource. LibreOffice and the fonts above are what the renderer
# needs; Node is what the dashboard build needs.
if ! command -v node > /dev/null 2>&1; then
  log "installing Node"
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y -qq nodejs
fi

# ---------------------------------------------------------------------------
# 3. Python, at the version this repository pins.
#
#    core/agentic_v2_license.py compares a pinned version string against
#    sys.version_info at import, so "a Python 3.10" is not the same as 3.10.12.
#    Ubuntu 24.04 ships 3.12, so this is built rather than installed.
# ---------------------------------------------------------------------------
PY_PREFIX="${WORK_ROOT}/python-${PYTHON_VERSION}"
if [ ! -x "${PY_PREFIX}/bin/python3" ]; then
  log "building CPython ${PYTHON_VERSION} (Ubuntu 24.04 ships 3.12; the repository pins ${PYTHON_VERSION})"
  SRC="/tmp/Python-${PYTHON_VERSION}"
  rm -rf "${SRC}" "${SRC}.tgz"
  curl -fsSL -o "${SRC}.tgz" "https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz"
  tar -xzf "${SRC}.tgz" -C /tmp
  ( cd "${SRC}" \
    && ./configure --prefix="${PY_PREFIX}" --enable-optimizations --with-ensurepip=install > /dev/null \
    && make -j"$(nproc)" > /dev/null \
    && make altinstall > /dev/null )
  ln -sf "${PY_PREFIX}/bin/python3.10" "${PY_PREFIX}/bin/python3"
  ln -sf "${PY_PREFIX}/bin/pip3.10" "${PY_PREFIX}/bin/pip3"
fi

# ---------------------------------------------------------------------------
# 4. A clean checkout from origin/main. The card is explicit: do not copy the
#    user's existing checkout across. That checkout carries uncommitted work,
#    and a host built from it would not be reproducible from this file.
# ---------------------------------------------------------------------------
CHECKOUT="${WORK_ROOT}/gdpval-realworks"
if [ ! -d "${CHECKOUT}/.git" ]; then
  log "cloning ${REPO_URL}"
  git clone --depth 50 "${REPO_URL}" "${CHECKOUT}"
fi
VENV="${WORK_ROOT}/venv-py310"
if [ ! -x "${VENV}/bin/python" ]; then
  log "creating the virtual environment"
  "${PY_PREFIX}/bin/python3" -m venv "${VENV}"
fi
"${VENV}/bin/python" -m pip install -q --upgrade pip
"${VENV}/bin/python" -m pip install -q -r "${CHECKOUT}/batch-runner/requirements.txt"

if [ -n "${SUDO_USER:-}" ] || id gdpval > /dev/null 2>&1; then
  OWNER="${SUDO_USER:-gdpval}"
  chown -R "${OWNER}:${OWNER}" "${WORK_ROOT}" || true
  usermod -aG docker "${OWNER}" || true
fi

# ---------------------------------------------------------------------------
# 5. Measure. Nothing below this line changes the machine.
#
#    Two questions, and they are different questions:
#
#      * Do the five migration conditions still fire here? That is what the
#        card gates on, and answering it on the new host is how the move is
#        shown to have been worth making rather than assumed to be.
#      * Can Codex execute a command inside its sandbox here? That is the
#        execution-host question, and the answer on Ubuntu 24.04 is expected to
#        be no, for the reason recorded in docs/codex_sandbox_hosts.json.
#        Expected is not measured, which is why it is run.
# ---------------------------------------------------------------------------
log "measuring: migration conditions"
set +e
"${VENV}/bin/python" "${CHECKOUT}/batch-runner/scripts/check_dev_host_migration_triggers.py" \
  --json --out /tmp/dev-host-triggers.json
TRIGGERS_EXIT=$?

log "measuring: can Codex sandbox a command here"
( cd "${CHECKOUT}/batch-runner" \
  && "${VENV}/bin/python" scripts/diagnose_codex_sandbox_host.py --json --out /tmp/codex-sandbox-host.json )
SANDBOX_EXIT=$?
set -e

APPARMOR_SYSCTL="$(cat /proc/sys/kernel/apparmor_restrict_unprivileged_userns 2>/dev/null || echo absent)"

"${VENV}/bin/python" - "${REPORT}" "${TRIGGERS_EXIT}" "${SANDBOX_EXIT}" "${APPARMOR_SYSCTL}" <<'PY'
import json, os, platform, subprocess, sys

report_path, triggers_exit, sandbox_exit, apparmor = sys.argv[1:5]

def read(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:                      # noqa: BLE001
        # A measurement that could not be read is recorded as unread, never as
        # a pass. Everything in this repository that reports readiness works
        # this way, and a bootstrap report is not the place to start guessing.
        return {"unread": str(exc)}

def version(*cmd):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return (out.stdout or out.stderr).strip().splitlines()[0]
    except Exception as exc:                      # noqa: BLE001
        return f"unavailable: {exc}"

report = {
    "schema": "gdpval_dev_host_bootstrap/1",
    "host": {
        "kernel": platform.release(),
        "os": version("lsb_release", "-ds"),
        "cpu_count": os.cpu_count(),
        "apparmor_restrict_unprivileged_userns": apparmor,
    },
    "installed": {
        "python": version(sys.executable, "--version"),
        "docker": version("docker", "--version"),
        "node": version("node", "--version"),
        "git": version("git", "--version"),
        "bwrap": version("bwrap", "--version"),
        "libreoffice": version("libreoffice", "--version"),
    },
    "measured": {
        "migration_triggers": read("/tmp/dev-host-triggers.json"),
        "migration_triggers_exit": int(triggers_exit),
        "codex_sandbox_host": read("/tmp/codex-sandbox-host.json"),
        "codex_sandbox_host_exit": int(sandbox_exit),
    },
    "not_done_here": [
        "kernel.apparmor_restrict_unprivileged_userns was read and not written. "
        "Setting it to 0 would remove the restriction from every process on this "
        "machine, which is the refused shortcut, not the fix.",
        "No AppArmor profile was installed. Granting `userns create` to one "
        "binary is the targeted alternative and is a security-policy change, so "
        "it is asked for rather than applied by a bootstrap script.",
        "No role was assigned to this machine's managed identity. It exists so "
        "that no long-lived key has to be stored here; what it may do is a "
        "separate request.",
    ],
}
with open(report_path, "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, ensure_ascii=False)
    handle.write("\n")
print(json.dumps(report, indent=2, ensure_ascii=False))
PY

log "report written to ${REPORT}"

# Fail only on a broken install. A sandbox verdict of "restricted" is a finding
# about this image and this policy; treating it as a bootstrap failure would
# make an honest measurement look like a broken script.
MISSING=""
for tool in git docker node bwrap libreoffice jq; do
  command -v "${tool}" > /dev/null 2>&1 || MISSING="${MISSING} ${tool}"
done
[ -x "${VENV}/bin/python" ] || MISSING="${MISSING} venv-python"
[ -f "${MARKER}" ] || MISSING="${MISSING} dev-host-marker"

if [ -n "${MISSING}" ]; then
  log "FATAL: not installed:${MISSING}"
  exit 1
fi
log "done"
