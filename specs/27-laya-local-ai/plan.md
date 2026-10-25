# Milestone 27: Laya Local AI Stack (HA Assist Proxy & Decision Engine)

## 📌 Context & Objectives

To enable low-latency, private, local intent recognition for the Home Assistant Assist voice pipeline while retaining conversational intelligence for complex queries, we are deploying **`laya-assist-proxy`** (`dwyschka/laya-assist-proxy`) powered by **Convai's Laya** (`convaiinnovations/laya-multilingual`):

1. **System 1 Single-Pass Classification:** Unlike autoregressive LLMs that generate tokens sequentially, Laya evaluates voice/text commands against exposed Home Assistant intents, areas, and entities in a single forward pass (~150–200ms on CPU, with `/dev/dri` passed through for optional OpenVINO/iGPU optimization).
2. **Built-in Testing Web UI & Trace Inspector:** Exposed internally via Traefik at `https://laya.internal.pippinn.me` (LAN IP allowlist, no Authelia) for interactive testing of utterances, confidence score inspection, and entity catalog management.
3. **OpenAI-Compatible Bridge for Home Assistant:** Exposes `/v1/chat/completions` and `/v1/models` on port `7788` so Home Assistant's built-in **OpenAI Conversation** integration can use Laya as a native Conversation Agent in Assist pipelines.
4. **Smart LLM Escalation (Fallback):** High-confidence routine commands execute locally via direct Home Assistant tool calls; ambiguous, compound, or low-confidence queries seamlessly fall back to Google Gemini (`https://generativelanguage.googleapis.com/v1beta/openai`).
5. **Multilingual Support:** Configured with `multilingual` (`convaiinnovations/laya-multilingual`) to support English, Swedish, and Icelandic commands.

---

## 🛠️ Architecture & Decisions

### 1. Container & Service Layout (`services/laya/`)
- **Build Strategy:** Custom `Dockerfile` in `services/laya/Dockerfile` based on `python:3.12-slim` (pinned), installing CPU-only PyTorch (`--index-url https://download.pytorch.org/whl/cpu` to avoid 3GB+ CUDA bloat) and `dwyschka/laya-assist-proxy`.
- **Network Topology:**
  - Connected exclusively to `traefik_internal` (no host `ports:` or `extra_hosts` needed).
  - Traefik routes `https://laya.internal.pippinn.me` to container port `7788` (accessible to both browser UI and Home Assistant at `https://laya.internal.pippinn.me/v1`).
  - Laya reaches Home Assistant via `https://home-assistant.pippinn.me` over REST/WebSockets to sync exposed entities, areas, and voice aliases.
- **Hardware & Resource Limits:**
  - `/dev/dri:/dev/dri` passed through for Intel N150 iGPU / OpenVINO acceleration testing.
  - CPU limit: `4.0` cores (full burst across N150 cores during forward-pass inference).
  - Memory limit: `4096M` (accommodates ~1.6GB multilingual model weights + runtime).
- **Volumes & Backup Hygiene:**
  - `./data:/data` (`LAYA_ASSIST_HOME=/data`): Stores `project.yaml` (entity catalog, thresholds, settings) and `secrets.local.json` (HA Long-Lived Access Token, Gemini API key). Gitignored, **included** in BorgBackup.
  - `./cache:/cache` (`HF_HOME=/cache`): Stores downloaded Hugging Face model weights (~1.6GB). Gitignored, **excluded** from BorgBackup (`borg-exclude-homelab.txt`) as weights are regenerable.

### 2. Traefik & DNS Configuration
- **Internal Route:** `Host(\`laya.internal.pippinn.me\`)` on `websecure` entrypoint (protected by global `internal-only` LAN IP allowlist middleware, no Authelia).
- **DNS:** Register `laya` via `./scripts/add-dns.sh laya`.

### 3. Home Assistant Integration
- **HA -> Laya (Catalog Sync):** Generate a Long-Lived Access Token in Home Assistant and configure it in the Laya Web UI (`https://home-assistant.pippinn.me`). Laya uses this over WebSocket/REST to inspect entities exposed to Assist.
- **Laya -> HA (Conversation Agent):** Add the **OpenAI Conversation** (or Extended OpenAI Conversation) integration in Home Assistant pointing to Base URL `https://laya.internal.pippinn.me/v1` (with dummy API key `laya`), and assign it to an Assist Voice Pipeline.

---

## 📋 Execution Steps

### Step 1: Create Service Definition & Dockerfile
1. Create [`services/laya/Dockerfile`](file:///Users/grimur/personal-code/homelab/services/laya/Dockerfile) (pinned `python:3.12-slim`, CPU PyTorch wheel, `laya-assist-proxy`).
2. Create [`services/laya/compose.yaml`](file:///Users/grimur/personal-code/homelab/services/laya/compose.yaml) with Traefik v3 labels, `/dev/dri` passthrough, and `4.0` CPU / `4096M` RAM limits.
3. Create [`services/laya/vars.env`](file:///Users/grimur/personal-code/homelab/services/laya/vars.env) (`LAYA_ASSIST_HOME=/data`, `HF_HOME=/cache`).

### Step 2: Update `.gitignore` and Borg Backup Exclusions
1. Add `/services/laya/data/` and `/services/laya/cache/` to [`.gitignore`](file:///Users/grimur/personal-code/homelab/.gitignore).
2. Add `/home/grimur/homelab/services/laya/cache/` to [`infrastructure/backup/borg-exclude-homelab.txt`](file:///Users/grimur/personal-code/homelab/infrastructure/backup/borg-exclude-homelab.txt).

### Step 3: Deployment & DNS Registration (On NAS `pippinn`)
1. Register DNS in Pi-hole: `./scripts/add-dns.sh laya`.
2. Validate compose configuration: `docker compose -f services/laya/compose.yaml config`.
3. Build and start container: `docker compose -f services/laya/compose.yaml up -d --build`.
4. Monitor initial multilingual model checkpoint download via `docker logs -f laya` (or `GET /api/health`).

### Step 4: Configure Laya Web UI & Home Assistant Assist Pipeline
1. Open `https://laya.internal.pippinn.me`.
2. Configure Home Assistant connection (`https://home-assistant.pippinn.me` + HA Long-Lived Access Token) and sync the Assist entity catalog.
3. Configure Model (`multilingual`), confidence threshold (`0.6`), and Fallback LLM (Gemini OpenAI-compatible endpoint `https://generativelanguage.googleapis.com/v1beta/openai` + Gemini API key).
4. Test sample utterances directly in the Laya Web UI predictor and inspect confidence scores.
5. In Home Assistant, configure an Assist pipeline using Laya (`https://laya.internal.pippinn.me/v1`) as the Conversation Agent and verify end-to-end command execution.

---

## 🔄 Rollback Steps

1. Remove the Laya conversation agent from the Home Assistant Assist pipeline.
2. Tear down the container and volumes:
   ```bash
   docker compose -f services/laya/compose.yaml down
   ```
3. Revert Git commit if needed.
