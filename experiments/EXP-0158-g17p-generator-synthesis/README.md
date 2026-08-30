# EXP-0158 — G17P generator synthesis (DRV-ISA-01 / P0.6, closure rules 1 and 6)

## Question

`EXP-0112` proved a generator can build correct AGX9 programs at scale on the M4 — but its
DOC-02 labelling pass showed it succeeded partly by **copying verbatim tokens** out of a
compiled shader (`device_load`'s `dst_lo`/`dst_ext9`, `ld_format`, `falu2`'s `mod_hi`, and
`iadd2`'s entire register-mode block). Copying a token is replay, not generation, and
`CLAUDE.md`'s closure rules 1 and 6 are precisely about that distinction.

`EXP-0141`, `EXP-0139`, `EXP-0128`, `EXP-0138` and `EXP-0140` have since established rules
for those tokens on hardware. **How many of EXP-0112's programs can be rebuilt with every
field COMPUTED — zero verbatim tokens — and still run bit-exactly correct? And which token
is still missing a rule?**

And, for the first time, **on G17P** — the documentation target. Every rule being composed
here was established on the M4.

## Method

`synth.py` re-emits every instruction EXP-0112 emitted, but each field value carries a
machine-checked provenance tag (`RULE` / `FREE` / `PILOT` / `CARRIER` / `COPIED`), so the
experiment's headline number is *"how many programs pass with ZERO `COPIED` fields"* rather
than a pass rate. `generator.py` keeps EXP-0112's DAG-structure and register-allocation
passes **and its RNG stream**, so the 100 `MAIN_DAG` programs have exactly the shapes
EXP-0112 ran and field provenance and target are the only variables.

New capability exercised here that EXP-0112 did not have: `falu2`'s **inline 8-bit float
immediate** (EXP-0138 §3), which materialises a float constant inside the consuming
instruction's own operand field, and `iadd2` **register mode**, which replaces EXP-0112's
verbatim anchor. New freedom exercised: destination registers EXP-0112 could not reach,
including the pre-registered boundary pair **R = 63** (must work) and **R = 64** (must
silently fail).

The complete token inventory, hypotheses, refuters, and the disclosed pre-freeze pilot are
in `PRE_REGISTRATION.md`. Results, the failure taxonomy, and the G16G↔G17P comparison are
in `RESULTS.md`.

## Reproduce

On the neo (`~/agxre/experiments/EXP-0158-g17p-generator-synthesis/`):

```sh
# pre-freeze pilot (disclosed; its output is frozen before any gated run)
~/agxre/gpulease.sh EXP-0158-pilot 900 -- \
    python3 -B work/pilot/pilot.py --bin-dir work/bin --out work/pilot/<new-file>.jsonl
python3 -B analysis/freeze_from_pilot.py --pilot work/pilot/<new-file>.jsonl \
    --run-id <id> --write

# gates (no GPU)
python3 -B verify.py --selftest
python3 -B verify.py --seqtest
python3 -B verify.py --preflight

# gated captures
~/agxre/gpulease.sh EXP-0158-run01 1800 -- python3 -B run.py --run-id g17p-20260830-run01 --execute
python3 -B verify.py --between-runs
~/agxre/gpulease.sh EXP-0158-run02 1800 -- python3 -B run.py --run-id g17p-20260830-run02 --execute
python3 -B verify.py --captured

# analysis (no GPU, runs anywhere)
python3 -B analysis/summarize.py
```

## Clean-room provenance

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: this experiment's own authored generator/harness code and carrier MSL,
  plus a PINNED, hash-recorded snapshot of this repository's own tools/agx-isa isadb
  (read-only; tools/ is not modified).
Apple binary introspection: NONE.
Reproduction: the commands above.
Evidence: raw/g17p-20260830-run01/, raw/g17p-20260830-run02/, work/pilot/
```

## Notes for a reviewer

- `experiments/EXP-0112-m4-program-generator/` is committed evidence and was **not
  modified**. `experiments/EXP-0149-m4-generator-synthesis/` is a committed but never-run
  M4 predecessor (killed by local-M4 host instability before its first capture); its
  `synth.py` provenance-ledger design is the direct ancestor of this experiment's and is
  likewise **not modified** — EXP-0158 is a new number with a fresh pre-registration, per
  CODEX.
- The ISA database is **pinned** into `work/isadb_pinned/`. `tools/agx-isa/db.json`
  changed under this agent mid-read (the orchestrator owns it and edits it concurrently),
  and a two-run byte-identity gate cannot depend on a moving file.
- Do NOT `git commit` — the orchestrator reviews and commits.
