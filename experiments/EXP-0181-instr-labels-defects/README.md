# EXP-0181 — the stale `_instruction` labels, and the four open descriptor defects

**Type: DESK EXPERIMENT — pure analysis over committed evidence. No device, no SSH, no GPU,
no `macvdmtool`.** Three device experiments were live on the neo throughout and were not
disturbed.

```text
Clean-room provenance: OWN-SHADER + HW-PROBE (re-analysis of committed evidence) + PUBLIC
Inputs inspected: tools/agx-isa/{db.json, validation.json, isadb.py};
  experiments/EXP-*/raw/**/*.jsonl -- the recorded behaviour of shaders WE compiled from OUR
  OWN MSL and spliced with OUR OWN tools; experiments/EXP-M4-13-full-corpus/hex/** -- the
  machine code the public newLibraryWithSource: API produced from our own source; and the
  cited experiments' RESULTS.md.
Apple binary introspection: NONE.
Reproduction: see "Commands" below.
Evidence: analysis/*.json (all regenerable by the scripts in the same directory)
```

## The two questions

1. **DEF-0173-1.** The emittability rule reads only FIELD labels and never `_instruction`.
   Thirty emittable instructions carry an `_instruction` label weaker than emitter grade.
   The orchestrator refused to gate on them because they are stale rather than
   authoritative — `mov_imm` is one of only two instructions proven END-TO-END and still
   reads `corpus-correlation`. **What should each of the thirty be, from evidence?**
2. **The four descriptor defects EXP-0168 handed over** — `iter_at.grp`,
   `pixel_order.scope`, `reg_move_cb.form`, `shift_amt_move.kind`, each declaring a field
   over bits its own `match` pins. Re-derive, then narrow or report.

The falsifiable hypotheses, the frozen decision rule (R1–R5) and the gates are in
`PRE_REGISTRATION.md`. The answers are in `RESULTS.md`.

## What is in `analysis/`

| file | what it is |
|---|---|
| `scan_dispatch_evidence.py` → `dispatch_evidence.json` | was each instruction ever DISPATCHED on hardware? case counts, outcome histograms, oracle-scored counts, baseline/anchor counts, per experiment |
| `verify_dispatched_bytes.py` → `dispatched_bytes_check.json` | do the dispatched bytes decode BACK to the descriptor the harness tagged them with? (a dst-generalised sibling is easy to mis-attribute) |
| `anchor_check.py` → `anchor_check.json` | the UNMUTATED anchor each experiment dispatched, with its outcome and what the live decoder makes of it |
| `anchor_reachability.py` → `anchor_reachability.json` | can the committed tokenizer even reach the HW-validated anchor? plus the encodings the corpus does reach |
| `rederive_defects.py` → `defects_rederived.json` | Task 2's independent re-derivation: free/pinned split from `db.json` alone, every raw sweep value with its outcome, and what the corpus emits |
| `apply_defects.py` | the ONE coherent write to `db.json`, with pre-state assertions on every field it touches |
| `ab_gate.py` → `ab_metrics.json` | the corpus + round-trip gate (EXP-0175's copy, which already runs `roundtrip_test.py` in a **subprocess** — DEF-0175-2; re-checked before use) |
| `make_instruction_labels.py` → **`instruction_labels.json`** | **Task 1 deliverable**: per instruction, recommendation vs current, evidence, reason, refuter, caveats |
| `make_orphan_list.py` → **`orphaned_validation_rows.json`** | **Task 2 deliverable**: 0 orphans, 0 created rows, 3 RE-SPANNED rows with re-scored recommendations |

`work/db.json.before` is the pre-image of `db.json` (sha `a77f8cfa…`), kept so the edit can
be diffed and reverted without git.

## Commands

```sh
cd /Users/user/asahi_re/public/agx-re
W="bf_add_dst bf_fma_dst cvt_bf16 cvt_f2h cvt_f2h_dst cvt_i2f falu3 falu3_ext \
   frag_depth_store frame_marker_compact h_coord_hi h_coord_hi_ext hminmax irotate \
   iter_flat mov_imm mov_zext16 n2_op6 n3_mov pack_convert psel ret_luse rtq_state_move \
   sel sfu_marker shift_amt_move sr_read_wide uniform_mov vary_slot vtx_coord_xform"
E=experiments/EXP-0181-instr-labels-defects

# Task 1 -- evidence gathering (each ~10 s; scans every committed raw/*.jsonl)
python3 $E/analysis/scan_dispatch_evidence.py  $W > $E/analysis/dispatch_evidence.json
python3 $E/analysis/verify_dispatched_bytes.py $W > $E/analysis/dispatched_bytes_check.json
python3 $E/analysis/anchor_check.py            $W > $E/analysis/anchor_check.json
python3 $E/analysis/anchor_reachability.py        > $E/analysis/anchor_reachability.json
python3 $E/analysis/make_instruction_labels.py

# Task 2 -- re-derive, apply, list the re-spanned rows
python3 $E/analysis/rederive_defects.py > $E/analysis/defects_rederived.json
python3 $E/analysis/apply_defects.py --dry-run     # then without --dry-run to write db.json
python3 $E/analysis/make_orphan_list.py

# Gates
python3 $E/analysis/ab_gate.py                     # corpus + round trip, subprocess-isolated
python3 tools/agx-isa/roundtrip_test.py | tail -2
python3 tools/agx-isa/match_overlap_report.py | head -4
python3 tools/agx-isa/validate_labels.py ; echo "exit=$?"
```

`apply_defects.py` asserts the pre-state of every field it touches, so re-running it against
an already-patched tree fails loudly instead of double-applying.

## What this experiment changed

* `tools/agx-isa/db.json` — three field narrowings, three `match_notes` entries, four
  semantics additions. sha `a77f8cfa163fcf72…` → `1ada4e7bb7879cd6…`.
* Nothing else. `validation.json`, `docs/`, `PROVENANCE.md` and every other experiment
  directory are untouched, and nothing was committed.
