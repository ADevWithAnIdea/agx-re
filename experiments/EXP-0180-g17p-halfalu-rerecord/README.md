# EXP-0180 — re-recording the 25 half-ALU emitter-grade row-claims, on G17P

**Successor to EXP-0169** (new number, fresh pre-registration, per `CODEX.md` §2). EXP-0169
withdrew its `C2_load` carrier for **DEF-0169-1** — `device_load` on G17P is asynchronous and
its harness issued no wait anywhere — and **held** 16 rows rather than downgrading them,
because the carrier had failed for a harness defect and not because the fields resisted.
This experiment owns those rows.

**Target: Apple A18 Pro / G17P.** Every claim is a G17P claim.

## Question

**Can the 25 emitter-grade row-claims over `half_alu_ext8` / `half_alu_fma12` be substantiated
by a fresh, per-case, attributable capture — and if not, which must be WITHDRAWN?**

They have already failed to substantiate twice: `EXP-M4-14` has **no `raw/` tree at all**
(EXP-0164), and EXP-0169's carrier had no detection power for them. A third inconclusive
result is itself a finding, and **withdrawal is an accepted outcome**.

## The target set

**25 row-claims over 16 DISTINCT fields** (`analysis/target_rows.py` →
`work/target_rows.json`). The nine `EXP-M4-14` rows are a **strict subset** of the sixteen
EXP-0169 held, so nine fields carry two claims each and get two verdicts each. All 16 spans
are byte-identical to the ones EXP-0169 measured against this experiment's **pinned**
`db.json` (`a77f8cfa…`, which is also the hash `validation.json` was generated against).

## What went wrong last time, established OFFLINE before this build

`PROGRESS.md` M3/M4 derives all of this from EXP-0169's committed raw. Four defects:

* **DEF-0180-A (carrier).** The lifted anchors name half-registers `0x81`/`0x83` = registers
  **64/65**, which the synthesized carrier never seeds, and the carrier's float seeds have
  **zero low 16 bits**, so every even half-register descriptor reads `0.0`. The anchors
  computed `0` and wrote it where `0` already was. Only 28 of 256 `dst` values could move —
  exactly the odd descriptors of the *seeded* registers.
* **DEF-0180-B (db model).** The destination GPR of the `byte0==0x10` family is **byte0's
  HIGH NIBBLE** (result → that register's low 16 bits), visible in EXP-0169's own falsifier
  case: `byte0 0x10 → 0x00` moved the result from `r1` to `r0`, preserving `r0`'s high half.
  `db.json` pins all 8 bits of byte0 in `match` and calls bits 8..15 `dst` — those bits are a
  **source** descriptor. Same defect class as `mov_zext16`/DEF-0161-2, one family over.
* **DEF-0180-C/D (length model).** `db.json` says byte0 `0x10` is `6, or 8 if (byte+2 & 0x02)`;
  `isadb.instr_length` implements `6 + 2*(byte+4 & 3)`. They contradict each other and
  **neither has been measured on hardware**. The code rule explains EXP-0169's otherwise
  unexplained all-`0xDEADBEEF` cases at `srcB ≡ 2 (mod 4)` exactly.
* **The falsifier was not a falsifier.** `byte0 → 0x00` changes only the destination register
  of this family. It cannot null the op — which is why 16 rows were held on a "ladder
  failure" that was an artefact.

## Method

Two structurally different carriers, neither seeded by `device_load`; every GPR carries
**distinct non-zero fp16 values in both halves**; every case dumps all 16 GPRs **before** and
**after** the block, so **"the seeds landed" is proved per case, not per batch**, and there is
**no periodically refreshed baseline anywhere**. Poison `0xDEADBEEF`; PRE sentinel in memory
before the block; POST sentinel written after it; the OS fault-classification string recorded
verbatim on every non-`ok` case; `tok_instr` **and** a hardware-measured instruction length
recorded per case, so a mutation that changes instruction identity can never be counted as
movement. No abort path: every value dispatches regardless of outcome.

Full contract: **`PRE_REGISTRATION.md`** (frozen before any build) and
**`CAPTURE_CONTRACT.json`**.

## Files

| path | what |
|---|---|
| `PRE_REGISTRATION.md` | frozen hypotheses H0–H5, carriers, arms, coverage, oracles, falsifiers, ladder, gates, §11 amendment 01 |
| `CAPTURE_CONTRACT.json` | frozen pins, schema, run ids, timeouts, gates, amendments |
| `analysis/target_rows.py` | resolves the 25 claims → 16 fields and re-checks every span (offline) |
| `work/target_rows.json` | the resolved target set |
| `work/frozen/` | the **pinned** `db.json` + `isadb.py` the hardware runs against |
| `PROGRESS.md` | per-milestone log, append-only |

## Clean-room provenance

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/*.metal (authored by us) and the AGX machine code the PUBLIC
  runtime API compiled from that source; committed raw/ trees of EXP-0169 and the committed
  tools/agx-isa/{db.json,isadb.py,validation.json}, all READ-ONLY.
Apple binary introspection: NONE.
Reproduction: see PRE_REGISTRATION.md; commands land here once the harness is frozen.
Evidence: raw/ (append-only), analysis/field_verdicts.json, work/target_rows.json
```
