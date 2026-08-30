# EXP-0188 — dimension carriers for four `single-template-inference` fields (G17P)

**Question.** Nine of the sixteen instructions one field away from emittable are blocked by a field
labelled `single-template-inference` — proven inert on the carriers tried, role unknown. That label
has been overturned five times in a day, always by **a carrier that differs in the dimension the
field actually controls**. For each field here we name that dimension, build a carrier that differs
in it, and report whether the field moves — treating a null on a carrier that provably *can* express
the dimension as the strong result it is.

**Fields, and the dimension built for each**

| field | dimension | carrier axis |
|---|---|---|
| `if_push.scope` | region KIND: cond-skip (`scope_kind` 0x01) vs loop-iteration (0x1a) | six nested / memory-bounded loop shapes (`kernels/k_cf188.metal`) |
| `iadd2.b2_fmt` | operand FORMAT/WIDTH: 16/32/64-bit, imm-vs-reg srcB, uniform operand | seven integer-add shapes (`kernels/k_ia188.metal`) |
| `simd_ballot.cache` | execution-mask BANK / divergence depth | depth 0,1,2,3 + loop-iteration (`kernels/k_sd188.metal`) |
| `simd_shuffle.cache` | same (**width 1** — one bit of a byte that is 0x54 everywhere) | same |

Four further offered fields (`iter.b9`, `imageblock_store.b4`, `frag_color_store.store_mode`,
`vtx_out_pos.slot`) are **declined with reasons** in `PRE_REGISTRATION.md` §2: their dimensions are
pipeline state (sample count, MRT count, imageblock layout, system output slots) and require a render
harness this window cannot build and validate. `cvt_f2i.b9` is declined because EXP-0184 spanned its
dimension earlier the same day.

**Hypotheses and falsifiers:** `PRE_REGISTRATION.md` §3 (frozen before any build).
**Gate:** `PRE_REGISTRATION.md` §6, implemented by `analysis/verdicts.py` and nothing else.
**Results:** `RESULTS.md`. **Machine-readable verdicts:** `analysis/field_verdicts_flat.json`.

## Method

1. `analysis/census.py` (pre-freeze, calibration only, **no verdict may cite it**) compiles every
   carrier with our own `shdump` and reports which ones emit the target instruction, where, with what
   compiled field value, and with what value of the dimension field.
2. `analysis/gen_arms.py` applies the frozen selection rule and writes `harness/arms188.json`
   (hashed into the contract by amendment, then never edited).
3. `run.py` sweeps each target field densely over its full range with **no abort path**, poisoned
   read-back, an integrity sentinel, the OS fault-classification string, majority-of-3 on every
   non-`ok` case, and the pinned tokenizer's mnemonic recorded per case.
4. `analysis/verdicts.py` recomputes every verdict from `raw/` under the frozen gate.

## Reproduction

```bash
export SSHPASS='...'                                   # SSHPASS only, never in a file
bash harness/sync.sh push
python3 harness/verify_remote.py --contract CAPTURE_CONTRACT.json \
        --remote agxre/EXP-0188 --host 192.168.10.243   # SEPARATE step; exit 0 required
bash harness/sync.sh build
bash harness/sync.sh shell 'cd ~/agxre/EXP-0188 && python3 analysis/census.py'
bash harness/sync.sh shell 'cd ~/agxre/EXP-0188 && python3 analysis/gen_arms.py'
bash harness/sync.sh shell 'cd ~/agxre/EXP-0188 && python3 run.py --run-id g17p_20260830_run01'
bash harness/sync.sh shell 'cd ~/agxre/EXP-0188 && python3 run.py --run-id g17p_20260830_run02'
bash harness/sync.sh pull
python3 analysis/verdicts.py raw/g17p_20260830_run01 raw/g17p_20260830_run02
```

## Clean-room attestation

```
Clean-room provenance: HW-PROBE + OWN-SHADER
Inputs inspected:      kernels/{k_cf188,k_sd188,k_ia188}.metal -- authored by us -- and the
                       `_agc.main` bytes the public Metal runtime compiled from them
Apple binary introspection: NONE
Reproduction:          the block above
Evidence:              raw/<run_id>/sweep.jsonl, raw/<run_id>/env.json, raw/prefreeze/
```

No Apple binary is disassembled, decompiled, symbol-dumped or otherwise introspected anywhere in this
experiment. Every byte inspected or mutated is the compiled form of MSL in `kernels/`, written by us.
