# EXP-M4-09 / CMD-2 — Stencil ops 0–7 on all three op fields

**Clean-room category:** DATA-TRACE (iotrace interposer on the userspace↔kernel
boundary) + OWN-SHADER (our own MSL, compiled at runtime). No Apple binary
disassembled; no shader-code BO inspected. State-pool bytes only.

**Device:** LOCAL host — **Apple M4** (Mac16,10), macOS 26, Metal feature family
Apple9. (Doc offsets under test were originally established on A18 Pro / T8140 in
EXP-0019 — see A18-cross-confirm flag below.)

**Harness:** reused `svar.m` + `iotrace.c` + `bodiff.py` from
`RT-2a-cmdstream-falsify/harness` (built `-arch arm64e`). Run driver `run.sh`,
decoder `extract.py`. Raw captures in `caps/`, diffs in `analysis/`.

## Gap addressed

EXP-0019 swept all 8 stencil ops on the **PASS** field only; sfail/zfail were tested
with just 2 of 8 ops. The doc's shared 0–7 stencil-op enum across all three op fields
was therefore an **assumption** for sfail/zfail. This experiment sweeps all 8 ops
**independently** on each of pass (`spass`, [18:16]), zfail (`szfail`, [21:19]), and
sfail (`sfail`, [24:22]) to confirm the shared enum + exact bit positions, and checks
front vs back-face.

## Method

Front stencil word lives at `0x58000` state-pool **+0x3c**, back at **+0x44** (doc).
Reference (enabled) config: `--stencil --scmp less --spass replace`. `--scmp less`
(≠ always) keeps the depth/stencil packet enabled even when an op field is `keep`, so
every capture emitted a valid packet (all 26 dispatches returned `status=4`,
GPU-completed). To isolate one op field, the other two op fields are held at `keep`;
for the szfail/sfail sweeps `--spass replace` is held as a constant anchor and verified
to stay `pass=2` throughout (subtracted out). One byte per capture read straight from
the +0x3c word; `bodiff.py` used to prove isolation.

`svar.m --sback` sets a DISTINCT hardcoded back face — Metal
`compare=equal, sfail=zero, zfail=invert, pass=replace, readMask=0x0f, writeMask=0x3c`
— to test the back-face word (+0x44) encoding independently.

## Raw results — front-face word (+0x3c), one representative per op

Reference `s_ref` (--scmp less --spass replace): `+0x3c = 0x0202ffff`
(wm=0xff rm=0xff pass=2 zfail=0 sfail=0 cmp=1).

### spass sweep — pass-op field [18:16]
| op | 3-bit code | raw +0x3c word |
|----|-----------|----------------|
| keep      | 0 | 0x0200ffff |
| zero      | 1 | 0x0201ffff |
| replace   | 2 | 0x0202ffff |
| incrclamp | 3 | 0x0203ffff |
| decrclamp | 4 | 0x0204ffff |
| invert    | 5 | 0x0205ffff |
| incrwrap  | 6 | 0x0206ffff |
| decrwrap  | 7 | 0x0207ffff |

(zfail=0, sfail=0, cmp=1 constant across the sweep — only bits [18:16] move.)

### szfail sweep — zfail-op field [21:19]
| op | 3-bit code | raw +0x3c word |
|----|-----------|----------------|
| keep      | 0 | 0x0202ffff |
| zero      | 1 | 0x020affff |
| replace   | 2 | 0x0212ffff |
| incrclamp | 3 | 0x021affff |
| decrclamp | 4 | 0x0222ffff |
| invert    | 5 | 0x022affff |
| incrwrap  | 6 | 0x0232ffff |
| decrwrap  | 7 | 0x023affff |

(pass=2, sfail=0, cmp=1 constant — only bits [21:19] move.)

