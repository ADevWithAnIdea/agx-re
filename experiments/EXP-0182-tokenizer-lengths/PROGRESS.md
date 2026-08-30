# EXP-0182 — PROGRESS

Append-only. Timestamped after every milestone (SUBAGENT_BRIEF: assume the host dies).

## M0 — 2026-08-30 — orientation complete, baseline gate reproduced

Read `CLAUDE.md`, `CODEX.md`, `experiments/SUBAGENT_BRIEF.md`,
`experiments/FIELD-SWEEP-PROTOCOL.md` §3, `tools/agx-isa/isadb.py:instr_length`,
EXP-0180 `analysis/{db_defects,length_rule}.json`, EXP-0181 `RESULTS.md` §3.3 +
`analysis/anchor_reachability.py`, EXP-0175 `analysis/ab_gate.py`.

* **Baseline corpus gate reproduced EXACTLY**: `clean=833/1080 leftover=388604 tokens=25419`.
* **DEF-0181-2 reproduced exactly** against the live `tools/agx-isa` (before any edit):

| descriptor | anchor | declared len | `instr_length` | `decode_one` |
|---|---|---:|---|---|
| `bf_add_dst`  | `21001c001100c081`     | 8  | **2**    | `operand_word` |
| `bf_fma_dst`  | `21001e0086041000c081` | 10 | **2**    | `operand_word` |
| `hminmax`     | `22001c0010c0`         | 6  | **10**   | truncated (need 10, have 6) |
| `cvt_bf16`    | `0101148105024000`     | 8  | **None** | unknown length (byte0=0x01) |
| `cvt_f2h_dst` | `c10114810402`         | 6  | **None** | unknown length (byte0=0xc1) |
| `cvt_f2h` (control) | `110114810402`   | 6  | 6        | `cvt_f2h` ✅ |

* **EXP-0180 is COMPLETE, not still running** (its `PROGRESS.md` M11 + `RESULTS.md` +
  `analysis/length_rule.json` are on disk). Its DEF-0180-2 hardware verdict has LANDED:
  the measured half-ALU length rule is keyed on `(byte+2 & 7, byte+4 & 3)` and BOTH
  `db.json`'s stated rule (wrong in 25/32 cells) and `isadb.py`'s implemented rule
  (wrong in 18/32) disagree with it. Coordination point, not a pre-emption.

Next: M1 = re-derive each defect from committed `raw/` before touching `isadb.py`.
