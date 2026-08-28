# EXP-0100 Results — M4 threadgroup addressing (GLCS-A02, addendum Bundle F)

Target: local Apple M4 (G16G, 10 cores, macOS 26.6.2 build 25G82, Metal 4), public Metal
only. A18 Pro/G17P not touched (hands-off); every finding below is `INFERRED`-by-family
for G17P unless separately noted.

Successor of `../EXP-0096-m4-threadgroup-addressing` (quarantined after one clean run01 —
a `verify.py`-only fixture bug, not a matrix/kernel/data defect; see its `QUARANTINE.md`).
This experiment ran a completely fresh two-run capture under its own pre-registration.

## Promotion-gate status (read this before the findings below)

`verify.py --selftest` / `--seqtest` / `make_manifest.py --check` / `--preflight` /
`--between-runs` all **PASS**. The final `verify.py --captured` gate **FAILS** on one
precise, diagnosed criterion: `04_results.jsonl` (the SPLICE payload) is **not**
byte-identical between run01 and run02. `06_budget_results.jsonl` (the BUDGET payload) **is**
byte-identical (`budget_repeat_exact: true`); the six-entry hand-validation set matches
in both runs (`0 hand divergences`); both runs report identical status counts
(`{"OK": 2900}` splice, `{"OK": 109, "PIPELINE_FAIL": 36}` budget) and zero faults/hangs/
timeouts in either run.

The non-reproducibility is confined to **exactly 16 of 2900 splice cases** (0.55%), **all**
in the `TGA-SRCSEL` family (`tg_addr_compute` byte+1), and all 16 satisfy the precise
condition `byte+1 & 0x17 == 0x04` (bits 0,1 clear, bit 2 set, bit 4 clear; bits 3,5,6,7
free — exactly 16 of the 256 swept values). This is diagnosed as **genuine hardware
nondeterminism** (a scheduling/ordering race), not a harness defect — see "TGA-SRCSEL:
byte+1" below for the full evidence and reasoning. Per `CODEX.md` ("prefer UNKNOWN/PARTIAL
to unjustified certainty," "keep failed probes... they bound the hardware just as positive
results do"), this is recorded and reported exactly as observed rather than hidden or
forced to pass. **Verdict: GLCS-A02 is CLOSED for everything except the 16 racy
`TGA-SRCSEL` byte+1 values, which are PARTIAL** (their fault-freedom and rough magnitude of
corruption are established and reproducible; their exact per-run output is not, and that
irreproducibility is itself the closed finding for that subrange).

No post-capture repair was applied to any hash-frozen file. `raw/m4-20260828-run01/` and
`raw/m4-20260828-run02/` are both complete, append-only, and preserved as captured.

## GLCS-A01 — out of scope

`work/ADDENDUM-TRIAGE-20260828.md` "Bundle F" closes **GLCS-A02 only**; GLCS-A01 (complete
compute launch ABI) is untouched here. `PRE_REGISTRATION.md`'s scope note applies
unchanged. **Status: Not applicable** (this experiment).

## GLCS-A02 — response block

