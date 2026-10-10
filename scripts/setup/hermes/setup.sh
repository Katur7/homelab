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

# 1. Ensure Python 3 and venv support are available
if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 is required but not installed." >&2
    exit 1
fi

if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
    echo "Error: 'ensurepip' module is missing. On Debian/Ubuntu, python3-venv is required." >&2
    echo "Please run on the host:" >&2
    echo "  sudo apt update && sudo apt install -y python3-venv python3-pip" >&2
    exit 1
fi

# 2. Create virtual environment
echo "==> Creating virtual environment at ${VENV_DIR}..."
mkdir -p "$(dirname "${VENV_DIR}")"

# If directory exists but pip is missing, cleanup the broken venv
if [[ -d "${VENV_DIR}" && ! -f "${VENV_DIR}/bin/pip" ]]; then
    echo "Existing virtualenv at ${VENV_DIR} is incomplete (missing pip). Removing and recreating..."
    rm -rf "${VENV_DIR}"
fi

if [[ ! -d "${VENV_DIR}" ]]; then
    if ! python3 -m venv "${VENV_DIR}"; then
        echo "" >&2
        echo "Error: Failed to create virtualenv. Please ensure python3-venv is installed:" >&2
        echo "  sudo apt update && sudo apt install -y python3-venv python3-pip" >&2
        rm -rf "${VENV_DIR}"
        exit 1
    fi
fi

# 3. Install or update hermes-agent
echo "==> Installing hermes-agent in virtualenv..."
if [[ ! -f "${VENV_DIR}/bin/pip" ]]; then
    echo "Error: ${VENV_DIR}/bin/pip was not created. Running ensurepip..." >&2
    "${VENV_DIR}/bin/python3" -m ensurepip --upgrade || true
fi

"${VENV_DIR}/bin/pip" install --upgrade pip
"${VENV_DIR}/bin/pip" install --upgrade hermes-agent aiohttp

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

# API Server Configuration (required for Hermes Workspace)
API_SERVER_ENABLED=true
API_SERVER_HOST=0.0.0.0
API_SERVER_PORT=8642
API_SERVER_KEY=
EOF
    chmod 600 "${HERMES_DIR}/.env"
    echo "Created ${HERMES_DIR}/.env (chmod 600). Please add your GEMINI_API_KEY and API_SERVER_KEY."
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
