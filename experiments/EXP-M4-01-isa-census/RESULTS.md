# EXP-M4-01 — M4 ISA census: does the Mac Mini M4 share the A18 Pro ISA?

**Hypothesis:** The Apple **M4** (Mac16,10, this host — local Mac Mini M4, 10-core GPU, Metal 4)
runs the same AGX shader ISA as the A18 Pro (G17P / Apple9), so the A18 clean-room DB
(`tools/agx-isa`) should disassemble M4-compiled shaders.

**Method (clean-room, OWN-SHADER):** Built `shdump` locally on the M4
(`clang -fobjc-arc -framework Metal -framework Foundation`). Compiled the **57-shader A18
corpus** (`experiments/EXP-0036-consolidation-census/corpus/*.metal`) on the M4 via runtime
`newLibraryWithSource:`, extracted each `_agc.main` with our own Mach-O parser
(`agxparse.py`), and ran the **A18 DB resync census** (`census/census.py`) over the M4 bytes.

## Result — M4 IS the same ISA

| metric | A18 Pro (G17P) | **M4 (Mac16,10)** |
|---|---|---|
| corpus shaders compiled | 57 | **57 (0 failures)** |
| threadExecutionWidth | 32 | **32** |
| maxThreadsPerThreadgroup | 1024 | **1024** |
| container / image format | AppleGPU (cputype 0x1000013), `_agc.main` | **identical** |
| tokens cleanly tokenized | ~88% | **88.6%** |
| **byte coverage (A18 DB on the bytes)** | ~90.6% | **91.5%** |

The A18 disassembler decodes M4-compiled shaders at the **same coverage**, and the first
instructions of a mixed kernel match **including the A18 red-team corrections** — `get_sr`
`sr_sel=0xa0`, `device_load` with the corrected **byte+5 index register**, `icmp_pred`, and the
`scoreboard_fence` (`0x07`/byte+2=`0x02`) variant decoded during RT-ISA-FIX. Integer
`imad`/`imul` (byte0 `0x9f`, **byte+2=0x56** vs `iadd2`'s `0x54`) also decode identically.

**Conclusion:** M4 and A18 Pro share the AGX Apple9 shader ISA. M4 GPU config delta so far:
**10 GPU cores** (vs A18 Pro's 5). Remaining ISA work: the census shows ~28 undecoded byte0
groups (mostly length-mis-count resync cascades in dense kernels — see
`UNDECODED-INVESTIGATION-NOTES.md`); being driven to ~0 to prove the ISA DB is complete on
both parts.

## Provenance
`census/` (harness + `hex/` = M4-compiled `_agc.main` bytes, OWN-SHADER), `raw/M4_census.txt`,
`work/` (isolation kernels). Method: OWN-SHADER + HW-PROBE (local M4). No Apple binary inspected.
