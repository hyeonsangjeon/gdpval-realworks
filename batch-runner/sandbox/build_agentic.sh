#!/usr/bin/env bash
set -euo pipefail

IMAGE="${AGENTIC_SANDBOX_IMAGE:-gdpval-agentic-sandbox:local}"
BASE_IMAGE="${SANDBOX_IMAGE:-gdpval-sandbox:latest}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTEXT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SBOM_PATH="${AGENTIC_SBOM_PATH:-${CONTEXT_DIR}/sandbox/agentic-sbom.spdx.json}"

command -v docker >/dev/null
command -v python3 >/dev/null
docker info >/dev/null
docker image inspect "${BASE_IMAGE}" >/dev/null

docker build \
  --build-arg "BASE_IMAGE=${BASE_IMAGE}" \
  -f "${SCRIPT_DIR}/agentic.Dockerfile" \
  -t "${IMAGE}" \
  "${CONTEXT_DIR}"

docker run --rm --entrypoint python "${IMAGE}" \
  -I -B /opt/gdpval/agentic_image_audit.py

docker run --rm --entrypoint python "${IMAGE}" \
  -I -B /opt/gdpval/agentic_sbom.py > "${SBOM_PATH}"
EMBEDDED_SBOM="$(mktemp)"
trap 'rm -f "${EMBEDDED_SBOM}"' EXIT
docker run --rm --entrypoint cat "${IMAGE}" \
  /opt/gdpval/agentic-sbom.spdx.json > "${EMBEDDED_SBOM}"
cmp --silent "${SBOM_PATH}" "${EMBEDDED_SBOM}"
python3 -c '
import json, pathlib, sys
document = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
assert document["spdxVersion"] == "SPDX-2.3"
assert len(document["packages"]) > 20
' "${SBOM_PATH}"

docker image inspect --format '{{.Id}}' "${IMAGE}"
sha256sum "${SCRIPT_DIR}/agentic-seccomp.json" \
  "${SCRIPT_DIR}/agentic-capabilities.json" "${SBOM_PATH}"