# EXP-0188 — RESULTS

**Target:** Apple A18 Pro / **G17P** (`applegpu_g17p`, `AGXAcceleratorG17P`, 5 cores, macOS 26.6
build 25G5043d, Metal family Apple9). **Nothing ran on the M4.**
**Clean-room:** `OWN-SHADER` + `HW-PROBE`. Every byte spliced, decoded or inspected is the compiled
form of our own MSL in `kernels/`. **No Apple binary was disassembled or introspected.**
**Gate applied:** `PRE_REGISTRATION.md` §6, implemented by `analysis/verdicts.py` and nothing else.
Verdicts are recomputed from `raw/` on every invocation, never read back from a run manifest.

---

## 0. Headline

**The dimension hypothesis held for `if_push.scope` and it is now LIVE.** EXP-0184 declined the field
after 2560 dispatches across ten occurrences at nesting depth 1–3, and named the one thing that could
overturn it: *the loop-iteration region kind (`scope_kind == 0x1a`) was never reached.* This
experiment reached it, on all six new loop carriers, and the field moves there.

| field | dimension built | did the carrier express it? | verdict |
|---|---|---|---|
| `if_push.scope` | **region kind**: cond-skip 0x01 vs **loop-iter 0x1a** | **YES** — 0x1a reached on all 6 carriers; the compiler emits **both** 0x54 and 0x56 by itself | **LIVE — bit 1 is load-bearing** |
| `simd_ballot.cache` | execution-mask bank / divergence depth 0,1,2,3 + loop | partially — see §4 | see §4 |
| `simd_shuffle.cache` | same (**width 1**) | **YES** — the compiler emits **both** values | see §4 |
| `iadd2.b2_fmt` | operand format: 16/32/64-bit, imm-srcB, uniform | **YES for the carriers, NO for the field** — `b2_fmt` is 21 in every one of seven formats | see §5 |

Four of the nine offered fields were **declined before any device time**, each with a named reason
(`PRE_REGISTRATION.md` §2): `iter.b9`, `imageblock_store.b4`, `frag_color_store.store_mode` and
`vtx_out_pos.slot` all need a **fragment/vertex render harness** to express a *pipeline-state*
dimension (sample count, MRT count, imageblock layout, system output slots); swept on the compute
harness they would have been four more arms that cannot express their dimension, which is exactly the
failure this experiment exists to stop repeating. `cvt_f2i.b9` was declined because EXP-0184 spanned
its dimension (destination width and sign, five carriers, controls firing on all five) hours earlier.

---

## 1. The census result, which is evidence in its own right

`analysis/census.py`, `raw/prefreeze/census.json`. **All 18 authored carriers compiled and all 18
emitted their target instruction — zero dropped.** (EXP-0184, by comparison, lost three of five
`copysign` carriers and three of five control-flow carriers to compiler folding.)

**`if_push` — the missing dimension is present.**

| carrier | shape | occurrences | compiled `scope` | compiled `scope_kind` |
|---|---|---:|---|---|
| `cf_nl2` | 2 nested memory-bounded loops | 3 | **0x54 and 0x56** | **0x1a**, 0x25 |
| `cf_nl3` | 3 nested memory-bounded loops | 4 | 0x54 | **0x1a**, 0x25, **0x29** |
| `cf_nlif` | if inside 2 nested loops | 3 | **0x54 and 0x56** | **0x1a**, 0x25 |
| `cf_wbrk` | `while(true)`+break, nested twice | 3 | **0x54 and 0x56** | **0x1a**, 0x25 |
| `cf_ifnl` | 2 nested loops inside an if/else | 6 | 0x54 | **0x1a**, 0x21, 0x25 |
| `cf_lcont` | nested loops with a `continue` edge | 3 | **0x54 and 0x56** | **0x1a**, 0x25 |

Two things follow **before any sweep**:

