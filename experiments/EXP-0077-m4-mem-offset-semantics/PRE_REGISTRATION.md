# EXP-0077 pre-registration — M4 device_load/store memory-offset semantics (MEM-01..MEM-05)

**Frozen state: PRE-GPU.** No spliced variant of our kernel has been executed
on the GPU for EXP-0077 at freeze time, and no observation of the questions
below has been made under this experiment. What happened before the freeze is
the **authoring stage** only, documented below: our own MSL was compiled with
our own `shdump` and disassembled/assembled with our own `tools/agx-isa` DB
(compile-only; no dispatch), so that the probe instruction bytes and offsets
frozen in this registration and in `CAPTURE_CONTRACT.json` are the actual bytes
of the actual kernels. This mirrors the authoring flow of every splice
experiment in this repository (EXP-0003…EXP-0018, RT-1a-FIX, EXP-M4-14).

**Authoring-stage facts frozen below** (derived from our own compiled bytes,
`work/auth` scratch, re-derived deterministically by `baseline.py` at capture
time; any mismatch is a STOP, never an improvisation):

- `kernels/ld_bank.metal` → `_agc.main` 114 bytes, probe load at main+0x26 =
  `6700440202002000510100404600` (device_load, addr_mode 0x44 canonical
  indexed form, base_slot 2 = `a[]`, index_reg r0 = the iadd result
  `j = i0 + i1`, ld_format 17 = 32-bit scalar, idx_off 0, elem_size byte 0x46).
- `kernels/st_bank.metal` → `_agc.main` 108 bytes, probe store at main+0x4C =
  `e700540401012100110000901100` (device_store, base_slot 1 = `tgt[]`,
  index_reg r1 = `j`, st_format 17, idx_off 0, byte+12 baseline 0x11 — its
  scale semantics are probed, NOT pre-assumed).
- Both mains tokenize cleanly under `tools/agx-isa` and every instruction
  survives an `assemble(decode(bytes)) == bytes` round trip.
- The kernels put the runtime index in a GPR via `j = i0 + i1` with `i1` bound
  to 0, so `j == idxbuf[0]` bit-exactly (including 0xFFFFFFFF; `x + 0` never
  wraps) and the index is runtime-controlled without any confounding ALU wrap.
- Probe read buffer `a[]`: 4096 words, `a[w] = 0x3CA50000 | w`; byte 3 of every
  word is the tag 0x3C, byte 2 is 0xA5, bytes 0..1 carry the word index, so any
  32-bit read at a byte offset B < 16381 decodes uniquely to (word, residue).
- Probe store target `tgt[]`: 2048 words, zero-filled, store data constant
  `0x5A17C0DE`; changed bytes identify the effective store byte offset.

## Question

Part-II questionnaire items **MEM-01 … MEM-05** of
`APPLE9_RE_IMPLEMENTATION_GAPS.md` (P0 "Memory addressing and robustness"):

- MEM-01: does `device_load/store` interpret its GPR index as an element index
  scaled by the encoded element size?
- MEM-02: is the in-instruction immediate offset added in element units rather
  than bytes?
- MEM-03: complete signedness and legal range of the immediate element offset,
  hardware-validated (exact usable range, holes, first-invalid value, failure
  mode).
- MEM-04: can `device_load/store` directly encode `base + index*stride +
  offset` for arbitrary vertex strides, or must the multiply be lowered to
  ALU/IMAD first?
- MEM-05: does 32-bit address/index arithmetic wrap exactly as NIR buffer
  offsets require?

Compiler consequence (recorded, not implemented): a No on MEM-04 keeps index
multiplication in ALU/IMAD before the memory op; a Yes on MEM-05 lets NIR
32-bit offset arithmetic be emitted as-is.

## Hypotheses (falsifiable, frozen)

