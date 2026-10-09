#!/usr/bin/env bash
# setup.sh — Install and configure Hermes Agent host daemon with Tirith smart approvals
#
# Usage:
#   ./scripts/setup/hermes/setup.sh
#
# Runs as non-root user (e.g. grimur) on Debian NAS host (pippinn).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HERMES_DIR="${HOME}/.hermes"
VENV_DIR="${HOME}/.local/share/hermes/venv"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"

echo "==> Setting up Hermes Agent Host Daemon..."

# 1. Ensure Python 3 venv is available
if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 is required but not installed." >&2
    exit 1
fi

# 2. Create virtual environment
echo "==> Creating virtual environment at ${VENV_DIR}..."
mkdir -p "$(dirname "${VENV_DIR}")"
if [[ ! -d "${VENV_DIR}" ]]; then
    python3 -m venv "${VENV_DIR}"
fi

# 3. Install or update hermes-agent
echo "==> Installing hermes-agent in virtualenv..."
"${VENV_DIR}/bin/pip" install --upgrade pip
"${VENV_DIR}/bin/pip" install --upgrade hermes-agent

# 4. Create ~/.hermes configuration
echo "==> Configuring ~/.hermes..."
mkdir -p "${HERMES_DIR}"

if [[ ! -f "${HERMES_DIR}/config.yaml" ]]; then
    cat <<'EOF' > "${HERMES_DIR}/config.yaml"
# Hermes Agent Configuration
model: gemini-3.8-flash

terminal:
  backend: local

gateway:
  host: 0.0.0.0
  port: 8642

security:
  tirith_enabled: true

approvals:
  mode: smart
  timeout: 300
EOF
    echo "Created ${HERMES_DIR}/config.yaml with Tirith Smart approval mode."
else
    echo "${HERMES_DIR}/config.yaml already exists. Preserving existing configuration."
fi

# 5. Initialize .env template if not present
if [[ ! -f "${HERMES_DIR}/.env" ]]; then
    cat <<'EOF' > "${HERMES_DIR}/.env"
# Hermes Agent Secrets
GEMINI_API_KEY=
EOF
    chmod 600 "${HERMES_DIR}/.env"
    echo "Created ${HERMES_DIR}/.env (chmod 600). Please add your GEMINI_API_KEY."
else
    echo "${HERMES_DIR}/.env already exists."
fi

# 6. Install systemd user service
echo "==> Installing systemd user service..."
mkdir -p "${SYSTEMD_USER_DIR}"
cp "${SCRIPT_DIR}/hermes.service" "${SYSTEMD_USER_DIR}/hermes.service"

systemctl --user daemon-reload
systemctl --user enable hermes.service

# Enable lingering for the user so systemd user services run when logged out
if command -v loginctl >/dev/null 2>&1; then
    loginctl enable-linger "${USER}" || true
fi

echo ""
echo "✅ Hermes Agent daemon setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit ${HERMES_DIR}/.env and set your GEMINI_API_KEY"
echo "2. Start the service: systemctl --user start hermes.service"
echo "3. Check status:     systemctl --user status hermes.service"
echo "4. Check logs:       journalctl --user -u hermes.service -f"
