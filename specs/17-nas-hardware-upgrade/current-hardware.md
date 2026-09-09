# Current NAS Hardware — As-Built

## System

| Item | Detail |
|------|--------|
| Case | Fractal Design Node 304 (mini-ITX) |
| Motherboard | ASUS E35M1-I (mini-ITX) |
| CPU | AMD E-350 (Bobcat, 2011) — soldered APU, 2C/2T @ 1.6 GHz |
| x86-64 baseline | v1 only (below v2 — blocks modern container images) |
| TDP | 18W |
| RAM | 2x 4GB DDR3 SO-DIMM @ 1066 MT/s (Kingston 99U5471-017.A00LF) |
| RAM slots | 2/2 occupied — **platform maxed at 8GB** |
| Swap | 976 MiB — 750 MiB used at time of audit |

## Network

| Interface | IP | Notes |
|-----------|-----|-------|
| eth0 | 192.168.86.17 | 1GbE onboard |
| IPv6 | 2001:9b1:c5c2:7200:16da:e9ff:fe68:6362 | |

## Storage

| Device | Model | Type | Size | Used | Mount |
|--------|-------|------|------|------|-------|
| sda | Plextor PX-256M6S | SSD (SATA) | 238 GB | 157 GB | `/` (OS) |
| sdb | WD WD30EZRX-00MMMB0 | HDD (WD Green, SMR) | 2.7 TB | 672 GB | `/srv/...9e6b...` |
| sdc | WD WD30EZRX-00MMMB0 | HDD (WD Green, SMR) | 2.7 TB | 502 GB | `/srv/...220b...` |
| sdd | WD WD30EZRX-00MMMB0 | HDD (WD Green, SMR) | 2.7 TB | 312 GB | `/srv/...f120...` |
| sde | WD WD30EZRX-00MMMB0 | HDD (WD Green, SMR) | 2.7 TB | 641 GB | `/srv/...0dda...` |

**OS SSD free:** ~64 GB
**Node 304 bays used:** 5/6

## OS & Software

| Item | Detail |
|------|--------|
| OS | Debian 12 (Bookworm) |
| Kernel | 6.12.85+deb12-amd64 (backport) |
| Management | OpenMediaVault |
| Docker stacks | Managed via this GitOps repo |

## Known Limitations

| Limitation | Impact |
|------------|--------|
| Below x86-64-v2 baseline | Cannot run Immich ML on NAS — offloaded to Pi (spec 10) |
| No Intel QSV / hardware transcode | Plex software transcoding only — CPU too slow to sustain |
| RAM maxed at 8GB | Swap heavily used (77%); headroom exhausted |
| WD Green (SMR) HDDs | Poor random write performance; not rated for NAS workloads |
| CPU soldered | No CPU upgrade path on current platform |
