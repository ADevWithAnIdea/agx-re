# EXP-0193 — The full 337-arm `STABLE-LIVE` population, under EXP-0192's frozen criterion

**Status:** COMPLETE. **Pure offline analysis — no device contacted, no SSH, no shader
compiled, no GPU.** (The A18 Pro was down for the duration; nothing here needs it.)

**Criterion: INHERITED UNCHANGED from `EXP-0192-fault-as-movement`.** This experiment adds no
case, tunes no threshold, and writes no second implementation. It imports EXP-0192's committed
`classify_row()` and calls it. The scope changes; the rule does not.

## The question

EXP-0192 named its own unswept remainder in `RESULTS.md` §7:

> *"Scope was the four emitter-grade rows named by EXP-0191 plus one control. **The full 337-arm
> `STABLE-LIVE` population was not re-scored under this criterion**; that sweep is the obvious
> successor and is mechanical from `analysis/valid_payload_audit.py`."*

EXP-0191 had measured that **7 of 337** `STABLE-LIVE` arms carry fewer than two distinct VALID
payloads; EXP-0192 examined the **4 rows** already flagged and withheld 3. **The other 3 arms —
and every field attributed to them, and the other 330 arms — had never been examined.** This
experiment scores all of them.

Why the rule exists: `EXP-0190/analysis/collect_raw.py::sig_of` builds a per-case signature as
`"<hardclass>|<sha1(observed)[:10]>"`, so an `ok` case and a `fault` case **always** differ and
`audit.py`'s `moved` counts a fault as movement. A field whose values merely fault — never
producing two distinguishable valid outputs — can therefore be scored `STABLE-LIVE` and reach
emitter grade.

## The criterion (EXP-0192 `PRE_REGISTRATION.md` §4.2, verbatim)

| case | condition | verdict |
|---|---|---|
| **A** | some attributing arm shows **≥2 distinct VALID payloads** | **STANDS** |
| **B** | <2 valid payloads and **≤1 legal value** | **STANDS**, `legality-only` — nothing for an emitter to choose |
| **C** | <2 valid payloads but **≥2 legal values** | **WITHHOLD** — inertness that `sig_of` re-scored as movement |

## Population

Every `<mnemonic>.<field>` key of `EXP-0190/analysis/audit.json` for which some
`per_experiment[eid][arm].stable_live` is true — the same enumeration
`EXP-0191/analysis/detection_gate.py` performs to build `slcheck`.

**337 arms** (matching EXP-0191's committed `n_stable_live_arms_checked`), **503 fields**,
**23 experiments**.

## Answer

**497 Case A · 0 Case B · 6 Case C · 0 unverifiable.** Three of the six were already withheld by
EXP-0192. **Three are new**, and all three are emitter-grade today:

| row | live label | V | L | arms | what the "movement" actually was |
|---|---|---:|---:|---:|---|
| `frag_color_pack.fmt_class` | `hardware-run` | 1 | 255 | 1 | **2 cells, both `undecodable` at value 86 — our own disassembler, not the hardware** |
| `ray_move_copy6.optype` | `hardware-run` | 1 | 191 | 1 | 128 `fault` cells |
| `vtx_coord_xform.operand` | `isolated-byte-diff` | 1 | 817 | 1 | 987 `no_draw` + 39 `fault` cells |

For every one of the six, `moved` is **exactly** the hard-class cell count. The two `irotate.b2`
arms and the one `call.offset` arm that EXP-0191 flagged and nobody had examined both come out
**Case A** — rescued by other arms of the same experiments, on the same target.

**Honest number: 32 of 166 emittable, 543 of 1040 emitter-grade fields** (from 33 / 546).
`vtx_coord_xform` is the one family that changes state.

## Controls

- **R1 (positive control, expectation recorded in `PRE_REGISTRATION.md` §5 before running):**
  `call.b5` — `hardware-run`, ~50 % of its cases faulting — must come out **Case A with
  V = 3, 4, 2** across three arms. **PASSED**, with all five per-arm counters
  (`n_cases`, `n_fault_cells`, `V`, `V_all`, `L`) matching EXP-0192's committed table exactly.
  Had it not, the deliverable would have been a broken-pipeline report and no verdict.
- **R2 (re-derivation):** EXP-0192's four rows land on their committed cases (A, C, C, C).
  **PASSED.**
- **R3 (discrimination):** both directions occur — 497 A and 6 C.
- **R4 (attribution):** 0 of 503 rows unlocatable in the pinned index.

## Reproduction

```
python3 analysis/population_audit.py
```

Deterministic: run01 and run02 produced identical output. ~7.6 s. Writes
`analysis/population_audit.json` and, because Case C fired on emitter-grade rows,
`analysis/reclassify.json`. **It edits no label and no other experiment's files** (verified:
the SHA-256 of every frozen input is unchanged after the run, and `git status` shows only this
directory).

## Clean-room statement

```
Clean-room provenance: derived analysis of already-committed evidence (OWN-SHADER/HW-PROBE lineage)
Inputs inspected: experiments/*/raw/**/*.jsonl (our own append-only capture records),
                  tools/agx-isa/{db,validation}.json,
                  EXP-0190/analysis+work, EXP-0191/analysis, EXP-0192/analysis
Apple binary introspection: NONE. No shader compiled, no device contacted, no SSH.
Reproduction: python3 analysis/population_audit.py
Evidence: analysis/population_audit.json, analysis/reclassify.json,
          work/run01_stdout.txt, work/run02_stdout.txt
```