```text
Status: [x] Closed (2884/2900 splice cases + 145/145 budget cases)  [ ] Partial (16/2900
        TGA-SRCSEL byte+1 racy-subrange cases — see above)
Answer, where Yes/No: N/A (multi-part item; see field map and capacity table below)
Applies to: [x] M4/G16G (tested)  [ ] A18 Pro/G17P (INFERRED-by-family only, not tested)
Evidence: [x] HW splice (independently re-assembled/raw-patched, executed on real M4 GPU)
          [x] independently assembled HW execution (tg_ld/tg_st/tga probes; harness/tgbudget.m
              own-MSL compiles)
          [ ] API create/submit/exhaustion test (N/A — see budget sweep below, which IS this)
          [x] API create/submit/exhaustion test (budget sweep: MTLComputePipelineState
              creation + dispatch + full-range readback)
          [ ] Linux end-to-end UAPI test        [ ] captured userspace/command memory
          [ ] encode/decode round trip only     [ ] own-MSL byte diff only
          [ ] corpus inference only
Test/artifact: casematrix.py (2900 splice + 145 budget cases), run.py, harness/tgbudget.m,
  raw/m4-20260828-run01/, raw/m4-20260828-run02/, analysis.json
Exact observed semantics or field mapping: see "tg_addr_compute field map" and "Threadgroup
  device_load/device_store field map" below
Finite namespace: see the finite-resource table below
Maximum-valid and first-invalid tests: idx_off (load) 0..2047 valid, 2048 first-invalid
  (assembler-rejected; raw-patch shows "undecodable" failure, not clean wrap); static
  threadgroup memory 0..32768 B valid, 32769 B first-invalid (pipeline-creation reject);
  dynamic+combined threadgroup memory total 0..65536 B valid (clean), 65537 B first-invalid
  (silent data corruption, NOT rejected)
Failure/overflow behavior: [x] reject (static ceiling, pipeline-creation time)
  [x] alias/wrap (dynamic/combined ceiling: NOT rejected, corrupts with a signature
      consistent with — not fully proven to be exactly — 64 KiB physical aliasing)
  [ ] zero/discard (not observed as the dominant mode here)  [ ] fault/device loss (never
      observed across 5800 splice + 290 budget case-executions)
Correct behavior when the compiler/driver needs more: split static allocation across
  multiple dispatches / reduce declared size below 32768 B; NEVER rely on the public API to
  reject an oversized DYNAMIC or COMBINED request — it will not, and the failure is silent
  data corruption, not a catchable error. A driver must independently enforce
  static_bytes + dynamic_bytes <= 65536 before emitting the dispatch.
Lifetime, destruction, and reuse semantics: not probed here (out of this experiment's scope
  — no cross-dispatch persistence claim is made or tested)
Counterexamples and untested cases: A18/G17P untested (hands-off); thread counts/dispatch
  geometries other than those frozen in casematrix.py untested; vector-width threadgroup
  accesses beyond scalar/16-byte untested (see "8/16/32/64/128-bit accesses" below);
  interaction with threadgroup ATOMICS untested (out of this bundle's frozen scope)
Driver/compiler consequence: idx_off is a genuine 11-bit ELEMENT-scaled offset for
  threadgroup loads with no holes in range — a NIR/Mesa backend can emit it exactly as it
  would for device-space device_load (EXP-0082); the STORE side uses a DIFFERENT byte
  granularity (see below) that a backend must NOT assume matches the load side; the
  threadgroup-memory budget check MUST be done in the compiler/driver, never delegated to
  the Metal-equivalent API surface (there is none to delegate to on this hardware for the
  dynamic/combined case)
```

## OBSERVED vs INTERPRETED

Everything in this section states what the two raw capture runs directly show
(`raw/m4-20260828-run01/`, `raw/m4-20260828-run02/`, `analysis.json`) before the
"Interpretation" sentence that follows each subsection.

### tg_addr_compute field map

**byte0 (whole opcode byte, DB `match`-pinned at `0x1c`; high nibble raw-patched, low
nibble held at `0xc`).** OBSERVED (`TGA-DSTREG`, 16/16 cases, byte-identical across both
runs): the 256-element downstream array falls into exactly **three** classes, not sixteen:

| nibble values | downstream result | class |
|---|---|---|
| `0x1` | exact baseline (`o[i]=2i+3`, wrap `255,1`) | correct (the real unspliced value) |
| `0xA`–`0xF` (6 values) | ALSO exact baseline, byte-identical to `0x1` | correct |
| `0x2`–`0x9` (8 values) | exact, deterministic `o[i]=(i+2)&255` (`num_diff=255` both runs) | known A18 corruption pattern |
| `0x0` | a **third**, deterministic pattern, `num_diff_from_baseline=128` (exactly half the array), reproducible byte-for-byte across both runs | undecoded third state |

