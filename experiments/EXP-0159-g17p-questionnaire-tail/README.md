# EXP-0159 — G17P questionnaire tail: the last six items that needed hardware

**Target: Apple A18 Pro / G17P** (`AGXAcceleratorG17P`, `applegpu_g17p`, 5 GPU cores, macOS 26.6
build `25G5043d`, Metal family Apple9, 8 GiB unified memory) — **the documentation target itself**,
so every answer here is direct evidence, not `INFERRED`.

## The question

The Part-II compiler questionnaire in `APPLE9_RE_IMPLEMENTATION_GAPS.md` has 181 items. 145 were
answered by committed experiments and a desk pass produced verdicts for 14 more, leaving **six that
genuinely need hardware** (plus `SFU-04`, blocked by clean-room rule 5 and deliberately untouched
here):

| item | question |
|---|---|
| `P2-06` | Is any native FP64 arithmetic present beyond integer register-pair machinery? |
| `TEX-01` | Does the Apple9 coordinate-projection setup form implement exactly NIR's projective divide? |
| `TEX-19` | Can every argument-buffer texture entry through 1,000,000 be selected dynamically? |
| `TEX-21` | Can every bindless sampler entry through 499,999 be selected dynamically? |
| `TEX-22` | What happens at the 500,001st sampler, an unpopulated entry, a destroyed ID? |
| `MEM-19` | Can the USC constant/uniform program populate every usable base slot, and what happens past capacity? |

**Numbering trap, stated so a later reader does not fall into it:** Part-II `P2-01..06` are **not**
the Part-I `DRV-P2-01..05` rows. Part-II `P2-06` is **FP64**.

## Hypotheses, method and controls

`PRE_REGISTRATION.md` is the frozen contract (hypotheses, independent/controlled variables,
oracles, refuters, positive controls, confounders, timeouts); `CAPTURE_CONTRACT.json` pins the 50
authored source hashes, the target identity, the case sets and the gates. Both were written and
frozen **before** any gated build or run. A pre-freeze feasibility probe (retained in
`raw/prefreeze/`, explicitly **not** evidence) established the three facts needed to specify the
contract at all.

Six probe families:

| family | item | what it does |
|---|---|---|
| FA | P2-06 | 16 authored MSL sources × 3 language versions; records the verbatim compiler diagnostic. Controls `float`/`half`/`ulong` must accept. |
| FB | P2-06 | **Complete single-byte space** of the only known native 64-bit ALU instruction — 10 bytes × 256 values — spliced into our own compiled `ulong` kernel and executed against 4 input rows that separate binary64 from int64, f32×2, passthrough, zero and poison. Control: byte0 bit 7 must give an exact 64-bit integer add. |
| FC | TEX-19 | A 1,000,000-entry (and a 2,000,000-entry) bindless texture argument buffer, canaries at boundary indices, runtime `uint` selection, uniform and per-lane. |
| FD | TEX-21/22 | Sampler ceiling walk to 2,000,000 distinct descriptors; dedup; destroyed-ID reuse; a 1,000,000-entry heap with canaries whose resource IDs exceed 500,000; raw out-of-table IDs under the GPU lease. Oracle: each sampler's fingerprint measured first through a **directly bound** `[[sampler(0)]]` — an independent path. |
| FE | MEM-19 | USC constant/uniform-program census over 1…30 buffer bindings (uniform and thread-varying), the declared-buffer API ceiling, and a 256-value `base_slot` selector sweep on a spliced probe load. |
| FF | TEX-01 | `tex_addr_setup.form` sweep with directed numeric edge cases (0, −0, ±inf, NaN, 1e±30) on a 2D and a 2D-array carrier whose texel value names the texel and level, plus two adversarial refuter hunts. |

## Reproduction

```sh
# on the repo host: push sources and build the harnesses on the neo
SSHPASS=... bash analysis/deploy.sh

# preflight: authored sources match the frozen contract
python3 analysis/verify.py --preflight

# the two gated runs (on the neo, in ~/agxre/EXP-0159/harness)
python3 run.py --run-id g17p-20260829-run01 --family all
python3 run.py --run-id g17p-20260829-run02 --family all

# post-registration confirmation / adversarial passes
~/agxre/gpulease.sh EXP-0159 900 -- python3 fe_isolated.py --run-id g17p-20260829-fe-iso01
python3 ff_formsweep.py --run-id g17p-20260829-adv01 --carrier texlod
python3 ff_formsweep.py --run-id g17p-20260829-adv02 --carrier texarr
python3 fbleaseconfirm.py --run-a g17p-20260829-run01 --run-b g17p-20260829-run02 \
        --out-run g17p-20260829-fbc01 --reps 5

# on the repo host: gates and consolidation
python3 analysis/verify.py --captured g17p-20260829-run01 g17p-20260829-run02
python3 analysis/verify.py --captured g17p-20260829-run01 g17p-20260829-fe-iso01
python3 analysis/summarize.py            # writes analysis/verdicts.json
```

## Layout

```
PRE_REGISTRATION.md      frozen hypotheses/oracles/refuters/gates
CAPTURE_CONTRACT.json    frozen target, case sets, raw schema, 50 source hashes
kernels/                 authored MSL (FA's 16 FP64 probes, the 5 carriers, the slot-count sets)
harness/                 authored ObjC probes + Python runners
analysis/                deploy/poll scripts, verify.py (gates), summarize.py, verdicts.json,
                         questionnaire_answers.md  <- the six answer blocks
raw/                     append-only: prefreeze/, the two gated runs, and the confirmation passes
RESULTS.md               observations vs interpretation, tested range, limitations, verdicts
```

## Clean-room provenance

```
Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC
Inputs inspected: authored MSL (kernels/*.metal, kernels/fa/*.metal), authored ObjC harnesses
  (harness/*.m), authored Python runners and analysis, and the AGX machine code compiled from our
  own MSL by the public runtime API. Public Metal/MSL API names (MTLSamplerDescriptor,
  MTLArgumentEncoder, MTLResourceID, MTLGPUFamily) were used as calling conventions only, never
  as a source of a hardware fact.
Apple binary introspection: NONE. No Apple binary, dylib, kext, firmware, system shader cache or
  Apple-authored precompiled shader was disassembled, decompiled, symbol-dumped, strings-scanned,
  debugged or otherwise introspected. The only machine code inspected or spliced is the code the
  runtime compiler produced from source we wrote.
Reproduction: the command sequence above.
Evidence: raw/g17p-20260829-run01, raw/g17p-20260829-run02, raw/g17p-20260829-fe-iso01,
  raw/g17p-20260829-adv01, raw/g17p-20260829-adv02, raw/g17p-20260829-fbc01, analysis/verdicts.json, manifest.json.
```
