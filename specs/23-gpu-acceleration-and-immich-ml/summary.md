# Spec 23: Intel GPU Acceleration (Plex QuickSync & Immich Machine Learning Repatriation) — Summary

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

3. **Pi Fleet Decommissioning:**
   - Removed `pi/services/immich-ml/` service definition from the git repository.
   - Documented Pi container teardown and model volume pruning commands (`docker compose down -v`).

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

# Recreate Plex stack
docker compose -f services/plex/compose.yaml up -d

# Recreate Immich stack
docker compose -f services/immich/compose.yaml up -d
```

### 2. Configure Plex Web Transcoder

1. Navigate to `https://plex.internal.pippinn.me` (or `http://192.168.86.17:32400/web`).
2. Go to **Settings ➔ Server ➔ Transcoder** (click **Show Advanced**).
3. Set **Transcoder temporary directory** to `/transcode`.
4. Ensure **Use hardware acceleration when available** is enabled.
5. Ensure **Use hardware-accelerated video encoding** is enabled.
6. Set **Hardware transcoding device** to `Alder Lake-N / Intel UHD Graphics` (or Auto).
7. Click **Save Changes**.

### 3. Verify Hardware Transcoding in Plex

1. Start streaming a video from a client and force a transcode (e.g. set playback quality to 720p 4Mbps).
2. Open Plex Web **Dashboard** (Activity icon ➔ Dashboard).
3. Check **Now Playing**:
   - Ensure the stream shows **Transcode (hw)** for video decode and encode.
4. Verify `/transcode` tmpfs:
   ```bash
   docker exec -it plex df -h /transcode
   ```

### 4. Verify Immich Machine Learning

1. Check ML container logs:
   ```bash
   docker logs --tail 50 immich_machine_learning
   ```
   Verify OpenVINO initializes and loads the Intel GPU / execution provider.
2. Check Immich Server logs:
   ```bash
   docker logs --tail 50 immich_server
   ```
   Confirm successful ping/connection to `http://immich-machine-learning:3003`.
3. Open Immich Web UI at `https://photos.pippinn.me` and test a Smart Search (e.g., query "lake", "dog", or "forest") to verify inference results.

### 5. Decommission Remote Immich ML on the Raspberry Pi (`192.168.86.26`)

```bash
ssh grimur@192.168.86.26
cd ~/homelab/pi/services/immich-ml
docker compose down -v
docker rmi ghcr.io/immich-app/immich-machine-learning:v3.2.2 || true
cd ~/homelab && git pull
```
