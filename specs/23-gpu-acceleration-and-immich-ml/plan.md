# Spec 23: Intel GPU Acceleration & Workload Repatriation (Plex QuickSync, Immich ML & Photoframe Server)

## 📌 Context & Motivation

Following the NAS hardware upgrade to the Intel N150 (Twin Lake / Alder Lake-N with 24EU Intel UHD Graphics and 32GB RAM in Milestone 17), three workloads that were previously constrained by the legacy NAS or hosted on the Raspberry Pi 4 are repatriated to the NAS:
1. **Immich Machine Learning Repatriation:** In Milestone 10, Immich ML had to be offloaded to the Raspberry Pi 4 because the legacy AMD E-350 CPU lacked the x86-64-v2 microarchitecture baseline (NumPy 2.4 / SIGILL crashes). The new Intel N150 fully supports modern x86 extensions and possesses an integrated GPU capable of accelerating neural network inference (CLIP smart search and facial recognition) via Intel OpenVINO.
2. **Plex QuickSync Hardware Transcoding:** The legacy NAS lacked hardware video encoding/decoding. Passing the Intel GPU (`/dev/dri`) into the Plex container allows hardware transcoding (`Transcode (hw)` via Intel QuickSync), drastically reducing CPU load during stream conversions. Mounting a RAM-backed `tmpfs` for transcoded video segments prevents unnecessary SSD wear.
3. **Photoframe Server Repatriation:** In Milestone 18, the Photoframe server was placed on the Pi because the Pi was already hosting lightweight secondary tasks. Migrating it to the NAS centralizes application hosting, enables dual access (direct port 8088 for the ESP32-S3 photo frame plus Traefik HTTPS routing), and frees up resources on the Pi.
4. **Pi Fleet Decommissioning:** Decommissioning remote Immich ML and the Photoframe server on the Pi returns the Pi 4 to its lean role as a secondary DNS (PiHole), monitoring hub (Beszel / Uptime Kuma), and sync node.

---

## 🎯 Objectives

1. **Repatriate Immich ML to NAS:**
   - Add `immich-machine-learning` to `services/immich/compose.yaml` using the OpenVINO-accelerated image (`-openvino` tag).
   - Pass `/dev/dri` into the container for iGPU acceleration.
   - Use a fast NVMe Docker named volume (`model-cache:/cache`) for model weights.
   - Update `services/immich/vars.env` to point `IMMICH_MACHINE_LEARNING_URL` to the local service (`http://immich-machine-learning:3003`).
   - Configure resource limits: 4GB RAM (`4096M`) and 2.0 CPUs.

2. **Enable Plex QuickSync (QSV) & RAM Transcoding:**
   - Pass `/dev/dri:/dev/dri` into `services/plex/compose.yaml`.
   - Add a dedicated 4GB in-memory tmpfs mount (`/transcode:size=4G`) for Plex transcode buffers.
   - Update Plex resource limits to 8GB RAM (`8192M`) and 4.0 CPUs to accommodate the 4GB tmpfs buffer plus Plex runtime.
   - Configure Plex Web UI to use `/transcode` as the temporary transcoder directory.

3. **Repatriate Photoframe Server to NAS:**
   - Document `services/photoframe/README.md` pointing to standalone repository `~/photoframe-server` on the NAS.
   - Configure dual ingress: direct port `8088:8088` (for ESP32-S3 firmware compatibility) plus Traefik HTTPS routing (`photoframe.internal.pippinn.me`) on `traefik_internal`.
   - Update custom PiHole DNS host record for `photoframe.internal.pippinn.me` to point to `192.168.86.17`.

4. **Decommission Pi Services:**
   - Immich ML: stop container and prune model cache volume (`docker compose down -v`).
   - Photoframe: stop container on Pi (`docker compose down -v`).
   - Clean up repo directories (`pi/services/immich-ml` and `pi/services/photoframe`) and update `pi/README.md`.

5. **Update System Architecture Documentation:**
   - Update `ARCHITECTURE.md` to reflect Immich ML, Plex QuickSync, and Photoframe running on the NAS.

---

## 🛠️ Implementation Plan

### Part 1: Immich Machine Learning Stack Updates

#### 1. Modify `services/immich/vars.env`
Update the machine learning endpoint from the remote Pi IP to the local compose service name:
```env
IMMICH_MACHINE_LEARNING_URL=http://immich-machine-learning:3003
```

#### 2. Modify `services/immich/compose.yaml`
1. Reintroduce `immich-machine-learning` service:
   ```yaml
   immich-machine-learning:
     image: ghcr.io/immich-app/immich-machine-learning:${IMMICH_VERSION:-v2.6.1}-openvino
     container_name: immich_machine_learning
     restart: unless-stopped
     device_cgroup_rules:
       - 'c 189:* rmw'
     devices:
       - /dev/dri:/dev/dri
     volumes:
       - model-cache:/cache
     networks:
       - default
     labels:
       - "wud.watch=false"
     deploy:
       resources:
         limits:
           cpus: "2.0"
           memory: 4096M
   ```
2. Add `immich-machine-learning` to `depends_on` under `immich-server`:
   ```yaml
   depends_on:
     - redis
     - database
     - immich-machine-learning
   ```
