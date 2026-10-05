# Spec 23: Intel GPU Acceleration & Workload Repatriation (Plex, Immich ML & Photoframe) — Summary

## What Was Done

1. **Immich Machine Learning Repatriation:**
   - Updated [`services/immich/vars.env`](file:///Users/grimur/personal-code/homelab/services/immich/vars.env) to configure `IMMICH_MACHINE_LEARNING_URL=http://immich-machine-learning:3003`.
   - Updated [`services/immich/compose.yaml`](file:///Users/grimur/personal-code/homelab/services/immich/compose.yaml) to:
     - Add `immich-machine-learning` with OpenVINO image tag (`${IMMICH_VERSION:-v2.6.1}-openvino`).
     - Pass `/dev/dri:/dev/dri` and device cgroup rules `c 189:* rmw` for Intel UHD Graphics acceleration.
     - Mount Docker named volume `model-cache:/cache` on the NVMe SSD.
     - Add `immich-machine-learning` to `depends_on` under `immich-server`.
     - Assign resource limits: **4GB RAM (`4096M`)** and **2.0 CPUs**.

2. **Plex QuickSync Hardware Transcoding & RAM tmpfs:**
   - Updated [`services/plex/compose.yaml`](file:///Users/grimur/personal-code/homelab/services/plex/compose.yaml) to:
     - Pass `/dev/dri:/dev/dri` for Intel QuickSync GPU access.
     - Mount dedicated 4GB in-memory tmpfs buffer: `tmpfs: - /transcode:size=4G` to eliminate SSD write wear during transcoding.
     - Increased resource limits to **8GB RAM (`8192M`)** and **4.0 CPUs** to support the 4GB tmpfs transcode buffer and active streams.

3. **Photoframe Server Repatriation:**
   - Created [`services/photoframe/README.md`](file:///Users/grimur/personal-code/homelab/services/photoframe/README.md) documenting deployment of `~/photoframe-server` on the NAS with dual access (direct port `8088:8088` and Traefik HTTPS router on `traefik_internal`).
   - Removed `pi/services/photoframe/` from the git repository.
   - Updated [`pi/README.md`](file:///Users/grimur/personal-code/homelab/pi/README.md) and [`pi/scripts/update-containers.sh`](file:///Users/grimur/personal-code/homelab/pi/scripts/update-containers.sh).

4. **Architecture Documentation:**
   - Updated [`ARCHITECTURE.md`](file:///Users/grimur/personal-code/homelab/ARCHITECTURE.md) to document Immich ML local inference with Intel OpenVINO and Plex hardware transcoding with QuickSync.

---

## Deployment & Verification Runbook

### 1. On the NAS (`pippinn` — `192.168.86.17`)

```bash
cd ~/homelab

# Pull updated images
docker compose -f services/plex/compose.yaml pull
docker compose -f services/immich/compose.yaml pull

# Recreate Plex & Immich stacks
docker compose -f services/plex/compose.yaml up -d
docker compose -f services/immich/compose.yaml up -d

# Clone and run Photoframe on NAS
cd ~
git clone https://github.com/Katur7/photoframe-server.git
cd photoframe-server
scp grimur@192.168.86.26:~/photoframe-server/.env .env
docker compose up -d --build

# Update PiHole DNS host record
/home/grimur/homelab/scripts/add-dns.sh photoframe.internal.pippinn.me 192.168.86.17
```

### 2. Configure Plex Web Transcoder

1. Navigate to `https://plex.internal.pippinn.me` (or `http://192.168.86.17:32400/web`).
2. Go to **Settings ➔ Server ➔ Transcoder** (click **Show Advanced**).
3. Set **Transcoder temporary directory** to `/transcode`.
4. Ensure **Use hardware acceleration when available** and **Use hardware-accelerated video encoding** are enabled.
5. Set **Hardware transcoding device** to `Alder Lake-N / Intel UHD Graphics` (or Auto).
6. Click **Save Changes**.

### 3. Decommission Services on the Raspberry Pi (`192.168.86.26`)

```bash
ssh grimur@192.168.86.26

# Decommission Immich ML
cd ~/homelab/pi/services/immich-ml
docker compose down -v
docker rmi ghcr.io/immich-app/immich-machine-learning:v3.2.2 || true

# Decommission Photoframe
cd ~/photoframe-server
docker compose down -v

# Sync homelab repo
cd ~/homelab && git pull
```
