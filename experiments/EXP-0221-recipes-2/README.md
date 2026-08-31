# EXP-0221 — the three blockers EXP-0220 named (G17P)

**Question.** `RE_EXPERIMENT_PROCESS_CORRECTIONS.md` Gate D asks for an instruction whose
every required byte is constructed from documented rules, run as the exact generated
program, and compared against a host prediction of the **complete** state — with every
copied region identified and no required field taken from a compiler-emitted donor. The
recipe dashboard reads **2 of 166** `canonical-recipe-proven`. EXP-0220 named exactly what
holds the next three back:

| instruction | blocker |
|---|---|
| `device_store` | the **THREADGROUP address space** (4 of 4 `space` bit-1 values faulted), `extmode >= 128`, and nine fields SAMPLED rather than swept densely |
| `device_load` | four fields with no emitter-grade label, and eight more held at one value each |
| `stop` | `stop.reserved`, a 24-bit field sampled at 73 of 16,777,216 values |

**Hypothesis.** EXP-0220's threadgroup faults are a property of its **carrier**, which
declared no threadgroup memory, not of the encoding; with a tile declared, the class can be
generated and predicted.

**Method.** Two carriers of our own MSL — `carrier221.metal` with 16 KiB of static
threadgroup memory and `carrier221_notg.metal` without, identical otherwise — compiled
through the public runtime API; the **entire `_agc.main` region** is then overwritten with
bytes this experiment assembles from a pinned `db.json`. 7,160 cases per run, each a
complete generated program with a 24-register state dump, all three buffers read back byte
for byte against a host oracle computed before the GPU is touched, and a machine-checked
`RULE`/`FREE`/`CARRIER`/`COPIED` provenance tag on every field. Every dense arm is scored
against a **pre-registered cross-target prediction** — EXP-0141's M4 accepted sets,
extracted mechanically from that experiment's committed raw and frozen before the run.
`stop` gets a **post-stop tripwire** store, because an instruction with no destination has
no observable and an inertness verdict without one is a check that cannot fail.

**Commands.** `RESULTS.md` §9.

**Clean-room category.** OWN-SHADER + HW-PROBE. Only shaders we compiled from our own MSL,
and bytes we generated ourselves, are ever inspected or executed. **No field value is read
off a compiled instruction, including our own carriers'** — the threadgroup descriptors are
*measured* by a round-trip probe, the way EXP-0220 measured `base_slot`. No Apple binary is
disassembled, decompiled or introspected.

**Layout.**

```
PRE_REGISTRATION.md       frozen before the first gated dispatch; section 6 is the
                          DISCLOSED PRE-FREEZE PILOT, section 7 the COPIED-REGION LEDGER
CAPTURE_CONTRACT.json     frozen hashes of every authored input, the case matrix, the
                          gates and their pass criteria
kernels/carrier221.metal      our own MSL carrier, 16 KiB of static threadgroup memory
kernels/carrier221_notg.metal the same kernel with NO threadgroup allocation (Phase-5 control)
harness/synth221.py       provenance-tracking emitter; every device_load field overridable
harness/prog221.py        program builder + host oracle over every byte of all three buffers
harness/cases221.py       the case matrix: 32 arms, 7,160 cases
harness/run221.py         the capture driver (runs on the neo)
harness/runner221.py      persistent-runner driver, one reader thread per child
harness/tgpilot.py        the DISCLOSED PRE-FREEZE threadgroup pilot (stages 1..9)
harness/selftest221.py    OFFLINE gates T0..T5 -- no device, no SSH
analysis/census221.py     rebuilds every program and asserts sha256 against raw
analysis/score221.py      the five gates, scored separately
analysis/coverage221.py   per-field exact numerators, and G17P vs M4 accepted sets
analysis/recipe221.py     writes the recipe records dashboard 4 reads
analysis/field_verdicts.json  six-axis verdicts + db_defects
raw/                      three gated runs, append-only
work/pilot/               the disclosed pre-freeze pilot's raw (NOT gated evidence)
```

**Verdict.** `device_store` → **stays `generated-no-donor`.** The threadgroup class is now
characterised — it no longer faults, it round-trips, and its store/load offset law is
measured — but the round trip is **not shape-independent**, so no implementer could emit it
from this recipe and no canonical record is written. `device_load` and `stop` gain the
evidence their labels need; the labels themselves are the orchestrator's. Seven documented
rules were corrected or refuted along the way, including one of my own pre-registered
models; see `RESULTS.md` §3.
