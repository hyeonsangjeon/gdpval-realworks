# GDPVal grading image — the judge's eyes, frozen into a layer.
#
# WHY THIS EXISTS
#   On formatting criteria the renderer is not a detail of how a grade is
#   produced; it *is* the evidence. grade-run.yml asks apt for
#   libreoffice-core and friends with no version, so whichever build the
#   mirror serves that morning becomes what the judge sees, and two runs a
#   generation apart are not comparable however identical their model,
#   prompt, and grader_source_hash.
#
#   That install is also a live outage surface. On 2026-08-19 the Ubuntu
#   mirror stalled mid-transfer for ~25 minutes; apt imposes no wall-clock
#   ceiling on itself, five grade jobs sat in that step for 5h18m, and 63 of
#   the 220 tasks died with them.
#
#   scripts/preflight_grading_renderer.py closed the comparability half by
#   asserting the installed build before Azure login, so drift costs a free
#   step instead of a paid corpus run. This image closes the other half: the
#   renderer stops being installed at run time at all.
#
# WHY ubuntu:24.04 AND NOT THE EXISTING SANDBOX IMAGE
#   ghcr.io/hyeonsangjeon/gdpval-sandbox ships LibreOffice 7.4.7.2 (it is
#   built FROM python:3.11-slim-bookworm). Every published grade file records
#   24.2.7.2. Reusing it would move the very scores this exists to stabilise,
#   and it carries neither git nor az, both of which the grade job needs.
#
# BUILD (from batch-runner/)
#   docker build -f sandbox/grading.Dockerfile -t gdpval-grading:dev sandbox
#
#   The RUN steps below are the acceptance test: a build that succeeds has
#   proven the renderer version, the font resolution, git, and az. There is
#   nothing to assert afterwards.

# Digest-pinned so a rebuild reproduces this renderer rather than today's.
FROM ubuntu:24.04@sha256:33ceb71981b602c1a7443a53469e4dba065f7503eab3078a2d7a57a2ab987517

LABEL org.opencontainers.image.title="gdpval-grading" \
      org.opencontainers.image.description="Frozen LibreOffice renderer and Actions runtime for GDPVal grading" \
      org.opencontainers.image.source="https://github.com/hyeonsangjeon/gdpval-realworks"

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1

# ── The renderer, and exactly the packages grade-run.yml installs ───────────
# tests/test_grading_image.py holds this list against that step, so the image
# cannot silently drop a package the runner has.
RUN apt-get update -qq \
 && apt-get install -y --no-install-recommends \
      libreoffice-core \
      libreoffice-calc \
      libreoffice-impress \
      libreoffice-writer \
      fonts-dejavu-core \
      fonts-liberation2 \
      fontconfig \
 && rm -rf /var/lib/apt/lists/*

# ── Actions runtime ────────────────────────────────────────────────────────
# Without git, actions/checkout silently falls back to a REST tarball with no
# .git, and the grade job's own verification (`git rev-parse`, upstream check,
# extraheader check) and the shard commit/push all fail.
RUN apt-get update -qq \
 && apt-get install -y --no-install-recommends \
      git \
      curl \
      ca-certificates \
      gnupg \
 && rm -rf /var/lib/apt/lists/*

# ── Azure CLI ──────────────────────────────────────────────────────────────
# azure/login shells out to `az`, so OIDC login needs it present.
#
# Installed from packages.microsoft.com rather than the aka.ms install script,
# which is a pipe from a redirect into a root shell. The key is verified by
# fingerprint before it is trusted, and the source line is signed-by that one
# keyring, so this repository cannot sign anything outside azure-cli.
ARG MICROSOFT_GPG_FINGERPRINT="BC528686B50D79E339D3721CEB3E94ADBE1229CF"
RUN set -eux; \
    curl -fsSL https://packages.microsoft.com/keys/microsoft.asc -o /tmp/microsoft.asc; \
    actual="$(gpg --show-keys --with-colons --with-fingerprint /tmp/microsoft.asc \
              | awk -F: '/^fpr:/ { print $10; exit }')"; \
    if [ "$actual" != "$MICROSOFT_GPG_FINGERPRINT" ]; then \
      echo "microsoft signing key fingerprint mismatch"; \
      echo "  expected: $MICROSOFT_GPG_FINGERPRINT"; \
      echo "  actual:   $actual"; \
      exit 1; \
    fi; \
    gpg --dearmor < /tmp/microsoft.asc > /usr/share/keyrings/microsoft.gpg; \
    rm -f /tmp/microsoft.asc; \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft.gpg] https://packages.microsoft.com/repos/azure-cli/ noble main" \
      > /etc/apt/sources.list.d/azure-cli.list; \
    apt-get update -qq; \
    apt-get install -y --no-install-recommends azure-cli; \
    rm -rf /var/lib/apt/lists/*

# ── Acceptance, enforced at build time ─────────────────────────────────────
# The version string is the whole point of the image, so a mismatch has to
# fail the build rather than be discovered by a grade run. It is deliberately
# the full line rather than a 24.2.7 prefix: the distribution build suffix
# moves only when the binary does, and the binary is the thing under test.
ARG EXPECTED_LIBREOFFICE_VERSION="LibreOffice 24.2.7.2 420(Build:2)"
RUN set -eux; \
    mkdir -p /opt/gdpval; \
    actual="$(soffice --headless --version)"; \
    if [ "$actual" != "$EXPECTED_LIBREOFFICE_VERSION" ]; then \
      echo "renderer version mismatch"; \
      echo "  expected: $EXPECTED_LIBREOFFICE_VERSION"; \
      echo "  actual:   $actual"; \
      exit 1; \
    fi; \
    printf '%s\n' "$actual" > /opt/gdpval/renderer-version.txt; \
    fc-match --format '%{family}\n' 'Liberation Sans' \
      | tr ',' '\n' | sed 's/^[[:space:]]*//; s/[[:space:]]*$//' \
      | grep -qx 'Liberation Sans'; \
    git --version; \
    az version --output none; \
    dpkg-query -W -f='${Package}=${Version}\n' | sort > /opt/gdpval/grading-packages.txt

WORKDIR /work