Working on the DB's field layout (`tools/agx-isa` `device_load`/`device_store`,
14 bytes): `index_reg` = byte+5 (bits[40:48]); `idx_off` = 11 bits at
bits[79:90] (byte+9 bit7 = LSB, byte+10 = bits 1..8, byte+11 bits 0..1 =
bits 9..10); `elem_size` = byte+12 (bits[1:4] code). A18-side evidence
(EXP-0012 + RT-1a-FIX, splice-and-observe on the A18) supports element
addressing `(index + offset) × element_size`; M4-side HW-splice evidence for
these fields does not yet exist — this experiment establishes it.

- **H-ELEM**: effective byte offset = ((j + off) mod 2^32) × scale — the
  immediate offset is in ELEMENT units, added to the index BEFORE the
  element-size scale. **H-BYTE**: byte offset = j×scale + off — the offset is
  in BYTE units. Discriminating cases are frozen where the two differ
  (e.g. idx=0, off=+1, 4 B elements → word 1 under H-ELEM vs byte 1 under
  H-BYTE; idx=1, off=+1 → word 2 vs byte 5).
- **H-U / H-S**: the 11-bit `idx_off` is unsigned (0…2047) or two's-complement
  signed (-1024…+1023). The dense sweep at idx=1024 lands in-bounds under BOTH
  models, so every field value's observed element decides; the idx=64 family
  additionally shows whether field values ≥ 0x400 go below the buffer
  (negative side, first-invalid + failure mode).
- **H-SC**: element-size codes (bits[1:4] of byte+12) {0:16, 1:1, 2:2, 3:4,
  4:8} bytes. Codes 5..7, odd codes (bit0 set) and high bits are exploration:
  if code 5 = 32 B works, strides remain powers of two; a fault or a no-op is
  a first-class result.
- **H-W32**: the (index + offset) × scale computation wraps modulo 2^32
  exactly (e.g. j = 0xFFFFFFFF, off = +1, 4 B → byte 0 = word 0; j =
  0x40000000, 4 B → byte 0; j = 0x7FFFFFFF, off = +1, 4 B → byte 0). The
  far-OOB controls (j = 0xFFFFFFFF with 1 B elements → byte 0xFFFFFFFF) record
  the failure mode if no wrap occurs.
- **MEM-04 null expectation**: the only scale field is `elem_size` (powers of
  two) and the only additive field is `idx_off`; no encoding produces a
  non-power-of-two stride (e.g. 3), so arbitrary vertex strides must be
  pre-multiplied in ALU/IMAD. Refuted if any probe combination yields stride 3.

- Independent variables: the spliced instruction field(s) (ONE field family
  per case) and the runtime GPR index `j = idxbuf[0]`.
- Controlled variables: kernel sources (hash-frozen), compile options
  (`--no-fast-math` for both shdump and the archive identity compile; fastMath
  state is irrelevant to integer address arithmetic but frozen anyway),
  dispatch geometry (grid 1 × threadgroup 1), buffer sizes and fill patterns,
  the splice path (agxtest + binary archive + `FailOnBinaryArchiveMiss`), and
  the baseline anchors (re-derived at capture; drift = STOP).
- Expected observation if the hypotheses hold: every OK case's decoded byte
  offset equals the H-ELEM+H-U (or H-S where signed) prediction; see the
  per-case frozen predictions in `casematrix.py` / `CAPTURE_CONTRACT.json`.
- Refuters: (1) any MEM-02 case matching H-BYTE instead of H-ELEM; (2) any
  dense-sweep field value whose observed element matches NEITHER signedness
  model (a hole or misencoded field); (3) any wrap case NOT landing at word 0;
  (4) any elem-code probe producing a non-power-of-two stride; (5) any
  self-test/seqtest/preflight failure before capture; (6) non-byte-exact
  repeat between run01 and run02; (7) the hand-validation set diverging.
- Known confounders: the Metal compiler's register allocation is not observed
  and not assumed — the baseline (unspliced) instruction is correct by
  construction and every splice preserves all bytes outside the ONE changed
  field family (asserted byte-wise by `run.py::splice_case`); the 26.6.2 M4
  compiler emits a byte+2=0x44 load form (A18 experiments saw 0x44/0x54) —
  the offset/size fields are form-independent claims re-anchored by the
  controls; an out-of-allocation access may return 0, garbage, fault the
  command buffer, or (for stores) corrupt memory outside `tgt` — each outcome
  is recorded as a failure-mode observation, never retried in place; the store
  data path is a compile-time constant so address splices cannot move the
  stored value.

