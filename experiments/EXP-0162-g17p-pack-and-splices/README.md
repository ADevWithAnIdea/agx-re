# EXP-0162 — the PACK coverage gap, and two descriptor defects that need a fragment splice

**Target: Apple A18 Pro / G17P** (`applegpu_g17p`, `AGXAcceleratorG17P`, 5 GPU cores,
macOS 26.6). Every result in this directory is labelled `target: G17P`.

```
Clean-room provenance: OWN-SHADER + HW-PROBE (+ PUBLIC for IEEE-754 / bfloat16 and the
  MSL format-conversion definitions, used only to write the host oracle, never to source
  an Apple9 encoding fact)
Inputs inspected: kernels/carriers.metal (EXP-0144's authored carriers, verbatim),
  kernels/render_probe.metal (authored here), the machine code compiled from both, and
  this repository's own committed own-MSL corpus (EXP-M4-13-full-corpus/hex) and
  tools/agx-isa/ (read-only)
Apple binary introspection: NONE
Reproduction: see "Reproduction" below
Evidence: raw/g17p_20260829_run01__{cvt_bf16,cvt_f2h_dst,packed_half2_hi}/,
  raw/g17p_20260829_run04__rog/, raw/g17p_20260829_run05__{kill,vary}/ (append-only
  JSONL); raw/g17p_20260829_run02__* retained unused; analysis/*.json
```

## The questions

1. **EXP-0144's coverage gap.** Eighteen fields returned to `untested` because two shards
   never dispatched a case (`cvt_bf16` 8 fields, `packed_half2_hi` 5) and a third died
   mid-run (`cvt_f2h_dst` 5 of 6) when `MTLCompilerService` collapsed. Two findings were
   *withdrawn* as inadmissible: `cvt_bf16`'s RNE rounding and `packed_half2_hi`'s
   high-lane-only semantics.
2. **Has anyone ever measured a bf16 numeric result?** Part-II questionnaire items P2-01/02
   are "hardware YES, emit NO": no committed experiment had.
3. **`pixel_order`** declares a field and a match constant over the *same* bits. Two
   candidate fixes were built and both are wrong (`work/DB-DEFECT-TRIAGE.md` §4). The corpus
   has **zero** `pixel_order` firings, so it cannot adjudicate.
4. **`vary_store`** (`emit_unsafe`): a byte0=0x57 op in a fragment main is a 6-byte
   kill/mask op mis-tokenized as the 8-byte vertex store (EXP-0091). What discriminates?
5. Can either descriptor defect be **settled** — a change with hardware evidence that
   passes round-trip and does not regress the corpus?

## Hypotheses and falsifiers

Frozen in `PRE_REGISTRATION.md` (+ `AMENDMENT 1`, made after two smoke runs and before any
gated capture) and `CAPTURE_CONTRACT.json`. Five hypotheses, H1–H5, each with a named
refuter; two arms carry a pre-registered **detection-power control** that voids the arm if
it fails.

## Method

* Compile our own MSL on the target (`tools/shdump`), locate `_agc.main`, splice bytes in
  place, execute, read back — the standard `tools/agxtest` route (`agxrun_persist` for
  compute, EXP-0147's `rendersweep.m` for render, which reloads a fresh `MTLLibrary` from
  each spliced archive so the spliced bytes really run).
* **Poisoned read-back** (`0xDEADBEEF + i` per word): the output and sentinel buffers are
  bound as *input* files pre-filled with poison, so `agxrun_persist` reuses them and an
  unwritten word is distinguishable from a genuine silent zero.
* Majority-of-3 escalating to 5; `…ErrorInnocentVictim` attempts discarded and re-run;
  baseline re-validated every 100 cases; OS fault-classification string recorded per case.
* Concurrency: **unlocked**, per the current `experiments/NEO-TARGET-BRIEF.md` (the GPU
  lease was removed from that brief while this experiment was running — see `RESULTS.md` §6).
* `db.json` was **not** edited. Proposals live in `analysis/proposed_db_changes.json` and
  were A/B'd against COPIES built by `analysis/make_variant.py`.

## Reproduction

```sh
# desk (this repo, no GPU)
python3 experiments/EXP-0162-g17p-pack-and-splices/analysis/corpus_scan.py
python3 experiments/EXP-0162-g17p-pack-and-splices/analysis/scan57.py
python3 experiments/EXP-0162-g17p-pack-and-splices/analysis/compute_analysis.py
python3 experiments/EXP-0162-g17p-pack-and-splices/analysis/make_verdicts.py
for v in pixel_order vary_store both; do
  python3 experiments/EXP-0162-g17p-pack-and-splices/analysis/make_variant.py $v; done
python3 experiments/EXP-0162-g17p-pack-and-splices/analysis/ab_run.py

# device (on the neo, under ~/agxre/EXP-0162)
python3 harness/locate.py                                  # compile + tokenize, no dispatch
AGXRE_ROOT=$HOME/agxre python3 harness/runcompute.py --run-id <id> --arm cvt_bf16
AGXRE_ROOT=$HOME/agxre python3 harness/runcompute.py --run-id <id> --arm packed_half2_hi
AGXRE_ROOT=$HOME/agxre python3 harness/runcompute.py --run-id <id> --arm cvt_f2h_dst
AGXRE_ROOT=$HOME/agxre python3 harness/runrender.py  --run-id <id> --arm rog
AGXRE_ROOT=$HOME/agxre python3 harness/runrender.py  --run-id <id> --arm kill
AGXRE_ROOT=$HOME/agxre python3 harness/runrender.py  --run-id <id> --arm vary
```

## Files

| path | what |
|---|---|
| `PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json` | frozen contract + amendment 1 |
| `kernels/carriers.metal` | EXP-0144's compute carriers, verbatim |
| `kernels/render_probe.metal` | the three render carriers authored here |
| `harness/locate.py` | compile-and-tokenize pilot (no dispatch) |
| `harness/cases162.py` | frozen compute case matrix + the four competing bf16 models |
| `harness/probe162.py` | EXP-0144's `probe.py` plus the poisoned read-back |
| `harness/runcompute.py`, `harness/runrender.py` | the two capture drivers |
| `harness/rendersweep.m`, `harness/rsdrv.py`, `harness/shdump2.m` | EXP-0147's render runner, unmodified |
| `analysis/corpus_scan.py`, `analysis/scan57.py` | desk scans over the own-MSL corpus |
| `analysis/compute_analysis.py`, `analysis/make_verdicts.py` | derived reports |
| `analysis/make_variant.py`, `analysis/ab_run.py` | the db-change A/B, against COPIES only |
| `analysis/field_verdicts.json` | per-field verdicts (`FIELD-SWEEP-PROTOCOL` §5) |
| `analysis/proposed_db_changes.json` | the two settled defects + one still blocked |
| `raw/` | append-only per-case JSONL, including the retained unused run02 |
