#!/usr/bin/env bash
# The development host, from nothing to measured and back to nothing.
#
#   ./deploy.sh plan        what would be created, without creating it
#   ./deploy.sh deploy      create it
#   ./deploy.sh bootstrap   install and measure, through the Azure agent
#   ./deploy.sh status      what exists and what it costs to leave running
#   ./deploy.sh deallocate  stop paying for compute, keep the disks
#   ./deploy.sh start       bring it back
#   ./deploy.sh delete      remove the resource group entirely
#
# The last four are the card's completion criterion 5 — "자동 종료·deallocate·
# 삭제 절차가 검증된다" — as commands that can be run rather than a paragraph
# describing what someone would do.
#
# Which subscription. The card puts this machine in the *external* subscription
# and says it is not used for the internal one or for Foundry permission work.
# This script will not deploy anywhere until GDPVAL_DEV_HOST_SUBSCRIPTION names
# the intended subscription, and it refuses outright if that resolves to the
# subscription the Foundry checks expect. The comparison is on values that
# arrive from the environment; neither is printed, only a short hash of each, so
# running this in a place with a transcript does not publish an identifier.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMAND="${1:-help}"

RESOURCE_GROUP="${GDPVAL_DEV_HOST_RESOURCE_GROUP:-rg-gdpval-devhost-krc}"
LOCATION="${GDPVAL_DEV_HOST_LOCATION:-koreacentral}"
NAME_PREFIX="${GDPVAL_DEV_HOST_NAME_PREFIX:-gdpval-devhost}"
VM_NAME="${NAME_PREFIX}-vm"
DEPLOYMENT_NAME="${GDPVAL_DEV_HOST_DEPLOYMENT_NAME:-gdpval-devhost}"
PROVENANCE="${GDPVAL_DEV_HOST_PROVENANCE:-${HERE}/last-deployment.json}"

die() { printf 'FATAL: %s\n' "$*" >&2; exit 1; }
log() { printf '[dev-host] %s\n' "$*"; }
fingerprint() { printf '%s' "$1" | sha256sum | cut -c1-16; }

require_subscription() {
  local intended current expected
  intended="${GDPVAL_DEV_HOST_SUBSCRIPTION:-}"
  [ -n "${intended}" ] || die \
"GDPVAL_DEV_HOST_SUBSCRIPTION is not set.

 This script will not pick a subscription for you. The card puts the
 development host in the external subscription and keeps it away from the
 internal one that carries the Foundry permissions, and 'whichever one az
 happened to be signed into' is not a way to honour that."

  current="$(az account show --query id -o tsv 2>/dev/null || true)"
  [ -n "${current}" ] || die "not signed in: run 'az login' first"

  # Accept either an id or a name for the intended subscription.
  local resolved
  resolved="$(az account show --subscription "${intended}" --query id -o tsv 2>/dev/null || true)"
  [ -n "${resolved}" ] || die "GDPVAL_DEV_HOST_SUBSCRIPTION does not resolve to a subscription this sign-in can see (fingerprint $(fingerprint "${intended}"))"

  expected="${AZURE_AI_EXPECTED_SUBSCRIPTION_ID:-}"
  if [ -n "${expected}" ] && [ "${resolved}" = "${expected}" ]; then
    die \
"refusing: the subscription named here is the one the Foundry checks expect.

 That is the internal path this repository authenticates its paid model calls
 through, and the card says the development host does not go there. If this is
 genuinely wrong, it is wrong in AZURE_AI_EXPECTED_SUBSCRIPTION_ID, not here.
 (target fingerprint $(fingerprint "${resolved}"))"
  fi

  if [ "${current}" != "${resolved}" ]; then
    log "switching to the named subscription (fingerprint $(fingerprint "${resolved}"))"
    az account set --subscription "${resolved}"
  fi
  log "subscription fingerprint: $(fingerprint "${resolved}")"
}

require_key() {
  KEY_FILE="${GDPVAL_DEV_HOST_SSH_PUBLIC_KEY:-${HOME}/.ssh/id_ed25519.pub}"
  [ -f "${KEY_FILE}" ] || die \
"no public key at ${KEY_FILE}.

 There is no password path -- main.bicep sets disablePasswordAuthentication and
 has no default for the key -- so a machine cannot be created without one. Point
 GDPVAL_DEV_HOST_SSH_PUBLIC_KEY at the key you want to use, or generate one:
   ssh-keygen -t ed25519 -C gdpval-devhost"
  PUBLIC_KEY="$(cat "${KEY_FILE}")"
  case "${PUBLIC_KEY}" in
    ssh-ed25519*|ssh-rsa*|ecdsa-sha2-*) : ;;
    *) die "${KEY_FILE} does not look like an OpenSSH public key" ;;
  esac
}

parameters() {
  # sshAllowedSourcePrefixes is deliberately absent unless the operator sets it.
  # Absent means no inbound rule at all; there is no branch that turns an unset
  # variable into a wildcard.
  local args=(
    "location=${LOCATION}"
    "namePrefix=${NAME_PREFIX}"
    "adminPublicKey=${PUBLIC_KEY}"
  )
  if [ -n "${GDPVAL_DEV_HOST_VM_SIZE:-}" ]; then
    args+=("vmSize=${GDPVAL_DEV_HOST_VM_SIZE}")
  fi
  if [ -n "${GDPVAL_DEV_HOST_SSH_SOURCES:-}" ]; then
    args+=("sshAllowedSourcePrefixes=${GDPVAL_DEV_HOST_SSH_SOURCES}")
  fi
  if [ -n "${GDPVAL_DEV_HOST_PUBLIC_IP:-}" ]; then
    args+=("attachPublicIp=${GDPVAL_DEV_HOST_PUBLIC_IP}")
  fi
  printf '%s\n' "${args[@]}"
}

