# EXP-0206 progress log (append-only)

- 2026-08-30 ~11:50Z — dir created; pinned db.json/isadb.py/agxparse.py/shdump.m/
  agxrun_persist.m/persistrun.py. Nothing resolves through `tools/`.
- 2026-08-30 ~11:55Z — kernels authored (`k_cf206.metal` 6 loop shapes,
  `k_cl206.metal` 9 call shapes spanning the LINK and ORDERING dimensions).
  `PRE_REGISTRATION.md` written and frozen BEFORE any build.
- 2026-08-30 ~12:00Z — pushed + built on the neo (192.168.170.254). shdump and
  agxrun_persist built from PINNED sources.
- 2026-08-30 ~12:02Z — CENSUS run 1 (pre-freeze calibration). Found: `ret` in ZERO
  carriers. Root cause: the callee lives in its OWN symbol region of the shader
  __text section; `_agc.main` holds the CALL, not the RETURN. `compile_carrier`
  rewritten to carve every region separately.
- 2026-08-30 ~12:05Z — CENSUS run 2. `if_push` scope_kind 0x1a (LOOP-ITERATION)
  REACHED on all six loop carriers — the region kind EXP-0184 named as its own
  limitation. `pop_reconverge` scope 0x04 AND 0x24 both compiler-emitted.
  `ret` found in leaf callees (linkmode 0x02). NON-LEAF callees: walk dies on the
  undecodable 6-byte word `ef 02 54 00 00 50` immediately before `8f 12 54 00`.
- 2026-08-30 ~12:07Z — bounded-resync walk added (contract amendment 1). Non-leaf
  `ret` (linkmode 0x12) now located in c_mid / d_mid / d_out / s_big. `cl_atomic`
  carries a REAL compiler-emitted `ret_luse` `8f 12 56 00`.
- 2026-08-30 ~12:08Z — census refutes H6's premise: NO natural mid-program `stop`
  exists (follows_code False at all nine). Contract amendment 2 adds the
  CONSTRUCTED mid-program stop over the optional 4-byte frame marker.
- 2026-08-30 ~12:09Z — arms generated: 132 arms, 12,173 cases.
- 2026-08-30 ~12:11Z — CAPTURE_CONTRACT.json frozen; `verify_remote.py` run as a
  SEPARATE step: 20/20 files match. Next: pilot, then the gated pair.
- 2026-08-30 ~12:15Z — PILOT p01 (calibration, `--limit-values 32`, 434 cases,
  101.6 s = 0.234 s/case). Findings, all calibration:
  * the SYNTHESIZED mid-program stop TERMINATES (sentinel present, all 32 value
    words still POISON) — the section-9 positive control in the termination
    dimension FIRES;
  * the FINAL stop with byte0 -> 0x00 is still fully correct — that control does
    NOT fire, so the final-stop arm is heading for UNRESOLVED, as pre-registered;
  * `if_push.scope` at the LOOP-ITERATION push of cf_nl2/cf_nlif (compiled 0x56)
    FAULTS for every bit-1-clear value; at cf_nl3+182 (compiled 0x54) it does not.
    The pre-registered "correct iff bit 1 set" rule is therefore already partly
    refuted, which is a result, and the field clearly MOVES;
  * `ret_luse.linkmode` faults at all 8 sampled values (none has v&7 == 4).
  * `not_written` reclassified as a VALID payload (contract amendment 4).
- 2026-08-30 ~12:18Z — COURTESY NOTICE (FIELD-SWEEP-PROTOCOL section 7): the
  `if_push.scope` and `ret_luse.linkmode` arms produce `ErrorHang` device resets
  in bulk. Expect device-level resets on 192.168.170.254 for the next ~2 hours.
  No hang budget and no abort path, by design (protocol 3c).
- 2026-08-30 ~12:19Z — contract re-frozen (amendment 4); verify_remote 20/20.
  Starting gated run01.
- 2026-08-30 ~12:30Z — **run01 KILLED at 152 cases and RETAINED.** Measured
  1.756 s/case with 46% faults against the pilot's 0.234 s/case. The process table
  showed SIBLING EXPERIMENTS sweeping the same GPU (EXP-0200, EXP-0201, EXP-0202,
  EXP-0207 — up to **9 other GPU processes**). The full 12,173-case set would have
  taken ~6 h per run. Run01 is left exactly as it is, never topped up, id never
  reused, cited by no verdict.
- 2026-08-30 ~12:35Z — the user published
  `/RE_EXPERIMENT_PROCESS_CORRECTIONS.md` (NORMATIVE, overrides the
  dispatch gates where they conflict). Implemented before any gated dispatch:
  * **Gate A** actual-byte ledger — requested value, requested bytes, ACTUAL bytes
    read back out of the final dispatched blob, independently re-decoded value,
    program sha256, absolute instruction offset. `ledger_ok` on every case.
  * **Gate C** competing semantic models with a per-case prediction
    (`analysis/models206.py`, 3–4 models per field) and the five-bucket
    observation vocabulary correct/coherent/dead/reject/invalid.
    `sem_checked == 0` can never produce `hardware-run`.
  * **Gate E** second gated run in REVERSED case order; process table sampled into
    `raw/<run>/procs.jsonl` at start, every 100 cases, and at end, so "the machine
    was busy" is a MEASUREMENT and not prose.
  * `PRE_REGISTRATION_A2.md` frozen BEFORE the first gated dispatch; run01 and the
    pilot retained as the superseded record.
  * gate self-test extended to FIVE cases and now also refuses (a) liveness with
    zero semantic checks and (b) an arm whose actual bytes did not match the
    request.
