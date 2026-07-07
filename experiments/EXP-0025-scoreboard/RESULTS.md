# EXP-0025 RESULTS — scoreboard / async-wait model on G17P

**All findings HW-validated unless marked (inferred).** Method: OWN-SHADER extract + tokenize + splice-and-run.

## Headline
**G17P compute has NO explicit per-op scoreboard `wait` instruction.** Device load/store, atomics and
texture sample/read feed their consumers *directly*; async completion is enforced by a **hardware register
interlock** (a consumer reading a still-pending destination register stalls in HW until the op retires).
This is a fundamental departure from G13 (Mesa `agx_insert_waits.c`: an explicit 2-byte `wait` op + a
2-slot software scoreboard, `AGX_MAX_PENDING=8`). The **only** explicit ordering op the compute compiler
emits is the **threadgroup / execution barrier** (`byte0 0x07`, 6 B), for cross-lane threadgroup-memory
visibility that a per-lane register interlock cannot cover.

## 1. Which ops are async — is there a wait op between the async op and its consumer? → NO
Tokenized `_agc.main` for a full battery. In every case the consumer immediately follows the async op with
**no wait/barrier instruction** between them:

| kernel | pattern | stream (elided) | wait op? |
|---|---|---|---|
| `copy` | `out=a[i]` | get_sr · **load** · **store** · stop | none |
| `add2` | `out=a[i]+b[i]` | get_sr · load · load · **fadd** · store · stop | none |
| `loaduse` | `out=v*v+3` | get_sr · load · **fma** · store · stop | none |
| `loadfar` | load, long indep chain, use at end | get_sr · load · cvt · 4×fma · **fadd(uses load)** · store | none |
| `gather` | `out=a[idx[i]]` (**dependent** load) | get_sr · load(idx) · **load(a[idx])** · store | none |
| `chain` | 3× pointer-chase (dependent) | get_sr · load · **and** · load · and · load · store | none |
| `manyload` | 10 independent loads → sum | get_sr · 10×load · reduce · store | none |
| `sampleuse` | `tex.sample()` then `.x+.y` | get_sr… · **tex_sample** · mov · **fadd** · store | none |
| `atomicuse` | `atomic_fetch_add` then `+7` | …simd_reduce · **atomic_rmw** · shuffle · **iadd** · store | none |

**Proof of the HW interlock** (immediate consume, zero slack, correct output ⇒ HW must interlock):
`add2`=11,22,33,44 · `gather`(dependent)=13,11,12,10 · `loaduse`=7,12,19,28 (`raw/interlock_proofs.txt`).

## 2. Slot-assign field / wait-mask / how many slots / max in-flight
- There is **no slot-assign field** on the async ops and **no wait-mask field** anywhere — because there is
  no wait op. (Suspect load bytes `byte+1`/`byte+2 bit4` that differ between consecutive loads are addressing
  mode, not a scoreboard slot; splicing them does not produce stale reads.)
- **No compiler `AGX_MAX_PENDING` analog.** `manyload20` keeps **20 independent device loads outstanding**
  and sums them correctly with **zero** wait ops → **RESULT 1048575** (=2²⁰−1). 20 ≫ G13's 8, so max-in-flight
  is a **hardware** resource (bounded by the 96-GPR register file), not a compiler-emitted constant/slot count.
- **Disproved wait candidate:** `09 01 38 XX` (4 B) looked like the G13 `wait` (byte0 `0x38`). It is a **compact
  float ADD** (`falu_acc`): in the 10-value sum the stream has 6 six-byte `0x3c`/`0x1c` fadds + 3 of these =
  9 adds (exactly N−1); a byte+3 sweep changes the *arithmetic* sum by the referenced register's value
  (byte+3 = a data source), which a wait mask never would. See `raw/interlock_proofs.txt`.

