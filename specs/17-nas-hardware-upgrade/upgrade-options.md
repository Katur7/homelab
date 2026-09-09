# NAS Hardware Upgrade Options

## Problem Statement

| Issue | Root Cause |
|-------|-----------|
| Insufficient RAM | DDR3 platform hard-capped at 8GB, both slots occupied |
| Slow CPU | E-350 Bobcat 2C @ 1.6 GHz — 14-year-old architecture |
| Immich ML on NAS impossible | Below x86-64-v2 baseline (required since Immich v2.6) |
| No Plex hardware transcoding | No Intel QSV; too slow for software transcode |

All four issues share the same root cause: the ASUS E35M1-I platform is end-of-life with no upgrade path (CPU soldered, RAM maxed).

---

## Option A — Storage only, keep platform

**~£100–200 | Solves: nothing critical**

| Action | Detail | Est. cost |
|--------|--------|-----------|
| Replace 4x WD Green with CMR NAS drives | e.g. 4x WD Red Plus 4–6TB | £80–160 |
| Add NVMe via PCIe adapter | Docker volumes / scratch | £30–50 |
| 2.5GbE NIC | PCIe x1 Realtek 8125 | £20 |

Does not fix RAM, CPU, ML, or transcoding. Not recommended as primary action.

---

## Option B — Platform replacement (RECOMMENDED)

**~£140–185 | Solves: all four issues**

Drop the ASUS E35M1-I, keep the Node 304 case, PSU, and all 4 HDDs.

### Platform comparison

| Spec | E-350 (current) | Intel N100 (proposed) |
|------|-----------------|-----------------------|
| Architecture | Bobcat (2011) | Alder Lake-N (2023) |
| x86-64 baseline | v1 | v3 |
| Cores / Threads | 2C / 2T | 4C / 4T |
| Boost clock | 1.6 GHz | 3.4 GHz |
| TDP | 18W | 6W |
| Max RAM | 8GB DDR3 | 16–32GB DDR4 |
| iGPU | Radeon HD 6310 | Intel UHD (QuickSync) |
| Immich ML | No | Yes |
| Plex HW transcode | No | Yes (QSV) |

### Case compatibility

The Node 304 is mini-ITX. All N100 boards listed below are mini-ITX — direct fit.
Node 304 has 6x 3.5" bays. Moving OS to M.2 frees the Plextor SSD bay, leaving 5 bays for HDDs.

### Candidate boards (verify SATA count before purchase)

| Board | SATA ports | M.2 slots | Notes |
|-------|-----------|-----------|-------|
| Cwwk N100 6-SATA NAS board | 6 | 1 | Purpose-built; most ports |
| Topton N100 NAS mini-ITX | 6 | 1 | Popular in homelab community |
| ASRock N100DC-ITX | 4 | 1 | Move OS to M.2, use all 4 SATA for HDDs |

Minimum requirement: 5 SATA ports, or 4 SATA + 1 M.2 (OS on M.2).

### Boards evaluated (Sweden, May 2026)