3. Add the top-level named volume:
   ```yaml
   volumes:
     model-cache:
   ```

---

### Part 2: Plex Hardware Acceleration & Transcode tmpfs

#### Modify `services/plex/compose.yaml`
1. Add device passthrough:
   ```yaml
   devices:
     - /dev/dri:/dev/dri
   ```
2. Add RAM-backed `tmpfs` transcode volume:
   ```yaml
   tmpfs:
     - /transcode:size=4G
   ```
3. Update resource limits from `512M / 1.5 CPU` to `8192M / 4.0 CPU`:
   ```yaml
   deploy:
     resources:
       limits:
         cpus: "4.0"
         memory: 8192M
   ```

---

### Part 3: Photoframe Server Setup on NAS

#### 1. Register Documentation
Create `services/photoframe/README.md` and remove `pi/services/photoframe/README.md`.

#### 2. Compose Configuration in `~/photoframe-server/compose.yaml`
```yaml
name: photoframe-server

services:
  photoframe:
    build: .
    container_name: photoframe_server
    restart: unless-stopped
    ports:
      - "8088:8088"
    networks:
      - traefik_internal
    env_file:
      - .env
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=traefik_internal"
      - "traefik.http.routers.photoframe-internal.entrypoints=websecure"
      - "traefik.http.routers.photoframe-internal.rule=Host(`photoframe.internal.pippinn.me`)"
      - "traefik.http.services.photoframe-internal.loadbalancer.server.port=8088"

networks:
  traefik_internal:
    external: true
```

#### 3. Update PiHole DNS Record
Update the local DNS host record so `photoframe.internal.pippinn.me` points to `192.168.86.17`:
```bash
/home/grimur/homelab/scripts/add-dns.sh photoframe.internal.pippinn.me 192.168.86.17
```

---

### Part 4: Deployment & Host Validation Runbook

#### 1. NAS Service Bring-Up
On the NAS (`pippinn`):
```bash
# Pull new images
docker compose -f services/plex/compose.yaml pull
docker compose -f services/immich/compose.yaml pull

# Recreate Plex stack
docker compose -f services/plex/compose.yaml up -d

# Recreate Immich stack
docker compose -f services/immich/compose.yaml up -d

# Deploy Photoframe on NAS
cd ~
git clone https://github.com/Katur7/photoframe-server.git
cd photoframe-server
scp grimur@192.168.86.26:~/photoframe-server/.env .env
docker compose up -d --build
```

#### 2. Configure Plex Web Transcoder
1. Open Plex Web UI at `https://plex.internal.pippinn.me` (or `http://192.168.86.17:32400/web`).
2. Navigate to **Settings** (wrench icon) ➔ **Transcoder** (under Server settings).
3. Click **Show Advanced**.
4. Set **Transcoder temporary directory** to `/transcode`.
5. Ensure **Use hardware acceleration when available** is checked.
6. Ensure **Use hardware-accelerated video encoding** is checked.
7. Set **Hardware transcoding device** to `Alder Lake-N / Intel UHD Graphics` (or Auto).
8. Click **Save Changes**.

#### 3. Decommission Remote Services on Pi
On the Raspberry Pi (`192.168.86.26`):
```bash
# Stop and prune Immich ML
cd ~/homelab/pi/services/immich-ml
docker compose down -v
docker rmi ghcr.io/immich-app/immich-machine-learning:v3.2.2 || true

# Stop and prune Photoframe
cd ~/photoframe-server
docker compose down -v
```

---

## ✅ Verification Checklist

### Plex Hardware Transcoding:
- [ ] Inspect container devices: `docker exec -it plex ls -l /dev/dri` shows `card0` and `renderD128`.
- [ ] Inspect transcode tmpfs: `docker exec -it plex df -h /transcode` displays a ~4.0G `tmpfs` mount.
- [ ] Start a stream on a client device that forces video transcoding (e.g. convert 4K/1080p to 720p 4Mbps).
- [ ] Open Plex Web Dashboard (Activity ➔ Dashboard / Now Playing):
  - Confirm video stream states **Transcode (hw)** for both Decode and Encode.

### Immich Machine Learning:
- [ ] Inspect container health: `docker ps --filter "name=immich_machine_learning"` is Up.
- [ ] Check ML container logs: `docker logs --tail 50 immich_machine_learning` confirms OpenVINO initializes and loads the Intel GPU execution provider.
- [ ] Check Immich Server logs: `docker logs --tail 50 immich_server` confirms connection to `http://immich-machine-learning:3003`.
- [ ] Perform a Smart Search in Immich Web UI (e.g. search "dog", "sunset"): verify search returns relevant results.

### Photoframe Server:
- [ ] Verify DNS: `dig +short photoframe.internal.pippinn.me @192.168.86.27` returns `192.168.86.17`.
- [ ] Verify Direct Port HTTP: `curl -I http://photoframe.internal.pippinn.me:8088/current.png` returns `200 OK`.
- [ ] Verify Traefik HTTPS: `curl -I https://photoframe.internal.pippinn.me/current.png` returns `200 OK`.
- [ ] Verify Pi services stopped: `ssh grimur@192.168.86.26 "docker ps"` shows no immich or photoframe containers.
