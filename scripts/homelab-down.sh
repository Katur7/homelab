#!/usr/bin/env bash
# homelab-down.sh — Save active stack state, then tear down all containers.
# Called by homelab-containers.service ExecStop (before Docker daemon shuts down).
# Removes all containers + containerd task references to prevent stale-task exit-128
# errors after Docker engine updates.
#
# No set -e: teardown must always proceed regardless of individual failures.

set -uo pipefail

# shellcheck source=homelab-common.sh
source "$(dirname "$0")/homelab-common.sh"

failed=0

# --- Phase 0: Save which stacks have running containers (best-effort) ---
# Single docker ps call reads compose project labels — atomic snapshot, avoids
# the per-stack "docker compose ps" loop that was unreliable under systemd stop.
echo "Saving active stack state to $STATE_FILE ..."
if active=$(docker ps --format '{{.Label "com.docker.compose.project.working_dir"}}' 2>/dev/null | sort -u | grep -v '^$'); then
    echo "$active" > "$STATE_FILE"
    count=$(echo "$active" | wc -l)
    echo "Recorded $count active stack(s)."
else
    : > "$STATE_FILE"
    echo "WARNING: No active stacks detected (or docker ps failed)."
fi

# --- Phase 1: Tear down service stacks (parallel) ---
echo "Stopping service stacks ..."
pids=()
for dir in "$HOMELAB"/services/*/; do
    [ -f "${dir}compose.yaml" ] || continue
    docker compose -f "${dir}compose.yaml" down --remove-orphans &
    pids+=($!)
done
if (( ${#pids[@]} )); then
    for pid in "${pids[@]}"; do
        if ! wait "$pid"; then
            echo "WARNING: A service stack failed to stop (pid $pid)."
            failed=1
        fi
    done
fi

# --- Phase 2: Tear down infrastructure stacks (reverse dependency order) ---
echo "Stopping infrastructure stacks ..."

# Auto-discovered non-priority stacks first (any order)
for dir in "$HOMELAB"/infrastructure/*/; do
    [ -f "${dir}compose.yaml" ] || continue
    name=$(basename "$dir")
    [[ " ${INFRA_PRIORITY[*]} " == *" $name "* ]] && continue
    if ! docker compose -f "${dir}compose.yaml" down --remove-orphans; then
        echo "WARNING: Failed to stop infrastructure/$name."
        failed=1
    fi
done

# Priority stacks last (reverse order — gateway stops last)
for (( i=${#INFRA_PRIORITY[@]}-1; i>=0; i-- )); do
    name="${INFRA_PRIORITY[i]}"
    dir="$HOMELAB/infrastructure/$name"
    [ -f "$dir/compose.yaml" ] || continue
    if ! docker compose -f "$dir/compose.yaml" down --remove-orphans; then
        echo "WARNING: Failed to stop infrastructure/$name."
        failed=1
    fi
done

if (( failed )); then
    echo "Teardown completed with errors. Check journalctl for details."
else
    echo "All stacks torn down."
fi
# Always exit 0 — the unit must stay 'active' so PartOf= triggers ExecStop
# on the next Docker restart. A non-zero exit puts it in 'failed' state,
# which skips ExecStop and defeats the stale-task prevention.
exit 0
