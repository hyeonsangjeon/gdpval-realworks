#!/usr/bin/env bash
# Give this job's own account permission to open /dev/kvm, and nothing more.
#
# Run 35072131325 on ubuntu-24.04 (kernel 6.17.0-1022-azure) read the runner and
# found the device present, the processor reporting vmx, and the kernel well
# above what Firecracker validates against -- and the open refused:
#
#     /dev/kvm is present and this process may not open it (Permission denied)
#
# That is the ordinary Ubuntu arrangement. udev ships the node as root:kvm 0660
# and the account a job runs as is not in the kvm group, so seeing the device
# and being allowed to use it come apart. Group membership cannot fix it from
# inside a running process: a supplementary group is read at login, and this
# process has already logged in.
#
# So an ACL entry for exactly this account, which takes effect immediately and
# leaves root:kvm 0660 as it was. If setfacl is not on the image, the fallback
# hands the node to this account at mode 0600. Deliberately not `chmod 0666`,
# which is the recipe that circulates: it opens the device to every account on
# the machine, and there is no reason to widen it past the one that asked.
#
# The jail account is untouched on purpose. The jailer mknods its own /dev/kvm
# inside the chroot and chowns it to the jailed uid, so it never reads the
# host's node -- and `account_to_jail_to` in run_agentic_c2_first_boot.py
# refuses outright if that account has gained any group beyond its own.
#
# This decides nothing. It changes a permission and then says what the
# permission is; whether the runner can host a guest is still settled by
# check_runner_can_host_a_guest.py, which opens the device and asks it to make
# a machine. A grant that failed shows up there as a refusal, which is why this
# script exits 0 either way rather than pre-empting the reading.
set -uo pipefail

DEVICE="${1:-/dev/kvm}"
ACCOUNT="$(id -un)"

say() { printf '%s\n' "$*"; }

if [ ! -e "$DEVICE" ]; then
  say "$DEVICE is not on this machine, so there is no permission to grant."
  say "The capability reading will refuse, and it will be right to."
  exit 0
fi

say "before: $(ls -l "$DEVICE")"

if command -v setfacl >/dev/null 2>&1; then
  if sudo setfacl -m "u:${ACCOUNT}:rw" "$DEVICE" 2>/dev/null; then
    say "granted: an ACL entry giving ${ACCOUNT} read and write on $DEVICE"
    say "after:  $(ls -l "$DEVICE")"
    getfacl -p "$DEVICE" 2>/dev/null || true
    exit 0
  fi
  say "setfacl is installed and did not take; falling back to ownership"
else
  say "no setfacl on this image; falling back to ownership"
fi

if sudo chown "$ACCOUNT" "$DEVICE" && sudo chmod u+rw "$DEVICE"; then
  say "granted: $DEVICE now belongs to ${ACCOUNT}"
  say "after:  $(ls -l "$DEVICE")"
  exit 0
fi

say "neither an ACL entry nor a change of owner took on $DEVICE."
say "Nothing was granted. The capability reading below is the answer."
exit 0
