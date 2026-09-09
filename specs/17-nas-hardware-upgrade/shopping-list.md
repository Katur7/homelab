# Shopping List — Option B, Candidate 1 (N150 DDR4)

**Prices checked: 2026-09-09.** AliExpress prices incl. VAT in SEK; Prisjakt "fr." (lowest listed) price. Re-verify before ordering.

See `upgrade-options.md` for the decision and rejected alternatives.

## 1. Motherboard — Generic N150 6-SATA Mini-ITX, DDR4

Same board from several stores. Buy one. Configure the SKU picker as: **CPU = N150 (with cooler if offered), RAM = none**. Do not buy the seller's RAM bundle.

| Priority | Listing | Price (board only) | Notes |
|----------|---------|--------------------|-------|
| **1** | https://www.aliexpress.com/item/1005012943875459.html | 3,123 kr | 5,215 sold. Highest volume. |
| 2 | https://www.aliexpress.com/item/1005013052887793.html | 3,049 kr (N150 + cooler) | 371 sold. 1 left at check time. |
| 3 | https://www.aliexpress.com/item/1005009710707269.html | 3,140 kr (N150 + cooler) | 52 sold, 8 reviews. Original spec candidate. |

**Verify in listing before paying:**
- 24-pin ATX main power (+ 4-pin CPU)
- 6x SATA III, 2x M.2 NVMe
- 1x DDR4 SO-DIMM, max 32GB
- 2x Intel i226-V 2.5GbE
- Mini-ITX 170×170mm

## 2. RAM — DDR4-3200 SO-DIMM, 1 module (board has one slot)

### 16GB (budget build)

| Module | Price | Link |
|--------|-------|------|
| GoodRAM GR3200S464L22/16G | 1,086 kr | https://www.prisjakt.nu/produkt.php?p=5638747 |
| **Kingston KCP432SS8/16** | 1,235 kr | https://www.prisjakt.nu/produkt.php?p=5448955 |
| Samsung M471A2K43DB1-CWE | 1,347 kr | https://www.prisjakt.nu/produkt.php?p=5391841 |
| Crucial CT16G4SFRA32A | 1,541 kr | https://www.prisjakt.nu/produkt.php?p=5456913 |

### 32GB (recommended — single slot, one-shot decision)

| Module | Price | Link |
|--------|-------|------|
| Adata Premier AD4S320032G22-SGN | 2,691 kr | https://www.prisjakt.nu/produkt.php?p=5926542 |
| Patriot Signature PSD432G32002S | 2,969 kr | search Prisjakt by part number |
| **Crucial CT32G4SFD832A** | 3,154 kr | https://www.prisjakt.nu/produkt.php?p=5324661 |
| Lexar LD4AS032G-B3200GSST | 3,220 kr | https://www.prisjakt.nu/produkt.php?p=5777695 |
| Kingston KCP432SD8/32 | 3,783 kr | https://www.prisjakt.nu/produkt.php?p=5555198 |

Crucial is the safest 32GB pick (JEDEC 1.2V, wide compatibility). 32GB modules are dual-rank; board spec says max 32GB but no review confirmed a 32GB module. Kingston 16GB is the zero-risk pick.

## 3. Reused parts (0 kr)

| Part | Use |
|------|-----|
| Fractal Node 304 | Case |
| Existing PSU | 24-pin + 4-pin to new board |
| Plextor PX-256M6S 256GB SATA SSD | OS, SATA port 1 |
| 4x WD WD30EZRX 3TB | Data, SATA ports 2–5 |
| SATA cables | Check count: need 5. Board usually ships with 2–4. |

## Totals

| Build | Board | RAM | Total |
|-------|-------|-----|-------|
| Board + Kingston 16GB | 3,123 | 1,235 | **~4,360 kr** |
| Board + Adata 32GB | 3,123 | 2,691 | ~5,810 kr |
| Board + Crucial 32GB | 3,123 | 3,154 | **~6,280 kr** |

Excludes AliExpress shipping (~6–30 kr on these listings) and any extra SATA cables.

## Fallback — CWWK N150 via Amazon.de (EU returns)

| Part | Price | Link |
|------|-------|------|
| CWWK N150 "M2" 6-bay, DDR5, PCIe x4, 24+4-pin ATX | 3,274 kr + 98 kr shipping | https://www.amazon.de/dp/B0H7WL8F9Z |
| Crucial CT16G48C40S5 DDR5-4800 16GB SO-DIMM | ~2,840 kr | Prisjakt |

Total ~6,200 kr for 16GB. Choose only if returns/brand support are worth ~1,900 kr over Candidate 1.

## Follow-up purchases (not now)

- 4x CMR NAS HDDs to replace the 10+ year old WD Green SMR drives (biggest failure risk in the system).
- 2.5GbE switch/NIC on the client side to use the board's i226-V ports.
