# EXP-0031: special-register enum + preloaded-register ABI

- **Date:** 2026-07-07
- **Clean-room category:** OWN-SHADER + HW-PROBE (+ PUBLIC for the agx-isa DB *schema*)
- **Phase / question:** backlog #4, gap G-5 (a compiler must know the SR-number table
  and how built-in inputs arrive in registers). Compute + graphics (VS/FS).
- **Device state:** Apple A18 Pro / G17P, SoC T8140, macOS 26.6 (25G5043d), Metal 4 /
  Apple9, SIP disabled. Device workspace `~/cleanroom_work/exp0031/`. **Reboots: 0.**

## Hypothesis
1. Built-ins read via `get_sr` (byte0 low-nibble `0xC`, 4B) encode the SR number in a
   field we can enumerate by compiling one-built-in-per-shader and byte-diffing. EXP-0010
   guessed the SR-select is the byte0 **high nibble**; we test that.
2. Some built-ins are *preloaded* into registers at shader entry rather than read via
   `get_sr` (e.g. VS `vertex_id`, vertex-attribute base); determine the entry contract.
3. FS inputs (varyings, `[[position]]`, `[[color]]`) arrive via interpolation/get_sr; the
   FS returns color via a fixed epilog.
4. VS `[[stage_in]]` attributes are pulled by a fetch (in-shader) or preloaded.

## Method (clean-room legal)
- **OWN-SHADER:** `gen_kernels.py` writes MSL **we authored**, one built-in each, storing
  to a *constant* address so the only `get_sr` is the one under study. `run_extract.py`
  compiles them on-device with **our** `shdump` (`newLibraryWithSource:` -> `MTLBinaryArchive`)
  and extracts the AGX bytes with **our** `agxparse.py`. No Apple binary is disassembled.
- **HW-PROBE (splice-and-observe):** `agxtest.py` splices the candidate SR-number byte into
  a dispatched `out[gid]=builtin` kernel and reads the output back — proving which field is
  the SR selector by *behaviour*, not byte-diff.
- **Graphics:** `agxrender` (own VS+FS -> BGRA8 target -> pixel readback) HW-validates FS
  built-ins; `harness/attrdump.m` (our own harness = shdump render path + a real
  `MTLVertexDescriptor`) extracts the VS to see how `[[stage_in]]` attributes are pulled,
  varying format/offset/stride/step to prove shader specialization.

## Procedure
```sh
# host: generate kernels
python3 gen_kernels.py
# device: build tools + extract every built-in's AGX bytes
scp shdump.m agxparse.py agxrun.m agxtest.py agxrender.m run_extract*.py manifest.json <dev>:~/cleanroom_work/exp0031/
scp kernels/*.metal harness/attrdump.m <dev>:~/cleanroom_work/exp0031/kernels/
ssh <dev> 'cd ~/cleanroom_work/exp0031 && clang -fobjc-arc -framework Metal -framework Foundation -o shdump shdump.m &&
           clang ... -o agxrun agxrun.m && clang ... -o agxrender agxrender.m && clang ... -o attrdump attrdump.m &&
           python3 run_extract.py && python3 run_extract2.py'
# host: analyze
python3 analyze.py            # -> raw/getsr_table.txt
# HW SR-number splice validation (device):
ssh <dev> 'cd ~/cleanroom_work/exp0031 && for sp in 82 85 9c 98 a4 a0; do \
  python3 agxtest.py --source kernels/hw_tidx.metal --function k --grid 64 --tg 64 --int --out 0=64 \
    --splice _agc.main@0x05=$sp; done'
```
Full transcripts in `raw/` (see below).

## Raw results
- `raw/extract.json` — every built-in's extracted `_agc.main`/`constant_program` hex (compute + VS/FS).
- `raw/extract2.json` — stage_in vertex-attribute fetch across 6 layout variants + barycentric FS.
- `raw/getsr_table.txt` — analyzer output: SR number (byte1) per built-in.
- `raw/splice_validation_compute.txt` — **HW proof** SR number = byte1 (+ the mov_imm sibling).
- `raw/render_validation.txt` — front_facing (both windings) + barycentric gradient pixels.
- `raw/vertex_attr_fetch.txt` — the 6-variant proof that vertex fetch is shader-specialized.

## Analysis / established facts
See `RESULTS.md`. Headline: **SR number = get_sr byte1** (HW-validated; corrects
EXP-0010's "high nibble" — that nibble is the dest GPR). Full SR-number table for compute
+ graphics; VS/FS entry ABI; FS epilog; and **vertex attribute fetch is in-shader
software fetch** (compiler lowers the vertex descriptor into the VS prologue).

## Established facts → docs (orchestrator owns docs/)
- SR-number table + get_sr byte1 encoding → `docs/isa/` (get_sr section) + `PROVENANCE.md` (OWN-SHADER+HW-PROBE, EXP-0031).
- Preloaded-register / entry ABI per stage → `docs/pipeline/` (or `docs/isa/` machine model) + `PROVENANCE.md`.
- Vertex attribute fetch = shader-specialized → `docs/pipeline/` (vertex) + coordinate with EXP-0014 cmdstream.
- Refined descriptors staged in `new_descriptors.json` (do NOT edit `tools/agx-isa/`).

## Follow-ups
See `RESULTS.md` §Recommended next.
