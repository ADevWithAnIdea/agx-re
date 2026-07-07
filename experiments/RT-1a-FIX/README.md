# RT-1a-FIX — apply the RT-1a corrections, each INDEPENDENTLY HW-re-validated

**Role:** take the five red-team findings from `experiments/RT-1a-isa-operand-falsify/RESULTS.md`
and, for **each**, run our OWN splice-and-observe test on the real A18 Pro GPU to confirm the
corrected encoding BEFORE trusting it — then apply the fix to `tools/agx-isa/*` + `docs/isa/*`.
The red-teamer may itself be wrong; nothing is applied on its say-so alone.

**Clean-room category:** OWN-SHADER + HW-PROBE. Every byte inspected/spliced is the compiled form
of MSL *we wrote* (`kernels/*.metal`), run on the real GPU. No Apple binary was disassembled.
Device workspace: `~/cleanroom_work/rt1afix/`.

## Method
Compile our MSL → extract `_agc.main` (`tools/shdump`) → splice bytes → run on hardware via
`agxrun_persist` and read back outputs (`tools/agxtest`). The a[]-ramp trick (`a[j]=100·j+3`)
de-confounds "the load read a[k]" from "the store read a stale register".

## Harness (`harness/`)
- `mem_index.py` — item 1: sweep the a[i0] load's byte+5 (index reg), byte+6 (inert?), byte+1
  (space), byte+9/10/11 (immediate offset); `off_confirm.py` confirms the +512/+2 offset scaling.
- `iadd_polarity.py` — item 2: splice a real add's byte0 `0x9f→0x1f`, read 10+20 vs 10−20.
- `uniform_src.py` — item 3: prove `a+uniform` reads the runtime uniform (vary p.k); prove the
  minifloat-vs-uniform split (splice cadd byte+1); map the uniform index (`uni_multi.metal`).
- `undecoded.py` / `fb_confirm.py` — item 4: characterize byte0 `0x60` (spill/frame marker) and
  the byte+2=`0x18` compact accumulate (splice/observe; dst-redirect load-bearing check).
- `verify_fixes.py` — pure-DB check that all five edits decode + round-trip and both former-
  halting programs tokenize with 0 leftover (no device needed).

## Kernels (`kernels/`)
`bank.metal` (D4 index), `add.metal`/`cadd.metal` (add / minifloat imm), `rt1a_uni.metal` +
`uni_multi.metal` (uniform source), `rt1a_iaddbank.metal` (iadd2 polarity), `rt1a_big.metal`
(0x60 spill marker), `rt1a_falubank.metal` (0x18 compact accumulate).

## Results
See `RESULTS.md`. Raw logs in `raw/`. Deliverable edited `tools/agx-isa/*` + `docs/isa/README.md`
+ `docs/isa/encoding-tables.md` + `docs/isa/agx3.xml` (regenerated); did NOT commit.
