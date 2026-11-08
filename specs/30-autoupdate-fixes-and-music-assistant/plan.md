# Milestone 30: Autoupdater Socket Permission Fix & Music Assistant Autoupdate

## 1. Objectives
1. Fix permission failure on `/var/run/docker.sock` in `autoupdater` container by aligning container group ID with host docker GID (host GID is 995, compose had 992).
2. Enable automated updates for `music-assistant-server` by adding `wud.autoupdate=true` label in `services/home-assistant/compose.yaml`.
3. Verify `autoupdater` functionality against the Docker API.

## 2. Changes
- **`infrastructure/wud/compose.yaml`**: Update `autoupdater` service user from `1000:992` to `1000:995`.
- **`services/home-assistant/compose.yaml`**: Add label `"wud.autoupdate=true"` to `music-assistant-server`.

## 3. Impact Analysis
- `autoupdater`: Brief container recreation via `docker compose up -d autoupdater`. Gains valid write/read access to Docker daemon socket.
- `music-assistant-server`: Compose config change; container will be updated via WUD autoupdater trigger on next check or webhook trigger.
- Security/Persistence: No secrets touched. GID 995 matches host `docker` group membership for user `grimur` (`1000`).

## 4. Rollback Plan
- Revert `user: "1000:995"` back to `user: "1000:992"` if permission regressions occur.
- Revert `"wud.autoupdate=true"` label from `services/home-assistant/compose.yaml` if autonomous updates fail.
