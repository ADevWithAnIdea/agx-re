# EXP-0175 — apply EXP-0171's five defects, fold the vacuous fields, hunt the wrong-operand class

**Type: desk experiment. NO device work.** Every input is already-committed evidence in this
repository. Nothing was dispatched to the neo (one device experiment was live there and was not
disturbed), the M4 GPU, or M5. Status board: `../../docs/P0-P1-CLOSURE.md`. Rows served:
**P0.6 / P0.8 / P1.3** — the ISA database is what an implementer emits from, so a descriptor
that mis-describes a field is a synthesis defect even when every byte round-trips.

## The three questions

1. **Do DEF-0171-1 … DEF-0171-5 survive an independent re-derivation?** EXP-0171 reported five
   descriptor defects, hardware-proven and none patched. Precedent forbids taking `RESULTS.md`
   on trust: EXP-0165 re-derived nine defects and found one **half wrong**
   (`fspecial.fnclass` bit 2 is live, not a don't-care) and one whose **severity claim** was
   wrong. Each defect here is re-derived from EXP-0171's committed `raw/` by a script that
   computes its own verdict, and any defect that does not survive is **not applied**.
2. **Should the 25 zero-free-bit "fields" be folded into `match`?** They have exactly one legal
   value, so they are part of the match, not fields — and **16 of them carried an emitter-grade
   label**, which asserts a choice an implementer does not have.
3. **Which fields NAME an operand but cannot select one?** Four instances of this class were
   found *by accident*. This experiment enumerates it on purpose, because
   `roundtrip_test.py` is structurally blind to it (EXP-0170: it passes against an assembler
   that cannot clear a bit; EXP-0173: it passes with `falu3.srcA`↔`srcB` swapped).

Full frozen design, hypotheses, refuters and stop conditions: **`PRE_REGISTRATION.md`**
(written before any script and before any edit).

## What changed, and what deliberately did not

| | |
|---|---|
| **Edited** | `tools/agx-isa/db.json` (sole editor this session) |
| **Also edited, forced and minimal** | `tools/agx-isa/roundtrip_test.py` — fixture keys only, no byte changed (see `RESULTS.md` §6) |
| **Read only, never written** | `tools/agx-isa/validation.json`, `docs/`, `PROVENANCE.md` — the orchestrator's |
| **Measured but NOT landed** | the full `ilogic`+`b_alu10_*` merge; the `isadb.py` length rule for byte0 `0x31`; a `mov_zext16` match tightening |
| **Not committed** | nothing was `git commit`ed |

## Commands

```bash
# re-derivations (each prints its own verdict from raw/, independent of EXP-0171's RESULTS.md)
python3 analysis/rederive_def1.py              # DEF-0171-1  ilogic byte0 == (dst<<4)|0x0b
python3 analysis/rederive_def2_def5.py         # DEF-0171-2  and  DEF-0171-5
python3 analysis/rederive_def3_and_ibfe.py     # DEF-0171-3  and the ibfe closure question
python3 analysis/rederive_def4.py              # DEF-0171-4  outmod is a source-read control

# apply (idempotent per change set; --merge is opt-in and was NOT used on the live tree)
python3 analysis/apply_defects.py --into <tree>/db.json

# gates
python3 analysis/ab_gate.py work/pre           # corpus + roundtrip + firing delta, A/B
python3 ../../tools/agx-isa/roundtrip_test.py
python3 ../../tools/agx-isa/validate_labels.py
python3 ../../tools/agx-isa/emit_worklist.py
python3 ../../tools/agx-isa/match_overlap_report.py

# reports
python3 analysis/make_orphan_list.py           # -> analysis/orphaned_validation_rows.json
python3 analysis/operand_defects.py            # -> analysis/operand_defects.json
python3 analysis/operand_defects.py --db work/pre/db.json --out operand_defects_prefix.json
```

`work/pre/` is the pre-edit tree (`db.json` and `roundtrip_test.py` taken from `HEAD`,
db sha `322847609de7…`), kept so every A/B in `RESULTS.md` is re-runnable.

## Clean-room provenance

```text
Clean-room provenance: OWN-SHADER + HW-PROBE (re-analysis of committed evidence) + PUBLIC
Inputs inspected: experiments/EXP-0171-g17p-ilogic-srca/raw/** — the observed behaviour of
        OUR OWN compiled shaders, spliced by our own tools and run on our own harness;
        tools/agx-isa/db.json and validation.json (our own database);
        experiments/EXP-M4-13-full-corpus/hex/** (our own + committed permissively
        licensed corpus).
Apple binary introspection: NONE. No Apple binary was opened, disassembled, symbol-dumped
        or strings-scanned. No device was dispatched to.
Reproduction: the commands above; every analysis script is self-contained.
Evidence: analysis/def1_rederived.json, def2_def5_rederived.json, def3_rederived.json,
        def4_rederived.json, ab_metrics.json, orphaned_validation_rows.json,
        operand_defects.json, validate_after.txt
```

Observations separated from interpretation, with the tested range and the limitations:
**`RESULTS.md`**.
