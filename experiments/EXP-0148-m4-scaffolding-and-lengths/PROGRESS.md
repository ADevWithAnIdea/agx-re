# EXP-0148 progress log

- 2026-08-28 T0 — read CLAUDE.md / CODEX.md / SUBAGENT_BRIEF.md / FIELD-SWEEP-PROTOCOL.md /
  docs/evidence-classification.md. Created experiment dir. Copied `tools/agx-isa/{db.json,
  isadb.py,roundtrip_test.py,validation.json,validate_labels.py}` into `work/isa_copy/`
  (db.json sha256 6f082cc4…, isadb.py sha256 aa4791f6…). Live tree untouched.
- T1 — baseline `python3 tools/agx-isa/roundtrip_test.py` = 302 OK / 0 FAIL (confirmed).
- T2 — wrote `analysis/tokenize_corpus.py`; tokenized all 1080 own-MSL corpus hex files
  (`experiments/EXP-M4-13-full-corpus/hex`, 587 586 bytes).
  Baseline strict walk: 803/1080 files clean, 395 390 leftover bytes, 24 613 instrs.
  Baseline resync walk: 4 902 gap bytes (0.83 %), 78 979 instrs.
- T3 — wrote `analysis/classify_scaffolding.py` + `analysis/continuation_test.py`;
  produced `analysis/context_stats{,_clean}.json` and `analysis/continuation_clean.json`.
- T4 — wrote `analysis/dump_context.py`; read raw windows for the three flagged
  over-consumers. KEY OBSERVATION (desk, structural): in the low-nibble-9 float group the
  op-select (byte+2 bits[2:0]) values {0,1} are exactly the byte+2 values already listed as
  the 4-byte compact form (0x18/0x19/0x21/0x30/0x31/0x38/0x39). The `6 + 2*(byte+4 & 3)`
  extension is being applied to those, so byte+4 — which is the NEXT instruction's leader —
  selects a bogus length. Hypothesis formed; pre-registration next.
- T5 — built the A/B variant harness (`analysis/make_variant.py`, `make_variant2.py`,
  `ab_run.sh`, `ab_diff.py`, `tools/rt_shim.py`). Metrics for every variant are in
  `raw/ab/<variant>/metrics.json` with the full token streams beside them.
  Baseline (`isa_copy`): roundtrip 302/0, strict clean 803, strict gaps 395 390, resync gaps 4 902.
  * `h1_lo9`  (lo-9 opsel {0,1} -> 4)                : 804 / 395 264 / 4 878  ACCEPT
  * `h1b_coord` (0x26/0x2e -> 6+2*(b4&3))            : 825 / 389 944 / 4 630  ACCEPT
  * `h1_h1b`                                          : 827 / 389 702 / 4 598  ACCEPT, 24 fixed 0 broken
  * `h2_half` (0x10 opsel {0,1} -> 4, no descriptor)  : 790 / 398 254 / 5 338  REFUTED (undecodable)
  * `h2_half_desc` (+ half_compact4 descriptor)       : 800 / 395 886 / 4 898  REFUTED (7 broken)
  * `h2n_desc` (0x10 narrow byte+2 set + descriptor)  : 806 / 395 430 / 4 888  partial
  * `h4_nb10` ((byte+2 & 6)==6 -> 10, no descriptor)  : 798 / 396 050 / 5 024  REFUTED (undecodable)
  * `h4_nb10_desc` (+ b_alu10_lo6 descriptor)        : 804 / 395 106 / 4 868  ACCEPT, 1 fixed 0 broken
  * `final3` = h1 + h1b + h4 + h2-narrow (+2 descs)  : **832 / 389 368 / 4 548**, roundtrip 302/0,
    30 files fixed, 1 broken (`dec_n8__h2_multi`, whose alignment is chained off an
    `op04_len8` token that is itself the flagged over-consumer).
  * every `op04_len8` length candidate (2 / 4 / byte+1-conditional) measured WORSE than
    `final3` and several break the `cubearray_coord_const` round-trip case -> op04 stays OPEN.
- T6 — designing the hardware arm HW-LEN-1 (the 2-byte `mov_imm` length probe).
- T7 — RESUMED after a server-side kill (coordinator message). Re-oriented from PROGRESS.md and
  `raw/`; confirmed `work/isa_copy/{db.json,isadb.py}` still hash-match the live tree
  (6f082cc4… / aa4791f6…), so nothing had moved under me.
- T8 — DECISION: **no hardware arm.** Three GPU-contending siblings (EXP-0139/0141/0146) were
  live and `FIELD-SWEEP-PROTOCOL.md` §7 records that concurrent sweeps contaminate each other.
  A fault observed under contention is unattributable; the Prime Directive prefers no result to a
  tainted one. The carrier was still built and verified (`work/hw/add.bin`, `falu2` at
  `_agc.main+0x20`) so the successor probe is cheap; **nothing spliced was dispatched.**
- T9 — measured every one of the 23 under the corrected tokenizer. **`falu2_ext8b` → 0 firings**
  in both walks (was 45 / 146): it is 100 % a length-rule artifact.
- T10 — continuation test on the corrected stream found three perfect (1.000) separators:
  `tg_atomic_prep` → `frame_marker_compact` (byte+4 bit5, n=34, 34/34 have a trailing word);
  `simd_shuffle` → `n2_compact2` (byte+9 bit7, 7/7 vs 0/120); and `b_alu14_prep2` → 61/62 always
  immediately precedes `b_alu14_c83`. The strong-looking `device_load` → `n3_word` separator
  (0.994) was **refuted** — all 10 carriers sit in a desynchronised region.
- T11 — `variant_final4` (= h1 + h1b + h4-without-the-tg_atomic_prep-carve-out + h2-narrow,
  plus descriptors `half_compact4`, `b_alu10_lo6`, `tg_atomic_prep10`): roundtrip **302/0**,
  clean **832**, strict gaps **389 368**, resync gaps **4 548**; 30 fixed / 1 broken.
  `tg_atomic_prep` 8→10 bytes absorbs 34 phantom tokens with ZERO metric change.
  `variant_final4_del` additionally deletes the now-unreachable `falu2_ext8b` and 8-byte
  `tg_atomic_prep`: roundtrip 302/0, all metrics byte-identical. Deletion verified safe.
- T12 — `simd_shuffle` 12-byte form built and **rejected** (roundtrip 300/2, 2 files broken):
  recorded as an open lead, not proposed. `cubearray_coord_const` shown unreachable — its
  `f0 c0 04` signature is interior to `tex_addr_setup` in its own naming kernel.
- T13 — EXP-0099 §6.1's XOR example `4b 85 16 07 02 08 00 00 00 00`, previously decodable under
  NO family, now decodes as `b_alu10_lo6` (len 10); its counterpart is unchanged.
  `length_rule_gaps.b_alu10` can be marked RESOLVED.
- T14 — deliverables written: `analysis/scaffolding_classification.md` (23 = 3 continuation /
  13 genuine / 7 non-instruction), `analysis/proposed_db_changes.json` (4 length patches,
  3 additions, 2 deletions, 5 metadata updates, 6 flagged-not-changed),
  `analysis/field_verdicts.json`, `RESULTS.md`, `README.md`, `manifest.json`. No `git commit`.