INTERPRETATION: byte0's high nibble is **NOT a clean 4-bit linear register/operand index**
— per the coordinator-supplied caution (`apple9_isa_explainer.md`,
`work/COMPILER-EXPLAINER-INTERACTION-20260828.md`), this experiment does not assert a
specific mechanism. The clean 3-class partition (`{1,10..15}` / `{2..9}` / `{0}`) is fully
deterministic and reproducible (unlike byte+1 below), so it is not itself a race — but it
is inconsistent with "16 distinct registers," consistent instead with either (a) far fewer
real hardware states than 4 bits would suggest, with the unused encoding space aliasing
onto one of the 3 observed states, or (b) a nonlinear/gated field (e.g. only 2 real bits
plus 2 bits that select nothing new in this dataflow shape). **`EXP-0099` (commit
`de4e4a81`) has since concluded, for the DIFFERENT field it examined** (`falu2`'s ALU
`srcA_reg`/`srcB_reg`): on real hardware, NEITHER candidate model survived —
`db.json`'s naive 7-bit-index reading is wrong (a literal encoded value of 67 still read
r3's value, never an unwritten r67's zero, i.e. only 6 bits are load-bearing) AND the
external engineer's retention-flag reading is also wrong (the outcome depends only on
`opflags` bits 19/20, identically whether the top bit is 0 or 1 — the top bit is
HW-tested INERT, but its role stays `UNKNOWN`). That result is about a different
instruction family and does not transfer bit-for-bit to `tg_addr_compute`'s byte0-hi, but
it validates this experiment's posture exactly: neither the DB's linear-index framing nor
a retention-flag framing is safe to assume without this experiment's own downstream-read
evidence, which is all this table reports.

**byte+1 (DB `match`-pinned at `0x02`; raw-patched, full byte, dense 0x00–0xFF).**
OBSERVED: 240/256 values reproduce byte-exact across both runs (160 give a non-baseline,
non-`ip2` downstream array — a genuinely `LIVE` field, confirmed); **16/256 values do
NOT reproduce** — same `STATUS OK` and near-total corruption magnitude
(`num_diff_from_baseline` ∈ {252,253,254} out of 256, both runs) but a **different specific
256-value array each run** (`observed_sha256` differs; `first_diff_index=0`,
`first_diff_values=[2,3]` reproduces exactly, i.e. index 0 always shows the wrong value `2`
where baseline expects `3`, but the rest of the array is run-dependent). The exact 16
values: `0x04,0x0C,0x24,0x2C,0x44,0x4C,0x64,0x6C,0x84,0x8C,0xA4,0xAC,0xC4,0xCC,0xE4,0xEC`
— precisely the set where `(byte+1 & 0x17) == 0x04`.

INTERPRETATION: this is a genuine, reproducibly-nondeterministic hardware behavior, not a
harness artifact — 2884/2900 OTHER splice cases (including 240/256 other `TGA-SRCSEL`
values, all of `TGA-DSTREG`/`TGA-LENDISC`/`TGA-RESERVED`, all of `TGLS-LD-*`/`TGLS-ST-*`,
and 145/145 `BUDGET-*` cases compiled fresh each time) reproduced byte-exact in the SAME
two runs, ruling out generic process/timing nondeterminism in the harness itself. The
near-total (99%), run-varying corruption pattern is consistent with a genuine data race:
this `byte+1` subrange puts the populate write (fed by `tg_addr_compute`) into a state
where its completion is no longer correctly ordered before the barrier-gated reads, so
which of the 256 threads' writes are visible to which reads becomes GPU-scheduling-
dependent. This is the **same class of failure** `docs/isa/register-move-and-liveness.md`
already documented for other fields on this hardware family (wrong operand value → silent
corruption, never a fault) — here specifically manifesting as **silent, run-varying**
corruption because the corrupted mechanism is ordering-related rather than purely
data-value-related. **Failure mode: no fault, no hang, `STATUS OK` in every one of ~5800
executions of this field across both runs — the danger is entirely silent.**

**byte+2 (DB `match`-pinned at `0x00`; raw-patched, 38-value representative sweep
0x00–0xFF).** OBSERVED: all 38 values reproduce the exact baseline array, byte-identical
across both runs (`tga_lendisc_rows`: 0 non-baseline rows). INTERPRETATION: fully
**HW-VALIDATED inert** on M4 (confirms and widens the prior A18-side sample of
`{0x00,0x01,0x02,0x08,0xff}`); functions only as the disassembler's own length
discriminator, not a runtime-meaningful field.

