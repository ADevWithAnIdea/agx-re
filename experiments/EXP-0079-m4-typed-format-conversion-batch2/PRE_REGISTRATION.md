# EXP-0079 pre-registration — M4 public typed-format conversion, batch 2

**Frozen state: PRE-GPU.** EXP-0079 is the named successor to quarantined
EXP-0075 (`experiments/EXP-0075-m4-typed-format-conversion-batch2/QUARANTINE.md`).
EXP-0075's run01 capture (`raw/m4-20260827-run01/`) is **retained, verified,
single-run process history** — it captured 34/34 cases clean with zero
truncation and every guard byte intact — but it is **not treated as evidence
here**: no expected value in this registration is copied from EXP-0075's
*observations*. Where EXP-0075 disclosed a registration slip (arithmetic
error in the frozen expectation itself, independent of what the hardware
returned), this registration corrects the slip. Where EXP-0075 observed a
result that *contradicted* its own registered expectation, that observation
is carried forward only as a **named, falsifiable hypothesis** (H1, H2 below)
with its own predicted value spelled out — never as the new expectation. This
distinction is the entire point of a re-registration: EXP-0075 was a single,
uncorroborated run, and this experiment exists to independently confirm or
refute it, not to rubber-stamp it.

Third bounded increment of task-list item **DRV-FMT-01** (per-format
capability and conversion table) in `APPLE9_RE_IMPLEMENTATION_GAPS.md`
(P1.2), succeeding EXP-0070 (batch 1, six formats, fragment-store path) and
the quarantined EXP-0075 registration (batch 2, fourteen formats,
compute-store path, run01-only).

## Why EXP-0075 was quarantined, and the two structural fixes this experiment makes

EXP-0075's harness (`harness/probe.m`, carried over here **byte-identical**)
and its non-recorded pre-capture smoke gate (`run.py`'s `smoke_gate()`,
carried over here **unchanged in design**) both worked exactly as designed:
run01 captured 34/34 untruncated records, and the smoke gate caught a real
pre-capture defect (a dropped MSL `#include`) on its first invocation before
any GPU work. The quarantine cause was purely a **verifier gate-sequencing
bug**: EXP-0075's `verify.py --selftest` had a hardcoded PRE_GPU-only
precondition (`req(not (HERE / "raw").exists(), ...)`, and separately called
`static()` with a hardcoded `capture=False`), while its own frozen
`CAPTURE_CONTRACT.json` `pre_second_run_gate` contracted `--selftest` to run
**after** `--between-runs`, i.e. with `raw/run01` already present. No
execution could satisfy both constraints at once, so run02 was structurally
unreachable and no DRV-FMT-01 claim could be promoted.

Two structural fixes, made once, up front, in `verify.py`:

1. **`--selftest` is now state-agnostic.** It reads the tree's actual
   capture state (`raw/` present or not) and validates the closed-root/
   contract-static invariants for *that* state, instead of assuming
   PRE_GPU. Its synthetic schema self-test never reads or depends on the
   real `raw/` tree in the first place (it only calls `run.py`'s pure
   builders and constructs in-memory records), so nothing about making it
   runnable post-capture weakens what it proves.
2. **A new `verify.py --seqtest` gate-sequence state machine.** It builds
   three isolated, non-mutating fixture trees under `work/seqtest-<state>/`
   (`PRE_GPU`, `RUN01_PRESENT`, `RUN02_PRESENT`) — each a byte-identical
   copy of every authored file, plus a **synthetic** (no GPU call, no
   hardware access) `raw/` tree where the state requires one, built from the
   same `ok_payload()` generator `--selftest` already uses — and then
   actually **subprocess-invokes**, inside each fixture, every gate
   `CAPTURE_CONTRACT.json` contracts for that state (`selftest`,
   `manifest --check`, and `preflight`/`between-runs`/`captured` as
   appropriate; `analysis.py --write` too for `RUN02_PRESENT`), requiring
   each to actually exit 0. This is real, executable proof, not source-text
   pattern matching, and it is exactly the check that would have caught
   EXP-0075's contradiction *before a single GPU cycle ran*: a fixture
   standing in for `RUN01_PRESENT`, exercised against a hypothetical
   pre-fix `--selftest` that still required `raw/` to be absent, fails
   immediately in that fixture — while the tree doing the asking is still
   sitting in `PRE_GPU`.

`run.py`'s own gate sequence is updated to match the corrected contract
order: `--selftest`, `--seqtest`, `make_manifest.py --check`, then
`--preflight` (run01) or `--between-runs` (run02) — see
`CAPTURE_CONTRACT.json` `capture.pre_capture_gate` /
`capture.pre_second_run_gate`.

