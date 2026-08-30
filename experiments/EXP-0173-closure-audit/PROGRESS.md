# EXP-0173 progress log (append-only)

## M0 — 2026-08-30T09:31Z — frozen
`PRE_REGISTRATION.md` + `CAPTURE_CONTRACT.json` written BEFORE any verdict.
rev `2792d7ca`, db.json `3228476…`, validation.json `65185b3a…`.
26 dirty paths, all under EXP-0168/0171/0172 (device experiments in flight); none mutated.

## M1 — 2026-08-30T09:4xZ — tool gates run + SENSITIVITY-TESTED
`raw/gate_runs.txt`, `raw/mutation_runs.txt`, `analysis/gate_sensitivity.json`.

Recomputed headline **contradicts the status board**:
- `validate_labels.py` → **588 emitter-grade / 1062**, **35 of 166** emittable. Exit 0.
- `docs/P0-P1-CLOSURE.md` P0.6 still says **616/1062 and 41 of 166**. STALE. (H3 CONFIRMED.)

Gate sensitivity (each gate run, then given a defect it is claimed to catch):
- `roundtrip_test.py` baseline PASS.
  - M1 bare-OR `assemble()` (the DEF-0166-1 bug) → **STILL ALL PASS**. Independently
    reproduces EXP-0170 by construction, not by citation.
  - M2 `assemble()` forces dst/srcA/src to 0 → suite FAILS. So it does catch gross operand loss.
  - M3 `falu3.srcA`↔`srcB` swapped in a db.json copy → **STILL ALL PASS**. An operand SWAP —
    the exact `fspecial` defect class — is invisible to a symmetric round trip. NEW.
- `validate_labels.py` baseline exit 0.
  - V1/V1b fabricated `hardware-run` promotion → exit 1, but **only on coverage arithmetic**.
  - V1c same fabrication with all coverage arithmetic recomputed → **exit 0, clean PASS**.
    **The validator never opens an evidence path.** A `hardware-run` label citing
    `EXP-9999/raw/does_not_exist/run.json` passes. It is a schema checker, not an evidence checker.
- `match_overlap_report.py`: 59 overlap / 25 zero-free-bit / 16 vacuous emitter-grade —
  reproduced exactly. Its committed `match_overlap.json` is 3 rows STALE vs current
  validation.json (2 label drifts + 1 `instruction_emittable` true→false); I regenerated,
  diffed, and `git checkout --` restored it, leaving no unrequested edit.
- `work/merge_verdicts.py --dry-run` over every `EXP-01*/analysis/field_verdicts.json`:
  exit 1 (downgrade refusals working), and reports **588→692 emitter-grade, 35→66 emittable**.
  The documented merge command therefore RECONSTRUCTS the discredited headline from committed
  verdict files that were never retracted in place.

## M2 — 2026-08-30T10:0xZ — PROVENANCE.md audited row by row
`analysis/provenance_audit.py` → `analysis/provenance_audit.json`. 171 rows.

**The headline finding is NOT the one I pre-registered (H2 is only weakly confirmed).**
- **0 rows cite an artifact that is absent.** Every cited experiment directory, raw path,
  glob, and git commit in PROVENANCE.md resolves on disk. I looked for the worst thing and
  it is not there. (The extractor needed four fixes to reach this: EXP-G1a-style ids,
  RT-*/REVIEW-* bare dir names, `work/`+`raw/`+`analysis/` being ambiguous between repo root
  and experiment dir, and `file.c:171-172` line suffixes. Each fix is in the script.)
- **3 rows cite NOTHING resolvable at all** — no experiment id, no path, no commit:
  L17 (target identity), L18 (runtime MSL compiles under CLT only), L104 (`agx3.xml` W3
  render). L17/L18 are corroborated by later EXP-0002 rows; L104's claim is re-derivable
  from `tools/agx-isa/gen_agx3_xml.py` + `docs/isa/agx3.xml`, both present — but the row
  points at neither, so the chain CODEX requires is not written down.
- **1 row cites the wrong artifact for its own literal:** L28 claims `0e000000` and
  `1ca01006` and cites `raw/*info.txt` + `raw/determinism.txt`; those bytes are in
  `raw/k05_fma.text.hex` etc. Citation-precision defect, not fabrication.
- **The real weakness: `claim_reproduced` is `not-mechanically-checkable` for 162 of 171
  rows.** The chain proves an artifact EXISTS; it does not prove the artifact SAYS what the
  row says. That is precisely the failure mode that cost 125+ fields in the last day, and no
  tool in the repo closes it. Only 5 rows had a (text artifact x distinctive literal) pair I
  could grep; all 5 passed at analysis level.

