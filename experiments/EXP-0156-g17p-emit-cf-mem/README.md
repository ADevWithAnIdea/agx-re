# EXP-0156 — A18 Pro / G17P: control flow, memory, and the bf16/half cluster

**Target: Apple A18 Pro / G17P** (`Mac17,5`, macOS 26.6, `AGXAcceleratorG17P`,
`applegpu_g17p`, 5 GPU cores, Metal family Apple9). Every result here is a **DIRECT
G17P** result. The local M4 is the repo/analysis host only.

## Question

Twenty-seven instructions across three families are decodable but not emittable, and
**loops are unemittable**, which blocks any real shader. Three questions, in priority
order:

1. **Do loops become emittable on G17P?** A loop needs `if_push_pred`, `jump_cond`,
   `if_push`, `ret`, `jump` and `pop_reconverge` emittable simultaneously. EXP-0140
   concluded four of those were "one gated capture short, not one hardware result short",
   and that `jump_cond` failed on **carrier liveness** — its guard's only true lane had
   trip count 0, so every offset, including out-of-program targets, reproduced the
   baseline.
2. **Does the `tg_addr_compute` G16G↔G17P divergence reproduce on real A18 silicon?**
   It is the only known live cross-target contradiction in the corpus: EXP-M4-14 (A18)
   recorded byte0 `0x1c` *and* `0xfc` reproducing; EXP-0141 (M4) found only `0x1c`.
3. **What is a bfloat16 arithmetic result on this hardware?** No experiment in this
   repository has ever measured one.

## Method

The smallest possible change from the prior art, so the evidence composes:

* **CF and atomics:** EXP-0152's frozen case matrix, reused unchanged and retargeted to
  G17P. It splices into EXP-0090/EXP-0112's **HW-validated 152-byte CF skeleton**,
  perturbing exactly one named field of one instruction per case, so **no branch
  displacement is ever recomputed** and the carrier is never lengthened (EXP-0140 §9
  showed lengthening a CF carrier is not semantically neutral even with `acc`-only
  padding).
* **The `jump_cond` unlock:** bind the `n` buffer to **all zeros**. That makes the
  loop-entry guard uniformly true and the branch **actually taken**, with no change to a
  single program byte, no length change and no displacement recomputation. Paired
  controls with the original mixed `n` prove the difference is the input, not the bytes.
* **`tg_addr_compute`:** EXP-M4-14's own `k_thr.metal`, byte-for-byte, so the two
  records are adjudicated on the same source.
* **bf16/half:** EXP-0145's own-MSL carriers, with **host-computed exact bit-pattern
  oracles** and inputs chosen so every expected `a+b`, `a*b`, `a*b+c`, `max` and `min` is
  exactly representable — so a match is a numeric proof, not an inertness test. A
  separate input pair, on identical program bytes, measures the **rounding mode**.

## Reproduction

```sh
# on the neo (A18 Pro), under ~/agxre/experiments/EXP-0156-g17p-emit-cf-mem
sh harness/build.sh work/bin
python3 harness/pilot_locate.py work/bin work/pilot_loc      # compile-only, no GPU
python3 harness/baseline.py work/bin work/baseline_bin       # compile-only, no GPU
python3 harness/cases.py                                     # 13 991 frozen cases, no GPU
bash harness/batch.sh                                        # every gated capture

# on the repo host (analysis only, no GPU)
python3 analysis/verdicts.py            # cross-run gate over the frozen run pairs
python3 analysis/field_verdicts.py      # FIELD-SWEEP-PROTOCOL §5 verdicts
python3 analysis/emittability.py        # instruction-level emittability delta
```

## Clean-room attestation

```
Clean-room provenance: HW-PROBE + OWN-SHADER
Inputs inspected: our own MSL (kernels/*.metal — authored by this project or reused
                  byte-for-byte from EXP-0090/0112/0141/0145/M4-14) and the machine code
                  compiled from it; instruction bytes assembled by our own tools/agx-isa
                  (read-only use)
Apple binary introspection: NONE
Reproduction: the commands above
Evidence: raw/g17p-20260830-*/sweep.jsonl (append-only), each run's 00_inputs.json and
          01_summary.json, analysis/gate_report.json, analysis/field_verdicts.json,
          analysis/emittability.json, CAPTURE_CONTRACT.json
```

No Apple binary was disassembled, decompiled, symbol-dumped, strings-scanned or debugged.
The only machine code inspected or spliced is the compiled form of MSL we wrote.
`db.json`, `validation.json`, `docs/` and `PROVENANCE.md` were **not** edited; the
per-field verdicts are offered to the orchestrator in `analysis/field_verdicts.json`.