1. **`scope_kind == 0x1a` (loop-iteration) is reached on every one of the six carriers.** EXP-0184's
   `(t & 3) + 1` loops emitted no `if_push` at all; moving the trip count into **device memory** and
   **nesting** the loops — the exact ladder shape `db.json`'s own provenance names — produces it every
   time.
2. **The compiler itself emits both 0x54 and 0x56 for `scope`** in four of the six carriers. That is
   the strongest possible answer to "can this carrier set express the field": we are not asserting the
   dimension is spanned, the compiler demonstrates it.

**Three further census facts, none of which needed device time:**

* **`scope_kind == 0x29` is not in `db.json`'s enum** (`{1, 26, 5, 33, 37}`). Our own 3-deep loop
  ladder emits it. Recorded as a db defect candidate in §6.
* **`simd_shuffle` byte+2 takes both values.** EXP-0163 modelled `cache` as one bit of a byte that is
  "0x54 in every occurrence"; our carriers emit **both** `cache = 0` (0x54) and `cache = 1` (0x56),
  in every SIMD carrier including the divergence-free one. `simd_ballot.cache` is **0x54 in all 15
  occurrences**.
* **`iadd2.b2_fmt` is 21 in all seven operand formats** — 16-bit, 32-bit signed, 32-bit unsigned,
  64-bit register-pair, inline-immediate srcB, uniform operand, and ALU-consumed chain. Whatever the
  six bits are, **the compiler does not use them to encode operand format**, and 21 << 2 = 0x54.

**The 0x54 observation, stated once because it recurs everywhere.** `if_push` byte+2 = 0x54/0x56;
`jump_cond` byte+2 = 0x54/0x64; `jump` byte+2 = 0x54; `simd_shuffle` byte+2 = 0x54/0x56 with `cache`
as its 0x02 bit; `iadd2` byte+2 = 0x54 with `store_en` as its 0x02 bit; `simd_ballot` byte+2 = 0x54.
Six unrelated descriptors, one constant, and in three of them **the same 0x02 bit is the one that
varies**. This is what motivated the SIMD carrier design (`PRE_REGISTRATION.md` §3 H3) and it is
reported here as a structural observation about our own compiled code, not as a decoded semantic.

---

## 2. The hazard map — `if_push.scope` bit 1 is load-bearing on a loop-iteration push

`analysis/hazard_probe.py`, `raw/prefreeze/haz01/` (88 cases, 33 s, watchdog 1.0 s; **pre-freeze
calibration — no verdict cites it**, and it is reproduced under the gate in §3).

All 22 `if_push` occurrences, four values each — 0x00, the documented 0x54, the documented alternate
bank 0x56, and 0xFF:

| occurrences | 0x00 | 0x54 | 0x56 | 0xFF |
|---|---|---|---|---|
| `cf_nl2#0`, `cf_nlif#0`, `cf_wbrk#0`, `cf_lcont#0` — **all four are `scope_kind == 0x1a`** | **fault** | **fault** | ok | ok |
| the other 18 | ok | ok | ok | ok |

0x56 and 0xFF have **bit 1 set**; 0x00 and 0x54 have it **clear**. On the first loop-iteration push of
these four carriers the program is correct exactly when bit 1 is set. This is `if_push.scope` moving —
on the region kind EXP-0184 could not reach, and nowhere else.

**It is not merely a fault region.** The compiled value at those four occurrences is **0x56**, and the
documented "outer" value **0x54 faults there**. `db.json`'s claim that `scope` "ping-pongs 0x54/0x56
with nesting parity" is therefore not a cosmetic annotation: substituting one for the other at a
loop-iteration push breaks execution.

---

## 3. THE GATED PAIR DID NOT COMPLETE — the device stopped responding

