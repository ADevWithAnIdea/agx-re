# EXP-0146 — Part-II answer block for the `I64` section

**For the orchestrator to splice into `APPLE9_RE_IMPLEMENTATION_GAPS.md`.** This experiment did
**not** edit that file. Format follows the existing `INT`/`PACK` blocks in
`work/GAPS-ANSWER-BLOCKS.md`: an `ANCHOR:` line copied byte-for-byte from the task list, then the
block to insert immediately after it, separated by one blank line, with `  > ` indentation.

Anchor verified unique at authoring time:
`grep -Fxc "  These answers validate the current \`lower_int64_options\` mask instead of merely inheriting it." APPLE9_RE_IMPLEMENTATION_GAPS.md` == 1

---

### ANCHOR:   These answers validate the current `lower_int64_options` mask instead of merely inheriting it.

  > **Answered 2026-08-28 (EXP-0146, M4/G16G) — I64 block.** Two gated capture runs (`run01`,
  > `run03`, 18 786 records each) plus a 5x-serial adjudication pass (`run04`, 1 735 cases) and a
  > targeted second-method pass (`run05`); **0 unresolved cases remain**. Nineteen 64-bit kernels
  > we authored were executed against host-computed oracles on 8 frozen boundary rows each and
  > were **exact in every row**, so every structural claim below sits on a working program.
  > **I64-01 YES — but not the way the compiler does it. A native, single-instruction 64-bit ADD
  > exists and the Apple compiler never emits it.** Source-level `a + b` on `ulong` compiles to a
  > FIVE-instruction chain — `iadd2` (low) -> `carry_gen` -> `psel` -> `iadd2` -> `iadd2` —
  > confirming EXP-0102's INT-13 observation on a fresh compile. But `a - b` on the same types
  > compiles to **one** `iadd2` (byte0 `0x1f`) between an 8-byte `device_load` pair and an 8-byte
  > `device_store`, and `iadd2`'s byte0 bit 7 is the HW-validated add/subtract selector. Splicing
  > **only that bit** (`0x1f -> 0x9f`) turns that single instruction into a **complete 64-bit add
  > with carry across the word boundary**: exact on all 8 rows of the frozen input set in both
  > gated runs, and exact again on a second, independently chosen boundary set in 5/5 repetitions
  > (`run05` P1) — including `0xFFFFFFFFFFFFFFFF + 1 = 0`, `2^63 + 2^63 = 0`,
  > `0xFFFFFFFF00000000 + 0x00000000FFFFFFFF = 0xFFFFFFFFFFFFFFFF` and
  > `0xAAAA…AAAA + 0x5555…5556 = 0`. A backend may therefore emit ONE 10-byte instruction where
  > Apple emits five. **This is the single highest-value finding of the experiment and it
  > supersedes the reading of EXP-0102/EXP-0038 that 64-bit add is necessarily a carry chain.**
  > **I64-02 YES** — one register-pair instruction performs a complete 64-bit subtract including
  > the borrow. `k_u64sub.metal` / `k_s64sub.metal` both compile to
  > `get_sr, device_load, device_load, iadd2, device_store, stop`: exactly **one** arithmetic
  > instruction, with the loads/stores using element code 4 (8 bytes) rather than code 3 (4
  > bytes). Borrow-crossing rows (`0x0123456789ABCDEF - 0x00000000FEDCBA98`,
  > `0 - 0`, `0x0000000A7FFFFFFF - 0x0000000B80000000`) all read back exact, so the borrow is
  > produced inside that single instruction. Signed and unsigned are byte-identical.
  > **I64-03 PARTIAL / mostly UNKNOWN.** What was established, by dense hardware sweeps of the
  > 64-bit form's own fields (all 256/128/64/2 values per field, both gated runs agreeing):
  > the destination is a register-PAIR base encoded `(reg<<1)|size` in byte+3 whose size bit is a
  > don't-care; **destination byte values `0xBE..0xFF` (register index >= 95) raise a contained
  > GPU address fault**, which independently corroborates the ~96-entry addressable GPR file of
  > EXP-0020 from a different family; and in the source-A descriptor (byte+7) **every value with
  > bits 0 and 1 both set faults** (64 of 256). What was NOT established: whether the operation
  > works at *other* pair placements. Moving a source descriptor also changes which register is
  > read, so in a carrier whose loads write fixed registers a relocated operand reads garbage and
  > is indistinguishable from an illegal placement. Answering I64-03 properly requires
  > co-mutating the `device_load` destinations with the `iadd2` operands; that was scoped out and
  > is the recommended successor. **Do not assume unaligned pairs work.**
  > **I64-04 YES** — 32x32->64 multiplication is a single `imad` for both interpretations.
  > `ulong(a)*ulong(b)` and `long(a)*long(b)` each compile to
  > `get_sr, device_load, device_load, imad, device_store, stop`, and the two differ in exactly
  > **one byte** (`imad` byte+10: `0x0a` unsigned vs `0x1e` signed) — the signed-mulhi selector
  > already located by EXP-M4-13, here confirmed as the *only* difference. Both exact on all 8
  > rows including `INT32_MIN` and `0xFFFFFFFF` operands.
  > **I64-05 YES (there is no native 64x64->low64 multiply).** `ulong * ulong` compiles to
  > **three** `imad` instances (`imad, imad, imad`, 86 bytes) — the classic
  > lo*lo / lo*hi / hi*lo decomposition — versus the single `imad` of I64-04. Exact on all 8 rows.
  > **I64-06 YES — every 64-bit compare, shift, min/max, bit-scan and select is a compound
  > sequence; none is a native register-pair operation.** Measured instruction sequences, all
  > functionally exact against host oracles: `<` (unsigned and signed) =
  > `icmp_pred, psel, isel10_c, n2_op6, ...` (94 B); `==` =
  > `b_alu10_loe, reg_move_cb, shift_amt_move, n2_op6, scoreboard_fence, n3_mov` (82 B);
  > `min` = `icmp_pred, psel, isel10_c x2, isel10 x2` (100 B); `<<` by a runtime amount =
  > `tex_coord_setup, iadd2, ibfe, ibfins x3, iadd2, isel10 x2` (148 B); `>>` =
  > `tex_coord_setup, ibfins, ibfe` (84 B); `clz` = 12 non-boilerplate ops (142 B) built from
  > `ibitcount x2, iadd2, isel10, icmp_pred, psel, isel_reg, isel10_c x2`; `ctz` = 132 B;
  > `popcount` = `ibitcount x2 + iadd2` (62 B, i.e. per-word popcount then a 32-bit add);
  > `c ? a : b` = **two** `isel10` (one per word); bitwise `&` = one `ilogic` plus a second
  > 4-byte op for the high word. The only 64-bit operations that are NOT compound are subtract
  > (I64-02) and — if a backend chooses to use it — add (I64-01). **`lower_int64_options` must
  > therefore keep every compare/shift/minmax/bitscan/select bit set, and may clear the add and
  > sub bits.**
  > Open sub-items deliberately left UNKNOWN: **I64-03's placement question is genuinely open**
  > (see above) — only the fault boundaries were established, not the legality of alternative
  > aligned/unaligned pairs. I64-01's native add was validated in ONE carrier shape (the
  > compiler's own 64-bit subtract with a single bit flipped); it was not synthesized from
  > scratch, and the field that makes the operands 64-bit wide rather than 32-bit was located
  > (byte+7 differs, `0x50` in the 64-bit form vs `0xA8` in the 32-bit form) but **not isolated**,
  > because changing that byte also changes which register is read. I64-06's sequences are
  > compiler-emitted structure plus functional exactness; no attempt was made to prove that no
  > *unemitted* native 64-bit compare/shift exists — given I64-01, such an instruction may well
  > exist and is a recommended probe. All rows are M4/G16G; A18 deferred.
  > Evidence: `experiments/EXP-0146-m4-emit-int-misc/` (OWN-SHADER + HW-PROBE; host oracles
  > written from PUBLIC C/MSL/IEEE definitions only; M4 target; A18 deferred).