| Board | Price | SATA | Power | Verdict |
|-------|-------|------|-------|---------|
| ASUS Prime N100I-D D4 | 2,601 kr | 1 | ATX | ❌ Only 1 SATA — unusable |
| ASRock N100M | 2,601 kr | 4 | ATX | ❌ Micro-ATX — does not fit Node 304 |
| CWWK M8 8-bay N150 | 4,010 kr | 8 | DC | ❌ DDR5, DC power, overpriced |
| **Generic N100 6-SATA ITX (AliExpress)** | **2,347 kr** | **6** | **ATX** | **✅ Candidate** |
| **Topton 8-bay i5-8265U (AliExpress #1005008835788329)** | **1,760 kr** | **8** | **ATX** | **✅ Candidate** |

### Selected board — Generic N100 Mini-ITX NAS (AliExpress)

| Spec | Detail |
|------|--------|
| CPU | Intel N100 (soldered) |
| Form factor | Mini-ITX (170×170mm) |
| Power | 24-pin ATX + 4-pin CPU |
| SATA | 6x SATA III |
| M.2 | 2x NVMe (PCIe 3.0 x1 signal) |
| RAM | 1x DDR4 SO-DIMM, max 32GB |
| NIC | Dual 2.5GbE Intel I226-V |
| PCIe | 1x PCIe x4 slot (x2 signal) |
| Linux compat | Confirmed (Ubuntu/CentOS logos on listing) |

### Candidate A — Generic N100 6-SATA Mini-ITX (AliExpress #1005009710707269)

| Spec | Detail |
|------|--------|
| CPU | Intel N100 (soldered, 6W TDP) |
| Form factor | Mini-ITX (170×170mm) |
| Power | 24-pin ATX + 4-pin CPU |
| SATA | 6x SATA III |
| M.2 | 2x NVMe (PCIe 3.0 x1 signal) |
| RAM | 1x DDR4 SO-DIMM, max 32GB |
| NIC | Dual 2.5GbE Intel I226-V |
| PCIe | 1x PCIe x4 slot (x2 signal) |
| Linux compat | Confirmed (Ubuntu/CentOS logos on listing) |
| **Est. total** | **~2,650 kr** (board + RAM) |

### Candidate B — Topton 8-bay i5-8265U Mini-ITX (AliExpress #1005008835788329)

| Spec | Detail |
|------|--------|
| CPU | Intel i5-8265U (Whiskey Lake 2018, 15W TDP) |
| Form factor | Mini-ITX |
| Power | 24-pin ATX |
| SATA | 8x SATA |
| M.2 | 2x NVMe |
| RAM | 2x DDR4 SO-DIMM (dual channel) |
| NIC | Dual 2.5GbE |
| PCIe | 1x PCIe x1 |
| Intel QSV | ✅ (UHD 620) |
| x86-64-v3 | ✅ |
| **Est. total** | **~2,160 kr** (board + RAM, 2 slots so 2x8GB viable) |

**Tradeoff vs Candidate A:**

| | Candidate A (N100) | Candidate B (i5-8265U) |
|--|-------------------|----------------------|
| Board price | 2,347 kr | 1,760 kr (−587 kr) |
| TDP | 6W | 15W |
| Extra power cost/year | — | ~200–260 kr |
| Board saving recouped | — | ~2–3 years |
| RAM slots | 1 | 2 (dual channel) |
| Long-term TCO (5yr) | Lower | Higher |

### Parts list

| Part | Action | Cost |
|------|--------|------|
| Fractal Node 304 | Reuse | 0 kr |
| PSU | Reuse | 0 kr |
| Plextor 256GB SATA SSD | Reuse (OS drive, SATA port 1) | 0 kr |
| 4x WD 3TB HDDs | Reuse (SATA ports 2–5) | 0 kr |
| Generic N100 6-SATA Mini-ITX board | Buy (AliExpress) | 2,347 kr |
| 16GB DDR4 SO-DIMM | Buy (source locally or AliExpress) | ~400 kr |
| **Total** | | **~2,750 kr** |

**SATA allocation:**

| Port | Drive |
|------|-------|
| SATA 1 | Plextor 256GB (OS) |
| SATA 2–5 | 4x WD WD30EZRX 3TB |
| SATA 6 | Empty (spare) |

### Migration path

1. Install OMV on new board + M.2 NVMe
2. Mount existing HDDs — UUIDs preserved, fstab entries carry over
3. `git clone` this repo to `/home/grimur/homelab`
4. Restore `.env` files from backup
5. `docker compose up -d` per stack
6. Update `ARCHITECTURE.md` with new CPU/RAM specs
7. Move Immich ML back from Pi to NAS (reverse spec 10)

### Post-migration gains

- Immich ML runs locally — Pi offloaded
- Plex QuickSync HW transcode enabled
- 16GB RAM eliminates swap pressure
- Power draw drops from ~18W to ~6W idle

---

## Option C — Dedicated NAS appliance

**£400–800 | Not recommended**

Synology DS923+ or TerraMaster F4-424 Pro. Loses GitOps flexibility, custom networking (Traefik, Authelia, Cloudflare Tunnel), and full Docker control. Significant migration cost. Not suitable given current stack complexity.

---

## Decision

| Criteria | Option A | Option B | Option C |
|----------|----------|----------|----------|
| Fixes all 4 issues | No | Yes | Partial |
| Reuses Node 304 | Yes | Yes | No |
| Cost | £100–200 | £140–185 | £400–800 |
| Migration effort | None | Medium | High |
| Recommended | No | **Yes** | No |