## Authorized pre-capture plumbing validation (no observation recorded)

Before the first capture and after this registration is frozen in shape, the
runner authorizes exactly TWO non-recorded plumbing invocations into `work/`
(never promoted into `raw/`, never cited as evidence, identical in kind to the
in-run smoke gate — the lesson of the quarantined EXP-0072):

1. the UNMODIFIED `ld_bank` archive through `agxtest`/`agxrun` (identity
   round-trip: proves the M4 binary-archive dispatch path and the output
   readback parse);
2. ONE spliced scratch case (`idx_off=+1`, idx=64: proves the splice mechanism
   — archive tampering accepted, `FailOnBinaryArchiveMiss` pipeline still
   instantiates, the byte changed is the byte that ran);
3. the UNMODIFIED `st_bank` archive with the full 8 KiB target readback (proves
   the store probe's buffer binding and the large-readback parse path).

These are shape checks of the testbed, not observations of MEM-01..05: the
first cannot answer any questionnaire item (it is the compiler's own correct
code), and the second is the same single datum the in-run smoke gate would
record. If either fails, the experiment is BLOCKED before capture (no run id
burned, `STOP` reported to the orchestrator).

## Exact frozen method

1. `run.py --execute --run-id m4-20260827-run01|run02` refuses to run without
   `--execute`, first requires `verify.py --selftest` AND `verify.py --seqtest`
   to pass (runnable in every tree state — they only build synthetic scratch
   trees), then the state gate (`--preflight` for run01, `--between-runs` for
   run02).
2. Provenance (git revision + dirty flags, sw_vers, xcrun, python, machine,
   SHA-256 of every authored blob) is recorded; run02 additionally must match
   run01's revision and authored hashes exactly.
3. Build phase: `harness/build.sh` compiles the read-only tool sources
   (`tools/shdump/shdump.m`, `tools/agxtest/agxrun.m`) into `work/<run>/`;
   `baseline.py --bin-dir` re-compiles both kernels, re-derives the anchors and
   STOPs on any drift from the frozen anchors.
4. NON-RECORDED smoke gate: one spliced scratch case (ld, `idx_off=+1`,
   idx=64) runs in `work/` — never promoted into `raw/` — and its output must
   parse completely (STATUS OK, PIPELINE_SOURCE archive, OUT lines, successful
   decode, exactly one spliced byte). Failure = `STOP.json` at phase
   `smoke_gate`; no capture is burned on a harness defect.
5. The sweep: for each of the **2164** frozen cases, ONE field-family splice
   re-assembled with `tools/agx-isa` (`assemble(decode(probe)+override)`),
   executed via `tools/agxtest/agxtest.py` → `agxrun` in a fresh process on
   the local M4 (hard timeout 120 s per case), output parsed and decoded,
   appended to `raw/<run>/04_results.jsonl` (flushed per case). A fault
   (`CMDBUF_ERROR`), hang (`HANG`) or timeout is a recorded RESULT; the sweep
   continues in a fresh process.
6. Two runs are required, each in a fresh process; final verification requires
   byte-identical results files and identical status counts.

## Frozen matrix (2164 cases; full list in casematrix.py / CAPTURE_CONTRACT.json)

| family | cases | what it decides |
| --- | ---: | --- |
| CTRL (unspliced, both kernels) | 6 | baseline correctness of both probes |
| VAL-IDXREG (byte+5 sweep 0x00..0xFF) | 14 | M4 re-validation of the A18-proven index-register selector (non-load-bearing; the M4 compiler's 0x44 form may differ) |
| MEM-01 scale (idx × elem code, ld+st) | 23 | element-size scaling of the GPR index; store byte+12 code space |
| MEM-02 offset units (ld+st) | 12 | H-ELEM vs H-BYTE discriminating cases |
| MEM-03 dense (ld, idx=1024, field 0…2047) | 2048 | signedness, exact usable range, holes |
| MEM-03 negative side (idx=64, field ≥ 0x3FE) + tail probes + st boundary | 21 | first-invalid below the buffer, byte+11 bits 2..7 inertness, store range |
| MEM-04 elem-code space (ld+st) | 25 | stride ceiling, odd codes, no non-power-of-two stride |
| MEM-05 wrap (ld 9 + st 2) | 11 | exact mod-2^32 arithmetic + far-OOB failure modes |
| VAL-EXTRA (byte+1 space, byte+6 inert) | 4 | ties to prior A18-side evidence |

## Frozen hand-validation set (11 entries, hand-computed bit patterns)

`casematrix.py::hand_validation()`: e.g. `ld_ctrl_idx64` → `0x3CA50040`;
`ld_scale1_code1` (1 B elements, idx 1 → byte 1) → `0x013CA500`;
`ld_scale1_code2` → `0x00013CA5`; `ld_scale1_code0` (16 B) → `0x3CA50004`;
`ld_off1_code3_idx0` under H-ELEM → `0x3CA50001`; `ld_range_f0000` →
`0x3CA50400`; `ld_wrap_ffffffff_p1` under H-W32 → `0x3CA50000`. Any divergence
between the observed value and the hand-computed word is an analysis-gate
failure (STOP-equivalent for interpretation).

## Environment, timeouts, raw schema (frozen)

- Target: the local Apple M4 (G16G, 10 cores, macOS 26.6.2 build 25G82,
  Metal 4) through public Metal only. A18 hands-off; `macvdmtool` never.
- Hard timeouts: environment commands 10 s; harness build 60 s; baseline
  derivation 180 s; every case process and the smoke case 120 s.
- Raw schema per run (`append-only`, regular files only): `00_inputs.json`,
  `01_cases.json` (complete matrix echo), `02_build.json` (harness+baseline
  receipts), `03_dispatch.json` (single authoritative sweep record),
  `04_results.jsonl` (one line per case, key set `CASE_KEYS`, includes the
  full case stdout/stderr), `05_run_manifest.json`. `STOP.json` ends a run;
  never an automatic retry.

## Promotion rule and scope

Before any capture, in this exact order and all passing:
`verify.py --selftest`, `verify.py --seqtest`, `make_manifest.py --check`,
`verify.py --preflight`. Before run02: `--selftest`, `--seqtest`,
`make_manifest.py --check`, `--between-runs`. After run02:
`analysis.py --run-a m4-20260827-run01 --run-b m4-20260827-run02 --write`,
`make_manifest.py --write && --check`, `verify.py --captured` — all must exit
zero (hand set reproduced, runs byte-identical). Until then MEM-01…MEM-05
remain **Open** for the M4.

Scope: local M4 public-Metal splice evidence on the two frozen kernels, for
the exact 2164-case matrix, in the exact compiled forms frozen above. No A18
(G17P) inference (hands-off), no Linux/UAPI claim, no M5 evidence. What this
experiment RE-VALIDATES on M4 silicon versus the A18-side record is separated
in RESULTS.md (candidates: element addressing from EXP-0012-M2; index-register
selector from RT-1a; offset-field existence from RT-1a-FIX).

## Authored blob hashes at freeze (SHA-256)

Derived from this experiment's own final bytes; enforced by
`CAPTURE_CONTRACT.json` (`authored_sha256`) and re-checked at every gate.

Clean-room provenance: HW-PROBE / OWN-SHADER (authoring stage compile-only; capture planned)
Inputs inspected: authored MSL, harness, runner/verifier/analysis/matrix/baseline modules,
and our own compiled shader bytes (splice targets)
Apple binary introspection: NONE
Reproduction: `python3 -B verify.py --selftest && python3 -B verify.py --seqtest
&& python3 -B make_manifest.py --check && python3 -B verify.py --preflight`;
capture requires explicit `run.py --execute`
Evidence: no raw observations exist at freeze; `CAPTURE_CONTRACT.json` is the frozen grammar
