# EXP-M5-03 — third-party MSL corpus + G17P-DB baseline census on the M5

**Device:** `user@192.168.170.253` — Apple **M5**, SoC **T8142**, macOS 27.0
(kernel `xnu-13432.0.5.501.1 RELEASE_ARM64_T8142`). `threadExecutionWidth = 32`,
`maxThreadsPerThreadgroup = 1024`.

**Goal.** Build the reusable M5 machine-code corpus from the committed permissive
third-party MSL under `thirdparty/`, and measure how far the unmodified A18/G17P
disassembler DB (`tools/agx-isa`, 170 descriptors) gets on real-world programs when
compiled on the M5. This is OBJECTIVE 3's adversarial validation set.

**Clean-room.** Every byte is the compiled form of permissive open-source MSL
(SPIRV-Cross Apache-2.0, Dawn/Tint BSD-3, wgpu/naga MIT/Apache, PyTorch BSD-3,
llama.cpp MIT, ToyPathTracer Unlicense) compiled with our own `shdump` (builds an
MTLBinaryArchive; never dispatches) and extracted with our own `agxparse.py`. No Apple
binary introspected. DB used read-only and byte-identical to the repo. No GPU dispatch, no reboots.

## 1. Compile / extract results
13,039 files compiled STANDALONE; each success had `_agc.main` extracted to `tp_hex/`.

| project | files | compiled OK | hex | failed | lone | no-entry |
|---|---:|---:|---:|---:|---:|---:|
| SPIRV-Cross | 1058 | 450 | 450 | 45 | 553 | 10 |
| dawn/Tint | 11812 | 2546 | 2547 | 6934 | 765 | 1567 |
| pytorch | 48 | 13 | 13 | 30 | 0 | 5 |
| wgpu/naga | 119 | 79 | 83 | 4 | 32 | 4 |
| ToyPathTracer | 1 | 1* | 2 | — | 0 | 0 |
| llama.cpp | 1 | 0 | 0 | 1 | 0 | 0 |
| TOTAL | 13039 | 3089 | 3095 | 7015 | 1350 | 1586 |

*ToyPathTracer: only its self-contained vertex/fragment prefix compiles (rest needs a
local header absent from the corpus). llama.cpp: single 10.8k-line monolith needs local
C headers (ggml-common.h / ggml-metal-impl.h) never collected — legitimate negative
result. Failure classes: parse-error 6933, include-not-found 32, unsupported-feature 24.

Result: 3095 hex programs across 5 of 6 projects, 12 MB on device.

## 2. Census — unmodified G17P DB on the M5 third-party corpus
Byte-weighted resync tokenizer (EXP-M4-01 method), dedup by sha256.

| metric | value |
|---|---|
| hex programs | 3095 (709 unique) |
| instruction tokens | 61,766 |
| total instruction bytes | 285,972 |
| fully-named | 80.60 % (230,482 B) |
| raw (length-only) | 5.46 % (15,622 B) |
| desync | 13.94 % (39,868 B) |
| cleanly tokenized | 86.06 % |
| distinct byte0 groups | 232 |

### 2a. Top desync leaders (byte0), with own-corpus rank for cross-check
| byte0 | TP regions | own rank | own regions | note |
|---|---:|---:|---:|---|
| 0x26 | 2175 | 34 | 171 | **family _6, #1 in real code (under-weighted in own corpus)** |
| 0x2e | 720 | 32 | 190 | family _e |
| 0x3e | 602 | 1 | 1863 | family _e (top in own) |
| 0x5f | 496 | 60 | 62 | family _f |
| 0xb7 | 454 | 2 | 1671 | new leader |
| 0x07 | 411 | 14 | 442 | mem/varying |
| 0xa0 | 391 | 5 | 915 | 0xa_ |
| 0xa4 | 364 | 37 | 142 | 0xa_ |
| 0x36 | 358 | 84 | 26 | family _6 |
| 0x90 | 223 | 51 | 90 | |
| 0x10 | 202 | 42 | 107 | |
| 0x02 | 185 | 10 | 647 | |
| 0x21 | 179 | 27 | 223 | |
| 0xbe | 157 | 9 | 691 | family _e |
| 0x38 | 152 | 16 | 397 | |

Full 149-leader histogram: census.txt / census.json.

### 2b. Desync collapses to ~13 low-nibble families (high nibble = dst register)
`_6` 22.8% · `_e` 16.3% · `_0` 12.2% · `_f` 9.9% · `_7` 8.2% · `_1` 6.8% · `_8` 6.3% ·
`_4` 5.7% · `_2` 5.4% · `_b` 2.2% · `_5` 1.7% · `_a` 1.6% · `_d` 0.9%. For every top
leader `instr_length` returns None on M5 bytes — length-rule/leader divergences, not
missing field descriptors. Fixing families `_6`, `_e`, `_0`, `_f`, `_7` recovers the bulk.

### 2c. Raw (length-known, unnamed) leaders — 5.46% of bytes
0x27 (836), 0x8f (205), 0x17 (156), 0x01 (96), 0x47 (86). Field-decode gaps, lower priority.

## 3. Cross-check vs the independent M5 own-shader corpus (EXP-M5-02/hex)
| corpus | unique | instr bytes | named | raw | desync |
|---|---:|---:|---:|---:|---:|
| third-party | 709 | 285,972 | 80.60% | 5.46% | 13.94% |
| own M5 | 842 | 536,960 | 75.86% | 8.37% | 15.77% |

They agree on which leaders diverge: **143 of 149** third-party desync leaders also
desync in the own corpus; top-weight leaders (0x3e, 0xb7, 0xa0, 0x07, 0x02, 0xbe, 0x38,
0xa8) rank high in both. Disagreement is only in ranking — real code over-weights family
`_6` (0x26 #1 in TP vs #34 in own); own corpus over-weights exotic long-immediate/mask/ray
forms. Byte0 only in third-party (not own): 0x6e, 0x8d, 0x8e, 0xd7, 0xf7 — high-dst
variants of already-flagged families, **no new family**.

## 4. Headline
Identical own MSL: ~97% named on A18/G17P → 75.9% named / 15.8% desync on M5; real
third-party: 80.6% named / 13.9% desync on M5. M5 = G17P-derived ISA with systematic
length-rule deltas concentrated in ~13 low-nibble families (`_6 _e _0 _f _7`), independently
corroborated by both corpora. This is OBJ-3's validation baseline; re-census after DB fixes.

## 5. Reusable infrastructure (kept on device)
`~/cleanroom_work/EXP-M5-03/tp_hex/` — 3095-program M5 corpus (12 MB). Re-census after each
DB fix: `python3 census_m5.py tp_hex --out census`. Regenerate: `python3 m5_tp_compile.py`.

## Clean-room attestation
Permissive third-party MSL only (projects retain their original licenses), compiled with our
own tools; DB verified byte-identical to repo. No Apple binary disassembled/introspected; no
GPU dispatch. Every number from an actual census run; scripts committed for reproduction.