**No byte-compared record anywhere in this experiment carries a timing,
duration, address, or pid field.** `receipt` records do carry a
`started_utc` timestamp field, but it is checked only for ISO-8601 UTC
*format* (`receipt()`'s timestamp check), never compared for equality across
runs or across a tamper check; `compare_runs()`'s byte-exact repeat
requirement applies only to the case *payload* objects (`rows`), whose key
set (`PAYLOAD_KEYS`) contains no timestamp, address, or pid field at all —
this was already true of EXP-0075 and is unchanged here, verified again by
inspection of `PAYLOAD_KEYS` in `verify.py`.

## Question and bounded hypotheses

For each of the fourteen named public pixel formats, what complete owned
backing bytes follow one authored **compute** store (`access::write`) of
authored constants to the sole texel of a 1x1 texture, and what does one
authored, in-bounds typed compute `read(uint2(0,0))` of the same texture
observe in the same public command buffer? The formats are R8Unorm, R8Snorm,
RG8Unorm, RG8Snorm, RGBA8Snorm, R16Float, RG16Float, R16Sint, R16Uint,
R32Float, R32Sint, RG11B10Float, RGB9E5Float, RGBA16Uint — unchanged from
EXP-0075/EXP-0072, still frozen at fourteen.

Per-case testable hypotheses (full table in `CAPTURE_CONTRACT.json`, rules
a/b/c — rule **c** is now explicitly defined as "hypothesis-to-falsify", see
`expected_value_rules` in the contract):

- **a** — value exactly representable in the format, or a trivial
  passthrough with no rounding/scale question; word derived from the
  documented channel bit layout only. Not a hypothesis.
- **b** — documented Metal conversion/clamp/rounding rule applied to an
  exactly-authored input, at a point where the competing candidate rules
  happen to coincide (so the point is not diagnostic by itself).
- **c** — **hypothesis-to-falsify.** The registered expected value is the
  documented/textbook prediction; `rule_note` names the falsifying
  alternative and its exact predicted value. A "deviation" verdict on a
  rule-c case is a *result*, not a defect — it is what the case exists to
  produce.

### Named hypotheses carried forward from EXP-0075 (falsify, don't assume)

**H1 — snorm8 encode scale.** EXP-0075's single run observed `r8snorm_m100`
(input `-1.0`) as physical byte `0x81`, decoding to `-1.0` on typed read.
This is consistent with a **symmetric `round(c × 127)`** encode scale
(`round(-127) = -127 = 0x81`), which is *a* candidate public convention.
EXP-0075's *registration*, inherited unchanged from EXP-0072, predicted
`0x80` under the **`[-1,1] -> [-128,127]`** asymmetric-clamp convention
(also a documented public convention, e.g. the classic D3D/Metal-family
snorm decode `max(v/127, -1.0)` implies an encode side that reaches `-128`
for `-1.0`). This registration keeps `0x80` as the frozen expectation for
`r8snorm_m100`, `rg8snorm_m100_zero`, and `rgba8snorm_pack` (rule **c**), and
registers `0x81` as H1's exact falsifying alternative in each case's
`rule_note`. **EXP-0075's observation is not promoted to fact here — it is
the reason this case is retested, not the reason it is assumed.**

**H2 — reduced-float store narrowing rounds toward zero (truncates), not to
nearest-even.** EXP-0075's single run observed all four tested
reduced-destination-precision narrowings (fp16 in `r16float_mid`, fp11/fp10
in `rg11b10float_mid`, and the RGB9E5 shared mantissa in `rgb9e5float_mid`)
landing on the round-toward-zero prediction rather than the
round-to-nearest-even prediction, for a literal (`0.5 - 2^-25`) chosen to
sit just below an exponent-boundary tie. This registration keeps the
round-to-nearest-even value as the frozen expectation in every affected case
(rule **c**, reclassified from EXP-0075's `a`/`b` — see "Corrections" below),
and registers the exact round-toward-zero alternative word in each
`rule_note`. Two **new** cases (below) are added specifically to stress-test
H2 from directions EXP-0075 never probed.

## Corrections to the EXP-0075/EXP-0072 registration (disclosed by EXP-0075, independently re-verified here)

EXP-0075's own `RESULTS.md` and `PRE_REGISTRATION.md` disclosed three
registration slips. All three are independently re-derived here (by a
from-scratch Python fp32/eXmM bit-level converter, not by copying
EXP-0075's stated correction) before being frozen into
`CAPTURE_CONTRACT.json`:

1. **`r32float_exact`** (input `0.5`, R32Float, rule **a**, trivial fp32
   passthrough with no conversion at all): corrected `expected_texel_hex`
   from `0000803f` (`0x3F800000` = 1.0) to **`0000003f`** (`0x3F000000` =
   0.5). The old value was simply wrong arithmetic inherited from EXP-0072;
   its own read-word expectation (`3f000000`) was already internally
   inconsistent with it.
2. **`rg11b10float_exact`** (inputs `0.5,0.5,0.5`, rule **a**): corrected
   `expected_texel_hex` from `0038c071` (word `0x71C03800`, which does not
   decode to `(0.5,0.5,0.5)` under any layout with the format's own 11/11/10
   bit widths) to **`80031c70`** (word `0x701C0380`). Layout: R in bits
   `[10:0]` (e5m6, no sign), G in bits `[21:11]` (e5m6), B in bits `[31:22]`
   (e5m5). `fp11(0.5) = 0x380`, `fp10(0.5) = 0x1C0`; word `= 0x380 |
   (0x380<<11) | (0x1C0<<22) = 0x701C0380`. Verified by an independent
   Python bit-level fp32->eXmM converter (bias 15, round-to-nearest-even
   with mantissa-overflow carry) below.
3. **`rg11b10float_mid`**: same layout correction, `expected_texel_hex`
   corrected to **`80031c70`** (the round-to-nearest-even prediction; see H2
   below for the truncation alternative).

Independent re-derivation (this registration, run before any capture):

```
$ python3 -c "
import struct
def f32_bits(x): return struct.unpack('<I', struct.pack('<f', x))[0]
def fp32_to_eXmM(x, mbits, mode):
    bits = f32_bits(x); exp32 = (bits>>23)&0xFF; mant32 = bits & 0x7FFFFF
    e_stored = (exp32-127) + 15; shift = 23-mbits; keep = mant32>>shift
    if mode=='rne':
        rem = mant32 & ((1<<shift)-1); halfway = 1<<(shift-1)
        if rem>halfway or (rem==halfway and (keep&1)==1):
            keep += 1
            if keep==(1<<mbits): keep=0; e_stored+=1
    return (e_stored<<mbits)|keep
def word(r,g,b): return (r&0x7FF)|((g&0x7FF)<<11)|((b&0x3FF)<<22)
for label, x in (('exact',0.5), ('mid',0.4999999701976776123046875)):
    for mode in ('rne','trunc'):
        r=fp32_to_eXmM(x,6,mode); g=fp32_to_eXmM(x,6,mode); b=fp32_to_eXmM(x,5,mode)
        w=word(r,g,b)
        print(label, mode, 'word=%08x LE=%s' % (w, w.to_bytes(4,'little').hex()))
"
exact rne   word=701c0380 LE=80031c70
exact trunc word=701c0380 LE=80031c70
mid   rne   word=701c0380 LE=80031c70
mid   trunc word=6fdbfb7f LE=7ffbdb6f
```

The `mid trunc` result (`7ffbdb6f`) is bit-for-bit identical to EXP-0075's
raw hardware observation for `rg11b10float_mid` under the *corrected*
layout — independent evidence the corrected layout is right (both the exact
case and the H2 alternative reconstruction agree with what the hardware
already returned once), not evidence that H2 itself is right (that is what
this experiment's own captured run determines).

## New cases (EXP-0079 additions; full 14-format set otherwise unchanged)

Two additions, three new cases, both format R8Unorm / R16Float (already in
the fourteen — the format count stays 14; only the case count grows from 34
to 37):

1. **`r8unorm_sep_a`** (input `1.5 / 255.0`) and **`r8unorm_sep_b`** (input
   `2.5 / 255.0`) — half-even vs half-up separators for R8Unorm. The
   existing `r8unorm_p050` tie (`0.5*255 = 127.5`, floor `127` odd) cannot
   separate round-half-even from round-half-up, because both rules round an
   *odd*-floor tie up to the same even neighbour (`128`) — this was already
   noted as a limitation in EXP-0075's `RESULTS.md`. `1.5/255` (floor `1`,
   odd) is the same kind of non-discriminating control point (both rules
   give `2`); `2.5/255` (floor `2`, **even**) is the discriminator: round-
   half-even keeps the even neighbour `2` (rounds *down*), round-half-up
   always rounds the `.5` up to `3`. Registered expectation `0x02`
   (round-half-even/round-half-down-at-even-tie, consistent with the
   `r8unorm_p050` precedent); falsifying alternative `0x03`
   (round-half-up). **Confounder, disclosed up front:** the literal
   `1.5/255.0`/`2.5/255.0` is evaluated at MSL compile time in fp32, so the
   value the encoder actually multiplies by 255 may differ from the
   mathematical `1.5`/`2.5` by a few ULP of fp32 double-rounding (~1e-7
   relative) — far smaller than the 1-part-in-255 tie width, so not expected
   to move the case across the tie, but recorded as an alternative not
   excluded.
2. **`r16float_pos_trunc`** (input `0.500244140625` = exactly `0.5 +
   2^-12`) — positive-direction fp16 truncation-direction probe, the H2
   companion to `r16float_mid`. `0.5 + 2^-12` is the *exact* halfway point
   between fp16 `0x3800` (0.5) and fp16 `0x3801` (`0.50048828125`), in the
   **same** exponent bracket as `0x3800` (no boundary crossing is at stake,
   unlike `r16float_mid`). An independent from-scratch Python RNE and
   truncation fp32->fp16 converter (below) confirms **both** round-to-
   nearest-even (even-mantissa tie-break) and round-toward-zero truncation
   predict `0x3800` here — so this point does not by itself separate RNE
   from truncation. What it *does* separate is round-toward-zero from a
   round-away-from-zero/ceiling-like alternative, which would predict
   `0x3801`. Combined with `r16float_mid` (which shows the store path stays
   *below* 0.5 rather than crossing the exponent boundary up to it), an
   observed `0x3801` here would refute simple toward-zero truncation and
   reopen the direction question; an observed `0x3800` corroborates
   toward-zero truncation as the unique rule consistent with both probes at
   once. Registered expectation: `0x3800` (both candidate rules agree).

Independent re-derivation (run before any capture; also cross-checked
against EXP-0075's own raw observation for `r16float_mid`, which the model
below reproduces exactly):

```
$ python3 -c "
import struct
def f32_bits(x): return struct.unpack('<I', struct.pack('<f', x))[0]
def fp32_to_fp16(x, mode):
    bits=f32_bits(x); exp32=(bits>>23)&0xFF; mant32=bits&0x7FFFFF
    e16=(exp32-127)+15; shift=13; keep=mant32>>shift
    if mode=='rne':
        rem=mant32&((1<<shift)-1); halfway=1<<(shift-1)
        if rem>halfway or (rem==halfway and (keep&1)==1):
            keep+=1
            if keep==(1<<10): keep=0; e16+=1
    return (e16<<10)|keep
for x in (0.5, 0.4999999701976776123046875, 0.5+2**-12, 1.0/3.0):
    print(x, 'RNE=%04x'%fp32_to_fp16(x,'rne'), 'TRUNC=%04x'%fp32_to_fp16(x,'trunc'))
"
0.5                  RNE=3800 TRUNC=3800
0.4999999701976776   RNE=3800 TRUNC=37ff   # r16float_mid: matches EXP-0075's raw observation (37ff) under TRUNC
0.500244140625       RNE=3800 TRUNC=3800   # r16float_pos_trunc: both agree
0.3333333333333333   RNE=3555 TRUNC=3555   # r16float_third: both agree (not diagnostic, unchanged)
```

## Authored input values (frozen)

- unorm/snorm families: +1.0, 0.0, 0.5, and -1.0 (snorm only), plus the two
  new tie-separator literals `1.5/255.0`, `2.5/255.0` (R8Unorm only),
  authored as MSL decimal/expression literals.
- Float families: `0.5` (exactly representable in fp16/fp11), the mid
  literal `0.4999999701976776123046875` (= `0.5 - 2^-25` = exact fp32
  `0x3EFFFFFF`, not representable in fp16/fp11/fp10, inside the round-to-0.5
  zone of all three under RNE), `1.0 / 3.0` (compiler constant fold), and
  the new positive-direction probe literal `0.500244140625` (= exactly `0.5
  + 2^-12`, exact fp32 `0x3F001000`, R16Float only).
- Integer formats: 1, 2, 3855 (0x0F0F), stored as-typed via
  `texture2d<int/uint, access::write>` through the same compute-store path
  as the float formats (unchanged).

## Exact method and controls

Unchanged from EXP-0075/EXP-0072, byte-identical harness. Each case is one
fresh process with its own device, command queue, library (runtime
`newLibraryWithSource:` with `MTLCompileOptions.fastMathEnabled = NO`,
language version left at the host default), compute pipelines, command
buffer, and exactly two *owned* shared buffers: the texture backing (64
`0x5a` guard bytes, a 256-byte payload row, then 64 `0xa5` guard bytes; the
1x1 texture occupies the payload start at offset 64 with
`bytesPerRow=256`) and the typed-read result (64 `0x5a`, sixteen result
bytes, 64 `0xa5`). Kernel 1 (`s_<case>`) stores the authored constant to
`uint2(0,0)` only; kernel 2 (`k_read_float`/`k_read_int`/`k_read_uint`)
reads `uint2(0,0)` only and emits four little-endian uint32 words. There is
no out-of-bounds path and no blit. After command-buffer completion the
harness prints public status/error information plus complete owned buffer
hex. It never retains or inspects compiled shader bytes, archives, command
streams, BOs, pointers, private interfaces, or Apple helpers.

**Environment capture (frozen, unchanged):** `00_inputs.json` records `git
rev-parse HEAD`, a `git_dirty` flag plus the porcelain status of the
experiment directory, `sw_vers`, `xcrun --version`, `sysctl -n hw.model`,
machine, and the SHA-256 of every capture-bound authored blob. Per case, the
record carries `fast_math_enabled: false` (explicitly set) and
`msl_language_version`, the raw public `MTLCompileOptions.languageVersion`
value read from a freshly allocated options object before anything is set
on it.

Hard timeouts: environment commands 5s each, host clang build 120s, per-case
process 300s, in-harness phase watchdogs of 120s (compile phase) and 300s
(dispatch phase); `run.py`'s own gate-step subprocess calls (verify.py
--selftest / --seqtest / make_manifest.py --check / --preflight /
--between-runs) carry a 900s ceiling (`GATE_TIMEOUT` in `run.py`) — generous
because `--seqtest` alone spawns roughly thirteen no-GPU subprocesses across
its three fixture states, none of which should individually take more than
a few seconds. A watchdog breach, nonzero exit, or OS error during capture
writes a `STOP.json`, ends the run, and receives no automatic retry.

Two fresh append-only runs (`m4-20260828-run01`, `m4-20260828-run02`, the
actual capture date) are required. Run 01 begins only from the raw-free
pre-GPU tree after the contracted `pre_capture_gate` sequence passes
(`verify.py --selftest`, `verify.py --seqtest`, `make_manifest.py --check`,
`verify.py --preflight`, then the non-recorded smoke invocation). Run 02
begins only after the contracted `pre_second_run_gate` sequence passes
(`verify.py --selftest`, `verify.py --seqtest`, `make_manifest.py --check`,
`verify.py --between-runs`, then the non-recorded smoke invocation again) —
**this is the sequence EXP-0075 could never satisfy; EXP-0079 exists to make
it satisfiable and then prove it was satisfied.** Before creating run 02 the
runner also requires its current Git revision and authored hash map to equal
the closed run-01 record. Final verification additionally requires
identical `sw_vers`, `xcrun --version`, and `sysctl -n hw.model` output and
byte-exact equal case payloads across the two runs.

## Promotion rule and scope

Before any build: the full `pre_capture_gate` sequence must pass. Before
run02: the full `pre_second_run_gate` sequence must pass. Before
interpretation: `verify.py --captured`, `analysis.py --run-a
m4-20260828-run01 --run-b m4-20260828-run02 --write`, and `make_manifest.py
--check` must all pass for exactly the two contracted runs. Deviations
between preregistered expected values and observed values are RESULTS,
recorded verbatim by the analyzer; they do not fail verification — this is
especially true of every rule-**c** (hypothesis-to-falsify) case, where a
deviation is the falsification result itself. Until all gates pass, this
increment of DRV-FMT-01 remains **OPEN**. These observations cannot
establish native PBE/epilog behavior, descriptors, Linux mappings, A18/G17P
behavior, filtering, blending, atomics, MSAA, NaN/infinity/subnormal
handling, out-of-range inputs, or general conversion semantics beyond the
exact authored values. Everything here is **M4-target only**.

Clean-room provenance: HW-PROBE / OWN-SHADER source / PUBLIC API (planned only)
Inputs inspected: committed authored MSL, harness, contract, and future owned readbacks; EXP-0075's retained raw/m4-20260827-run01 tree was read only as a source of DISCLOSED REGISTRATION SLIPS (its own RESULTS.md/PRE_REGISTRATION.md prose, not its raw bytes) and as named hypotheses H1/H2, never copied as an expected value
Apple binary introspection: NONE
Reproduction: `python3 -B verify.py --preflight`; `python3 -B verify.py --selftest`; `python3 -B verify.py --seqtest`; future capture requires explicit `run.py --execute`
Evidence: no raw observations exist yet; `CAPTURE_CONTRACT.json` is the frozen capture grammar and expected-word matrix
