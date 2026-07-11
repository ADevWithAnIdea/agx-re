# EXP-M5-02 — M5 own-corpus ISA census vs the G17P/A18 DB (prioritized delta list)

**Device:** Apple M5 / **Apple10 / G17g** / SoC T8142 / macOS 27.0. Clean-room: our own MSL
corpus (reused from the A18 phase), compiled on the M5 with our own `shdump`, decoded with our
own `agx-isa` (the unmodified 170-descriptor **A18/G17P** DB). No Apple binary introspected.

## Corpus
- 902 own-MSL source files → **1085** extracted stage programs (compute + render); compile pass:
  939 compute / 73 render OK, 41+28 fail (render-fail, unsupported MSL, non-kernel entry) —
  see `build_summary.json`, `manifest.txt`. Hex kept on device (`~/cleanroom_work/EXP-M5-02/hex`,
  gitignored); `hex_sample.tgz` is a small committed sample.

## Headline coverage (unmodified G17P DB on M5 bytes) — `census.txt`
- **96,897 instructions** walked over 701 unique streams.
- **FULLY-NAMED: 76.82%** of tokens · length-only 3.57% · **UNDECODED 19.61%**.
- **BYTE COVERAGE (named+length): 84.13%** · undecoded bytes **15.87%**.
- 240 distinct byte0 groups; **44 never decoded** (pure gaps).
- **Confirms: M5 (G17g) is a G17-family *sibling* of the A18 (G17P) — a delta, not a rebuild.**
  ~84% of bytes already decode; the job is the ~16% G17P→G17g variance.