ensure_group() {
  if ! az group show --name "${RESOURCE_GROUP}" > /dev/null 2>&1; then
    log "creating resource group ${RESOURCE_GROUP} in ${LOCATION}"
    az group create --name "${RESOURCE_GROUP}" --location "${LOCATION}" \
      --tags purpose=gdpval-devhost benchmark_execution_environment=no > /dev/null
  fi
}

case "${COMMAND}" in
  plan)
    require_subscription
    require_key
    ensure_group
    mapfile -t PARAMS < <(parameters)
    az deployment group what-if \
      --resource-group "${RESOURCE_GROUP}" \
      --name "${DEPLOYMENT_NAME}" \
      --template-file "${HERE}/main.bicep" \
      --parameters "${PARAMS[@]}"
    ;;

  deploy)
    require_subscription
    require_key
    ensure_group
    mapfile -t PARAMS < <(parameters)
    log "deploying"
    az deployment group create \
      --resource-group "${RESOURCE_GROUP}" \
      --name "${DEPLOYMENT_NAME}" \
      --template-file "${HERE}/main.bicep" \
      --parameters "${PARAMS[@]}" \
      --query 'properties.outputs' -o json > /tmp/dev-host-outputs.json
    cat /tmp/dev-host-outputs.json

    # `latest` is what the card asks for and is not something a later reader can
    # reproduce from, so the version it resolved to is written down here.
    log "recording what was actually created"
    az vm show --resource-group "${RESOURCE_GROUP}" --name "${VM_NAME}" \
      --query '{
        vmSize: hardwareProfile.vmSize,
        location: location,
        image: storageProfile.imageReference,
        osDiskSizeGb: storageProfile.osDisk.diskSizeGb,
        identityType: identity.type,
        passwordAuthenticationDisabled: osProfile.linuxConfiguration.disablePasswordAuthentication,
        securityType: securityProfile.securityType
      }' -o json > "${PROVENANCE}"
    az network nsg rule list --resource-group "${RESOURCE_GROUP}" --nsg-name "${NAME_PREFIX}-nsg" \
      --query '[].{name:name,access:access,direction:direction,port:destinationPortRange,sources:sourceAddressPrefixes,source:sourceAddressPrefix}' \
      -o json > /tmp/dev-host-nsg.json
    log "provenance: ${PROVENANCE}"
    log "nsg rules:  /tmp/dev-host-nsg.json"
    ;;

  bootstrap)
    require_subscription
    log "running bootstrap.sh through the Azure agent (no inbound port is used)"
    az vm run-command invoke \
      --resource-group "${RESOURCE_GROUP}" \
      --name "${VM_NAME}" \
      --command-id RunShellScript \
      --scripts "@${HERE}/bootstrap.sh" \
      --query 'value[0].message' -o tsv | tee /tmp/dev-host-bootstrap.log
    log "log: /tmp/dev-host-bootstrap.log"
    ;;

  status)
    require_subscription
    az vm show --resource-group "${RESOURCE_GROUP}" --name "${VM_NAME}" -d \
      --query '{name:name,power:powerState,size:hardwareProfile.vmSize,location:location}' -o table
    az deployment group show --resource-group "${RESOURCE_GROUP}" --name "${DEPLOYMENT_NAME}" \
      --query 'properties.provisioningState' -o tsv 2>/dev/null || true
    echo
    echo "Auto-shutdown schedule:"
    az resource show --resource-group "${RESOURCE_GROUP}" \
      --resource-type Microsoft.DevTestLab/schedules \
      --name "shutdown-computevm-${VM_NAME}" \
      --query 'properties.{status:status,time:dailyRecurrence.time,zone:timeZoneId}' -o table 2>/dev/null \
      || echo "  (none found)"
    ;;

  deallocate)
    require_subscription
    # Deallocate, not stop. A guest `shutdown -h` leaves the machine Stopped and
    # still billed for its compute reservation; this releases it.
    log "deallocating ${VM_NAME} (disks are kept and still cost)"
    az vm deallocate --resource-group "${RESOURCE_GROUP}" --name "${VM_NAME}"
    az vm show --resource-group "${RESOURCE_GROUP}" --name "${VM_NAME}" -d --query powerState -o tsv
    ;;

  start)
    require_subscription
    az vm start --resource-group "${RESOURCE_GROUP}" --name "${VM_NAME}"
    az vm show --resource-group "${RESOURCE_GROUP}" --name "${VM_NAME}" -d --query powerState -o tsv
    ;;

  delete)
    require_subscription
    [ "${GDPVAL_DEV_HOST_CONFIRM_DELETE:-}" = "${RESOURCE_GROUP}" ] || die \
"refusing to delete ${RESOURCE_GROUP}.

 Set GDPVAL_DEV_HOST_CONFIRM_DELETE to the resource group name to confirm.
 Everything in the group goes, including the data disk -- recover the artifacts
 first."
    log "deleting resource group ${RESOURCE_GROUP}"
    az group delete --name "${RESOURCE_GROUP}" --yes
    ;;

  help|--help|-h)
    sed -n '2,30p' "${BASH_SOURCE[0]}"
    ;;

  *)
    die "unknown command '${COMMAND}'. Try: plan deploy bootstrap status deallocate start delete"
    ;;
esac
