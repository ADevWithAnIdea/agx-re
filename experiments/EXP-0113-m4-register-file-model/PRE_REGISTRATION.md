# PRE_REGISTRATION -- EXP-0113 M4 register-file model (H1/H2/H3)

Frozen before any gated hardware capture. Pinned repository revision:
`72c2dde8afd896e384afa20050bdd040f657ca78` (dirty at pre-registration time:
several sibling experiments' untracked artifacts present in the working
tree, none touching this experiment's own files -- per SUBAGENT_BRIEF.md,
this experiment gates on `authored_*_sha256`, never on live `HEAD`).

Target: **local Apple M4 / G16G only** (this host, 10 GPU cores, macOS
26.6.2/25G82). A18 Pro hands-off, not touched. No M5 evidence used.

## 0. Background this experiment builds on (established, not re-derived)

- EXP-0099/EXP-0105: `falu2`/`falu2i`'s packed `srcA_reg`/`srcB_reg` 7-bit
  field top bit is HW-tested inert; field value 67 (low6=3) reads r3's
  seeded value, never a genuinely-unwritten r67's 0.0 (an "aliasing", not
  a fault). No validated mechanism for r64-95 addressing via this field
  was found. `opflags` bits22/23, `mod_hi` bit44, `ctrl` bits0/1 are
  general silent corruptors (zero the result regardless of register);
  `ctrl` bits2/3 inert; `ctrl` bits4-6 UNTESTED.
- EXP-0101: `reg_move` (the compact-move family, byte0 low-nibble 0xb,
  byte+2 low-nibble in {0,1,9,b}) does NOT read a live GPR at
  `src_flag=0`. Its readback is independent of the producer's value and
  family, depends only on `src_reg` (register-pair-quantized), and
  varies with the kernel's own buffer signature -- consistent with a
  fixed, per-kernel PRELOADED/uniform-file slot. `byte0=0x2b` (hex
  `2b0009c0`, from EXP-0087's own `k_swap` compile) was flagged
  "completely undecoded by tools/agx-isa" and named the candidate REAL
  GPR move, never chased further.
- EXP-0092: a `get_sr` `dst`/`dst_hi` (7-bit, `dst_lo|dst_hi<<4`) +
  `device_store` `index_reg` round trip works for registers 0-95 and
  faults (`CMDBUF_ERROR`) for 96-127 (except register 112, nondeterministic).
  This is the ONLY currently-validated path that reaches r64-95 at all --
  but it was only ever tested writing/reading the VALUE 0 (thread 0's
  `thread_position_in_grid.x`), never a genuinely distinguishing nonzero
  value, and it is a WRITE-side (get_sr) mechanism only.

## 1. Pilot-phase findings that shaped this design (disclosed; PROGRESS.md
   has the full trail; NONE of these pilot runs are part of the gated
   capture below -- every claim they inform is INDEPENDENTLY re-tested
   under this frozen contract)

1. **Flush-to-zero on denormal inputs is ACTIVE for `falu2i` (float
   ALU).** Seeding a low register with a small integer via
   `get_sr`+`device_store` (raw bits round-trip correctly, e.g. u32
   value 3) and reading it back via `falu2i(srcA=that reg, K=0.0)`
   reads back exactly `0.0`, not the denormal float the raw bits would
   represent. This means any H1 test routed through float-ALU arithmetic
   needs either a NORMALIZED (non-denormal, i.e. raw integer value
   `>=2^23`) seed, or a non-float consumer, to avoid a "silent zero"
   false negative that is indistinguishable from "read the wrong
   register."
2. **`device_store`'s `index_reg`-based address computation has a
   16-bit ceiling.** Storing to element index >= 65536 silently fails
   (destination buffer keeps its zero-initialized default) regardless of
   the value being stored; exact boundary 65535 (last correct) / 65536
   (first silently lost), reproducible, `STATUS OK` throughout (no
   fault). This rules out a large-dispatch-plus-per-thread-index
   technique for seeding a genuinely large value into r64+ within this
   experiment's time budget, and is itself a new, disclosed
   finite-resource fact (recorded in RESULTS.md, not chased further here
   -- its exact unit, byte-vs-element, and interaction with `elem_size`
   remain UNKNOWN).