## 3. Ordering / batching rules; separate scoreboards?
- **Device RAW hazards:** no compiler action — HW register interlock. The compiler batches async ops freely
  (10, 20 in flight) and schedules independent work between an op and its use (`loadfar`) to hide latency.
- **No separate tex vs mem vs global scoreboards visible** — none are exposed in the instruction stream (the
  interlock is per-register, keyed on the destination register number, uniform across load/atomic/texture).
- **Cross-lane threadgroup-memory ordering IS explicit:** the `threadgroup_barrier` op.
  `simdgroup_barrier` emits **no** op (a 32-lane SIMD-group is lockstep).

## 4. The wait/barrier instruction that DOES exist — encoding + splice-proven danger
Differential compile (`raw/mains.txt`): `tgbar` vs `tgbar_none` differ by **exactly 6 bytes** — the barrier.

```
threadgroup_barrier   07 04 54 <mem_scope> <flags> 00        (byte0 0x07, 6 bytes)
  byte+3 mem_scope :  0x61 = threadgroup (mem_threadgroup)   [tgbar]
                      0x85 = device      (mem_device)        [tgbar_dev]
  byte+4 flags     :  0x09 (threadgroup) / 0x08 (device)     (not the fence-critical bit)
```
`tgbar_dev` (mem_device) only changes byte+3 `0x61→0x85` and byte+4 `0x09→0x08` ⇒ **byte+3 is the fenced
memory-scope field**.

**Splice-proven stale read (silent corruption).** Kernel `tgdiv2` (256 threads, per-lane variable-length
LCG write delay so lane 0 — fastest — reads `scratch[255]` written by lane 255 — slowest; `a[i]=i`):

| version / splice | STATUS | stale-zero reads / 256 | result |
|---|---|---|---|
| `tgdiv2` barrier intact (baseline) | OK | **0** | correct LCG values |
| `tgdiv2_none` (barrier removed in source) | OK | **128** | out[0..127]=0 |
| splice barrier `byte+3 0x61→0x00` | OK | **128** | out[0..127]=0 (fence neutralised) |
| splice barrier `byte+4 0x09→0x00` | OK | 0 | benign |

Splicing the barrier's fence-scope byte from `0x61` to `0x00` **silently corrupts 128/256 lanes** (they read
stale zeros — no fault, STATUS OK), exactly reproducing the compiler's barrier-less race. The intact barrier
reads 0 stale. This proves the `0x07` op is the load-bearing threadgroup-memory ordering primitive and that
`byte+3` is its fence field. (`raw/splice_barrier.txt`, `raw/div2_*`.)

## 5. Round-trip / faults / next
- `tools/agx-isa` updated: `threadgroup_barrier` (0x07, 6 B, `mem_scope` enum) + `falu_acc` (compact fadd) +
  length rules + `db.json` `scoreboard_model`. **`roundtrip_test.py` ALL PASS** (40 descriptors, 35 HW-validated;
  `manyload10` tokenizes as 22 instrs with 0 leftover).
- **Faults/reboots:** none. Every splice was a contained per-command-buffer run (STATUS OK throughout); no GPU
  wedge, no reboot. All corruption was *silent* (STATUS OK + wrong data), which is precisely the G-1 hazard.
- **Recommended next:** (a) fragment/tilebuffer async waits (`wait_pix`/`signal_pix` analogue) — this run is
  compute-only; (b) barrier byte+1/byte+5 sub-op space (execution-only vs memory-only fence, `mem_none`);
  (c) confirm a cross-threadgroup device memory fence needs no op beyond the barrier's device-scope variant.

## Implications for the acceptance gate (G-1)
The classic G13 "forgot a `wait` → silent stale read" **cannot occur for device RAW on G17P** (there is no
software wait to omit; HW interlocks). A driver author must know: **do not** try to emit G13-style scoreboard
waits/slots (they don't exist here), **do** emit the `0x07` barrier for threadgroup-memory ordering — omitting
it is the one remaining silent-corruption surface, splice-proven above.
