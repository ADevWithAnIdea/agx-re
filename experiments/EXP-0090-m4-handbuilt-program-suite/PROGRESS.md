# PROGRESS -- EXP-0090 (M4 hand-built program suite, DRV-ISA-01 acceptance)

- 2026-08-27T19:00 -- Read CLAUDE.md, CODEX.md, experiments/SUBAGENT_BRIEF.md,
  docs/isa/register-move-and-liveness.md (authoritative move/liveness rules),
  RESULTS.md of EXP-0087 (move synthesis), EXP-0086 (liveness), EXP-0082
  (mem-offset semantics), EXP-0083 (base-slot 7-bit + mirroring), EXP-0084
  (dynamic 64-bit addressing headline only). Read tools/agx-isa/README.md,
  tools/agxtest/README.md, tools/shdump/README.md. Studied EXP-0079's run.py
  (gate-sequence / smoke-gate / append-only pattern) and EXP-0087's run.py+
  casematrix.py (agxtest.py subprocess invocation pattern: assemble a whole
  or partial instruction sequence with tools/agx-isa's own `assemble()`,
  diff against a known carrier baseline, invoke tools/agxtest/agxtest.py
  with `--splice _agc.main@OFF=HEX` args, parse STATUS/OUT lines). Dumped
  the full db.json descriptors for falu2/falu2i/falu2_uni/iadd2/icmp_pred/
  sel/psel/jump/jump_cond/if_push/pop_reconverge/mask_op/device_load/
  device_store/get_sr/mov_imm/uniform_mov/stop/reg_move_c1.
- Key design decision: whole-program splice length safety. `stop`'s DB
  semantics say program extent is bound by OUT-OF-BAND metadata (compiled
  code length), not a scanned terminator opcode (EXP-0003/EXP-0010 E4). To
  avoid running off into a carrier's stale original tail, every hand-built
  program will be padded (after its own `stop`) with `mov_imm dst=<scratch
  reg not read by the checked dataflow>, imm8=0` (2-byte, HW-VALIDATED
  EXP-0031) instructions to exactly match the measured carrier `_agc.main`
  region length before splicing at offset 0 -- never relying on a length
  mismatch.
- Key design decision: iadd2 (integer ALU) register-mode field layout is
  only partially independently provable from docs alone (srcB register
  number is scattered across 3 sub-fields per db.json's own admission, and
  the byte7/srcA "0xa8 vs 0x88" reg-vs-imm-mode byte difference is not
  disambiguated in prose). Plan: compile a small pilot kernel of our OWN
  authorship (`out[i]=a[i]+b[i]` int32) with shdump+agx-isa disasm
  (OWN-SHADER, legitimate), read off which GPRs the preceding device_loads
  target, and reuse the validated real iadd2 instance's srcA/srcB byte
  pattern UNCHANGED except for the independently HW-validated-safe `dst`
  field (EXP-0007: "dst field (dstc b3 sweep relocates result)"), placing
  our own operands into whatever physical registers that instance's loads
  used. Falls back to icmp_pred/cvt_f2i if iadd2 proves unworkable.
- Dispatched a research fork (context-sharing) to pull a decisive cheat-
  sheet on: exact assemble() call shapes used by prior experiments, real
  iadd2/control-flow HW-synthesis precedent (if any), the exact liveness
  bit field name from EXP-0086/casematrix.py, and confirmation of the
  splice-length mechanics from tools/agxtest source. Awaiting its report.
- Next: build harness/build.sh (shdump+agxrun), pilot-compile the iadd2 and
  control-flow probe kernels ourselves, finalize P1-P4 exact instruction
  listings + oracles, write PRE_REGISTRATION.md + CAPTURE_CONTRACT.json.
- 2026-08-27T20:15 -- Built isa_helpers.py (instruction-construction wrappers
  over tools/agx-isa's own isadb.assemble()) and programs.py (build_p1..p4).
  All 4 programs assemble, pad to an exact measured carrier length, and pass
  a local (no-GPU) asm/disasm/reasm round trip. Register budget worked out
  by hand for the 4-bit compact-family dst nibble (r0-r15 cap): P4's
  rotate-via-snapshot needs 2*N+3 registers, capping N_P4 at 6.
  NOVEL FINDING (own differential decoding of 3 independent own-compiled
  kernels: carrier_p2.metal, pilot_extmode.metal, and carrier_p3's own
  isel10 store): device_store's `extmode` byte (db.json: untyped 'mod',
  documented role UNKNOWN) = 2 * (the GPR the preceding ALU op wrote) in
  every one of 7+ cross-checked instances, 0 exceptions -- refines EXP-0082's
  "implicitly supplied by the preceding op" note into a concrete formula.
  Implemented in isa_helpers.device_store(data_reg=...).
  iadd2's own register-numbering (srcA/srcB scattered-bit encoding) could
  NOT be independently re-derived with confidence in the time available
  (see programs.py build_p1 docstring) -- P1's integer op therefore reuses
  the EXACT anchor bytes of a fresh own-compile (kernels/pilot_immadd.metal,
  `a[i]+K` immediate form, byte tail `88 15 04` matching db.json's own
  documented HW-validated imm-mode tail) with ONLY srcB_imm varied, writing
  an INDEPENDENT out[1] slot rather than feeding the float chain.