3. **A `device_load` whose `dst_lo`/`dst_ext9` fields are set to encode a
   candidate register R (`dst = dst_lo | (dst_ext9<<2)`), immediately
   followed by a PLAIN-8-bit-register-field consumer (`iminmax`'s
   `srcA`) ALSO set to R, appears to correctly forward the loaded value
   across an enormous R range** -- including R values (96-127) already
   proven, by the INDEPENDENT get_sr/device_store path (EXP-0092), to be
   OUTSIDE the physical 96-GPR file, with occasional unexplained
   exceptions (R=15, R=90 fail; R=16, 20, 31, 32, 63, 67, 94, 95, 96, 97,
   100, 110, 120, 127 succeed). Two decisive follow-ups (both
   independently reproduced under THIS experiment's own gate, group
   H1_LOADFWD) show this is NOT genuine persistent register-file access:
   a SECOND, later, independent consumer reading the SAME nominal R gets
   0 (persistence fails); and merely inserting that second consumer
   changes the FIRST read's own result too, even at R=7 (an ordinary low
   register that succeeds in isolation). This generalizes EXP-0105's own
   flagged "iminmax splice has zero effect" anomaly to a NEW variant
   (load-fed, not bare-splice) and a sibling family (`ilogic`, briefly
   probed, same qualitative unreliability observed informally, not
   gated).

## 2. Hypotheses and falsifiers

### H1 -- how (if at all) are r64-95 addressed as an ALU SOURCE operand?

