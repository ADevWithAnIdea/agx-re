# RT-1a — Red-team falsification of ISA arithmetic/logic/memory operand encodings + D4

**Role:** RED-TEAM verifier. Assume the ISA findings in `docs/isa/` and `tools/agx-isa/db.json`
may be subtly wrong in fields/attributes. Run splice-and-observe tests that try to **break**
the documented claims, not confirm them.

**Clean-room category:** OWN-SHADER + HW-PROBE. Every byte inspected/spliced is the compiled
form of MSL *we wrote* (`kernels/*.metal`), run on the real A18 Pro GPU. No Apple binary was
disassembled. Device workspace: `~/cleanroom_work/rt1a/`.

## Method
Compile our MSL → extract `_agc.main` (`tools/shdump`) → splice a single byte across a value
range → run on hardware via `agxrun_persist` and read back outputs (`tools/agxtest`). The
harness (`harness/sweep.py`, `harness/mapload.py`) sweeps one byte position of one instruction
and reports the runtime output per value, so we can see *which byte actually controls what*.
Truth tables / formulas are compared to the DB (`tools/agx-isa/isadb.py`).

Key trick for the memory-op index question: fill the indexed buffer `a[]` with `a[j]=100*j+3`
so an **index change** shows up as `a[k]` (…603,703,903,3) while a **dest/store-register**
change shows up as raw register contents (6,7,9) — this de-confounds "the load read a[k]" from
"the store read a stale register".

## Harness (`harness/`)
- `sweep.py` — sweep one byte of `_agc.main` over a value set; run each spliced archive; print outputs.
- `mapload.py` — classify every byte of a target instruction as index-affecting / dest-confound / inert.
- `minifloat_verify.py` — full-range packed-minifloat sweep vs the DB `imm_decode` formula (both signs).
- `lut_combo.py` — ilogic 2-input LUT: op_base × invert bytes, decode the boolean truth table from `out&0xF`.
- `census1.py` — resync tokenizer/census over one `_agc.main` (coverage %, undecoded + length-only leaders).

## Kernels (`kernels/`)
`bank.metal` / `idx3.metal` / `vec*.metal` (D4 index register), `cadd.metal` (minifloat immediate),
`icmp/fcmp/fge/iand.metal` (compare CC + bitwise LUT), `falubank2.metal` / `iaddbank.metal` /
`isub.metal` / `uni.metal` (falu2/iadd2 operands + uniform), `big.metal` / `hireg*.metal` (large stress).

## Results
See `RESULTS.md`. Raw logs in `raw/`. Deliverable did NOT edit `tools/agx-isa`, `docs/`, or commit.
