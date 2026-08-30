# EXP-0172 — the one-field-away tail of the emitter worklist (G17P)

**Question.** Of the 31 instructions the emitter worklist reports as **one field away** from
emittable, this experiment owns the remainder after EXP-0168 (the field name `dst` everywhere plus
12 instructions), EXP-0171 (`ilogic`, `srcA`, `tail`) and EXP-0169 (the 144 unverifiable fields plus
`get_sr.dst_hi`). For each field it owns: **can an emitter choose this field's value and get
documented hardware behaviour?**

**Hypotheses, variables, refuters, confounders and the promotion gate:** `PRE_REGISTRATION.md`
(frozen before any build; §9 records the one amendment, also made before any build).
**Frozen contract, pinned ISA-DB hash, timeouts, raw schema:** `CAPTURE_CONTRACT.json`.
**Observations vs interpretation, tested ranges, limitations, verdicts:** `RESULTS.md`.
**Machine-readable verdicts:** `analysis/field_verdicts.json` (flat `<mnemonic>.<field>`).

**Clean-room category: OWN-SHADER + HW-PROBE.** Every byte spliced, decoded or inspected is the
compiled form of MSL in `kernels/`, produced by the public Metal API from our own source. **No Apple
binary was disassembled, decompiled or introspected at any point.**

**Target: Apple A18 Pro / G17P** (`applegpu_g17p`, `AGXAcceleratorG17P`, 5 cores, macOS 26.6, Metal
family Apple9), host `users-MacBook-Neo.local`. Nothing was run on the M4.

## Method

1. **Freeze** `PRE_REGISTRATION.md` + `CAPTURE_CONTRACT.json`, including a **pinned snapshot of
   `tools/agx-isa/db.json`** (172 instructions / 1062 fields) resolved explicitly on the device —
   the neo's *shared* copy is stale (EXP-0169: 1036 fields, `falu2.srcA_class`/`srcB_class` replaced
   by `mod_lo`) and a `_find_isadb()` fall-through onto it would mis-key verdicts silently.
2. **Pre-freeze census** (`analysis/census.py`, calibration only, `raw/prefreeze/`): build all 24
   carriers with the exact pipeline descriptor the sweep will use, tokenize the compiled bytes, and
   report every occurrence of every target mnemonic with its decoded field values.
3. **Generate and freeze the arm list** (`analysis/gen_arms.py` → `harness/arms.py`) under the frozen
   selection rule: carriers that differ in the dimension the field controls, occurrences that span
   the field's own baseline values, and inside a bucket a preference for differing field context.
4. **Two gated runs** (`run.py`): per arm, a baseline; then a **full detection profile** (every field
   of the instruction, complemented and zeroed, recording whether the observation moved and whether
   the result still decodes as the same mnemonic); then the dense sweep of the target field.
5. **Verdicts** (`analysis/verdicts.py`) recomputed from `raw/`, never from a run manifest.

## What makes a null mean anything here

- **Detection power per arm**, not per experiment: an arm whose profile shows no status-OK,
  same-mnemonic control moving the observation is recorded and **barred** from supporting any
  verdict, inert or live.
- **Rule 2** (a never-moving field is promotable only if the carriers differ in the dimension the
  field controls) is applied through an *authored* `DIMENSION` table in `analysis/verdicts.py`, so an
  inert verdict rests on a named claim a reviewer can dispute.
- **Rule 3** (the observable must not co-vary with the field under test): `run.py` splices only the
  instruction under test at a frozen absolute offset and observes fixed surfaces at probe points
  chosen before the run. Nothing observed is a function of the swept value.
- **Rule 4**: no verdict cites a round trip, `rt_ok`, or tokenization.
- **DEF-0170-1**: patched instructions are re-decoded **in context**, and a value that no longer
  decodes as the same mnemonic is excluded from `encodable_range` rather than counted as coverage.
- **EXP-0169's asynchronous `device_load`** — the one contamination mode that can *fabricate* a
  positive against a diff-based oracle — is designed out of the Tier 1 carriers, which contain no
  `device_load` at all, and detected by the cross-run gate everywhere else.

## Layout

| path | what |
|---|---|
| `PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json` | the frozen contract (hypotheses, gate, hashes) |
| `kernels/*.metal` | **our own MSL**, one file per carrier |
| `harness/carriers.py` | carrier definitions + the frozen `TARGETS` / `DECLINED` tables |
| `harness/arms.py` | the FROZEN arm list (generated, then asserted byte-exact at run time) |
| `harness/gfrun2.m`, `harness/runner2.py` | render/compute persistent runners with watchdogs |
| `run.py` | the capture driver |
| `analysis/census.py`, `gen_arms.py`, `verdicts.py`, `manifest.py` | repeatable analysis |
| `raw/prefreeze/` | **calibration only — no verdict may cite it** |
| `raw/g17p_20260830_run01`, `…run02` | append-only evidence, one JSON object per case |
| `work/` | device-side scratch, the pinned DB snapshot, and the retained smoke runs |

## Commands (as run)

```sh
# on the neo, with the experiment's OWN pinned tool tree
export AGXRE_REPO=$HOME/agxre/EXP-0172
clang -fobjc-arc -O2 -Wno-deprecated-declarations -framework Metal -framework Foundation \
      harness/gfrun2.m -o work/gfrun2          # likewise shdump, agxrun_persist
python3 analysis/census.py                     # calibration
python3 analysis/gen_arms.py                   # -> harness/arms.py, then frozen
python3 run.py --run-id smoke02 --smoke-only   # baselines + detection profiles
python3 run.py --run-id g17p_20260830_run01 --deadline-s 3600
python3 run.py --run-id g17p_20260830_run02 --mnem <see RESULTS.md §hangs> --deadline-s 2400
# on the repo host
python3 analysis/verdicts.py                   # -> analysis/field_verdicts.json
python3 analysis/manifest.py                   # -> manifest.json
```
