# NAS Hardware Upgrade Options

**Last price check: 2026-09-09** (AliExpress SEK incl. VAT, Amazon.de SEK, Prisjakt.nu, Inet.se). Prices move; re-verify before ordering.

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

**~1,000–2,000 kr | Solves: nothing critical**

| Action | Detail |
|--------|--------|
| Replace 4x WD Green with CMR NAS drives | e.g. 4x WD Red Plus 4–6TB |
| Add NVMe via PCIe adapter | Docker volumes / scratch |
| 2.5GbE NIC | PCIe x1 Realtek 8125 |

Does not fix RAM, CPU, ML, or transcoding. Not recommended as primary action.

---

## Option B — Platform replacement (RECOMMENDED)

Drop the ASUS E35M1-I, keep the Node 304 case, PSU, and all 4 HDDs.

### Platform comparison

| Spec | E-350 (current) | Intel N100 | Intel N150 | Core 3 N355 |
|------|-----------------|------------|------------|-------------|
| Architecture | Bobcat (2011) | Alder Lake-N (2023) | Twin Lake (2025) | Twin Lake (2025) |
| x86-64 baseline | v1 | v3 | v3 | v3 |
| Cores / Threads | 2C / 2T | 4C / 4T | 4C / 4T | 8C / 8T |
| Boost clock | 1.6 GHz | 3.4 GHz | 3.6 GHz | 3.9 GHz |
| TDP | 18W | 6W | 6W | 15W |
| iGPU | Radeon HD 6310 | UHD 24EU (QSV) | UHD 24EU (QSV) | UHD 32EU (QSV) |
| Immich ML / Plex HW transcode | No | Yes | Yes | Yes |

N100 vs N150 is a wash for this workload (~5% clock). N355 adds cores this stack does not need.

### Hard requirements

| Requirement | Why |
|-------------|-----|
| Mini-ITX (170×170mm) | Node 304 |
| 24-pin ATX power (not DC barrel) | Reuse existing PSU |
| ≥5 SATA, or 4 SATA + M.2 for OS | 4x HDD + OS drive |
| x86-64-v3, Intel QSV | Immich ML, Plex |

### Market status (Sep 2026)

- **Swedish retail (Inet, Prisjakt, Komplett)**: no usable N-series ITX NAS board. Only ASUS Prime N100I-D D4 (~2,400 kr, 1 SATA) — unusable.
- **Geizhals.de**: no N100/N150/N355 onboard-CPU ITX boards with DE stock.
- **Realistic sources**: AliExpress (cheapest, no returns) or Amazon.de (CWWK brand, EU returns, ~+1,900 kr total incl. DDR5 RAM).
- **DRAM shortage**: DDR4 SO-DIMM 16GB ~1,100–1,800 kr, DDR5 SO-DIMM 16GB ~2,850–3,800 kr (Prisjakt). RAM is now ~30% of build cost. DDR4 platform saves ~1,600 kr. Buy 16GB once; do not stage 8GB→16GB.

### Candidate boards

Prices are board only, no RAM, cooler included where noted.

| # | Board | CPU | RAM | Power | PCIe slot | SATA / M.2 | Price (kr) | Source / track record |
|---|-------|-----|-----|-------|-----------|------------|------------|-----------------------|
| **1** | **Generic "YX" N100/N150 NAS ITX, DDR4** | N100 or N150 | 1x DDR4 SO-DIMM, max 32GB | 24-pin + 4-pin ATX | x4 (x2 signal) | 6 / 2 (PCIe 3.0 x1 each) | 2,990 (N100) / 3,100 (N150) | AliExpress. Same board sold by several stores: #1005012943875459 (5,215 sold), #1005009710707269 (52 sold, 8 reviews, orig. spec candidate), #1005013052887793 (371 sold) |
| **2** | **CWWK N150 "M2" 6-bay** | N150 | 1x DDR5 SO-DIMM, max 48GB | 24+4-pin ATX (confirmed) | x4 | 6 (ASM1166 on PCIe 3.0 x1) / 2 | 3,275 + 98 shipping | Amazon.de, sold by Amazon, EU returns. ASIN B0H7WL8F9Z |
| 3 | Topton 6-bay N100/N150/N355, DDR5 | N100 / N150 / N355 | 1x DDR5 | 24-pin ATX | x4 | 6 / 2 | 2,900 / 3,072 / 4,959 | AliExpress #1005010466494316, Topton store, 18 sold |
| 4 | CW N150K 6-bay, DDR5 | N150 | 1x DDR5 | unverified | x4 | 6 / 2 | 3,895 | AliExpress #1005012575831915, 6 sold |

### Rejected