## Root-cause target list — `first_desync.txt` (the actionable ranking)
Only **4.2%** of kernels decode fully; **but** the breaks concentrate on a few real ops. Ranking by
*first* desync per kernel (cuts the resync-artifact noise that inflates the raw byte0 histogram —
e.g. `0x01`'s 5365 "named-elsewhere" is a store **tail**, not a new op):

| rank | byte0 | #kernels break here first | sample ctx | likely family |
|---|---|---|---|---|
| 1 | **0x18** | **204** | `18 22 10 c0 41 00` | **memory load** (a[i]/b[i]) — top priority |
| 2 | 0x41 | 60 | `41 00 80 00 00 00` | store/mem (bit7-paired with 0xc1) |
| 3 | 0xc1 | 51 | `c1 00 80 00 00 00` | store/mem |
| 4 | 0x24 | 47 | `24 81 01 50 28 00` | mem/typed |
| 5 | 0x3f | 46 | `3f 0c 03 02 18 22` | ALU/preamble |
| 6 | 0x01 | 37 | `01 26 10 40 0e 00` | (partly tail resync) |
| 7 | 0xa0 | 34 | `a0 82 11 00 0f 08` | 0xa_ family |
| 8 | 0x07 | 30 | `07 02 82 00 0f 04` | varying/mem |
| 9 | 0x20 | 23 | `20 0e 04 95 10 06` | mem/pad |
| 10 | 0x78 | 22 | `78 2a 10 00 4f 08` | typed/sample (shares `2a 10` w/ 0x58/0x50) |
| … | 0xbe/0x3e | 14/12 | `be 20 39 0e` / `3e 40 19 0e` | short-ALU, 4B ending `0e` (bit7-paired) |
| … | 0xef/0xff | 15/9 | `ef 48 43 00 28 0c` | function/call (`43` = A18 call marker; bit4-paired) |
| … | 0xa5/0xa4/0xa1 | 8/8/7 | `a5 0a 02 00 1e 00` | 0xa_ family |

## Second angle — `predecessor_analysis.txt`
Most undecoded regions follow multi-word ops (`pad_operand`, `operand_word`, `n3_mov`). Strong
signal that several M5 multi-word instructions have **different length rules** than G17P — the
G17P length under/over-counts and leaves an operand tail that then fails to decode as a leader.
So the delta is a mix of: (a) a few **new/relocated leaders** (0xb7, 0xfe, 0x5e, 0xbe, 0x9e —
never decoded, named_elsewhere≈0), and (b) **length-rule/field deltas** on known multi-word ops.

## Prioritized Phase-1.3 fan-out (by family; splice-validate on M5)
1. **Memory family** — `0x18` load, `0x41`/`0xc1` store, `0x24`, `0x07`, `0x20` (~400 kernels; biggest win).
2. **Typed/sample family** — `0x78`/`0x58`/`0x50` (`2a 10` signature), `0x24`.
3. **Short-ALU + length-rule deltas** — `0x3e`/`0xbe`, `0x3f`, `0x32`, `0x02`, `0x42`; fix multi-word lengths.
4. **New leaders** — `0xb7`, `0xfe`, `0x5e`, `0x9e`, `0xa5` (provoke + byte-diff to identify).
5. **Function/call** — `0xef`/`0xff` (`43` marker), and the 0xa_ family (`0xa0`/`0xa1`/`0xa4`).
Each: author own-MSL provocations, byte-diff, splice-and-observe on M5, propose isadb.py patch;
main agent integrates + re-censuses to convergence. See `../M5-DELTA-SUBAGENT-BRIEF.md`.

## Refined analysis (final census run — 112,707 tokens / 536,960 bytes)
- **Structural finding: the low-nibble-`e` byte0 column is systematically broken** —
  `0x3e/0x5e/0x7e/0x9e/0xbe/0xde/0xfe/0xae` are *all* heavy undecoded leaders (5 of top-12; `0x3e`
  alone = 12.5 KB undecoded). A whole byte0 diagonal the G17P length rule no longer resolves ⇒ the
  **`0xNe` instruction format changed G17P→G17g**. Highest-value structural target.
- **Length-delta lever ranking** (fix the *predecessor* op's length rule, reclaims the tail):
  `n3_mov` is #1 (real-op count 9,153; dominant predecessor of `0x32`/`0x42`/`0x38`/`0x30` desyncs,
  ~2,300 regions — one fix, largest slice); then `n2_op10`→`0x01` (+~4B), `tex_deriv`+`b_alu10_lof`→`0xe0`
  (+~2B), `icmp_pred`→`0x1e` (+2B), `isel10`→`0xa1`/`0xa8` (operand delta).
- **Silent deltas (decode-but-wrong: named op systematically precedes a desync):** `b_alu10_lof`
  **100%** mis-lengthed (cleanest), `operand_word_x2_h5` 93%, `mask_op` 90%, `sr_read_wide` 84%,
  `falu3_ext` 78%, `n2_op10` 42%, `tex_deriv` 39% (highest volume, 1,455). **Length-only relocations**
  (matched length, lost name → match bits moved): `0x27` (2391 vs 869 named), `0x17`, `0x81`, `0x8f`.
- **Recommended next-wave order:** (1) `n3_mov` length/operand delta; (2) new `0xNe` leader column;
  (3) `0xb7` new opcode family; (4) `n2_op10` +4B (`0x01`); (5) `tex_deriv`+`b_alu10_lof` +2B (`0xe0`);
  (6) `icmp_pred`/`isel10` (`0x1e`/`0xa1`); (7) relocated match bits on `0x27`/`0x17`.
- Caveat (honest): `pad_operand` (22k) + `operand_word` (12k) tokens inflate the "named %" identically
  on A18 and M5, so **byte-coverage / undecoded-rate are the truer metrics** than fully-named %.

## Files
`census.py` / `census.txt` (full census), `first_desync.py` / `first_desync.txt` (root-cause; main-agent pass),
`predecessor_analysis.txt` (length-delta signal), `build_m5.py` / `build_summary.json` / `manifest.txt`
(corpus build), `hex_sample.tgz` (sample). Bulk hex on device (gitignored).

## Clean-room attestation
Own-MSL corpus + our own tools only; the only Apple-touching step is invoking the public Metal
runtime compiler on our own source. No Apple binary was disassembled/introspected. Numbers are
from actual runs; scripts committed for reproduction.
