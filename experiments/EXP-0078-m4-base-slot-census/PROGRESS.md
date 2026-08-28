# EXP-0078 progress log (append-only)

Operational note recorded at open (2026-08-27): per the governing directives
(`CLAUDE.md` / `CODEX.md`) all testing runs **locally on the M4** through the
public Metal API; the A18 Pro is **hands-off** (no SSH, no probing, no
reference); `macvdmtool` is never run against any target. Splice probes run
one changed field per case, every case in its own process, hard timeouts
everywhere. If the host wedges: STOP, mark BLOCKED, wait for manual reboot.

## 2026-08-27 (open) — M1: tasking + mandatory reading complete

- Read in order: `CLAUDE.md` (governing law), `CODEX.md` (binding process),
  `experiments/SUBAGENT_BRIEF.md`. Then the promoted pattern
  `../EXP-0076-m4-buffer-robustness-matrix/` (README, PRE_REGISTRATION,
  run.py, verify.py incl. selftest, analysis.py, make_manifest.py,
  CAPTURE_CONTRACT.json, RESULTS.md, PROGRESS.md), the quarantine record
  `../EXP-0075-m4-typed-format-conversion-batch2/QUARANTINE.md` (three
  contract-bug classes: (1) payload truncation by a racing worker thread ->
  single-threaded harness with fflush/ferror exit discipline + non-recorded
  smoke gate; (2) frozen gate-sequence contradiction (`--between-runs`
  requires raw/ to exist while `--selftest` was PRE_GPU-only -> run 02
  structurally unreachable) -> mandatory gate-sequence state-machine
  self-test; (3) capture-time hash binding makes post-capture repair
  impossible -> everything must be provable pre-capture), and the sibling
  `../EXP-0077-m4-mem-offset-semantics/` (PROGRESS only; concurrent
  MEM-01..05 offset-semantics experiment, never edited by us).
- Task: Part-II questionnaire items **MEM-15, MEM-16, MEM-17**
  (`APPLE9_RE_IMPLEMENTATION_GAPS.md`, "P0 — Memory addressing and
  robustness"): base-slot capacity, alias/hole/reservation map, and
  unpopulated/out-of-range slot behavior for load/store/atomic.
- Background studied: `docs/isa/README.md` (memory family + uniform/binding
  sections: `device_load`/`device_store`/`atomic_rmw`/`atomic_mem` are 14-byte
  memory-family ops with **base_slot at byte+4, 8 bits**; buffer bases are
  preloaded into uniform/binding slots supplied by the command stream/USC,
  not in shader code), `EXP-0012-memory/RESULTS.md` (base_slot HW-spliced:
  slot 0<->out(buffer0), 1<->a(buffer1); threadgroup uses slot 0x08;
  constant reads byte-identical to device), `EXP-0011-compute-cmdstream`
  (Tier-2 resource table, 8 B/slot in binding order, HW-validated 1/2/4/8
  buffers), `tools/agx-isa/db.json` (authoritative descriptors),
  `tools/agxtest` (splice testbed: shdump -> archive; FailOnBinaryArchiveMiss
  proves the spliced archived bytes execute), `tools/shdump/agxparse.py`
  (`--locate _agc.main` gives the absolute file offset for in-place splice),
  `RT-1a-FIX` (the working splice recipe this experiment scales up).
- Key prior facts being built on: base_slot byte+4 of the 14-byte memory
  family; EXP-0018 evidence that base_slot is a **base-register-table slot,
  not necessarily the Metal buffer index** (two atomic kernels whose target
  buffer sits at different MSL indices compiled byte-identical), i.e. the
  slot<->binding mapping is per-pipeline and exactly what this census maps.
- Tooling constraint honored: `tools/*` are read-only (invoked/imported,
  never edited); all scratch under this directory's `work/` (which must be
  empty at every gate, per the EXP-0076 closed-root discipline).
- No GPU dispatch has occurred yet.

## 2026-08-27 (pre-freeze) — M2: feasibility probe complete (scratch, deleted)

Pre-freeze authoring-feasibility probe, run in `work/feas/` (scratch; deleted
after this entry; nothing from it is evidence — the contracted runs are the
evidence). What ran: our own generators (`gen.py`, `gen2.py`) emitting the
kernel families below, compiled with `tools/shdump` (built from the read-only
tool source into the scratch dir), extracted with `tools/shdump/agxparse.py`,
walked with `tools/agx-isa/isadb.py` (imported read-only), and executed with
`tools/agxtest/agxrun.m` (public Metal API only, archive +
`MTLPipelineOptionFailOnBinaryArchiveMiss`, our own spliced bytes). Findings
that shaped the frozen design (all to be re-established by the contracted runs):

