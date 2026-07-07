# EXP-0025: scoreboard / async-wait model (acceptance-gate gap G-1)

- **Date:** 2026-07-07
- **Clean-room category:** OWN-SHADER (compile our MSL → inspect/splice our own bytes → run on HW) + PUBLIC (G13 model from Mesa `agx_insert_waits.c` / dougallj applegpu, for hypotheses only).
- **Phase / question:** Phase 1 ISA — the async-completion / scoreboard model. Long-latency ops (device load/store, atomics, texture sample) are asynchronous on AGX; a compiler that consumes the result before it lands reads **stale data with no fault** (silent corruption). Decode G17P's model.
- **Device state:** Apple A18 Pro / G17P, macOS 26.6 (T8140), SIP disabled. Device workspace `~/cleanroom_work/exp0025/`.

## Hypothesis
By analogy to G13 (Mesa asahi): async ops assign a **scoreboard slot** (a 1-bit `g` field on the load/store/tex), and a distinct 2-byte **`wait`** instruction (G13 byte0 `0x38`) drains a slot mask before the consumer; `AGX_MAX_PENDING=8`, 2 slots. Expect a G17P analogue: a wait/barrier op between an async op and its consumer, with a slot-assign field and a wait-mask field.

## Method (clean-room legal)
Compile our own MSL kernels that exercise `load→use`, `sample→use`, `atomic→use`, dependent/pointer-chase loads, deferred consume, N-way fan-in, and threadgroup-memory + barriers (OWN-SHADER). Extract `_agc.main` with `tools/shdump`, tokenize with `tools/agx-isa`, and **splice-and-run** on the real GPU with `tools/agxtest` to prove semantics. Public G13 sources are used only to form hypotheses, never copied.

## Procedure (reproducible)
```sh
# on device ~/cleanroom_work/exp0025 (tools: shdump, agxrun, agxtest.py, agxparse.py from tools/)
./shdump -o /tmp/K.bin -f k --no-fast-math kernels/K.metal
python3 agxparse.py /tmp/K.bin --stage compute --extract-hex        # _agc.main bytes
# tokenize on host: tools/agx-isa/agxisa.py tokenize <hex>
# splice + run:
python3 agxtest.py --source kernels/K.metal --function k --grid G --tg T \
    --buf 0=... --out N=M [--splice _agc.main@0xOFF=HEX]
```
Kernels in `kernels/`: `copy add2 add4 gather chain loaduse loadfar manyload manyload20
atomicuse atomicvoid sampleuse storeonly` (async-op battery); `tgbar tgbar_none tgbar_dev
simdbar tg128 tg256 tgdiv2 tgdiv2_none` (threadgroup-barrier differential + splice-proven race).

## Raw results
`raw/mains.txt` (extracted streams), `raw/interlock_proofs.txt` (immediate-consume correctness),
`raw/splice_barrier.txt` + `raw/splice_*.txt` (barrier splice sweep), `raw/div2_*` / `raw/tgrun_*`
(barrier race outputs), `raw/tgdiv2.main.hex`.

Key observations inline in `RESULTS.md`.

## Analysis
See `RESULTS.md`. Headline: **G17P emits NO explicit per-op scoreboard wait in compute** —
device load/store/atomics/textures rely on a **hardware register interlock**; the only explicit
ordering op is the **threadgroup/execution barrier** (`byte0 0x07`, 6 B), splice-proven to be
load-bearing for cross-lane threadgroup-memory ordering.

## Established facts → docs / tools
- `threadgroup_barrier` (0x07, 6 B) + `mem_scope` field + `falu_acc` compact fadd → `tools/agx-isa/`
  (`isadb.py` DB + length rule, `db.json`, `roundtrip_test.py`). DB now 40 descriptors, ALL PASS.
- Scoreboard model (no device wait; HW interlock; max-in-flight HW-managed; barrier = only ordering op)
  → `db.json` `length_rule.scoreboard_model`. Docs update owned by orchestrator.

## Follow-ups
- Barrier byte+1 (`0x04`) / byte+5 sub-op space (memory-only fence? execution-only? `mem_none`?) — inferred.
- Whether a `memory_barrier`/device-fence to global memory across threadgroups needs a distinct op (only the barrier's byte+3=0x85 device-scope variant was seen).
- Full bit-decode of `falu_acc` (byte+1 accumulator descriptor).
- Fragment-stage async waits (pixel/tilebuffer `wait_pix`/`signal_pix` analogue) — this experiment is compute-only.
