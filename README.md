# Pippinn Home Lab Infrastructure (GitOps-Lite)

This repository is the **Single Source of Truth** for the Docker-based 
services running on the OMV NAS. 
It is managed by the user `grimur` (UID 1000) to ensure IDE 
compatibility and version control.

## 📁 Repository Structure
- `/infrastructure/`: Core services (Traefik v3, Cloudflare Tunnel, Authelia).
- `/services/`: Application stacks (Immich, HomeAssistant, etc.).
- `/pi/`: Raspberry Pi host — backup DNS, sync, and uptime monitoring.
- `global.env`: System-wide variables (Domains, PUID/PGID).
- `ARCHITECTURE.md`: Technical details on networking and volume strategy.
- `AI_INSTRUCTIONS.md`: Critical rules for AI agents modifying this repo.

## 🚀 Quick Workflow
1. **Edit:** Use VS Code (Remote SSH) to modify `compose.yaml` or `vars.env`.
2. **Validate:** `docker compose config`
3. **Deploy:** `docker compose up -d --remove-orphans`
4. **Commit:** `git add . && git commit -m "Update <service>"`

---
*Note: OMV is used for storage management only. Do not use the OMV Docker Compose UI to manage these stacks.*