1. **MSL buffer-index limit.** `[[buffer(N)]]` compiles for N = 0..30 only:
   `error: 'buffer' attribute parameter is out of bounds: must be between 0
   and 30`. So the maximum direct-binding population is **31 buffers**; the
   frozen census kernel uses all 31 (out=0, b1..b29=1..29, idxbuf=30).
2. **Probe-load identification by differential compilation works exactly.**
   census31(probe=b1) vs census31(probe=b2): `_agc.main` differs in EXACTLY
   ONE byte (main+430), the base_slot byte of the probe load (verified +4 of
   a 14-byte 0x67 load; slot 1 vs 2). census4 (gid-variant) likewise: one
   byte at main+56. The frozen identification stage uses this diff rule for
   the census kernels.
3. **Thread-invariant loads hoist into the constant program.** With
   constant-index witness reads, the compiler hoisted 7 of them (b1..b7 plus
   the idxbuf read) into `_agc.main.constant_program` (whose own loads carry
   slots {0,2,4,6,8,10,12} in a currently-undecoded uniform-pipe encoding);
   the main program held witness loads for slots 8..29 plus the probe (slot
   1). gid-variant indices (out[k]=b_k[gid]) force ALL loads into the main
   program — used for the frozen `capacity` and `census4` kernels. This split
   is itself MEM-18/19-relevant and is recorded as an observation.
4. **Baseline hardware run is fully correct with 31 bound buffers** (out[0]
   =P(1,5), out[k]=P(k,0) k=1..29, out[30]=5), through the spliced-archive
   path (`PIPELINE_SOURCE archive`, STATUS OK).
5. **Spot splices (census31 probe slot byte):** slot 2 -> P(2,5), 29 ->
   P(29,5), 30 -> P(30,5) (the idxbuf binding); slots 31, 32, 63, 127, 255
   -> 0x00000000 with STATUS OK (no fault); slot 0 -> P(5,0) — NOT buffer 0
   (out), and word 0 under a word-5 probe (offset anomaly, hypothesis: a
   uniform-register window); slot 128 -> the same value as slot 0 (alias).
   These shape H2/H3 but are re-established by the contracted sweep.
6. **Store probe.** The probe store is the unique `device_store` whose
   base_slot != the out slot (byte+4 = 29 = the tgt MSL index); the v2 swap
   (tgt at 28) reorganizes 38 bytes (register cascade), so the frozen store
   identification uses the decode rule (unique non-out store) with the v2
   value as cross-check.
7. **Atomic probe — the base selector is byte+5 for this form.** For
   abuf(29): atomic = `67 11 54 00 00 1d 80 80 01 02 00 00 7c 02`
   (byte+4=0x00, byte+5=0x1d=29); for abuf(28): byte+5=0x1c. Splicing
   byte+5 29->28 retargeted the exchange (out[0] P(29,5) -> P(28,5));
   splicing byte+4 0->1 made the exchange return 0. So the DB's
   atomic_rmw/atomic_mem `base_slot`@byte+4 mapping is at minimum PARTIAL for
   these emitted forms (byte+4 is live but not the selector; byte+5 is).
   `tools/agx-isa` is read-only for this experiment: recorded for the
   orchestrator, not edited here.
8. No fault, hang, or wedge at any tested slot (0,2,29,30,31,32,63,127,128,
   255 across load/store/atomic shapes). All runs STATUS OK.

The frozen matrix therefore: census31 full 0..255 slot sweep (256 cases),
census4 boundary-subset sweep (76), capacity baseline (1), store probe
(8), atomic probe (10) = 351 cases per run.

## 2026-08-27 (pre-freeze) — M3..M5: artifacts authored, contract frozen, selftest green

