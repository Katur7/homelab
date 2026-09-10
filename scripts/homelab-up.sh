#!/usr/bin/env bash
# homelab-up.sh — Restore previously-active stacks after Docker daemon restart.
# Called by homelab-containers.service ExecStart (after Docker daemon is up).
# Only starts stacks that were running before the daemon stopped, preserving
# intentionally-stopped services.
#
# If no state file exists (first boot after install), this is a no-op.
#
# No set -e: must attempt all stacks. Always exits 0 so the systemd unit stays
# active — if it enters 'failed' state, PartOf= skips ExecStop on next Docker
# restart, which defeats the whole purpose. Failures are logged to journalctl.

set -uo pipefail

# shellcheck source=homelab-common.sh
source "$(dirname "$0")/homelab-common.sh"

# --- Check for state file ---
if [ ! -f "$STATE_FILE" ]; then
    echo "No state file found. Skipping."
    exit 0
fi

if [ ! -s "$STATE_FILE" ]; then
    echo "State file is empty (no stacks were active). Nothing to restore."
    rm -f "$STATE_FILE"
    exit 0
fi

echo "Restoring stacks from $STATE_FILE ..."
failed=0

# --- Phase 1: Infrastructure stacks (sequential, ordered) ---
echo "Starting infrastructure stacks ..."

# Priority stacks first (ordered — gateway creates networks others depend on)
for name in "${INFRA_PRIORITY[@]}"; do
    dir="$HOMELAB/infrastructure/$name"
    [ -f "$dir/compose.yaml" ] || continue
    if grep -Fxq "$dir" "$STATE_FILE"; then
        echo "  Starting $name ..."
        if ! docker compose -f "$dir/compose.yaml" up -d; then
            echo "WARNING: Failed to start infrastructure/$name."
            failed=1
        fi
    fi
done

# Auto-discovered non-priority infra stacks (any order)
for dir in "$HOMELAB"/infrastructure/*/; do
    [ -f "${dir}compose.yaml" ] || continue
    name=$(basename "$dir")
    [[ " ${INFRA_PRIORITY[*]} " == *" $name "* ]] && continue
    if grep -Fxq "${dir%/}" "$STATE_FILE"; then
        echo "  Starting $name ..."
        if ! docker compose -f "${dir}compose.yaml" up -d; then
            echo "WARNING: Failed to start infrastructure/$name."
            failed=1
        fi
    fi
done

# --- Phase 2: Service stacks (parallel, only active ones) ---
echo "Starting service stacks ..."
pids=()
for dir in "$HOMELAB"/services/*/; do
    [ -f "${dir}compose.yaml" ] || continue
    if grep -Fxq "${dir%/}" "$STATE_FILE"; then
        echo "  Starting $(basename "$dir") ..."
        docker compose -f "${dir}compose.yaml" up -d &
        pids+=($!)
    fi
done
if (( ${#pids[@]} )); then
    for pid in "${pids[@]}"; do
        if ! wait "$pid"; then
            echo "WARNING: A service stack failed to start (pid $pid)."
            failed=1
        fi
    done
fi

rm -f "$STATE_FILE"

if (( failed )); then
    echo "Some stacks failed to restore. Check journalctl for details."
else
    echo "All active stacks restored."
fi
exit 0