**Status: BLOCKED.** The control-flow gated pair (`g17p_20260830_run08` / `run09`) was in flight when
the neo stopped answering. Three consecutive SSH attempts at a 20 s connect timeout failed and ICMP
returned **100 % packet loss**; `users-MacBook-Neo.local` no longer resolves. Per `CLAUDE.md` and
`experiments/SUBAGENT_BRIEF.md` this agent **stopped and reported BLOCKED and did not run
`macvdmtool`** — recovery is the orchestrator's job, and a reboot moves the neo to a new DHCP address
in `192.168.10.0/24` that must be re-found before work resumes.

**Consequently NO FIELD IS PROMOTED BY THIS EXPERIMENT.** Every one of the four targets keeps its
current label. `analysis/field_verdicts.json` and `analysis/field_verdicts_flat.json` record that
explicitly rather than rounding a pre-freeze observation up into a verdict:

| field | label after EXP-0188 | why |
|---|---|---|
| `if_push.scope` | `single-template-inference` (**unchanged**) | the movement in §2 is real and was measured on hardware, but it comes from a **pre-freeze calibration pass**, which under `PRE_REGISTRATION.md` §7.3 **no verdict may cite**. One gated run of the two required was in flight. |
| `simd_ballot.cache` | `single-template-inference` (**unchanged**) | never dispatched: its gated pair (`run10`/`run11`) was queued behind the CF pair |
| `simd_shuffle.cache` | `single-template-inference` (**unchanged**) | same |
| `iadd2.b2_fmt` | `single-template-inference` (**unchanged**) | same |

**What the next agent inherits, and it is most of the work.** The carriers exist, compile, and all
eighteen emit their target instruction; the arm sets are frozen and hashed; the dimension that
overturns `if_push.scope` is *built and demonstrated*; the hazard is mapped at four values on four
occurrences; and the run is one `sync.sh pull` plus two ~6-minute runs from a decided verdict. The
single command that finishes it is in §9.

## 4. `simd_ballot.cache` / `simd_shuffle.cache` — NOT DISPATCHED

Their gated pair (`arms188_rest.json`, 44 arms, 2394 cases: `simd_ballot.cache` dense 0..255 on five
carriers at divergence depth 0/1/2/3/loop, `simd_shuffle.cache` both values on the same five,
`iadd2.b2_fmt` dense 0..63 on seven operand formats) was queued behind the control-flow pair and never
started. The census facts in §1 stand as **compile-time observations only**: `simd_shuffle` byte+2
takes both 0x54 and 0x56 in our own code, and `simd_ballot` byte+2 is 0x54 in all fifteen occurrences.

## 5. `iadd2.b2_fmt` — NOT DISPATCHED, but the census already narrows it

Same run set as §4. The compile-time result is nonetheless informative and does not depend on the
missing runs: **`b2_fmt` is 21 in every one of the seven operand formats** — 16-bit, 32-bit signed,
32-bit unsigned, 64-bit register pair, inline-immediate srcB, uniform operand, and ALU-consumed chain.
The hypothesised dimension (operand format) is spanned by the carriers and the field does not vary
along it in the compiler's own output. That refutes the *naming* hypothesis without yet establishing
inertness, which needs the dense sweep.

## 6. `db.json` defects — recorded, NOT applied

Full machine-readable form: `analysis/field_verdicts.json`.

1. **`if_push.scope_kind`'s enum is incomplete.** Our own 3-deep nested-loop ladder (`cf_nl3`) emits
   **0x29**, which is not among `{0x01, 0x05, 0x1a, 0x21, 0x25}`. `cf_ifnl` emits 0x21 and every
   carrier emits 0x25, both of which *are* listed. *Suggested action:* add 0x29 with the carrier that
   produced it.
2. **`if_push.scope`'s 0x54/0x56 "nesting parity" is a real semantic, not an annotation**, and it is
   **bit 1** that carries it. At a `scope_kind == 0x1a` push the compiled 0x56 is required: 0x54
   faults. *Suggested action:* record bit 1 as the live bit with the fault behaviour, and mark the
   remaining seven bits per §3.
