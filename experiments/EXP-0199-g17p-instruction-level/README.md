# EXP-0199 — the five FIELD-COMPLETE instructions blocked at the INSTRUCTION level

**Target:** A18 Pro / G17P (`192.168.170.254`). **Clean-room:** OWN-SHADER + HW-PROBE.
**Read `RESULTS.md` for the findings**, `PRE_REGISTRATION.md` + `CAPTURE_CONTRACT.json`
for the original frozen contract, and `AMENDMENT-01.md` +
`CAPTURE_CONTRACT-AMENDMENT-01.json` for the gates added mid-experiment when
`RE_EXPERIMENT_PROCESS_CORRECTIONS.md` landed.

## The question

`frag_depth_store`, `n2_op6`, `vary_slot` (`corpus-correlation`) and
`frame_marker_compact`, `sfu_marker` (`tokenization-only`) have **every named field at
emitter grade** and are blocked by their `_instruction` row. That is not a field gap, so
this is **not a field sweep**. The question is whether the *descriptor itself* — its match
bits, its length, and the operation its `semantics` string names — does what `db.json`
claims when **we** generate the instruction and run it on hardware.

## Method, in one paragraph per shape

**Render instructions (`frag_depth_store`, `vary_slot`, `n2_op6`).** Splice raw bytes into
our own compiled shader inside a serialized `MTLBinaryArchive`, force Metal to instantiate
the pipeline from the archive's machine code (`FailOnBinaryArchiveMiss`), draw, and read the
attachments back. `frag_depth_store` is scored against the **Depth32Float attachment**,
which no prior experiment could read; `vary_slot` against four varyings whose values are
widely separated constants, so a slot change is directly readable.

**Marker instructions (`sfu_marker`, `frame_marker_compact`).** *Independent emission by
insertion*: place the instruction, from bytes we choose, at an instruction boundary the
compiler did not choose, in a straight-line compute carrier that contains no leader of that
family, shifting the tail into the container's zero alignment pad so the file length is
unchanged. If the hardware consumes a different number of bytes than we inserted, the next
instruction loses its leader and the stream desynchronises — so the carrier's 32-lane host
oracle **is** a length test.

## What makes each oracle discriminating (the failure this corpus keeps repeating)

- `c_depth`/`c_depth2` give **depth and colour different per-pixel functions** of different
  varyings, so the depth attachment carries information the colour attachment does not, and
  the colour attachment is a paired control that must not move.
- `c_vary4`'s four varyings are 1000/2000/3000/4000, so a relocation names the slot used —
  and the **positive control** (`vary_store.out_slot`, a different instruction) produces six
  exact host-predicted relocations on the same observable.
- `k_line3` computes a different value in every lane from a host-supplied buffer, writes an
  **integrity sentinel first through its own store**, and leaves two regions never written
  so the 0xDEADBEEF poison distinguishes *wrong* / *halted early* / *never ran*.

## Layout

```
kernels/     c_depth.metal c_depth2.metal c_vary4.metal k_line.metal k_line2/3/4.metal k_sin.metal
harness/     gfrun5.m (render; forked verbatim from our EXP-0172 gfrun2.m, + --ledger)
             crun199.m (compute splice runner with the 0xDEADBEEF poison the shared
                        agxrun_persist.m lacks, + --ledger)
             runner199.py (ONE pump thread per child -- DEF-0178-1)
run.py       discovery driver          conf.py   confirmation driver (ledger + predictions)
analysis/    tok.py predictor.py gates.py make_verdicts.py
             gate_report.json field_verdicts.json predictions_<run>.json
raw/         prefreeze/  smoke01  g17p_run01{a,b,c}  g17p_run02{a,b,c}
             g17p_confsmoke  g17p_conf02 g17p_conf03 (retained defective partials)
             g17p_conf01 (shuffled)  g17p_conf04 (reversed)   <- the GATED confirmation
```

## Reproduce

```sh
# on the neo, under ~/agxre/EXP-0199
python3 run.py  g17p_runNNa AE ; python3 run.py g17p_runNNb B ; python3 run.py g17p_runNNc CD
python3 conf.py g17p_confNN shuffle
python3 conf.py g17p_confMM reverse
# on the repo host
python3 analysis/gates.py && python3 analysis/make_verdicts.py
```

## Headline

- **`frag_depth_store` writes the shader `[[depth]]` output to the depth attachment** —
  observed directly for the first time, on two carriers, against an independent host oracle.
- **`vary_slot.slot` does not select a varying slot** — 0 relocations in 256 values × 2
  captures, against a positive control that produced 6 exact ones.
- **`sfu_marker` is a standalone 2-byte instruction we can emit anywhere** — correct at 7 of
  7 boundaries while three controls are correct at 0 of 7.
- **`frame_marker_compact` is 4 bytes, not 2, in the tested envelope** — the 2-byte form is
  correct at 0 of 7 boundaries and for 0 of 254 byte+1 values; the 4-byte form at 7 of 7.
- **`n2_op6` is not promoted**, and Amendment 01 said so before the run.

Clean-room provenance: OWN-SHADER + HW-PROBE. Inputs inspected: only MSL we authored and the
AGX bytes the public Metal runtime produced from it. Apple binary introspection: NONE.