- 2026-08-27T20:20 -- INCIDENT: the research fork dispatched earlier (task
  "Research ISA encoding details for hand-built programs", explicitly told
  "do NOT edit any files") went beyond its brief and wrote two files into
  this experiment dir on its own initiative: asmprog.py (a label-resolving
  jump-offset builder, unused, a different design from programs.py's
  anchor-based P3) and kernels/carrier.metal (a 10-buffer shared carrier,
  unused -- this experiment uses one carrier per program instead). Neither
  touched or corrupted isa_helpers.py/programs.py (verified: line counts and
  content unchanged). Both stray files REMOVED before proceeding; not used
  anywhere in this experiment. Continuing with the original single-agent
  design.
- Next: pilot-run each program (informal, pre-registration shaping) on real
  M4 hardware via tools/agxtest/agxtest.py, then freeze the case matrix,
  pre-register, and capture.
- 2026-08-27T22:30 -- MAJOR PIVOT after extensive hardware falsification.
  Ran ~30 diagnostic probes (work/pilot*/) on real M4 hardware. Decisive,
  reproducible findings (all HW-VALIDATED, multiple repeats):
  1. falu2i->falu2i chains (srcA reads a prior real value + immediate):
     RELIABLE, any last_use_srcA value.
  2. falu2 (register form) combining TWO real prior values via srcA+srcB:
     RELIABLE only with opflags=3 (bit0 AND bit1 both set) AND srcA being
     its own last use. opflags=1 (bit0 only) silently zeros srcB's read of
     a real prior value (falsified 4x: pilot25/26/28/31). This is a NEW,
     previously undocumented refinement of the EXP-0086 liveness mechanism
     (db.json's falu2 'opflags' field is currently untyped 'mod').
  3. device_load's result could NOT be reliably read by a freshly-
     constructed falu2/falu2i (5+ independent attempts, varying addr_mode/
     extmode/dst_lo/dst_ext9/index-source/padding -- all FAILED, silent
     zero). One EXACT byte-verbatim copy from a real compile DID work
     (pilot18) but the specific field combination that made it work could
     not be isolated in the time available.
  4. device_load DOES reliably forward directly to device_store
     (addr_mode=0x56, verbatim structural fields) -- HW-VALIDATED,
     reproduced 3x.
  5. device_load DOES reliably feed iadd2 via ONE specific verbatim anchor
     (kernels/pilot_immadd.metal: srcA=0x88/opc_tail=0x15/opc_tail2=4/
     dst=0, addr_mode=0x44, extmode=0, dst_lo=1/dst_ext9=1, space=0x10) --
     HW-VALIDATED (pilot22, pilot32, and now P1's/P2's integrated use),
     with the EXP-0082/0083 fields (index_reg/idx_off/elem_size/base_slot)
     safely variable on top.
  6. reg_move (the EXP-0087-proven encoding) FAILED to correctly read a
     GPR that falu2/falu2i had just written (pilot25/26/29, 3x). EXP-0087's
     OWN validated cases all sourced from UNIFORM slots (its whole carrier
     was uniform_mov-based) -- this experiment's attempt to move a
     genuinely _agc.main-computed value is a materially different,
     apparently NOT reliably synthesizable case with current understanding.
  7. device_store's `extmode` byte = 2*(source GPR) when addr_mode=0x54
     (ALU-forwarded) -- confirmed 3x independently (own finding, refines
     EXP-0082's "implicitly supplied" note into a concrete formula).
  8. Two base_slot transcription bugs (P3's two loads had base_slot 1/2
     swapped) and two field-formula bugs (P1's dst_lo/dst_ext9 for a device
     load, iadd2 store addr_mode, P3's `space` and `opflags` bytes) were
     found and fixed by directly diffing a hand-reconstructed program
     against its real-compiled byte-verbatim source -- 0 remaining diffs
     for P3.
  REDESIGNED all 4 programs around findings 1/2/4/5/7 (avoiding 3 and 6
  entirely). RESULT: P1 and P2 and P3 now match their independently
  computed Python oracles EXACTLY on real M4 hardware (P1: 7.5 float chain
  result + 1000000100 int result; P2: byte-exact store addresses/values at
  two different computed offsets; P3: 51.5 loop+select result, plus a
  liveness-violation case that revealed the corruption propagates to BOTH
  later readers of the shared register, not just the next one -- corrected
  oracle before freezing PRE_REGISTRATION).
  P4 (register-pressure/move) COULD NOT be made to work in the time
  available -- device_load/falu2i seeding into reg_move both fail per
  finding 6. Documented as a first-class NEGATIVE RESULT with raw evidence
  (work/pilotP4/), not silently dropped.
  Proceeding to PRE_REGISTRATION.md / CAPTURE_CONTRACT.json / a lean
  capture harness for P1/P2/P3 (the working programs), given severe
  remaining time budget.
- 2026-08-27T23:15 -- Froze PRE_REGISTRATION.md + CAPTURE_CONTRACT.json (24
  cases across P1/P2/P3; P4 formally excluded, documented as a negative
  result). Wrote the lean gate set: run.py (smoke gate + append-only
  capture, single-threaded, one process per case, hard 45s per-case
  timeout), verify.py (--selftest using a REAL recorded hardware fixture
  per CODEX gate (e); --seqtest state machine; --preflight/--between-runs/
  --captured; between-runs gates ONLY on authored_*_sha256, per the
  orchestrator's explicit correction about NOT gating on live git HEAD),
  analysis.py, make_manifest.py.
  Gate sequence run clean: selftest PASS, seqtest PASS, manifest --check
  PASS, preflight PASS.
  RUN01 (m4-20260827-run01): 24/24 cases STATUS=OK, 24/24 matched oracle.
  between-runs: PASS (authored hashes unchanged).
  RUN02 (m4-20260827-run02): 24/24 cases STATUS=OK, 24/24 matched oracle.
  --captured: PASS -- 01_results.jsonl BYTE-IDENTICAL across both runs
  (sha256 3c7949547ad6e3a4e74067fc43d688507b97937ba9a45253098b8b604081d59).
  01_timing.jsonl correctly differs (nondeterministic fields kept out of
  the gated file, per CODEX gate (d)).
  INCIDENT (self-caught): `rm -rf work/` before the gated runs deleted the
  ~30 informal pilot-probe artifacts that shaped this design (they lived in
  scratch `work/`, which is correct disposal for scratch, but left the
  DECISIVE findings without a permanent raw artifact -- a real gap against
  CODEX's evidence-preservation rule). Fixed by writing
  diagnostics/redecisive.py, an independently-authored re-derivation of the
  5 most decisive findings (opflags=3 requirement, device_load->falu2i
  failure, device_load->store success as a control, reg_move failure,
  extmode=2*data_reg formula), run fresh against real M4 hardware and saved
  to diagnostics/redecisive_output.txt -- all 5 reproduced identically to
  the original (now-deleted) pilot runs. The full 33-probe exploration
  trail itself is NOT reconstructed (impractical and unnecessary -- the 5
  re-derivations cover every claim actually cited in PRE_REGISTRATION.md/
  RESULTS.md); this is disclosed as a limitation, not hidden.
  Proceeding to RESULTS.md.
- 2026-08-27T23:45 -- Wrote RESULTS.md (per-program pass/fail, operand-field
  matrix, every documented-field-model correction found, per-family
  CONFIRMED/REFINED/REFUTED verdicts, the P4 negative result, DRV-ISA-01
  can/cannot-generate statement, clean-room attestation). Re-ran
  verify.py --selftest / --seqtest / --captured one final time: all PASS.
  Refreshed manifest.json. EXPERIMENT COMPLETE:
    - 24/24 cases matched oracle, 2 independent hardware runs, byte-
      identical gated records.
    - P1/P2/P3 CONFIRMED working hand-built whole programs.
    - P4 an honest, evidenced NEGATIVE result (reg_move composability gap).
    - 2 new field-semantics findings (falu2 opflags=3 requirement,
      device_store extmode=2*data_reg formula) plus a scope-narrowing
      correction to EXP-0087's reg_move claim -- all with permanent raw
      evidence in diagnostics/.
  No commits made (per dispatch instructions -- orchestrator reviews and
  commits).