- **H1a (falu2/falu2i's own packed field).** Falsifier: an independently
  seeded, genuinely-written r67 (not merely unwritten) reads back
  correctly through `srcA_reg`/`srcB_reg`=67. Confounder ruled out by
  design: `H1_ALIAS_RECONFIRM` reuses ONLY the FTZ-safe, already-
  established EXP-0099/0105 construction (r3 seeded to a normal float,
  r67 genuinely unwritten) -- this does not attempt a genuine-r67-seed
  test (blocked by finding #2 above; disclosed limitation, not silently
  dropped).
- **H1b (a separate bank-select bit elsewhere in falu2's encoding).**
  Falsifier: any of `ctrl` bits 4-6 changes the reg=67 case away from
  the aliased/inert baseline while leaving reg=3 unchanged. Confounder:
  a bit that changes BOTH reg=3 and reg=67 identically is a general
  corruptor (EXP-0105's own established pattern for bits22/23/44/0/1),
  not a bank selector -- distinguished by the SAME reg=3-vs-reg=67
  crossing EXP-0105 used.
- **H1c (a structurally different, wider-field instruction family).**
  Falsifier: a plain-8-bit-field consumer (`iminmax`) reads a
  GENUINELY, INDEPENDENTLY seeded r64+ value correctly via a
  DECOUPLED, non-adjacent path (not merely the ephemeral single-hop
  forward characterized in pilot finding #3). Given pilot finding #3
  shows the single-hop construction itself is NOT a validated write+read
  of a persistent register, H1_LOADFWD's own gated cases are designed to
  CONFIRM/refute persistence and shape-sensitivity directly (not to
  re-litigate the single-hop sweep, which is pre-registered as EXPECTED
  to reproduce the pilot pattern per case).
- **Expected observation if r64-95 is genuinely, persistently
  ALU-source-addressable by SOME examined mechanism:** at least one of
  H1a/H1b/H1c's decisive cases reads back a value that (a) differs from
  both the "genuinely unwritten" (0.0/0) and "aliased-to-known-low-reg"
  predictions, and (b) SURVIVES being read by a second, later, 
  independent consumer.
- **Expected observation if it is a genuine restriction:** every decisive
  case's observed value equals either the aliasing prediction or 0
  (unwritten), AND no candidate bit unlocks a different reading, AND
  (H1_LOADFWD) the apparent load-forwarding success does not survive
  independent re-reading.
- **Positive control (detectability proof):** `positive_control_
  deliberate_mismatch` (SEED_CHECK) proves match-detection is not a
  rubber stamp; `H1_LOADFWD`'s own single-hop sweep contains BOTH
  pre-registered-success (R=7,16,32,63,67,96,127) AND pre-registered-
  failure (R=15,90) points in the SAME construction, proving the harness
  can and does distinguish "reads the seeded value" from "does not" at
  will -- the persistence-test's own MISMATCH prediction is therefore a
  meaningful negative, not an insensitive default.

### H2 -- is byte0=0x2b (the `2b0009c0` shape) the real GPR move?

Statically (no GPU): does `isadb.assemble('reg_move_c9', {dst:2,
src_reg:0, src_flag:0, src_class:0, op_desc:0xC0})` reproduce
`2b0009c0` byte-for-byte? (Verified in verify.py --selftest, no GPU.)
On hardware: does `reg_move_c9(src_reg=R)` read a live, ALU-written GPR
at R (producer-independence: SAME src_reg, DIFFERENT producer value ->
SAME observed output = NOT reading the GPR), and does its content match
the register-pair-quantization pattern EXP-0101 found for the sibling
`reg_move_c1` family (src_reg X and X^1 identical)? Falsifier for "it IS
a real move": producer-independence FAILS (different producer values ->
different observed output) for at least one src_reg. Falsifier for
"same mechanism as reg_move_c1": pair-quantization FAILS (X and X^1
differ).

### H3 -- what does `reg_move`'s `src_reg` (src_flag=0) actually address?

Does the RAW CONTENT observed at a fixed `src_reg` value shift when the
kernel's OWN bound-buffer count changes (1 vs 2 vs 3 float* buffers)?
Falsifier for "addresses something buffer-count-dependent": content is
IDENTICAL across all three carriers at every tested src_reg. A positive
(content DOES shift) is `STRUCTURAL`/`INFERRED` evidence only -- this
experiment does not independently cross-reference a `tools/iotrace`
capture of the SAME kernel's real argument-buffer bytes (disclosed
time-budget scoping decision; iotrace was not built/run this round).

## 3. Independent / controlled variables

- H1: the ALU source-operand FIELD VALUE (`srcA_reg`/`srcB_reg`/`ctrl`
  bits/`srcA` of `iminmax`); controlled: producer/seed construction,
  dispatch shape, carrier kernel.
- H2: `src_reg`, producer VALUE (30.0 vs 2.0 at the SAME src_reg=2);
  controlled: everything else in the 4-byte instruction.
- H3: bound-buffer COUNT (1/2/3); controlled: `src_reg` value, `reg_move_c1`
  field shape, dispatch (grid=1,tg=1 throughout).

## 4. Known confounders (disclosed, not silently absorbed)

- Float ALU flush-to-zero on denormals (pilot finding #1) -- every H1
  case in this gated matrix that could hit it either uses a normalized
  seed value (H1_ALIAS_RECONFIRM, CTRL groups: 30.0) or an
  integer-only consumer (H1_LOADFWD: `iminmax`, `device_store` raw u32).
- `device_store` 16-bit index ceiling (pilot finding #2) -- no gated case
  in this matrix stores to an index >= 100.
- H1_LOADFWD's own field conventions (`dst = dst_lo | dst_ext9<<2`,
  `srcB=192` tail byte) are COPIED VERBATIM from ONE compiled instance
  (this experiment's own pilot phase, PROGRESS.md Milestone 2) per the
  standing "copy from a compiler-observed pattern, never synthesize"
  discipline for under-characterized fields -- they are NOT claimed to
  be the general formula, and the group's own headline finding is that
  they do NOT constitute genuine persistent addressing regardless.
- H2's `reg_move_c9` programs cannot be validated via the standard
  whole-stream `isadb.disassemble()` round trip (isadb.py's
  `instr_length()` has no branch for byte0=0xNb + byte+2 low-nibble=9);
  `isa_helpers.assert_reg_move_c9_program()` substitutes a targeted,
  documented equivalent (exact instruction-byte match against
  `isadb.assemble()`, plus a normal round trip for every OTHER
  instruction in the same program).
- H3's correlation (if any) is `STRUCTURAL`/`INFERRED`, not
  `DATA-TRACE-VALIDATED` -- no `tools/iotrace` cross-check this round
  (disclosed scope narrowing).

## 5. Environment / tool revisions

- macOS 26.6.2 (25G82), `Mac16,10` (Apple M4, 10 GPU cores), arm64.
- `tools/agx-isa` (db.json/isadb.py), `tools/shdump`, `tools/agxtest` --
  READ-ONLY, used exactly as committed at the pinned revision.
- Frozen authored-file hashes (recorded here, checked by `run.provenance()`
  at every gate, NEVER against live `HEAD`):
  - `isa_helpers.py` `6bd5ac81d8323ce87951185c307772e91f6609475e8a5b31f25c58ac2388f486`
  - `casematrix.py` `808ff75d834b71bf2029496e5c0488e50d0955e6e9442b134436400470feff1e`
  - `harness/build.sh` `0d04edd519d73da89fb82d62067b231d481a9efc5336f940d343de83bf3d47ed`
  - `harness/case_exec.py` `214d125ea3b05c8bba98f2d26f6043531c6e4e70b1182d86c5e7421378252b17`
  - `run.py` `dddfd9d8469f12f5df5f9bea885044aa44b8ec74e8e467aae9eef7bd05cac20f`
  - `verify.py` `29121d28f8e2639b8295511312f3214d39c6605af7ea1f5ebb441ab3d0784865`
  - `baseline.py` `01e243a1a81c3bbdee40c5c273022058cedbb2b078bd1db7f22b42d54b009f7a`
  - `make_manifest.py` `fb2d66d8e87b10694b7b50ca9bd737374ef5b6a98d80a4d24bb28685011254ae`
  - `kernels/carrier.metal` `d487d78cf2b953326c5e27ccd8f449f21683602578a3a99e1719d577717ff509`
  - `kernels/loadfwd_carrier.metal` `a71597dafcd02b9d59b61fed940f17ce9d89fb262a32479eea4fba46495b5f78`
  - `kernels/carrier_buf1.metal` `8f29b042b6280db0bc7bc5866f65ca4a60803928a3a8dff5429bfa831b2040fd`
  - `kernels/carrier_buf2.metal` `115314ac02d83340ddddc2c4e49afe7d1e52ac4b47b53a25617a46c0d9a6d7bd`
  - `kernels/carrier_buf3.metal` `65ac9e925e0f61ef4771ad308ef0a90e6a4b442a0f4848272c98e0edcb7a9fee`
  - `PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json`, `README.md` -- hashed
    at capture time by `run.provenance()` (this file's own content
    necessarily cannot be pre-hashed here).
- Carrier compiled lengths, fresh-confirmed by `baseline.py --` (PASS,
  this session): `carrier.metal`=170, `loadfwd_carrier.metal`=154,
  `carrier_buf1.metal`=36, `carrier_buf2.metal`=42, `carrier_buf3.metal`=62.

## 6. Raw-record schema (frozen)

`01_results.jsonl` (GATED, byte-compared across both runs): one JSON
object per case with keys `i,name,group,carrier,oracle,expect_match,notes,
dispatch,status,pipeline_source,out_hex,observed,match` -- no
nondeterministic field. `01_timing.jsonl` (NON-GATED sibling): `i,
duration_ms,argv,stdout,stderr` -- explicitly NOT required to match.

## 7. Timeouts / safety

- Per-case subprocess timeout: 45s (`case_exec.py`); `agxtest.py --run-
  timeout 30`. Outer harness timeout: 60s (`run.CASE_TIMEOUT`).
- Every case: one fresh process, single-threaded, one change of
  instruction bytes per case (H3's buffer-count axis is the ONE exception
  where the CARRIER itself, not just the spliced bytes, varies -- each
  such case is still its own isolated process/run).
- Largest dispatch in this gated matrix: `H1_LOADFWD` group, grid=4,
  tg=4 (NOT the ~8.4M-thread dispatch explored informally in the pilot
  phase and abandoned per finding #2 above -- no case in this gated
  matrix dispatches more than 4 threads).
- `run_id_reuse_forbidden`: true. Two contracted runs:
  `m4-20260828-run01`, `m4-20260828-run02`.