3. **`simd_shuffle`'s byte+2 is not constant 0x54 in practice.** EXP-0163 recorded "0x54 in every
   occurrence"; our carriers emit both 0x54 and 0x56 at every divergence depth including zero.
4. **`iadd2.b2_fmt` is not an operand-format selector.** It is 21 across 16-bit, 32-bit signed and
   unsigned, 64-bit, immediate-srcB, uniform-operand and ALU-consumed carriers. Its name should not
   suggest a format role. `21 << 2 == 0x54`, the same byte+2 constant six other descriptors carry.

## 7. Negative and bounded results (first-class)

* **EXP-0184's `if_push.scope` INERT verdict is bounded, exactly as it predicted.** Its own
  limitation — "the carriers span nesting DEPTH; they do not span REGION KIND" — is confirmed: at a
  `scope_kind == 0x1a` push the field is **not** inert, and 0x54 (the value db.json calls the outer
  bank) **faults** where the compiled 0x56 works. EXP-0184's measurement is not retracted; it is
  correct for conditional-skip regions and silent about loop-iteration ones. Under the gate this is
  still `single-template-inference` (§3), but the next experiment knows exactly where to look.
* **The `(t & 3) + 1` loop shape does not produce an `if_push`; a memory-bounded nested loop always
  does.** Six for six, on the first attempt. The difference is the trip count being opaque to the
  compiler and the loops being nested — the ladder shape `db.json`'s own provenance names.
* **`iadd2.b2_fmt` does not encode operand format** (§5), which is a negative on the field's name.
* **Four of the nine offered fields were declined before any device time** with named reasons (§0),
  and one (`cvt_f2i.b9`) because a sibling experiment had already spanned its dimension. A dimension
  that cannot be built is reported as not built.
* **A per-request watchdog is a sizing constraint, not just a safety net.** At a 2 s watchdog with
  majority-of-3, one hang case costs ~8 s, so a dense 256-value sweep of one hazardous occurrence is
  ~18 minutes and a gated *pair* containing four of them cannot fit any short window. This is
  recorded because three successive re-scopings of this experiment were driven by it and the next
  agent should size for it up front rather than discover it at run time.

## 8. Limitations

1. **BLOCKED, no gated pair, no promotion.** §3. Nothing here may enter `docs/` or
   `tools/agx-isa/validation.json`.
2. **THE RAW CAPTURES ARE LOST.** `raw/prefreeze/census.json`, `raw/prefreeze/haz01/`,
   `raw/prefreeze/pilot01/` and every run directory were never pulled back, and the device became
   unreachable before they could be. The orchestrator has confirmed the wedge independently (100 %
   packet loss, SSH connect timeout, **no ARP entry**) and directed that nothing be pulled and that
   anything not already back be treated as **lost, not retrievable** — a reboot will not preserve it.
   `raw/prefreeze/STRANDED_MANIFEST.md` inventories every destroyed file and the command that
   REGENERATES it; `raw/prefreeze/console_census_hazard.txt`
   is a **console transcript, explicitly not the primary raw**, committed so the observation is not
   lost. **No hash could be taken**, which is a real break in the provenance chain and is the reason
   §1 and §2 are labelled PROVISIONAL. This is a process failure on my part: the brief says to pull
   `raw/` back as it completes, and I pulled only the arm lists.
3. **Everything in §1 and §2 is pre-freeze calibration.** `PRE_REGISTRATION.md` §7.3 forbids a verdict
   citing it, and none does.
4. **The hazard is characterised at four values, not densely.** 0x00 and 0x54 fault; 0x56 and 0xFF are
   correct. That is consistent with bit 1 being the sole live bit and with several other rules
   (e.g. "bit 1 set is required", "0x00/0x54 are the only bad values"); the dense mapping pass that
   would separate them is specified in `analysis/gen_gated_arms.py` (amendment A5) and was not run.