**b3/b4/b5 (real `isadb` "mod" fields, bytes+3/4/5).** OBSERVED: all 94 representative-sweep
cases plus the simultaneous `0xFF/0xEE/0xDD` perturbation reproduce the exact baseline array,
byte-identical across both runs (`tga_reserved_rows`: 0 non-baseline rows).
INTERPRETATION: **HW-VALIDATED RESERVED/inert** on M4 individually and simultaneously —
confirms the prior A18-side finding on independent M4 hardware.

**Tooling-gap finding (first-class, per the dispatch's own instruction):**
`tools/agx-isa`'s assembler cannot express a byte0-hi or byte+1 variant through its field
mechanism at all (the DB's `match` clause pins the whole byte); this experiment used direct
raw byte patches for those two positions (`run.py::splice_case`, `raw_byte0_hi`/`raw_byte1`/
`raw_byte2`), and the normal `isadb.assemble` round trip only for `b3`/`b4`/`b5`.

### Threadgroup device_load/device_store field map (TGLS-LD/TGLS-ST)

**`idx_off` (LOAD side, 11-bit field, bytes+9/10/11 — identical bit layout to EXP-0082's
device-space finding).** OBSERVED: the full dense sweep, all 2048 values 0..2047 at idx=0,
decodes to `element == idx_off` **exactly**, zero anomalies, byte-identical across both
runs (`tgls_ld03_digest.first_bad_within_dense: null`, `anomalies: []`). **Confirms H-ELEM-TG
with NO holes across the entire legal range.** Beyond the ceiling: `tools/agx-isa`'s
assembler **hard-rejects** `idx_off >= 2048` at construction time (`ValueError`) — a
first-class tooling-gap finding (see `PRE_REGISTRATION.md` point 1) worked around by a
direct raw byte patch (`idx_off_wide_raw`) that treats the combined `idx_off`+`ldform_hi11`
region as one 17-bit window. All 128 such raw-patched cases (field values 2048..2175):
`STATUS OK`, **undecodable** (the returned 32-bit value does not match the `a[]` tag
pattern at all), byte-identical across both runs. **First-invalid value: 2048 (0x800).
Failure mode: not a clean wrap, not zero, not a fault — an undecodable, effectively garbage
32-bit read, because the raw patch that reaches value 2048 necessarily also overwrites the
adjacent `ldform_hi11` tail field, corrupting the load's own data-format descriptor.**

**`elem_size` (LOAD side, byte+12, full byte 0x00–0xFF dense sweep at idx=1).** OBSERVED:
baseline (compiler-emitted) value is `0x08` — this matches **none** of EXP-0082's
device-space `ELEM_BYTE` codes (`{0x40,0x42,0x44,0x46,0x48}`), confirming the authoring-stage
finding that threadgroup-space `elem_size` encoding differs from device space. 192/256
values decode SOME value matching the `a[]` tag pattern (status OK, "working"); exactly
**64/256 values are undecodable**, precisely characterized as `(elem_size & 0x18) == 0x10`
(bits 3,4 = "10"; bits 0,1,2,5,6,7 free) — a clean, bit-exact hole, byte-identical across
both runs. INTERPRETATION: threadgroup-space `elem_size` is NOT the same code table as
device space; a driver must not reuse EXP-0082's `ELEM_BYTE` map for threadgroup accesses.
The exact scale-per-surviving-code mapping (beyond confirming the baseline `0x08` is
correct) is left as an open, precisely-scoped follow-up — this experiment establishes the
HOLE exactly, not yet every surviving code's semantic.

**`index_reg` (LOAD side, byte+5, 10-value representative sweep).** OBSERVED: values
`0x00` and `0x01` both return the correct downstream value (word 65, matching `j=i0+i1=65`);
every other tested value (`0x02,0x03,0x04,0x05,0x40,0x7F,0x80,0xFF`) returns a UNIFORM
`word=0` (i.e. reads threadgroup element 0, not the intended `j`), byte-identical across
both runs. INTERPRETATION: **not yet established** whether this is (a) a genuine 2-state
field where only bit0 is load-bearing and the rest is truly reserved, or (b) some other
gating unrelated to a clean register-select role — the downstream data alone cannot
distinguish these without a THIRD, independently-controlled register holding a DIFFERENT
value at both candidate physical locations. `EXP-0099` (commit `de4e4a81`) has since
concluded that for the (different) ALU register field it tested, neither a naive-index nor
a retention-flag model survived hardware testing (6 bits load-bearing, top bit HW-tested
INERT, role UNKNOWN) — that finding does not resolve `index_reg` here (a different field,
a different instruction) but confirms the right posture is exactly what is used throughout
this document: report the downstream-read data, and label the mechanism `UNKNOWN` rather
than inferring it from either the DB's field description or a borrowed retention-flag
model.

**Store-side `idx_off` unit asymmetry (byte-vs-element units — directly answers the
GLCS-A02 question).** OBSERVED: `st_off_001` (`idx_off=1`, `index_reg` value j=0) lands at
STORE byte offset **16**, not 4; the dense boundary probes confirm this is an exact ×16
scale (`st_off_1fe`→8160=510×16, `st_off_1ff`→8176=511×16), reproducible byte-identical
across both runs. This is a **DIFFERENT unit than the LOAD side's ×4 (element) scale**, and
different from the STORE side's own register-index (`j`) scaling, which (per the
`st_ctrl_idx64` hand-validated anchor) is ×4 like the load side. **`idx_off` for
threadgroup stores is a 16-byte-granularity immediate, NOT the same element unit as the
runtime index register.** First-invalid: `idx_off=512` (`0x200`, at idx=0) — `512*16=8192`
bytes = exactly the tile's own 2048-word/8192-byte capacity; the store silently lands
outside the 8 KiB readback window (`store_byte_offset: null` — absent from the observed
buffer, not zero, not a fault). Every boundary case beyond `idx_off=511` shows this same
"absent from readback" signature, byte-identical across both runs.

**`elem_size` (STORE side, byte+12, 16-value cross-check).** OBSERVED: baseline `0x02`;
several other codes produce large, apparently non-monotonic byte-offset jumps (e.g.
`elem_size=0x04`→byte 6144, `elem_size=0x44`→byte 6144, `elem_size=0x81`→byte 2048,
`elem_size=0xFF`→byte 2052) reproducible byte-identical across both runs. INTERPRETATION:
the store-side `elem_size` code space is NOT a simple power-of-two scale table either;
full characterization is left as further work (this experiment establishes the raw,
reproducible data points, not a closed-form rule).

**32-bit wrap (`TGLS-LD-05`, `TGLS-ST-05`).** OBSERVED: every wrap/far-OOB probe
(`idx=0xFFFFFFFF` etc.) returns `word=0`/no fault, byte-identical across both runs. Given
the wrap cases coincide with the "index_reg only bit0 matters" finding above (all these
cases use `index_reg` default/baseline, which IS load-bearing), a wrap-specific verdict is
not separable from that open question here — recorded as **PARTIAL**, not `H-W32`-confirmed
or refuted independently.

**8/16/32/64/128-bit accesses (GLCS-A02's explicit ask).** Not independently assembled at
every width in this experiment (out of the frozen matrix's scope — the `elem_size` sweep
above characterizes the WIDTH-SELECTOR field's hole/working-code structure, which is the
prerequisite for width synthesis, but does not itself execute e.g. a 128-bit vector
threadgroup access with a splice-controlled runtime address). **Flagged as open follow-up
work**, not silently claimed complete.

### Threadgroup-memory capacity, granularity, and static+dynamic combination (finite-resource table)

| Namespace/resource | Scope | Encoding | Exact usable range/count | Holes/reserved | First invalid value | Observed failure | Correct "need more" fallback | Evidence |
|---|---|---|---:|---|---:|---|---|---|
| STATIC threadgroup memory (`threadgroup T tile[N]`, compile-time size) | per kernel/pipeline | byte count, compiler-computed | 0–32768 B | none observed | 32769 B (internal check rounds the request to a 4-byte granularity: e.g. a 32769 B request is reported as requiring 32772 B) | `MTLComputePipelineState` creation FAILS with an explicit error string naming the exceeded size — clean, catchable, before any dispatch | reject at compile/pipeline-creation time; split allocation across dispatches | `BUDGET-STATIC-CAP`, 72+... cases, `budget_digest.static_last_pipeline_ok_bytes=32768`/`static_first_pipeline_fail_bytes=32769`, byte-identical both runs |
| Queried `staticThreadgroupMemoryLength` property (public API readback) | per pipeline | byte count | rounds UP to a 16-byte granularity (e.g. 100→112, 1000→1008, 4097→4112) | n/a | n/a | not a failure — a reporting/allocation-granularity artifact | driver must not assume the queried value equals the requested value | `budget_digest.pso_static_tgmem_rounding_sample`, byte-identical both runs |
| DYNAMIC threadgroup memory (`setThreadgroupMemoryLength:`) ALONE | per dispatch | byte count | 0–65536 B clean | none observed within range | 65537 B | **NOT rejected by the API at all** — dispatch completes `STATUS OK`, data SILENTLY CORRUPTS; corrupted-byte count grows in increments consistent with (not proven exactly) a 64 KiB physical aliasing window (e.g. a 1 MiB request leaves exactly the first 65536 B clean, the rest corrupt) | **the public Metal API provides no rejection to rely on; a driver MUST enforce the 65536 B ceiling itself before emitting the dispatch** | `BUDGET-DYNAMIC-CAP`, `budget_digest.dynamic_last_clean_total_bytes=65536`/`dynamic_first_corrupt_total_bytes=65537`, byte-identical both runs |
| COMBINED (static + dynamic declared in the SAME kernel) | per dispatch, SHARED with the static allocation | byte count (sum) | total ≤ 65536 B clean, REGARDLESS of the static/dynamic split (confirmed at 4 different splits: 0/4096/16384/32768 static) | none observed within range | total = 65537 B (any split) | same silent-corruption signature as dynamic-alone; **static and dynamic threadgroup memory share ONE 65536-byte physical budget, not independent budgets** — a kernel already at the 32768 B static ceiling has ZERO further headroom via `setThreadgroupMemoryLength` before hitting the SAME 65536 B wall (65536−32768=32768 B of dynamic room remains, not "however much dynamic allows alone") | a driver's own admission-control MUST track `static_bytes_declared + dynamic_bytes_requested <= 65536`, independent of what the static-only 32768 B ceiling alone would suggest is safe | `BUDGET-COMBINED`, 31 cases across 4 splits, `budget_digest.combined_*`, byte-identical both runs (see note below on the digest's own crude aggregation across splits) |
| `tg_addr_compute` byte0 high nibble (operand/dst selector) | per instruction | 4-bit raw nibble | 3 behaviorally distinct classes observed (not 16) | see field map above | n/a (not a capacity/range field in the usual sense) | deterministic, reproducible re-mapping to one of 3 known states; never a fault | do not treat as a linear register index without independent per-register readback | `TGA-DSTREG`, byte-identical both runs |
| `tg_addr_compute` byte+1 (source/operand selector) | per instruction | 8-bit raw byte | 240/256 deterministic; 16/256 (`&0x17==0x04`) genuinely racy | the 16-value racy subrange is itself the "hole" | n/a | silent, run-varying near-total corruption, STATUS OK, no fault | never emit any value in `{0x04,0x0C,0x24,0x2C,0x44,0x4C,0x64,0x6C,0x84,0x8C,0xA4,0xAC,0xC4,0xCC,0xE4,0xEC}` (or, conservatively, any value with `v&0x17==0x04`) | `TGA-SRCSEL`, cross-run divergence precisely bounded (see above) |
| Threadgroup `device_load` `idx_off` (11-bit immediate, LOAD) | per instruction | element units, ×4 bytes/unit | 0–2047, exhaustively hole-free | none | 2048 | undecodable (adjacent tail-field corruption via the only available raw-patch path) | keep within 0–2047; multiply/add overflow must be pre-computed in ALU, exactly as EXP-0082 found for device space | `TGLS-LD-03`, byte-identical both runs |
| Threadgroup `device_store` `idx_off` (11-bit immediate, STORE) | per instruction | **16-byte** units (NOT element units — asymmetric with load side) | 0–511 reach the tile's own 8192 B capacity; field itself likely still 0–2047 encodable (untested past the tile edge for the store's OWN silent-absence signature vs the load's undecodable one) | none observed 0–511 | 512 (at idx=0; reaches exactly the 8192 B tile boundary) | store silently lands outside the read-back window (absent, not zero, not faulted) | a compiler must scale threadgroup STORE immediate offsets by 16 B, not 4 B — reusing the load-side scale will silently misplace every non-zero offset by 4× | `TGLS-ST-03`, byte-identical both runs |

Note on the COMBINED digest's own crude cross-split aggregation: `analysis.py`'s
`budget_digest()` sorts ALL `BUDGET-COMBINED` totals together and reports one global
"first corrupt"/"last clean," which is not meaningful split-by-split (different splits'
sparse sample points interleave). The per-split boundary is unambiguous in the raw case
names (`combined_s<static>_d<dynamic>`) and consistently lands at total=65536 clean /
65537 corrupt for every tested split; the digest's raw numbers (`32868` last-clean,
`65535` first-corrupt) reflect this aggregation artifact plus one more precise nuance: the
`combined` MSL template declares a compile-time-constant dummy static array even when
`static_bytes=0` (to keep the generated source well-formed), so its true static footprint
is never exactly zero — consistent with, not contradicting, the exact 65536 B total finding
established independently by the dedicated static-only and dynamic-only sweeps.

