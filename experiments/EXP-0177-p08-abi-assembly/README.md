# EXP-0177 — P0.8 / DRV-ABI-01 evidence assembly

## Question

`docs/P0-P1-CLOSURE.md` row **P0.8 — DRV-ABI-01, "Complete VS/FS/CS ABI and programmable
prolog/epilog linkage"** is `OPEN` and its evidence cell reads literally **`queued`**. It is
the only P0/P1 row that cites no experiment at all — a fact EXP-0173's closure audit
recorded independently under closure rule 2 ("P0.8 cites no experiment at all").

That cell is wrong in one direction and right in another, and the point of this experiment
is to say precisely which. A large body of P0.8-relevant evidence exists in
`experiments/` and has never been gathered under the row; at the same time, the evidence
that exists does not meet the row's own six closure rules, and several sub-areas of the
row are genuinely near-empty.

**The question:** for each sub-area named in the P0.8 row — *inputs, outputs, sysvals,
interpolation, tilebuffer, calls, scratch, linking, sideband, and independently generated
blend/logic/conversion epilogs across advertised formats* — what does the committed
evidence actually establish, on which target, at what evidence strength, over what tested
range; and what can an implementer still not do?

## Method

**Pure analysis. No device, no SSH, no GPU.** Three device experiments were live when this
ran and none of their files was touched; `tools/agx-isa/db.json` and
`tools/agx-isa/validation.json` are owned by EXP-0175 and were read only.

Sources are restricted to this repository's own committed artifacts and public reference
material: `experiments/*/RESULTS.md`, `experiments/*/README.md`,
`experiments/*/QUARANTINE.md`, `PROVENANCE.md`, `tools/agx-isa/validation.json`, `docs/`,
and `APPLE9_RE_IMPLEMENTATION_GAPS.md`. Nothing new is established here; every claim is a
citation to an existing result, and every result is attributed to the target it actually
ran on.

Two mechanical checks back the narrative:

| script | output | what it establishes |
|---|---|---|
| `analysis/isa_status.py` | `analysis/isa_status.json` | per P0.8 sub-area, which stage-ABI instruction is `emittable`, which fields block it, at what label and on which target — read straight out of `tools/agx-isa/validation.json` |
| `analysis/provenance_check.py` | `analysis/provenance_check.json` | for every experiment this assembly cites: does it own a `PROVENANCE.md` row, is it quarantined, is it cited in `docs/` |

Both are re-runnable and read-only.

## Commands

```sh
python3 experiments/EXP-0177-p08-abi-assembly/analysis/isa_status.py
python3 experiments/EXP-0177-p08-abi-assembly/analysis/provenance_check.py
```

## Deliverables

- `RESULTS.md` — the assembly, structured by P0.8 sub-area.
- `analysis/p08_evidence.json` — per sub-area: what is established, the experiment and
  artifact establishing it, the evidence label, the target it ran on, and the exact tested
  range.
- `analysis/p08_gaps.md` — what an implementer still cannot do, ranked by how badly it
  blocks a working driver, each with the experiment that would close it.
- `analysis/p08_closure_cell_draft.md` — a **drafted** replacement for the P0.8 evidence
  cell in `docs/P0-P1-CLOSURE.md`. **Drafted for orchestrator review, NOT applied** —
  the orchestrator owns that file.

## Clean-room statement

```text
Clean-room provenance: PUBLIC (this repository's own committed clean-room artifacts, read
  only) — no hardware was touched, no shader was compiled, no byte was spliced.
Inputs inspected: experiments/*/{RESULTS.md,README.md,QUARANTINE.md,manifest.json},
  PROVENANCE.md, tools/agx-isa/validation.json, docs/**, APPLE9_RE_IMPLEMENTATION_GAPS.md,
  CODEX.md, CLAUDE.md. All are this project's own authored files.
Apple binary introspection: NONE. No disassembler, decompiler, or binary-inspection tool
  was run on anything. No Apple binary, framework, kext, firmware, precompiled shader, or
  system shader cache was read, and none is quoted or paraphrased anywhere in this
  experiment's output.
Reproduction: the two commands above.
Evidence: analysis/isa_status.json, analysis/provenance_check.json, analysis/p08_evidence.json.
```
