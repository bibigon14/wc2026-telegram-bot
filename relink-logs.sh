#!/usr/bin/env bash
# relink-logs.sh - find the current local-path PVC directory for
# wc2026bot-log and repoint ./access.log at it.
#
# Why this exists: k3s's local-path-provisioner names each PVC's backing
# directory after the PV's UID (pvc-<uid>_<namespace>_<pvc-name>). If the
# PVC is ever recreated (helm uninstall/install, PV reclaim, etc.) the UID
# changes and any existing symlink silently breaks - `ls` shows it, but
# reads fail with a confusing "Permission denied" (broken target) instead
# of a clear "no such PVC" error.
#
# Usage: ./relink-logs.sh [namespace] [pvc-name] [filename] [link-name]
# Defaults match the wc2026bot setup; override if reusing for another app.

set -euo pipefail

NAMESPACE="${1:-apps}"
PVC_NAME="${2:-wc2026bot-log}"
LOG_FILE="${3:-access.log}"
LINK_NAME="${4:-access.log}"

STORAGE_ROOT="/var/lib/rancher/k3s/storage"

# local-path-provisioner directory naming: pvc-<pv-uid>_<namespace>_<pvc-name>
PV_NAME=$(kubectl get pvc "$PVC_NAME" -n "$NAMESPACE" -o jsonpath='{.spec.volumeName}' 2>/dev/null) || {
  echo "Error: PVC '$PVC_NAME' not found in namespace '$NAMESPACE'." >&2
  exit 1
}

if [ -z "$PV_NAME" ]; then
  echo "Error: PVC '$PVC_NAME' exists but has no bound PV (not yet provisioned?)." >&2
  exit 1
fi

TARGET_DIR="${STORAGE_ROOT}/${PV_NAME}_${NAMESPACE}_${PVC_NAME}"
TARGET_PATH="${TARGET_DIR}/${LOG_FILE}"

if ! sudo test -d "$TARGET_DIR"; then
  echo "Error: expected directory not found: $TARGET_DIR" >&2
  echo "Listing what's actually under ${STORAGE_ROOT}/ matching '${PVC_NAME}':" >&2
  sudo ls -la "$STORAGE_ROOT" 2>/dev/null | grep "$PVC_NAME" >&2 || echo "  (nothing matched - PVC dir may not exist yet)" >&2
  exit 1
fi

# If a symlink (broken or not) already exists at LINK_NAME, remove it first.
if [ -L "$LINK_NAME" ]; then
  CURRENT_TARGET=$(readlink "$LINK_NAME")
  if [ "$CURRENT_TARGET" = "$TARGET_PATH" ]; then
    echo "Already correctly linked: $LINK_NAME -> $TARGET_PATH"
    # Still ensure ACL is set in case it was reset
    sudo setfacl -R -m u:${USER}:rX "$STORAGE_ROOT"
    sudo setfacl -d -m u:${USER}:rX "$STORAGE_ROOT"
    exit 0
  fi
  echo "Removing stale symlink (was -> $CURRENT_TARGET)"
  rm "$LINK_NAME"
elif [ -e "$LINK_NAME" ]; then
  echo "Error: $LINK_NAME exists and is not a symlink - refusing to overwrite." >&2
  exit 1
fi

ln -s "$TARGET_PATH" "$LINK_NAME"
echo "Linked: $LINK_NAME -> $TARGET_PATH"

# Grant read access to the storage root via ACL so sudo isn't needed for reads.
echo "Setting ACL on ${STORAGE_ROOT} for user ${USER}..."
sudo setfacl -R -m u:${USER}:rX "$STORAGE_ROOT"
sudo setfacl -d -m u:${USER}:rX "$STORAGE_ROOT"
echo "ACL set - ${USER} can now read PVC directories without sudo."

# Sanity check
if test -r "$TARGET_PATH"; then
  echo "Verified: target is readable."
else
  echo "Warning: symlink created, but target is not readable yet (file may not exist until the pod writes to it)." >&2
fi