## M3 — 2026-08-30T10:2xZ — operand-sanity sweep (the defect class, hunted on purpose)
`analysis/operand_sanity.py` → `analysis/operand_sanity.json`. Four DECISIVE mechanical tests.

**Two NEW members of the "named operand field that cannot be an operand" class:**
- **`cvt_f2h_dst.src` — P1c PARTIALLY PINNED, `hardware-run`, and the instruction IS in the
  emittable 35.** Declares 8 bits; only 4 are choosable (16 legal values, not 256). Any
  claimed range over that field over-states coverage 16x.
- `falu2_uni.usrc` — 7 of 8 bits choosable, `hardware-run`, instruction not emittable.
- `cvt_bf16.src` (0 of 8) reproduced as the known member.

**Clean negatives, worth having:** **0** descriptors have two fields whose spans overlap
each other (P4), and **0** have a field span running past `length * 8` (P5). Those two whole
failure modes are absent from `db.json`.

**Advisory, not a defect but an implementer fact: 10 of the 35 emittable instructions cap
their destination at r0..r15** — a 4-free-bit `dst` with NO extension-named sibling field in
the descriptor (`bf_add_dst`, `cvt_bf16`, `cvt_f2h_dst`, `falu3`, `h_coord_hi`, `hminmax`,
`iminmax`, `mov_imm`, `n2_op6`, `rtq_state_move`). A 4-bit dst nibble is a real AGX compact
form, so this is not automatically wrong — but "emittable" currently means "emittable into the
first 16 registers" for those ten, and nothing in the metric says so.

**Documentation gap:** three of the four named descriptor defects (`fspecial` swap +
`fspecial` dst>=96, `imad` missing `srcA`, `op04_len8` VETO) ARE in the emitter-safety block
of `docs/isa/README.md` (L341-380), and it additionally warns that `falu3`/`falu3_ext` field
NAMES are misleading. **`cvt_bf16.src` being fully match-pinned is NOT there** — it appears
only in the `docs/P0-P1-CLOSURE.md` P0.6 status cell, which is a board, not the normative
spec an implementer reads.

## M4 — 2026-08-30T10:5xZ — the captured-template question, answered per instruction
`analysis/template_dependency.py` → `analysis/template_dependency.json`.

**Three populations, and they are nearly disjoint.**
- EMITTABLE (label property, validation.json): **35** mnemonics.
- GENERATED (a zero-copied program using it actually ran on G17P; EXP-0167's own
  `assemble_defect_check.json` ledger): **18** mnemonics.
- **Intersection: 4** — `isel10`, `mov_imm`, `pop_reconverge`, `stop`. And two of those four
  (`isel10`, `pop_reconverge`) appear in the corpus **only** inside `cf.py`, whose every field
  is `_copied()` verbatim. **So the true GENERATED-AND-EMITTABLE set is `mov_imm` and `stop`.**

Per-mnemonic verdicts (35 ∪ 18 = 49 mnemonics):
- **GENERATED-AND-EMITTABLE 2** — `mov_imm`, `stop`.
- **GENERATED-NOT-EMITTABLE 2** + **PARTLY-DONOR 3** — `device_store`, `falu2`; `device_load`,
  `falu2i`, `iadd2`. These ran correctly from rules but the metric excludes them.
- **DONOR-DEPENDENT 11** — `get_sr`, `icmp_pred`, `if_push`, `if_push_pred`, `isel10`, `jump`,
  `jump_cond`, `pop_reconverge`, `reg_move_c0`, `ret`, `scoreboard_fence`. Auditable test:
  the mnemonic string appears in `cf.py` and in NONE of `synth.py`/`families.py`/
  `generator.py`/`casematrix.py`. **81 (mnemonic, field) donor pairs** in
  `summary.json:donor_tokens_still_required`.
- **EMITTABLE-NOT-GENERATED 31** — every field labelled emitter-grade, but no generated
  program containing the instruction has ever executed. **Closure rule 1 is not established
  for any of these 31 by EXP-0167.**

