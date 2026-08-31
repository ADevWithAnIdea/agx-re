# EXP-0220 — canonical generated recipes for `falu2` and `device_store` (G17P)

**Question.** `RE_EXPERIMENT_PROCESS_CORRECTIONS.md` Gate D asks for an instruction whose
every required byte is constructed from documented rules, run as the exact generated program,
and compared against a host prediction of the **complete** state — with every copied region
identified and no required field taken from a compiler-emitted donor. The recipe dashboard
read **2 of 166** `canonical-recipe-proven`. This experiment asks whether `falu2` and
`device_store`, the two closest candidates, clear that bar.

**Hypothesis.** Both can be generated with zero donor fields across the operand classes a
compiler actually selects, and their complete observable state predicted in advance.

**Method.** A compute carrier of our own MSL is compiled through the public runtime API; the
**entire `_agc.main` region** is then overwritten with bytes this experiment assembles from a
pinned `db.json`, padded with generated `mov_imm` words that run after `stop`. Every field
value carries a machine-checked provenance tag (`RULE` / `FREE` / `CARRIER` / `COPIED`), and
the experiment's gate is that the last two are **zero**. Each of 1,584 cases dumps 24
architectural registers to distinct out words and reads back all three bound buffers, which
are compared byte for byte against a host oracle computed before the GPU is touched.
`base_slot` — the one required field EXP-0167 had to read off its own compiled carrier — is
determined here by **hardware probe** (arm S0) instead.

**Commands.** `RESULTS.md` §8.

**Clean-room category.** OWN-SHADER + HW-PROBE. Only shaders we compiled from our own MSL,
and bytes we generated ourselves, are ever inspected or executed. No Apple binary is
disassembled, decompiled or introspected.

**Layout.**

```
PRE_REGISTRATION.md      frozen before the first gated dispatch; section 7 is the
                         COPIED-REGION LEDGER, section 6 the disclosed pre-freeze pilot
CAPTURE_CONTRACT.json    frozen hashes of every authored input, the case matrix, the gates
                         and their pass criteria
kernels/carrier220.metal our own MSL carrier (its arithmetic never executes)
harness/synth220.py      provenance-tracking instruction emitter (RULE/FREE/CARRIER/COPIED)
harness/prog220.py       program builder + host oracle over every byte of all three buffers
harness/cases220.py      the case matrix: 24 arms, the operand classes a compiler selects
harness/run220.py        the capture driver (runs on the neo)
harness/runner220.py     persistent-runner driver, one reader thread per child
harness/selftest220.py   OFFLINE gates T0..T5 -- no device, no SSH
harness/diag220.py       the disclosed pre-freeze diagnostics D1..D12
analysis/census220.py    rebuilds every program and asserts its sha256 against raw
analysis/score220.py     the five gates, scored separately
analysis/coverage220.py  per-arm and per-field exact numerators and denominators
analysis/generated_recipe.json  the recipe records the dashboard reads
analysis/field_verdicts.json    six-axis verdicts + db_defects
raw/                     two gated runs, append-only
```

**Verdict.** `falu2` → `canonical-recipe-proven`. `device_store` → `generated-no-donor`, held
back by one class a compiler selects and this recipe cannot emit (the threadgroup address
space). `device_load` → `generated-no-donor`, up from `generated-point`. Seven documented
rules were corrected along the way; see `RESULTS.md` §3.
