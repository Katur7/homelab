#!/usr/bin/env bash
set -euo pipefail

# setup-docker-maintenance.sh
# Configures Docker log rotation in /etc/docker/daemon.json and installs
# the weekly docker-prune systemd service and timer.
#
# Usage:
#   sudo ./scripts/setup-docker-maintenance.sh

if [[ $EUID -ne 0 ]]; then
   echo "Error: This script must be run as root (or with sudo)." >&2
   exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DAEMON_JSON="/etc/docker/daemon.json"

echo "==> Configuring Docker log rotation in ${DAEMON_JSON}..."
mkdir -p /etc/docker

if [[ ! -f "${DAEMON_JSON}" ]]; then
    cat <<'EOF' > "${DAEMON_JSON}"
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "20m",
    "max-file": "3"
  }
}
EOF
    echo "Created new ${DAEMON_JSON}."
else
    # Merge existing JSON with log-opts safely using python3 or jq
    if command -v python3 >/dev/null 2>&1; then
        python3 - <<'PY'
import json

path = '/etc/docker/daemon.json'
try:
    with open(path, 'r') as f:
        data = json.load(f)
except Exception:
    data = {}

data["log-driver"] = "json-file"
data["log-opts"] = {
    "max-size": "20m",
    "max-file": "3"
}

with open(path, 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
PY
        echo "Updated existing ${DAEMON_JSON}."
    else
        echo "Warning: python3 not found; please ensure log-opts are merged into ${DAEMON_JSON} manually."
    fi
fi

echo "==> Reloading Docker daemon configuration..."
if systemctl is-active --quiet docker; then
    systemctl reload docker || systemctl restart docker
fi

echo "==> Installing docker-prune systemd service and timer..."
cp "${SCRIPT_DIR}/docker-prune.service" /etc/systemd/system/
cp "${SCRIPT_DIR}/docker-prune.timer" /etc/systemd/system/

systemctl daemon-reload
systemctl enable --now docker-prune.timer

echo "==> Verifying timer status:"
systemctl list-timers docker-prune.timer --no-pager

echo ""
echo "✅ Docker log rotation and weekly prune timer successfully configured!"