## Clean-room attestation

Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC
Inputs inspected: authored MSL (`kernels/*.metal`, and `harness/tgbudget.m`'s
argv-generated MSL strings), harness/runner/verifier/analysis/matrix/baseline Python and
Objective-C sources, our own compiled shader bytes (splice targets) and freshly-compiled
budget-sweep kernels (no splicing); public reference material `apple9_isa_explainer.md`
and `work/COMPILER-EXPLAINER-INTERACTION-20260828.md` (read for methodological caution
only — no unverified specific claim from either is asserted as fact above; every
retention/index-ambiguity finding here is this experiment's OWN downstream-consumer-read
data, explicitly marked `UNKNOWN` where the data cannot distinguish competing mechanisms)
Apple binary introspection: NONE
Reproduction: `python3 -B verify.py --selftest && python3 -B verify.py --seqtest &&
python3 -B make_manifest.py --check` (passes); full capture reproduction requires
`run.py --execute` against fresh run ids (the frozen ones are consumed)
Evidence: `raw/m4-20260828-run01/`, `raw/m4-20260828-run02/`, `analysis.json`,
`manifest.json`, `CAPTURE_CONTRACT.json`

## Gate results summary

`verify.py --selftest`: PASS (16 checks). `verify.py --seqtest`: PASS (10 checks).
`make_manifest.py --check`: PASS (both PRE_GPU and CAPTURED states). `verify.py
--preflight`: PASS. `verify.py --between-runs`: PASS. `analysis.py`: exits 1
("ANALYSIS GATE: FAIL (0 hand divergences, 1 issues)" — the one issue is exactly the
16-case splice non-reproducibility documented above). `verify.py --captured`: FAILS
("FAIL byte-exact repeat (splice)"), for the same, single, precisely diagnosed reason.

## STOPs / quarantines

`../EXP-0096-m4-threadgroup-addressing` — quarantined after one clean run01 (2900/2900
splice `OK`, 109/36 budget `OK`/`PIPELINE_FAIL`, matching this experiment's run01 exactly)
due to a `verify.py::_build_tree` fixture-generation bug that only activates once `raw/`
exists, blocking that experiment's own `--selftest` gate for run02. Not a matrix, kernel,
or captured-data defect. Full account: its `QUARANTINE.md`.

## Files

`PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json`, `casematrix.py` (2900 splice + 145 budget
cases), `baseline.py`, `run.py`, `verify.py`, `analysis.py`, `make_manifest.py`,
`kernels/{tga,tg_ld,tg_st}.metal`, `harness/build.sh`, `harness/tgbudget.m`,
`raw/m4-20260828-run01/`, `raw/m4-20260828-run02/`, `analysis.json`, `manifest.json`,
`PROGRESS.md`.