| Board | Reason |
|-------|--------|
| Topton 8-bay i5-8265U (orig. spec Candidate B, #1005008835788329) | Listing gone (ID now a RAM listing). Equivalents (1,600–2,200 kr) all ship **ES** (engineering sample) CPUs. Dropped. |
| N100 quad-i226 DDR5 6-SATA (#1005012731249242, 2,077 kr) | DC power only. Incompatible with existing PSU. |
| "N150 DDR4 6-SATA" (#1005011930419454, 1,377 kr + 335 shipping) | 0 reviews, no spec table, anonymous store, 14-day dispatch. Too risky. |
| ASUS Prime N100I-D D4 | 1 SATA |
| ASRock N100M | Micro-ATX, does not fit Node 304 |
| CWWK M8 8-bay N150 10GbE | DDR5, 10GbE unused, 3,600–4,200 kr. Overkill. |
| N5105 "N100" ITX boards (~2,000 kr) | Actually Jasper Lake N5105 despite title. Lacks AVX2 (x86-64-v2 only). |

### Selected — Candidate 1 (N150, DDR4)

| Spec | Detail |
|------|--------|
| CPU | Intel N150 (soldered, 6W TDP) |
| Form factor | Mini-ITX (170×170mm) |
| Power | 24-pin ATX + 4-pin CPU |
| SATA | 6x SATA III |
| M.2 | 2x NVMe (PCIe 3.0 x1 signal) |
| RAM | 1x DDR4 SO-DIMM, max 32GB |
| NIC | Dual 2.5GbE Intel I226-V |
| PCIe | 1x PCIe x4 slot (x2 signal) |
| Buy from | Highest-volume listing (#1005012943875459) unless price diverges |

**Fallback — Candidate 2 (CWWK N150, DDR5, Amazon.de)** if EU returns/brand support is worth ~1,900 kr extra.

### Build cost

| Build | Board | 16GB RAM (local) | Total |
|-------|-------|------------------|-------|
| **Cand 1 N150 DDR4** | ~3,100 | ~1,250 (Kingston KCP432SS8/16 / Samsung) | **~4,350 kr** |
| Cand 1 N100 DDR4 | ~2,990 | ~1,250 | ~4,250 kr |
| Cand 2 CWWK N150 DDR5 | ~3,370 | ~2,850 (Crucial CT16G48C40S5) | ~6,200 kr |
| Cand 3 Topton N355 DDR5 | ~4,960 | ~2,850 | ~7,800 kr |

Original May 2026 estimate (~2,750 kr) is ~60% low: board +30%, RAM ×3.

### Parts list

| Part | Action | Cost |
|------|--------|------|
| Fractal Node 304 | Reuse | 0 kr |
| PSU | Reuse | 0 kr |
| Plextor 256GB SATA SSD | Reuse (OS drive, SATA port 1) | 0 kr |
| 4x WD 3TB HDDs | Reuse (SATA ports 2–5) | 0 kr |
| N150 6-SATA Mini-ITX board (Cand 1) | Buy (AliExpress) | ~3,100 kr |
| 16GB DDR4-3200 SO-DIMM | Buy locally (Kingston/Samsung/Crucial) | ~1,250 kr |
| **Total** | | **~4,350 kr** |

**SATA allocation:**

| Port | Drive |
|------|-------|
| SATA 1 | Plextor 256GB (OS) |
| SATA 2–5 | 4x WD WD30EZRX 3TB |
| SATA 6 | Empty (spare) |

### Migration path

1. Install OMV on new board (Plextor SSD or M.2 NVMe)
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
- 2.5GbE ready

---

## Option C — Dedicated NAS appliance

**5,000–10,000 kr | Not recommended**

Synology DS923+ or TerraMaster F4-424 Pro. Loses GitOps flexibility, custom networking (Traefik, Authelia, Cloudflare Tunnel), and full Docker control. Significant migration cost. Not suitable given current stack complexity.

---

## Decision

| Criteria | Option A | Option B | Option C |
|----------|----------|----------|----------|
| Fixes all 4 issues | No | Yes | Partial |
| Reuses Node 304 | Yes | Yes | No |
| Cost | 1,000–2,000 kr | ~4,350 kr | 5,000–10,000 kr |
| Migration effort | None | Medium | High |
| Recommended | No | **Yes** | No |

## Change log

| Date | Change |
|------|--------|
| 2026-05 | Initial evaluation. Candidates: generic N100 DDR4 (2,347 kr), Topton i5-8265U (1,760 kr). Est. total ~2,750 kr. |
| 2026-09-09 | Re-priced. N100 board +30%. DDR4 16GB ~1,250 kr, DDR5 16GB ~2,850 kr (DRAM shortage). Candidate B dropped (listing gone, ES CPUs). Added CWWK N150 via Amazon.de and Topton N150/N355 DDR5. Selected N150 DDR4. Est. total ~4,350 kr. |
