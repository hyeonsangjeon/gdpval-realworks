#!/usr/bin/env bash
# Build the GDPVal sandbox image.
#
# Usage (run from the batch-runner/ directory):
#     bash sandbox/build.sh
#     SANDBOX_IMAGE=myrepo/gdpval-sandbox:1.0 bash sandbox/build.sh
#
# The build context is batch-runner/ so the Dockerfile can COPY both
# requirements.txt and the skills/ package.
set -euo pipefail

IMAGE="${SANDBOX_IMAGE:-gdpval-sandbox:latest}"

# Resolve batch-runner/ regardless of where the script is invoked from.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTEXT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "🐳 Building sandbox image: ${IMAGE}"
echo "   Context:    ${CONTEXT_DIR}"
echo "   Dockerfile: ${SCRIPT_DIR}/Dockerfile"

if ! command -v docker >/dev/null 2>&1; then
  echo "❌ docker CLI not found. Install Docker first." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "❌ Docker daemon is not running. Start Docker and retry." >&2
  exit 1
fi

docker build \
  -f "${SCRIPT_DIR}/Dockerfile" \
  -t "${IMAGE}" \
  "${CONTEXT_DIR}"

echo "✅ Built ${IMAGE}"
echo "   Set execution.mode: sandbox in your experiment YAML to use it."