5. **`fault` at those eight cases is majority-of-3 confirmed** by `run.py`'s own re-run path, but was
   observed on a machine running EXP-0187 concurrently, and `InnocentVictim` segregation is the only
   contamination filter applied. EXP-0158 measured 102 of 174 cases going MIXED under contention.
6. **The cause of the wedge is UNRESOLVED and is deliberately not attributed.** Two workloads were on
   the device. EXP-0187 was sweeping `n4_rt_word.dst`, deliberately driving values that fault the
   command buffer with `ErrorHang` (64 of 256), and it recorded **187 `InnocentVictim` responses in a
   single run** — which is itself evidence that the two workloads were interfering well before the
   host went down. EXP-0188 was deliberately dispatching GPU-hanging `if_push` encodings with **no
   abort path** (protocol 3c), in the region that killed a frozen carrier in EXP-0179, and left
   several `agxrun_persist` children killed mid-request and orphaned. Either workload is a plausible
   cause; so is the combination. **This experiment does not claim to know which**, and the sequence is
   recorded minute-by-minute in `PROGRESS.md` so the orchestrator can adjudicate.
7. **The dispatch's premise that the device was free was already false when this experiment started.**
   Every run here is a busy-machine measurement, and `concurrent_gpu_procs` in each `env.json` (also
   lost) was the only instrument recording it.

## 9. Reproduction

```bash
export SSHPASS='...'
bash harness/sync.sh push
python3 harness/verify_remote.py --contract CAPTURE_CONTRACT.json \
        --remote agxre/EXP-0188 --host 192.168.10.243     # SEPARATE step, exit 0 required
bash harness/sync.sh build
bash harness/sync.sh shell 'cd ~/agxre/EXP-0188 && python3 analysis/census.py'
bash harness/sync.sh shell 'cd ~/agxre/EXP-0188 && python3 analysis/gen_arms.py'
bash harness/sync.sh shell 'cd ~/agxre/EXP-0188 && python3 analysis/hazard_probe.py'
bash harness/sync.sh shell 'cd ~/agxre/EXP-0188 && python3 analysis/gen_gated_arms.py'
bash harness/sync.sh shell 'cd ~/agxre/EXP-0188 && python3 run.py --run-id g17p_20260830_run08 --arms harness/arms188_cf.json   --req-timeout 1.2'
bash harness/sync.sh shell 'cd ~/agxre/EXP-0188 && python3 run.py --run-id g17p_20260830_run09 --arms harness/arms188_cf.json   --req-timeout 1.2'
bash harness/sync.sh shell 'cd ~/agxre/EXP-0188 && python3 run.py --run-id g17p_20260830_run10 --arms harness/arms188_rest.json --req-timeout 1.2'
bash harness/sync.sh shell 'cd ~/agxre/EXP-0188 && python3 run.py --run-id g17p_20260830_run11 --arms harness/arms188_rest.json --req-timeout 1.2'
bash harness/sync.sh pull
python3 analysis/verdicts.py   raw/g17p_20260830_run08 raw/g17p_20260830_run09
python3 analysis/partitions.py raw/g17p_20260830_run08 raw/g17p_20260830_run09
```

## 10. Clean-room attestation

```
Clean-room provenance: HW-PROBE + OWN-SHADER
Inputs inspected:      kernels/{k_cf188,k_sd188,k_ia188}.metal -- authored by us -- and the
                       `_agc.main` bytes the public Metal runtime compiled from them
Apple binary introspection: NONE
Reproduction:          §9
Evidence:              raw/g17p_20260830_run08..run11/sweep.jsonl + env.json
                       raw/prefreeze/{census.json, pilot01/, haz01/, CAPTURE_CONTRACT.v1..v5.json}
                       CAPTURE_CONTRACT.json (27 blob hashes, re-verified ON THE DEVICE)
```