**A published figure is inverted and I am correcting it.** The dispatch (and the reading it
came from) says "60 of the 233 rest on rules the experiment did not itself measure". EXP-0167's
own `summarize.py` defines `N0` as *"the subset of N that also contains zero PILOT fields, i.e.
rests only on rules published by earlier experiments"*, and `N0 = 60`. So the true statement is
the other way round: **only 60 of the 233 rest on previously published rules; the remaining 173
contain at least one field whose value EXP-0167 had to measure itself because no prior rule
existed.** From the immutable raw record, that is `falu2.mod_hi` in **163** cases and nine
`iadd2` fields in the other 16.

## M5 — 2026-08-30T11:2xZ — closure rules, vacuous fields, REVERSE chain
`analysis/closure_rules.json`, `analysis/vacuous_fields.json`, provenance reverse chain.

**Completion gate: NOT PASSED.** 0 of 16 rows CLOSED; the board itself says so and the
recomputation agrees. Of the three mechanically checkable rules: rule 2 (complete record)
MET for 10/16, rule 3 (PROVENANCE chain) 13/16, rule 5 (adversarial/second method) 6/16.
P0.8 cites no experiment at all ("queued"), so 2/3/5 are vacuously unmet there.

**THE REVERSE CHAIN IS THE BROKEN ONE.** PROVENANCE.md's rows point at real artifacts, but
**36 of 169 committed experiments have no row pointing back**, and **11 of those are cited in
`docs/`** — a direct CODEX §9 violation ("no hardware fact enters docs/ unless the same change
provides an auditable evidence link... add or update its row in PROVENANCE.md"):
EXP-0068, 0078, 0080, 0104, 0105, 0106, 0111, 0114, 0115, 0142, **0170**.
`EXP-0105` is the worst of these: `docs/isa/encoding-tables.md` cites it for
"`opflags` bits 22/23 and `mod_hi` bit 44 are general silent CORRUPTORS" — an emitter-safety
fact — with no provenance row. **EXP-0170 also has an EMPTY `raw/`** while its conclusions are
quoted verbatim in the P0.6 board cell.

**Vacuous fields (both ways, as asked).**
- as published: **588 / 1062 fields (55.37%), 35 of 166 instructions**
- folding the 25 zero-free-bit fields into `match`: **572 / 1037 (55.16%), 35 of 166** —
  numerator −16, denominator −25, **instruction count UNCHANGED**.
- also folding the 34 partially-pinned fields (NOT recommended): 555 / 1003, 37 of 166.
- 7 of the 25 sit inside currently-emittable instructions: `link_save_restore.b1/.marker/
  .scope`, `cvt_bf16.src/.fmt`, `rtq_state_move.form/.b3`.
**Recommendation: fold the 25.** It costs nothing (the headline instruction count does not
move) and it removes 16 emitter-grade labels that assert a choice the implementer does not
have. Do NOT fold the 34 partially-pinned ones — those have a real, narrower choice; the fix
there is to correct `start`/`width`.

## M6 — 2026-08-30T11:5xZ — compiler readiness + FIFTH tooling defect; RESULTS.md landed
`analysis/compiler_readiness.py` → `analysis/compiler_readiness.json`.

**`nir_op_mov` is STILL the first blocker.** No emittable descriptor moves one GPR to a
DIFFERENT GPR. `mov_zext16` is emittable but operates in place on one register (its own
semantics). `n3_mov` is the real candidate and is blocked on three `corpus-correlation`
fields: `dst`, `srcA_reg`, `srcA_uni`. `reg_move_c0` ran in a generated program but every field
is `untested` and it is the const-zero form. `n2_op6` is emittable and its text says
"compact select/move", but the same descriptor calls itself a "genuine catch-all bucket" whose
"per-sub-op value maps are mixed and needs-splice" and whose provenance says
"NOT HW-dispatch validated (M4 compile-only)".

**FIFTH TOOLING DEFECT, not previously named: the emittability rule never reads the
`_instruction` label.** `validate_labels.py` and `merge_verdicts.py` decide emittability from
FIELD labels + the `EMITTABLE VETO` note only. **21 of the 35 emittable instructions have an
`_instruction` label weaker than emitter-grade** — 20 `corpus-correlation` and `sfu_marker` at
`tokenization-only`. Requiring it would take the headline from 35 to ~14. Separately, **18 of
the 35 carry descriptor text warning about themselves** (`needs-splice`, `NOT HW-dispatch
validated`, `compile-only`, `catch-all`, `unresolved`).

`RESULTS.md`, `README.md`, `manifest.json`, `analysis/run_all.sh` written. Nothing outside
`experiments/EXP-0173-closure-audit/` was modified (`git status --porcelain tools/ docs/
PROVENANCE.md work/` is empty). No commit made.