### sfail sweep — sfail-op field [24:22]
| op | 3-bit code | raw +0x3c word |
|----|-----------|----------------|
| keep      | 0 | 0x0202ffff |
| zero      | 1 | 0x0242ffff |
| replace   | 2 | 0x0282ffff |
| incrclamp | 3 | 0x02c2ffff |
| decrclamp | 4 | 0x0302ffff |
| invert    | 5 | 0x0342ffff |
| incrwrap  | 6 | 0x0382ffff |
| decrwrap  | 7 | 0x03c2ffff |

(pass=2, zfail=0, cmp=1 constant — only bits [24:22] move.)

### Isolation (bodiff on 0x58000 pool, first 0x80 bytes)
`s_ref` vs `spass_invert` / `szfail_invert` / `sfail_invert`: the ONLY differing
words are +0x3c and +0x44 (both, because svar defaults back-face = front-face). No
other pool byte moves. → each op field is confined to the stencil word; changing it
touches nothing else.

### Back-face (+0x44)
| capture | front +0x3c | back +0x44 | back decode |
|---------|-------------|-----------|-------------|
| s_ref (back=front) | 0x0202ffff | 0x0202ffff | pass=2 zfail=0 sfail=0 cmp=1 wm=0xff rm=0xff |
| sback (distinct)   | 0x0202ffff | 0x046a0f3c | pass=2 zfail=5 sfail=1 cmp=2 wm=0x3c rm=0x0f |

`sback` back-face word decodes to exactly the Metal descriptor set on the back face
(compare=equal→2, sfail=zero→1, zfail=invert→5, pass=replace→2, writeMask=0x3c,
readMask=0x0f), while front +0x3c is untouched. bodiff `s_ref` vs `sback` shows a
**single** differing word: +0x44. → back-face is an independent word at +0x44 using
the **identical** bit layout and op/compare enums as front +0x3c.

## Verdict

**CONFIRM (all three fields).** All three stencil-op fields share one enum and sit at
the documented bit positions in the `0x58000+0x3c` (front) / `+0x44` (back) stencil
word. No per-field difference; no correction needed.

Stencil word bit layout (HW-validated on M4):
```
[7:0]   write-mask
[15:8]  read-mask
[18:16] pass-op   (spass)   \
[21:19] zfail-op  (szfail)   } shared stencil-op enum, see below
[24:22] sfail-op  (sfail)   /
[27:25] compare
[31:28] unused (0 in all captures, incl. distinct back-face)
```
Shared stencil-op enum (identical for pass / zfail / sfail, front and back):
```
0 keep   1 zero   2 replace   3 incrClamp
4 decrClamp   5 invert   6 incrWrap   7 decrWrap
```
This matches `docs/cmdstream/README.md` "Depth/stencil packet" exactly — the
assumption for sfail/zfail is now **validated** (was: 2-of-8 ops each; now: 8-of-8
independently, plus the distinct-back-face cross-check).

## Findings status
- **HW-validated** (dispatch confirmed, status=4): every row above. The op codes are
  data read from the registered state-pool BO after a GPU-completed draw.

## A18 cross-confirm flag
These captures are from the **M4** (Apple9). The M4 stencil word is byte-for-byte
consistent with the A18 doc (same offsets +0x3c/+0x44, same fields, same enums). The
doc's offsets/enums were originally from A18 (EXP-0019). Result **agrees** with the
doc, so no doc correction is needed and no contradiction to resolve. Recommend a
single A18 spot-check (e.g. `sfail_invert` + `szfail_invert` + `sback`) only if the
orchestrator wants belt-and-suspenders parity; nothing here suggests divergence.

## Reproduce
```
cd experiments/EXP-M4-09-cmdstream-coverage/cmd2-stencil
clang -arch arm64e -dynamiclib -o iotrace.dylib iotrace.c -framework IOKit -framework CoreFoundation
clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o svar svar.m
sh run.sh            # 26 captures -> caps/, decoded table -> analysis/table.txt
python3 extract.py   # re-decode
```
