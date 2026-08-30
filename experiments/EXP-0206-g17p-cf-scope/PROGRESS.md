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
