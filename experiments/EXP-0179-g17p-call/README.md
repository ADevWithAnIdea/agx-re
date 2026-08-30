# EXP-0179 — Can this ISA make a non-inlined CALL, and can we EMIT one? (A18 Pro / G17P)

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/*.metal and kernels/census/*.metal (authored by us) and the AGX
  machine code the public newLibraryWithSource: / MTLBinaryArchive API compiled FROM THEM;
  plus this repository's own committed evidence.
Apple binary introspection: NONE
Reproduction: harness/sync.sh push && harness/sync.sh build
              python3 harness/census.py --out raw/prefreeze/census_<id>
              python3 harness/calib.py  --run  calib_<id>
              python3 harness/run.py    --run  g17p_<date>_run01 --order forward
              python3 harness/run.py    --run  g17p_<date>_run02 --order reverse
              python3 analysis/census_report.py --run census_<id>
              python3 analysis/analyze.py  --runs g17p_<date>_run01 g17p_<date>_run02
              python3 analysis/verdicts.py --gate analysis/gate.json
Evidence: raw/prefreeze/** (calibration + census, never a verdict), raw/<run>/sweep.jsonl
```

## 1. The question, and why it matters

`docs/P0-P1-CLOSURE.md` P0.8 (the VS/FS/CS stage ABI and prolog/epilog linkage) was
assembled by EXP-0177. Its **ranked blocker #2**:

> `call.{b3,b5,b6,tail}` are `tokenization-only` — *"framing only (round-trips; no value
> semantics established)"* — and `ret.scoreboard` was declined in advance.
> **NO CALL CAN BE EMITTED.**

That is the instruction EXP-0137's split-epilog contract depends on. Without an emittable
call a compiler back end cannot implement a non-inlined function, cannot build the
programmable prolog/epilog linkage P0.8 is about, and cannot use the helper/scratch
machinery that assumes a call frame.

**Why nobody had done it:** EXP-0156 recorded `call` as **NOT ATTEMPTED** (its §5.3) for a
*carrier* reason, not a measurement reason — its frozen CF skeleton contained no call, and
the only same-length splice sites would have branched to an address computed from
uninitialised state. So the blocker was: nobody had built a program containing a real,
reachable, non-inlined call **that we control**.

## 2. What this experiment does

Three things, in order, each a deliverable on its own:

1. **A CENSUS (arm `Z`, compile-only).** 24 authored MSL constructs — explicit `noinline` in
   two spellings, a large body with no attribute, twelve call sites, tail and non-tail and
   mutual recursion, `[[visible]]` direct and through a `visible_function_table`, an address
   taken, non-leaf and three-deep and spilling frames, twelve arguments, `float4` and struct
   returns, and a call from the **fragment** and **vertex** stages — compiled through the
   public runtime API and scanned two independent ways for a `call`.
   → `analysis/call_census.json`.

2. **GENERATION (arms `G`, `T`, `M`).** A program whose **entire** `_agc.main` is replaced by
   one we assemble: seeds, a **generated** `call`, a **generated** callee placed past the
   `stop`, a **generated** `ret`, and a fixed 16-register read-back. The displacement is
   *computed from the layout*, so the target formula `target = call_addr + 4 + offset` is
   **re-measured on G17P by generation** rather than assumed from EXP-0035's four backward
   A18 call sites. 192 distinct generated calls across four plan × mask-nesting combinations.

3. **THE FIELDS (arms `B3`, `B5`, `B6`, `TL`, `R`, `L`).** Dense 0..255 sweeps of
   `call.{b3,b5,b6,tail}` and `ret.scoreboard`, on two carriers, in two gated runs.

Plus `O` (an ordering observable for `ret.scoreboard`, with the decline pre-registered),
`N` (a depth-2 generated call with **no** link save/restore — is the return address a
hardware stack or a single link register?), `S` (the same fields mutated in a **real**
compiler-emitted call, as an independent second method), and `F` (the falsifiers).

## 3. The declared clean-room boundary — stated because this experiment sits next to it

P0.8 lists **Apple's inlining heuristic** as a declared clean-room BOUNDARY. This experiment
does not approach it. We are not characterising *how Apple's compiler decides to inline*. We
author **our own MSL** until the instruction we want appears, and we report, per construct,
whether the machine code compiled **from our own source** contains a call. That is CODEX.md's
`OWN-SHADER` category and CLAUDE.md allowed technique 3.

* **Done here:** "construct X, compiled by the public runtime API, produced a program
  containing a 14-byte `0f 05 …` call" — a fact about *our* program's bytes.
* **Not done here:** any threshold or cost model, any interpolation between constructs, any
  claim about *why* a construct inlined, and any inspection of a compiler binary.

If a construct inlines, the census records `NO_CALL` and moves on. It never asks why.

## 4. Hypotheses and the frozen contract

`PRE_REGISTRATION.md` (H1–H7, the two carriers, the observable, the arms, the falsifiers,
the confounder table, the promotion gate) and `CAPTURE_CONTRACT.json` (authored-blob hashes,
case-matrix sha256, pinned toolchain, timeouts, raw schema) are frozen before any gated case
is dispatched. `raw/prefreeze/**` holds the census and the calibration and is **never**
evidence for a verdict.

## 5. The five rules of FIELD-SWEEP-PROTOCOL §3/§7, and how each is met

| rule | how |
|---|---|
| **(3a) the observable must not co-vary with the field** | **structural, not careful**: neither `call` nor `ret` declares a single register-typed field, so no swept value can name the read-back index register, any store's data register, the sentinels, or the callee register. The read-back is a fixed 16-store list, byte-identical in every case of every arm. |
| **(3b) a round trip is NOT an emitter gate** | `rt_ok` is recorded per case and read by **nothing**. No verdict, no gate, no label cites it. |
| **(3c) a per-field hang budget cannot characterise a contiguous hazard** | `analysis/analyze.py` computes the **longest contiguous run of hanging values** per field. If adjacent values hang, the gated arm stops at budget 2 and a **named, non-gated** mapping pass (`run.py --hang-tolerant`, run id containing `MAPPING_`) is dispatched over the whole range and reported separately. Control flow is where hangs live, so this is expected to matter. |
| **a never-moving field is promotable only if carriers differ in the dimension it controls** | the two carriers differ in **execution-mask stack depth** at the call, which is the dimension H4 says these bytes control (`call` shares the `0f 05` leader with `if_push`, whose descriptor names byte+2 the mask bank and byte+3 the scope kind — and `call` carries `if_push`'s own `0x1a` scope-kind value at byte+3). |
| **DEF-0169-1: `device_load` is asynchronous** | no `device_load` on any verdict path; every register is seeded with `mov_imm`. **No oracle is a diff against a refreshed baseline** — the baseline is re-run for run integrity only, and every prediction is host-computed from `isa_helpers.SEED_I`. Arm `O` is the single exception, where the asynchrony is deliberately the instrument. |
| **pin your own `db.json`** | `work/frozen/{db.json,isadb.py}`, sha256 in the contract, resolved by a fail-closed function with **no** path-search fallback. |

Poisoned read-back (`0xDEADBEEF`), a PRE sentinel written before the call and a POST sentinel
after it, a 28-word untouched tail region, the OS fault-class string on every non-`ok` case,
majority-of-3 before any `fault`/`hang`, and `values_dispatched` / `distinct_bytes` /
`encodable_range` / `start` / `width` on every row.

## 6. Layout

```
kernels/carrier_call.metal     the SYNTH carrier (only its LENGTH and bindings matter)
kernels/census/*.metal         the 24 authored census constructs
harness/isa_helpers.py         program construction; call_bytes/ret_bytes GENERATE the
                               instructions under test from the pinned descriptor geometry
harness/cases.py               the authoritative case matrix (sha256 in the contract)
harness/sweeprun.py            carrier, dispatch, poisoned observation, the call oracle
harness/run.py                 the gated-run driver
harness/calib.py               PRE-FREEZE calibration (five closed parameters + F1/F2)
harness/census.py              arm Z, compile-only
harness/fndump.m               EXP-0035's linked-function compiler, reused verbatim
harness/sync.sh                push/build/pull (SSHPASS from the environment, never a file)
analysis/analyze.py            the cross-run gate + the contiguous-hazard detector
analysis/verdicts.py           analysis/field_verdicts.json, flat, the eight labels only
analysis/census_report.py      analysis/call_census.json
analysis/freeze_contract.py    regenerates CAPTURE_CONTRACT.json from the blobs on disk
work/frozen/                   the PINNED db.json + isadb.py
raw/prefreeze/                 census + calibration — NEVER evidence
raw/<run>/                     the gated captures
```

## 7. Status

See `PROGRESS.md` (append-only, one entry per milestone) and `RESULTS.md`. `RESULTS.md`
states plainly at the top whether this ISA can make a non-inlined call and whether we can
emit one — including, if that is the honest answer, that we could not, and what we tried.
**A documented negative on the call ABI is a first-class result.**
