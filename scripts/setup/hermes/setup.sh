#!/usr/bin/env bash
# setup.sh — Install and configure Hermes Agent host daemon using official installer
#
# Usage:
#   ./scripts/setup/hermes/setup.sh
#
# Runs as non-root user (e.g. grimur) on Debian NAS host (pippinn).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HERMES_DIR="${HOME}/.hermes"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"
LOCAL_BIN="${HOME}/.local/bin"

echo "==> Setting up Hermes Agent Host Daemon (Official Standalone Installer)..."

# 1. Ensure curl and git are available
for cmd in curl git; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "Error: $cmd is required but not installed. Install with: sudo apt install -y $cmd" >&2
        exit 1
    fi
done

# 2. Run official installer if hermes binary is not present
mkdir -p "${LOCAL_BIN}"
if ! command -v hermes >/dev/null 2>&1 && [[ ! -x "${LOCAL_BIN}/hermes" ]]; then
    echo "==> Running official Hermes Agent installer..."
    curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
fi

# Clean up legacy pip virtualenv if it exists
if [[ -d "${HOME}/.local/share/hermes/venv" ]]; then
    echo "==> Removing deprecated pip virtualenv..."
    rm -rf "${HOME}/.local/share/hermes/venv"
fi

# 3. Create ~/.hermes configuration
echo "==> Configuring ~/.hermes..."
mkdir -p "${HERMES_DIR}"

if [[ ! -f "${HERMES_DIR}/config.yaml" ]]; then
    cat <<'EOF' > "${HERMES_DIR}/config.yaml"
# Hermes Agent Configuration
model:
  default: gemini-2.5-pro
  provider: gemini
  base_url: https://generativelanguage.googleapis.com/v1beta

terminal:
  backend: local

gateway:
  host: 172.17.0.1
  port: 8642

security:
  tirith_enabled: true

approvals:
  mode: smart
  timeout: 300
EOF
    echo "Created ${HERMES_DIR}/config.yaml with Gemini provider & Tirith Smart approval mode."
else
    echo "${HERMES_DIR}/config.yaml already exists. Preserving existing configuration."
fi

# 4. Initialize .env template if not present
if [[ ! -f "${HERMES_DIR}/.env" ]]; then
    cat <<'EOF' > "${HERMES_DIR}/.env"
# Hermes Agent Secrets
GEMINI_API_KEY=
GOOGLE_API_KEY=

# API Server Configuration (required for Hermes Workspace)
API_SERVER_ENABLED=true
API_SERVER_HOST=172.17.0.1
API_SERVER_PORT=8642
API_SERVER_KEY=
EOF
    chmod 600 "${HERMES_DIR}/.env"
    echo "Created ${HERMES_DIR}/.env (chmod 600). Please add your API keys."
else
    echo "${HERMES_DIR}/.env already exists."
fi

# 5. Install systemd user service
echo "==> Installing systemd user service..."
mkdir -p "${SYSTEMD_USER_DIR}"
cp "${SCRIPT_DIR}/hermes.service" "${SYSTEMD_USER_DIR}/hermes.service"

systemctl --user daemon-reload
systemctl --user enable hermes.service

# Enable lingering for the user so systemd user services run when logged out
if command -v loginctl >/dev/null 2>&1; then
    if ! loginctl enable-linger "${USER}" 2>/dev/null; then
        echo "Note: If linger is not enabled, run: sudo loginctl enable-linger ${USER}"
    fi
fi

echo ""
echo "✅ Hermes Agent daemon setup complete!"
echo ""
echo "Next steps:"
echo "1. Verify ~/.hermes/.env contains your GOOGLE_API_KEY / GEMINI_API_KEY and API_SERVER_KEY"
echo "2. Start the service: systemctl --user start hermes.service"
echo "3. Check status:     systemctl --user status hermes.service"
echo "4. Check logs:       journalctl --user -u hermes.service -f"
