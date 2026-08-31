# EXP-0217 — TRIAGE

Every item in `experiments/EXP-0216-descriptor-identity/analysis/proposed_db_edits.json`,
classified **before** any file was edited. Categories are the ones the dispatch names:

* **(a) prose / semantics only** — `note`, `semantics`. Not read by `isadb.decode_one`;
  tokenization-neutral by construction.
* **(b) match-bit change** — a tokenization change. Must be measured in an isolated
  variant tree before it may be taken.
* **(c) field add / remove / rename / metadata** — moves the field population, and a
  rename moves an evidence row's `label` onto a new name.
* **(d) refused** — the edit the proposal implies is stronger than the evidence behind it.

## The table

| # | Proposal | Category | Disposition | Why |
|---|---|---|---|---|
| **P1a** | `imad.srcC_lo` (byte+5): role is a multiplicand register selector, `reg = v >> 2`; the note's "ROLE UNRESOLVED — never swept" is false | **(a)** | **APPLIED** | Host oracle 64/64 in-domain; both addend models 0/64. "Never swept" also contradicts this row's own `range` in `validation.json` (byte+5 dense 0..255, 512 records). |
| **P1b** | `imad.srcC_lo` `type: "mod"` → `"reg"` | **(c)** metadata | **APPLIED** | `type` is documentation metadata — `isadb.decode_one` never reads it (only `gen_agx3_xml.py` / `gen_encoding_tables.py` do). No name, span, match, or label moves. The byte selects a register; the descriptor said "modifier". |
| **P1c** | `imad.srcB` (byte+6): the other multiplicand; **no `srcA` field exists** | **(a)** | **APPLIED** | 68/128 in-domain, the other 60 bit0-killed; byte+6-addend model 0/128. |
| **P1d** | **rename** `srcC_lo` to "a multiplicand name" | **(c)** | **(d) REFUSED** | EXP-0216 supplies no name and says A-vs-B is undecidable. Any name placed opposite `srcB` re-asserts the ordering. A rename also carries this row's `hardware-run` label onto a new name — the DEF-0166-2 / `tex_write.rsv10` hazard EXP-0212 refused. db.json already keeps two refuted names for exactly this reason (`iminmax.dst_full`, `mov_zext16.src_flag`). |
| **P1e** | Re-point EXP-0154's `imad.srcB` verdict onto the row now called `srcB` | — | **(d) REFUSED — and already respected** | EXP-0216's own `do_not`. Both rows already carry a "NAME MOVED BY DEF-0160-6" notice naming the byte each was measured on. |
| **P2a** | `cvt_f2h` match over-fit, with counts (6 550 / 6 555 fail; low nibble holds on 6 515) | **(a)** | **APPLIED** | Re-derived from `q2_sibling.json`: 6 555 records, 5 satisfy, 5 315 satisfy `cvt_f2h_dst`, low-nibble-1 count 6 440 + 5×15 = 6 515. |
| **P2b** | option (a): match `[[0,8,17]]` → `[[0,4,1]]` + add `dst (4,4)` | **(b)** + **(c)** | **(d) REFUSED — measured** | `work/var_m1`. **`roundtrip_test.py` 1 FAILURE.** Reassigns 5 corpus and 5 record tokens; adds an evidence-free `dst` row. |
| **P2c** | option (b): move the four `cvt_f2h` field citations to `cvt_f2h_dst` | **(c)** | **(d) REFUSED** | EXP-0216's own §3 verdict: the four rows are safe where they are (identical spans), and `cvt_f2h.src` is **not** freely re-pointable — 1 200 of its 1 280 records fall outside `cvt_f2h_dst`'s `(28,4)==8` pin. |
| **P3a** | `bf_alu` match over-fit, with counts (0 / 13 144 satisfy) | **(a)** | **APPLIED** | Re-derived: 13 144 records, 0 satisfy, byte+1 fails on all 13 144, byte0 fails on 12 626; 7 972 satisfy `bf_add_dst`, 2 652 `bf_mul_dst`. |
| **P3b** | "no change is required for the three suspect field rows" | — | **NO EDIT (as proposed)** | Per swept byte the three descriptors assign identical spans. Recorded in the semantics. |
| **P3c** | "if widened, do byte 0 and byte 1 only" — match → `[[0,4,1]]` | **(b)** | **(d) REFUSED — measured** | `work/var_m2`. **`roundtrip_test.py` 2 FAILURES.** Ties `bf_alu` with `bf_alu8_var` at 4 match bits and, winning on list order, swallows **all 135** of its resync firings. |
| **P4a** | Record the eight accepted byte+2 bfloat-add encodings, bounded to the EXP-0171 NAT carrier | **(a)** | **APPLIED** | On `bf_add_dst`, in §7 wording, with the sweep line numbers and the current tokenizer disposition. |
| **P4b** | The same question for the **multiply** side | **(a)** | **APPLIED as UNTESTED** | EXP-0171 observed only `0x1d` as the coherent multiply; no alias family was established. Recorded on `bf_mul_dst` so nobody assumes symmetry. |
| **P4c** | `isadb._n1_len` bfloat gate | — | **NOT RE-APPLIED (already in at `1fd2f16f`)** | Independently re-measured here — see RESULTS §4. It is strictly length-additive on both record sets (0 reassignments). |
| **P4d** | (implied) widen `bf_add_dst` / `bf_mul_dst` match to cover the seven aliases | **(b)** | **(d) REFUSED — measured** | `work/var_m3`. Round-trip passes and the corpus totals are unchanged, but **0 of the 37 corpus tokens it re-claims carry byte+1 == 0x00**, the only byte+1 EXP-0171's alias sweep held; and the `bf_mul_dst` half (22 of the 37) was invented by symmetry from zero evidence. |
| **P5** | `mov_zext16.src_reg` is also the destination | **(a)** | **ALREADY PRESENT — no edit** | db.json's field note and semantics already say "used as BOTH source and destination", with the N = 0..10 fit and the N ≥ 11 no-op bound. Verified, not re-asserted. |
| **P5b** | The `(8,7)` inertness re-derived in a second experiment | **(a)** | **APPLIED** | One sentence on `mov_zext16.src_flag`: EXP-0154 **and** EXP-0161, one identical 16-register vector across 128 values. |
| **P6** | `iminmax (40,8)` `dst_full`, `half_alu (32,8)` `ctrl` — frozen name refuted, current name unconfirmed | — | **NO EDIT (as proposed)** | EXP-0216 says "no edit. Open a targeted probe." Both notes already carry the refutation and the historical-name rationale. Honoured verbatim. |

## Counts

| category | items |
|---|---:|
| (a) prose / semantics only — **applied** | **7** |
| (c) field metadata — **applied** | **1** |
| (b) match-bit — **measured, all three refused** | **3** |
| (d) refused for evidence reasons (incl. the 3 above) | **6** |
| already satisfied / no edit by the source's own proposal | **4** |

Nothing was renamed, nothing was added, nothing was removed, no `label`, `range`,
`evidence` list, `target`, `start` or `width` changed anywhere.