- 2026-08-30 ~12:47Z — arms regenerated under `targets206.SELECT`: 52 arms,
  5,231 cases, three structurally different carrier classes for every inertness
  target. Contract re-frozen; verify_remote 22/22. Smoke test s01: 36/36
  `ledger_ok`, semantic buckets populated, 7–9 sibling GPU processes recorded.
- 2026-08-30 ~12:52Z — gated pair launched: **run03 forward**, **run04 reversed**.
  Run in parallel (the machine already carries 9 sibling agents, so serializing
  bought no quiet and cost hours); the reversed order decorrelates any
  order-dependent artefact. Recorded as a Gate E limitation, not hidden.
- 2026-08-30 ~13:55Z — **run03 COMPLETE: 5,231 cases in 1,107.9 s.** Ledger clean
  (every case `ledger_ok`). run04 still in flight.
  NOTE: the sequential launcher (`sh -c "run03; run04"`) tried to start run04 after
  run03 finished, and `run.py` correctly REFUSED because that id already existed —
  but the refusal message overwrote `work/run04.log`. The log is not evidence;
  `raw/g17p_20260830_run04/sweep.jsonl` is untouched and complete-so-far.
- 2026-08-30 ~14:10Z — first results, all from the gated pair:
  * `stop.reserved` INERT at both stop positions, 730 gated cases, and the
    TERMINATION-DIMENSION CONTROL FIRES BOTH WAYS: a synthesized mid-program stop
    terminates (sentinel + 32 poison words, identical in both runs), and at the
    FINAL stop byte0 -> 0x0f or 0x8f FAULTS reproducibly on three carriers in both
    runs while six other byte0 values are harmless. EXP-0003/EXP-0010's "corrupting
    any of it is a no-op" is thereby BOUNDED, not refuted.
  * `ret_luse.linkmode`: accepted set is `v & 3 == 2` (64/256), NOT EXP-0156's
    `v & 7 == 4`; and at the NON-LEAF return bit 4 (0x10) splits the accepted set
    into 32 correct and 32 different-but-coherent. **TWO DISTINCT VALID PAYLOADS —
    Case C cleared.**
  * `pop_reconverge.reserved`: LIVE. At cf_ifnl+184 the 9 values with a zero LOW
    BYTE are correct and all 43 with a non-zero low byte give one identical wrong
    payload. db.json's single 16-bit `reserved` field is really two.
  * `ret.scoreboard`: 1024/1024 correct across four occurrences spanning the
    ORDERING dimension (nothing outstanding -> load in callee -> store->load across
    the return -> non-leaf frame). EXP-0179's "this carrier cannot ask the question"
    is answered.
  * `if_push.scope`: LIVE at the one occurrence whose compiled value is 0x56
    (128/128 bit-1-set correct, 0/128 bit-1-clear correct), inert at three others
    INCLUDING two more `scope_kind == 0x1a` pushes. Both pre-registered models
    refuted. Cross-run: 122 values common, 122/122 identical.
- 2026-08-30 ~14:40Z — COURTESY (protocol section 7): run04's
  `if_push.scope@cf_nl2+106` arm is producing genuine `hang` outcomes (8 s watchdog
  + child restart) as well as faults on bit-1-clear values. Device resets on
  192.168.170.254 originate here.
- 2026-08-30 19:50Z (neo UTC) — **run04 STOPPED at 3,824 of 5,231 cases and
  RETAINED as a partial.** It was grinding the genuinely hang-heavy
  `if_push.scope@cf_nl2+106` arm (bit-1-clear values produce real `hang` outcomes:
  8 s watchdog + child restart + majority-of-3). Retained exactly as it is, never
  topped up, id never reused. **CORRECTION to my own earlier note:** the "~5 min per
  case" figure was my own polling latency, not device time — on the neo's clock the
  whole gated pair occupies 19:27–19:51 UTC.
- 2026-08-30 19:50Z — `g17p_20260830_run05` launched (shuffled order, seed 206) over
  the FIVE carriers holding the six arms run04 never reached: cf_nl3, cf_ifnl,
  cl_pure, cl_ldret, cl_stacross. A NEW id, not a top-up.
- 2026-08-30 19:52Z — **Gate E ruling adopted** (orchestrator): Gate E is currently
  unmeetable for the whole wave — EXP-0204's dedicated quiet-window helper sampled
  86 times and never found a quiet machine. Every reproducibility axis in this
  experiment now reads `INCOMPLETE - Gate E not met`, and no row claims
  `independently-confirmed`, even where the two runs agree perfectly.
- 2026-08-30 19:52Z — **EXP-0204 foreign-cascade window checked as a COMPUTATION,
  not a claim.** `verdicts206.py` re-scores any hard outcome timestamped inside
  2026-08-30 20:00–20:25 UTC as `measurement_failure`. **Zero of this experiment's
  cases fall in it**: run03 spans 19:27:16–19:45:43Z, run04 19:31:00–19:50:28Z,
  run05 19:50–19:5xZ — all before the window opens. The filter is retained and its
  count (0) is reported per field.