- **M3 kernels + harness.** Nine authored kernel sources in `kernels/`
  (census31 + _v2, census4 + _v2, capacity, storeprobe + _v2, atomicprobe +
  _v2); `harness/probe.m` (public-API-only, single-threaded, SIGALRM
  watchdogs 120 s compile / 100 s dispatch, fflush+ferror exit discipline,
  one complete JSON record per case incl. the out dump and every bound
  buffer dump, the binding layout captured by construction) and
  `harness/build.sh` (compiles probe.m + the read-only tools/shdump source
  into the experiment's work tree).
- **M4 runner/analysis/verifier/manifest.** `run.py` (frozen matrix: 351
  cases = 256 census31 + 76 census4 + 1 capacity + 8 store + 10 atomic;
  single authoritative key sets; pre-capture kernel compile + probe
  identification stage; NON-RECORDED smoke gate `c31_load_slot_1`; one
  case per fresh process; fault = recorded result), `analysis.py`
  (deterministic classification + hypothesis verdicts; the cross-run gate
  imported from run.py), `verify.py` (fail-closed static/captured checks;
  `--selftest` with 36 synthetic cases: 15 schema-gate mutation cases, 6
  smoke-purity cases, witness-corruption-is-valid-evidence,
  garbage-differ-is-reported-not-gated, and the **gate-sequence state
  machine** walking one synthetic root through PRE_GPU -> run01-present ->
  run02+analysis-present, proving every contracted gate runnable,
  satisfiable where invoked, and fail-correct where forbidden — the
  EXP-0075 fix), `make_manifest.py` (hashes everything but itself;
  contract: --write && --check immediately before every manifest-dependent
  gate).
- **M5 freeze.** `PRE_REGISTRATION.md` (hypotheses H1..H6, exact method,
  351-case matrix with sampling justification, schemas, timeouts, repeat
  policy, promotion rule + full gate sequence, disclosed pre-freeze
  feasibility), `README.md`, PRE_GPU `RESULTS.md` placeholder,
  `CAPTURE_CONTRACT.json` (authored hashes; 17 paths).
- **The selftest caught a real bug before any capture**: probe_word is the
  little-endian byte image of the 32-bit word; the first cross-run-gate
  draft decoded it as a big-endian int, which would have classified every
  pattern read as garbage and silently disabled the deterministic-class
  repeat gate. Fixed in the single authoritative implementation
  (`run.probe_word_value/class`), which analysis and verify both import.
- `python3 -B verify.py --selftest` → **PASS 36/36** (no Metal, no device).
- Next: harness link check (no Metal calls), then the contracted
  pre-capture gates, then run01.

## 2026-08-27 (capture) — M6: pre-capture gates green, run 01 captured

- Contracted sequence executed in order: `verify.py --selftest` **PASS
  36/36** (15 schema-gate mutation cases incl. ident-decoupling and both
  cross-run classes, 6 smoke-purity cases, witness-corruption-valid and
  garbage-differ-reported cases, and the 11-step gate-sequence state
  machine), `make_manifest.py --write`/`--check` PASS, `verify.py
  --preflight` PASS (PRE_GPU, no raw).
- `run.py --execute --run-id m4-20260827-run01`: harness link-checked
  first (argument-validation exits before any Metal call), host build OK,
  nine kernels compiled, identification recorded pre-capture (census31
  main+430 diff-byte; census4 main+56; storeprobe main+490 unique non-out
  0xe7 store, byte+4=29↔28; atomicprobe main+824 unique atomic, selector
  byte+5=29↔28), NON-RECORDED smoke case `c31_load_slot_1` passed, then
  **351/351 cases recorded, all status `ok`** — zero cb_error, zero
  watchdog, zero proc_fail, zero proc_timeout, zero STOP. No host wedge;
  no reboot needed; `macvdmtool` never run.
- Run 01 headline observations (full record in RESULTS.md): census31 slots
  1..30 -> own buffer word 5 bijectively; slot 0 -> P(5,0) (load-path
  reservation candidate); 31..127 -> 0x00000000; 128..255 exact mirror of
  0..127; census4 slots 0..3 -> own bindings (slot 0 = out); store via
  unpopulated slot discarded, via slot 3 -> buffer 3, via 128 -> OUT;
  atomic exchange via unpopulated selector returns 0 + discards, via 3 ->
  buffer 3, via 128 -> the slot-0 load-path value; capacity kernel reads
  all 31 bindings correctly at once.

## 2026-08-27 (stop) — M7: STOP at the between-runs gate (no post-capture repair)

- `verify.py --between-runs` fails permanently:
  `FAIL ident probe opcode m4-20260827-run01 storeprobe`. Root cause: the
  frozen verifier requires probe opcode 0x67 for every kernel; the store
  probe is a 0xe7 device_store (correctly identified and recorded in
  02_build.json). The gate is unsatisfiable against any real capture —
  EXP-0075's class, masked from --selftest because the synthetic ident
  fixtures were internally consistent but reality-inconsistent.
- The one-line fix was applied, proven sufficient by inspection against
  the run01 identification records, and **reverted**: any post-capture
  verifier change breaks the capture-time hash binding in 00_inputs.json
  (the EXP-0075/0072/0064/0073 quarantine rule). Frozen bytes restored;
  the failure reproduces verbatim.
- Disposition: run 01 retained append-only as single-run,
  repeat-unverified process history — NOT promotable evidence. RESULTS.md
  carries the STOP banner, the complete OBSERVED record, the INTERPRETED
  candidate findings, and the successor requirements (reality-consistent
  selftest fixtures; opcode-from-record check; re-register the same
  matrix with run01's observations as hypotheses).
- Final tree state: raw/m4-20260827-run01 complete (7 files), manifest
  regenerated, work removed, no __pycache__, `--preflight` correctly
  fails (raw exists) and `--between-runs` fails on the recorded defect.
- No further device operations were performed after run 01.
