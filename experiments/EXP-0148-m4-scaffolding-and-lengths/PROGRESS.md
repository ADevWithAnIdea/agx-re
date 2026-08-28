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
