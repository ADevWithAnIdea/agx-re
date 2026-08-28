# Part-II answer blocks, ready to splice into `APPLE9_RE_IMPLEMENTATION_GAPS.md`

**Do not edit `APPLE9_RE_IMPLEMENTATION_GAPS.md` from this file by hand.** Each section below
gives an `ANCHOR:` line copied byte-for-byte from the task list, followed by the answer block to
insert **immediately after that line, separated by one blank line** — matching the placement and
`  > ` indentation of the existing `MEM-05` and `MEM-06..10` blocks.

Every anchor line was verified unique in the file (`grep -Fxc` == 1) at the time of writing.

Scope rules honoured: verdicts and numbers are copied from the cited `RESULTS.md`, never inferred;
every block carries `M4 target; A18 deferred`; every explicitly-left-UNKNOWN sub-item is carried
through; every retraction/supersession the source experiments recorded is stated.

Companion files: `work/GAPS-COVERAGE.md` (per-item coverage table), `work/GAPS-PROGRESS.md`.

---

### ANCHOR:   `.has_atomic_load_store = true`.

  > **Answered 2026-08-28 (EXP-0121, M4/G16G, commit `1143ec55`) — OPT block (OPT-02 and OPT-09
  > answered separately above/below):**
  > **OPT-01 YES** — relaxed and precise division compile to structurally distinct sequences
  > (66 vs 300 bytes; a single `fspecial` SFU estimate vs. `fspecial` plus a multi-instruction
  > integer-domain refinement block). Confirms `.lower_fdiv = false`; the selection point is the
  > `fast::`/`precise::` namespace, **not** the global compile flag alone.
  > **OPT-03 YES** — `pow` genuinely needs a fixup: the naive `exp2(y*log2(x))` composition
  > returns NaN for **22 of 53** directed edge cases (negative base, zero base, zero exponent)
  > that `pow` gets IEEE/C99-correct, and `pow`'s compiled body is ~27x larger (2102 vs 76
  > bytes). Confirms `.lower_fpow = false` and the need for an `A9_POW`-style pseudo.
  > **OPT-04 PARTIAL / NO for "single instruction"; YES for numerical correctness** — the
  > dedicated `fldexp` opcode in `tools/agx-isa/db.json` was **never observed** across 4 fresh
  > compile variants of `ldexp(x,n)` with runtime `n`; the compiler emits a ~200-byte
  > integer-bit-manipulation composition instead. That composition is numerically correct
  > (451/452 exact against a DAZ+FTZ-adjusted oracle; the sole residual is a boundary-rounding
  > edge at the exact min-normal/max-subnormal threshold). **`.has_ldexp = true` is NOT supported
  > by this evidence for this calling pattern.**
  > **OPT-05 YES** — all 18 (type x condition) forms compile to exactly ONE fused `isel8`
  > (`get_sr, device_load x4, isel8, device_store, stop`, 86 bytes) whose `selTrue`/`cmpA`/`cmpB`
  > are independent register operands carrying arbitrary non-Boolean sentinel values. Enables
  > `.has_fused_comp_and_csel = true`.
  > **OPT-06 YES** — the same fused `isel8` serviced FP32, signed I32 and unsigned I32 for all six
  > of eq/ne/lt/le/gt/ge including signed/unsigned-distinguishing bit patterns; **825/825** corpus
  > rows matched the host oracle.
  > **OPT-07 NO (bounded structural negative), functionally correct via ALU-select** —
  > `iter`/`iter_flat`'s slot field is a compile-time `imm` in every observed instance
  > (0,6,8,10,12,14,16 — small constants, never a register). Dynamic 8-way indexing (extending
  > EXP-0111 FS-10's 4-way test) reads every candidate via ordinary fixed-slot interpolation then
  > selects via ALU, 8/8 exact. No register-sourced slot path exists even at 8 candidates.
  > **OPT-08 UNKNOWN/PARTIAL mechanism, positive-leaning structurally** — genuinely
  > per-fragment-divergent 2-way AND 3-way `[[color(n)]]` output both compile to exactly **ONE**
  > `frag_color_store` (not scaling 1:1 with target count, which the pre-registered falsifier
  > required for a negative reading), `rt_index=0` (imm) in both, yet hardware readback proves
  > correct independent routing to 2 and 3 distinct render targets. MSL still offers **no syntax**
  > for a dynamic-output store, so a compiler must keep lowering to a branch/select chain over
  > static `[[color(n)]]`; this experiment cannot license a NIR-level dynamic-output primitive.
  > **OPT-10 NO** — an ordinary aligned load does **not** reliably observe a cross-thread write
  > even surrounded by `atomic_thread_fence(mem_device, seq_cst, thread_scope_device)`: every
  > plain-consumer-load combination (`AP_fenced`, `PP_fenced`) showed massive producer/consumer
  > timeouts at every `PAIRS>=1` in both runs (e.g. `AP_fenced` PAIRS=1: 300/300 iterations never
  > completed), while the identical protocol with an atomic consumer load (`AA_fenced`,
  > `PA_fenced`) is fast and 100% clean at every scale.
  > **OPT-11 YES** — an ordinary aligned store observed by a *trusted atomic* load satisfies store
  > ordering/visibility under the same fence: `PA_fenced` is 0 mismatches / 100% completion at
  > every `PAIRS` in {1,4,8,16}, both runs, and its unfenced control `PA_unfenced` breaks at
  > `PAIRS>=4` exactly as required.
  > **Joint consequence: `has_atomic_load_store` must stay FALSE** — the gate needs both OPT-10
  > and OPT-11 to be `Yes`, and OPT-10 is `No`. A compiler must never lower an atomic load to a
  > plain load, fenced or not.
  > Open sub-items deliberately left UNKNOWN: OPT-04 was tested only for the exact
  > `ldexp(x[gid], n[gid])` MSL idiom (plus a uniform-`n` variant) — a different idiom might reach
  > the unobserved `fldexp` opcode; OPT-08's actual hardware mechanism behind the single
  > `frag_color_store` is not decoded (flagged for a dedicated splice-level follow-up); OPT-10/11
  > used `PAIRS` in {1,4,8,16} only, and `PAIRS=1` is uniformly too small to expose reordering for
  > any access method (matching EXP-0093), so the litmus threshold is a design fact, not a limit.
  > Evidence: `experiments/EXP-0121-m4-nir-contract/` (HW-PROBE + OWN-SHADER + STRUCTURAL mix;
  > M4 target; A18 deferred).

---

### ANCHOR:   A `Yes` confirms that the FP16 vectorizer must never generalize to 2x16 integer operations.

  > **Answered 2026-08-28 (EXP-0102, M4/G16G, commit `958f8307`) — PACK block.** Two capture runs,
  > 51/51 cases `OK` in both, all 51 gated records byte-identical.
  > **PACK-01 YES** — `float2 -> half2 -> as_type<uint>` compiles to TWO native `cvt_f2h_dst`
  > converts and **zero** `ibfins`/mask-shift-combine ops; functionally exact on all 7 directed
  > rows including fp16 max/min-normal and overflow-to-inf.
  > **PACK-02 YES** — the unpack direction compiles to TWO `falu2` instances (native, but via the
  > general float-ALU convert mode rather than a dedicated "unpack" mnemonic); exact on all 10
  > rows including NaN(0x7E00)/Inf(0x7C00) lanes.
  > **PACK-03 YES** — `pack_float_to_snorm2x16` compiles to a SINGLE `pack_convert`, the same
  > mnemonic and byte-identical body length (46 B) as `pack_float_to_unorm2x16`.
  > **PACK-04 YES** — `unpack_snorm2x16` is a single `unpack_convert`; **65536/65536** 16-bit lane
  > bit patterns bit-exact against an exact-Fraction oracle.
  > **PACK-05 YES** — `pack_unorm_2x16` matches `round(clamp(x,0,1)*65535)` with ties to EVEN
  > (confirmed at the one true exact tie, N=32767 -> 32768), NaN -> 0, negative -> 0, >1 -> 65535,
  > +/-Inf clamping like any out-of-range value; 10/10 directed rows.
  > **PACK-06 YES** — `unpack_unorm_2x16` is **65536/65536** bit-exact against `u/65535.0`.
  > **PACK-07 YES (normalized) / NO (generic)** — `pack_float_to_{unorm,snorm}4x8` compile to a
  > native two-instruction `pack_convert` + `frag_color_pack` pair; the hand-written GENERIC
  > (non-normalized) 4x8 integer gather is NOT native (15 instructions, `ibfins`-based).
  > `.has_pack_32_4x8` must be split: TRUE for normalized, FALSE for generic integer packing.
  > **PACK-08 YES** — `unpack_{unorm,snorm}4x8_to_float` each compile to TWO `unpack_convert`
  > instances, functionally exact on 8/8 rows each.
  > **PACK-09 YES** and **PACK-10 YES** — all 24 rows (8 exceptional-value pairs x add/mul/fma)
  > exact against a from-scratch exactly-rounded binary16 reference (genuinely fused for fma);
  > no cross-lane corruption for NaN, +/-0, subnormal or +/-Inf in any row. Closes the
  > correctness side of `.vectorize_vec2_16bit`.
  > **PACK-11 YES (packed short2 integer ALU is absent)** — `add` -> two independent `iadd2`;
  > `mul` -> two independent `imad`; `and` -> a different non-packed shape (two `mov_zext16` +
  > `mov_imm` + `pad_operand`, no `ilogic`). None reaches a packed 2-lane integer ALU op.
  > Open sub-items deliberately left UNKNOWN: PACK-04/06's exhaustive sweeps fixed the OTHER lane
  > equal to the tested lane, so the full 2^32 (lane0,lane1) cross-product is untested (PACK-09/10
  > cover cross-lane independence by targeted directed cases instead); PACK-05's tie rule rests on
  > 3 constructible exact ties, not a full tie sweep; PACK-08 is 8 directed rows, not exhaustive
  > over the 2^32 packed-word domain; PACK-07's `frag_color_pack` mnemonic appearing in a
  > COMPUTE-only kernel is reported as observed and flagged for `tools/agx-isa/db.json` provenance
  > review, not resolved; PACK-11's `and` decomposition (why `mov_zext16` rather than `ilogic`) is
  > observed but unexplained.
  > Evidence: `experiments/EXP-0102-m4-int-pack-semantics/` (HW-PROBE + OWN-SHADER, with PUBLIC
  > NIR/GLSL/MSL/IEEE-754 definitions used only to author the host oracle; M4 target; A18
  > deferred).

---

### ANCHOR:   Compiler consequence: determines `has_ford_funord` and `has_fneo_fcmpu`.

  > **Answered 2026-08-28 (EXP-0103, M4/G16G, commit `bbb1e9fc`) — FP block.** Two capture runs,
  > 47/47 cases byte-identical, zero faults/timeouts.
  > **FP-01 YES (fused), with an uncharacterized subnormal edge** — `fma_f32` 508/509 exact
  > against a genuinely-fused exact reference, including the canonical `(1+2^-23)^2 - 1`
  > fused-vs-separate-rounding vector. The one divergence has a subnormal `c` operand and is
  > consistent with — but on n=1 not an exhaustive characterization of — the DAZ+FTZ pattern.
  > **FP-02 YES** — `fma_f16` **2012/2012** exact (2000 random + every FP16 special triple).
  > **FP-03 PARTIAL (as pre-registered)** — `sub_f32` 818/820 exact against an IEEE `a+(-b)`
  > reference; both divergences are subnormal-operand DAZ. Whether this is literally a
  > negate-modifier bit on `fadd` or a separate op was NOT disassembled.
  > **FP-04 CHARACTERIZED, not "correct"/"incorrect"** (IEEE leaves it open) — of 620 pairs the
  > 2 genuine `+0`/`-0` ties returned **operand B's sign for BOTH `fmin` and `fmax`**
  > (`fmin(+0,-0)=fmax(+0,-0)=-0`; `fmin(-0,+0)=fmax(-0,+0)=+0`): on a magnitude tie this
  > hardware resolves to "the second operand", not to a sign rule. Non-tie: 618/618 `fmin`,
  > 617/618 `fmax` exact (the one `fmax` miss is subnormal DAZ).
  > **FP-05 YES** — every one-NaN pair returned the non-NaN operand for both `fmin` and `fmax`
  > (canonical / payload / negative-payload NaN, both operand orders). NaN-avoiding min/max.
  > **FP-06 NO — extensive, consistent DAZ+FTZ.** Every FP32 case touching a subnormal operand or
  > producing a correctly-rounded subnormal diverges, and every such divergence is explained by
  > DAZ+FTZ (`add`/`sub`/`mul`/`div_precise`: 3/3/32/39 divergences). **New here:** `saturate()`
  > also DAZs (49/1886 divergences, each a small positive subnormal returning `+0`), and FP32
  > relational compare DAZs too (`0x7fffff` vs `0x1` compare EQUAL). DAZ is not confined to
  > arithmetic — it extends through `fmax`/`fmin` (hence `saturate`) and relational compare.
  > **FP-07 YES, evidence points to per-instruction not device-fixed** — the same
  > `precise::rcp` kernel compiled with global `fastMathEnabled=YES` and `=NO` produced
  > **byte-identical** results (same DAZ+FTZ divergence set, same 1856/1886 exact count): the
  > global math-mode flag did not change `precise::` behavior, while `fast::` and `precise::`
  > differ from each other. Does NOT rule out a lower-level mode register the compiler always
  > sets identically; no register-level evidence collected.
  > **FP-08 YES** — FP16 subnormals preserved, scalar and packed; corroborated by the exhaustive
  > FP16 SFU result (zero DAZ/FTZ across all 65536 patterns for `rcp`/`rsqrt`/`sqrt`).
  > **FP-09 PARTIAL** — `saturate(NaN)` returned `+0.0` for every tested NaN class, exactly
  > matching the falsifiable prediction from composing `clamp(x,0,1)=fmin(fmax(x,0),1)` with
  > NaN-avoiding min/max; but subnormal inputs do NOT pass through (the FP-06 DAZ effect,
  > 49 divergences). 1837/1886 exact.
  > **FP-10 YES, perfectly** — FP32->FP16 is **1886/1886** exact round-to-nearest-even, including
  > explicit tie vectors; the narrowing conversion does NOT flush subnormal inputs or outputs.
  > **FP-11 YES in range; out-of-range characterized** — in-range truncation is 1177/1177 (int32),
  > 1077/1077 (uint32), 1011/1011 (int8), 988/988 (uint8) exact. Out-of-range/special behavior is
  > **saturating**, not wrapping: `+Inf -> *_MAX`, `-Inf -> INT*_MIN`/`0`, **NaN -> 0** in every
  > signed/unsigned 8/32-bit form.
  > **FP-12 YES (upgraded PARTIAL -> HW)** — `int(char(x))` and `int(char(clamp(x,-128,127)))` are
  > numerically identical for **1874/1886** cases (differing only on the 12 NaN inputs, exactly as
  > `clamp`'s NaN-avoiding composition predicts), and the PLAIN form compiles SHORTER (80 vs 92
  > bytes) — so the saturation is not a fused compiler-inserted clamp. FP32->int8 truncating
  > conversion saturates natively. Exact instruction encoding NOT decoded (OWN-SHADER-DIFF +
  > HW-PROBE, not splice-level ISA evidence).
  > **FP-13 YES, perfectly** — `fquantize2f16` via `float(half(x))` is **1886/1886** exact against
  > `widen(narrow(x))`, including every NaN/Inf/subnormal/boundary vector.
  > **FP-14 YES for NaN handling (419/420)** — `<,>,==,!=,<=,>=` and `isnan` all match an
  > IEEE-ordered reference across every NaN/Inf/normal/subnormal pairing; the sole divergence is
  > the FP-06 DAZ case, not a NaN issue. Whether the ISA exposes a *dedicated* unordered-compare
  > instruction (vs. software-composed `isnan`+select) was NOT disassembled.
  > Open sub-items deliberately left UNKNOWN: FP-01's subnormal-operand FMA behavior is not swept
  > to exhaustion; FP-02's packed `fma_f16x2` results were captured but not rescored (per-lane
  > unpack metadata not persisted — a scoring-tool gap, not a missing observation); FP-03's
  > negate-modifier-vs-separate-op question; FP-07's possible always-set lower-level mode register;
  > FP-14's dedicated-unordered-compare-instruction question. No FP64, no non-default rounding
  > modes (not exposed by the public API), and no claim about behavior inside a larger expression
  > graph the compiler might contract differently than these isolated single-op kernels.
  > Evidence: `experiments/EXP-0103-m4-fp-transcendental-semantics/` (HW-PROBE + OWN-SHADER +
  > PUBLIC MSL function names; M4 target; A18 deferred).

---

### ANCHOR:   pseudo.

  > **Answered 2026-08-28 (EXP-0102, M4/G16G, commit `958f8307`) — INT block.** Two capture runs,
  > 51/51 cases `OK` in both, all 51 gated records byte-identical.
  > **INT-01 YES** — `extract_bits(data, off, 0) == 0` for every tested `(data, off)` pair
  > (6 data patterns x 4 offsets); width 0 is a legal, deterministic zero-producing case.
  > **INT-02 NO — and the real contract is a three-way one, not NIR's.** Over a 122-row boundary
  > sweep the observed rule ("MODEL D") is: **`cnt==32` EXACTLY bypasses the offset** (verbatim
  > passthrough, even for `off == 2^32-1`); `cnt` in `{1..31}` or `{33..2^32-1}` applies `off` as
  > a **LITERAL, unmasked** shift, with `off>=32` zeroing the contribution. This is NOT NIR's
  > presumed "mask offset mod 32, clamp width to 32". **Scope note carried from the source:** this
  > is the SOURCE-LEVEL compiled behavior of Metal's `extract_bits` with runtime `off`/`cnt`
  > (compiled body: `ibfe` + `ibfins` + `b_alu10_loe` + `n2_op6` + store) — whether the `cnt==32`
  > bypass is raw `ibfe` hardware behavior or software the compiler adds around a plainer `ibfe`
  > was NOT distinguished. A NIR backend must emit an explicit `cnt==32` check rather than trust
  > hardware clamping.
  > **INT-03 YES** — the signed result equals MODEL D's unsigned result sign-extended over
  > `min(cnt,32)` bits in all 122 rows; no hidden signed mode. Lower signed extract to
  > unsigned + explicit sign-extend.
  > **INT-04 YES** — `rotl32(a, K mod 32)` for all 7 tested `K` (0,1,31,32,33,63,64) x 4 bases;
  > byte-identical compiled bodies prove the mod-32 reduction happens **at compile time**
  > (`imm0==imm32==imm64` fold to identity with no rotate op emitted; `imm31==imm63`;
  > `imm33==imm1`). Constant-amount rotate is a single 12-byte `irotate`.
  > **INT-05 YES** — `rotl32(a, n mod 32)` exact in all 64 rows (4 bases x 16 runtime amounts
  > incl. 0,1,16,31,32,33,63,64,65,127,128,255,256,1000,2^31,2^32-1).
  > **INT-06 YES (no one-instruction dynamic rotate)** — the runtime-amount kernel disassembles to
  > 10 instructions / 98 bytes vs. the immediate kernel's single `irotate` / 48 bytes.
  > **INT-07 YES** — `(a*b+c) mod 2^32` exactly, unsigned and two's-complement signed, at every
  > tested boundary triple (incl. `0xFFFFFFFF*2+1`, `INT32_MIN*-1+0`, `-1*-1*-1`); 14 rows.
  > **INT-08 PARTIAL / UNKNOWN — the probe design could not answer it.** The 40-live-temporary
  > register-pressure kernel produced a functionally exact result, but the compiler restructured
  > the 40-term reduction as a TREE of paired multiply-adds, so IMAD `dst` never exceeded r26.
  > **IMAD's own high-register reachability has never been tested by any experiment.** Do NOT
  > assume IMAD can address the full 0-95 range. (Note the still-open r>=64 addressing blocker is
  > a DIFFERENT instruction family — `falu2`/`falu2i` — see the ENC block.)
  > **INT-09 YES (DERIVED, not directly isolated)** — `clz` is HW-exact (0 -> 32, 1 -> 31,
  > 0x80000000 -> 0; 13 rows) and its compiled body (`ibitcount` -> `iadd2` -> `isel10`) is
  > structurally consistent with find-MSB + 31-minus + zero-clamp, i.e. the `ufind_msb`
  > (index-from-LSB) convention, NOT `ufind_msb_rev`. The find-MSB primitive's own standalone
  > output was never read back.
  > **INT-10 YES** — `clz` = `ibitcount` + `iadd2` + `isel10` (64 bytes, 3 non-trivial ops) vs.
  > popcount = `ibitcount` alone (44 bytes, 1 op). CLZ is necessarily compound.
  > **INT-11 YES (necessarily multi-instruction)** — one source-level `insert_bits` compiles to
  > THREE `ibfins`-family instances (distinguished by an internal `form` sub-field: 0, 16, 32)
  > plus TWO `b_alu10_loe` helper ALU ops. 256/256 rows match MODEL D. This refines EXP-0033's A18
  > mnemonic naming (three differently-named byte0 values there; one family + `form` here) without
  > changing the claim.
  > **INT-12 PARTIAL / UNKNOWN (nuanced) — NOT a uniform yes.** A real `ilogic` instruction with a
  > varying `lut_a` (2 bits, 0-3) + `lut_b` (1 bit, 0/8) selector plus operand-order swapping
  > realizes **10 of the 16** two-input functions (AND, NAND, OR, NOR, XOR, XNOR, AND-NOT and
  > OR-NOT in both orders). The 2 projections never reach any ALU op (free passthrough); the 2
  > negations route through a different dedicated `funary` op; the 2 degenerate constants fold to
  > `reg_move`/`mov_imm`+`iminmax`. The FULL field width — and whether `ilogic` could encode the
  > other 6 directly — is NOT established (no splice sweep of the raw `lut_a`/`lut_b` field).
  > **INT-13 YES for every compiler-emitted instance observed** — in BOTH compiled expression
  > shapes, every `carry_gen` is immediately preceded by the specific low-word `iadd2` whose
  > overflow it tests and immediately followed by `psel` then the dependent high-word add(s),
  > re-confirming EXP-0038's A18 finding fresh on M4. This is compiler-emitted evidence; it does
  > not prove the hardware *requires* adjacency (that is INT-14).
  > **INT-14 PARTIAL / UNKNOWN, deferred by design** — no new work: `carry_gen`'s operand-register
  > field layout has never been characterized (only its position/length), and the project-wide
  > silent-zero-on-wrong-operand-field warning makes a guessed splice liable to produce a false
  > result. Until closed, emit `carry_gen` ONLY in the adjacent pattern of INT-13; do not attempt
  > to synthesize a standalone carry-generate.
  > Open sub-items deliberately left UNKNOWN: INT-02/INT-11 are closed only at the
  > compiler-contract tier (a bare spliced `ibfe`/`ibfins` with an explicit width-32 field was not
  > constructed); INT-08's high-register IMAD question; INT-09's directly-isolated find-MSB
  > readback; INT-12's raw `lut_a`/`lut_b` field width and the 6 non-`ilogic` functions; INT-14
  > entirely. INT-11 also leaves a 40-byte `<unknown>` tokenizer tail (almost certainly the
  > `device_store`+`stop` epilogue) flagged as a `tools/agx-isa` DB coverage gap.
  > Evidence: `experiments/EXP-0102-m4-int-pack-semantics/` (HW-PROBE + OWN-SHADER, with PUBLIC
  > definitions used only for the host oracle; M4 target; A18 deferred).

---

### ANCHOR:   with exact robust-buffer semantics for vectors and boundary-straddling accesses?**

  > **Addendum 2026-08-28 (EXP-0122, M4/G16G, commit `f2b8ef66`) — refines MEM-05, MEM-08 and
  > MEM-12 above.** 74 guard cases (37 offsets x {load, store}) per run, two runs, 0 mismatches
  > across all 87 gated cases; 0 hangs, 0 faults, 0 command-buffer errors in 148 executions, and
  > no OOB store ever corrupted an adjacent allocation.
  > **MEM-05 refinement — the wrap period is EXACTLY 2^43 bytes.** For the
  > `(device uchar*)base + (uint64_t)off` idiom, all 12 discriminating cases match
  > `(base+off) mod 2^43` then align-down-4, including the two designed to exclude competing
  > periods (`1.5*2^43` rules out 2^42; `5*2^43+4` rules out anything larger), and the model
  > correctly predicts landing inside a real neighbouring allocation three times from three
  > different large offsets (`2^43-4`, `2^64-32`, `2^64-256` all read `5a5a5a5a`, our guard fill).
  > This does not contradict EXP-0082's MEM-05 `No` (mod-2^32 wrap is still refuted) — it names
  > the actual period. **Alternatives explicitly not excluded:** the 2^43 figure could reflect
  > (a) the GPU's real VA bus width, (b) a 43-bit addressing-operand width specific to this load
  > encoding, or (c) a firmware/driver address-space window. Untested for other access widths
  > (8/16/64/128-bit) and other idioms (texture addressing, argument-buffer-indirect pointers).
  > **MEM-08 refinement — "OOB reads return zero" is NOT page-wide and must not be relied on.**
  > EXP-0076's near-boundary model reproduces exactly under an independently authored harness
  > (offset 32 -> `05203b56`, 60 -> `f9142f4a`, 64 -> `00000000`, 1088 -> `00000000`), and 4096 B,
  > 32 KiB, 1 MiB, 16 MiB, 256 MiB, 4 GiB, 64 GiB, 1 TiB, 2 TiB and 4 TiB past the base all read
  > zero — **but at exactly 16384 B past the base (one sparse tile / the platform page quantum)
  > and its +/-256 B neighbourhood, reads return live, non-zero, non-guard-pattern data**
  > (`d166d8b1`, `0cda71aa`, `39ada2a3`, ... — not our `0x5A`/`0xC3` fills, so not our own guard
  > buffers). Both a "guard page around the allocation" model and an "everything unmapped reads
  > zero" model are falsified.
  > **MEM-12 consequence:** a `load_global_bounded` lowering must perform its own explicit bounds
  > check; it may NOT lean on address space adjacent to an owned allocation being safe or zero.
  > The zero-fill behaviour is real and reproducible at the tested small and very-large distances,
  > but it is not a property of "outside the allocation" in general.
  > Open sub-items deliberately left UNKNOWN: the owner of the live data at the 16384 B quantum is
  > not identified (most plausibly another `MTLBuffer`/`MTLLibrary`/queue-internal object);
  > `vm_start` / kernel-reserved-region boundaries are unbounded by this experiment (the lowest
  > address seen anywhere was `0x10000018000`, suggestively near 2^40, but allocation volume was
  > never driven high enough to bound the window); the allocator determinism observed
  > (byte-identical addresses across 3 alloc/free passes) is an observed behaviour within one
  > process, not an architectural guarantee, and was not tested across processes or under
  > concurrent allocation pressure.
  > Evidence: `experiments/EXP-0122-m4-sparse-vm-conventions/` (HW-PROBE + OWN-SHADER; M4 target;
  > A18 deferred).

---

### ANCHOR:   immediately before the memory operation?**

  > **Answered 2026-08-28 (EXP-0085, M4/G16G, commit `2e693a58`) — MEM-13/MEM-14 block:**
  > **MEM-13 YES — HW-VALIDATED.** Six cases, PASS on both runs: device load -> immediate `fma`;
  > dependent/gather load -> immediate `fma`; atomic RMW result -> immediate ALU (N=8192,
  > permutation invariant); **48 independent loads per thread with zero waits**, summed and
  > consumed with no intervening statement, at N=4096 AND N=65536 (the adversarial
  > register-pressure/occupancy stress case); and `texture2d::read` -> immediate `fma` over 4096
  > texels. Structural tokenization shows the consuming ALU byte-adjacent to its producer
  > (`device_load` -> `falu3`, 0 intervening bytes) with **no wait/scoreboard opcode anywhere** in
  > the chain — including through the compiler's multi-instruction SIMD-reduce/broadcast tail for
  > the atomic case. This extends EXP-0025's A18 finding to two operation classes it did not test
  > compute-side: texture `read()` and "atomic RESULT consumed by ALU" under real contention.
  > **MEM-14 YES — HW-VALIDATED.** The interlock is bidirectional: `il_store_src` (ALU-computed
  > `a[i]*b[i]-a[i]` stored with zero gap, N=8192, deterministic) compiles to
  > `device_load, device_load, falu3[fma], device_store, stop` with 0 intervening bytes, and
  > `il_atomic_src` (ALU-computed addend fed directly as the atomic operand, N=8192, commutative
  > sum invariant) shows no wait instruction between the ALU computation and the atomic. Both PASS
  > byte-identical on both runs.
  > **Driver consequence:** on M4 a driver need not reason about scoreboard/wait insertion in
  > either direction for ordinary compute memory or atomic instructions; the omission that would
  > be a silent-corruption bug on G13-style hardware cannot occur here for these classes.
  > Open sub-items deliberately left UNKNOWN: this is observational (a construction attempt that
  > produced correct results at every scale tried), NOT a proof that no register-pressure regime
  > beyond N=65536 / 48-deep chains could expose a hazard. Only the presence/absence of an opcode
  > between producer and consumer is treated as evidence — the atomic reg-pack tail's DB field
  > names (`ret_flag`, `addr_desc`, `data_desc`) remain unvalidated placeholders.
  > Evidence: `experiments/EXP-0085-m4-memory-interlock-atomics/` (HW-PROBE + OWN-SHADER +
  > STRUCTURAL tokenization; M4 target; A18 deferred).

---

### ANCHOR:   semantic limit from the values Metal happens to emit.

  > **Answered 2026-08-28 (EXP-0106, M4/G16G, commit `2858c20f`; TEX-15/TEX-16's raw half by
  > EXP-0114, commit `72c2dde8`) — TEX block.** EXP-0106: 56 cases per run x 2 runs,
  > `repeat_exact: true`, 40 match / 9 abort_confirmed / 7 rejection_confirmed / 0 deviation /
  > 0 unexpected. EXP-0114: 49/49 cases per run x 2 runs, `repeat_exact: true`, zero faults.
  > **TEX-01 DEFERRED** — Metal exposes no `sample`-with-w-divide entry point anywhere in the MSL
  > spec's texture function lists, so no compiler-emitted evidence is reachable; answering it
  > needs `op+2` bit-space fuzzing on a spliced valid `tex_sample` bundle. Not attempted.
  > **TEX-02 NO (no compiler-reachable one-op 4-offset gather)** — `gather()`/`gather_compare()`
  > take exactly one `int2 offset`; no 4-offset overload exists. `lower_tg4_offsets` remains
  > necessary. Whether the *hardware* has an unexposed native 4-offset form is deferred with
  > TEX-01/07/08.
  > **TEX-03 YES (partial-exhaustive)** — a 32x32 `r32uint` texture gathered at a fixed
  > grid-intersection with constant `int2` offsets at 12 boundary/corner points gives exactly
  > `(16+dy)*32 + (15+dx)` in every case, all 12 values pairwise distinct (`injective: true`) —
  > a clean signed affine encoding with **no aliasing** at the `[-8,+7]` extremes in both axes.
  > **Declared scope: 12 points, NOT the full 256-pair sweep.**
  > **TEX-04 YES (both halves)** — MSL accepts a non-constant, buffer-loaded, per-thread `int2`
  > offset, and a 4-thread dispatch each reading its own offset produced `[527, 466, 758, 263]`,
  > matching the corresponding constant-offset cases word-for-word. Dynamic, per-lane-divergent
  > texture offset is native — richer than the GLSL/Vulkan constant-offset convention.
  > **TEX-05 — a genuine, unexpected NEGATIVE result: `min_lod_clamp()` is functionally broken in
  > the COMPUTE stage for 3 of its 4 forms on this software stack.** Only
  > `gradient2d() + min_lod_clamp()` works end to end (sampled level tracked a runtime-supplied
  > `x` in {0,1,2,3} exactly, `0xE0..0xE3`). Standalone `min_lod_clamp()`, `bias(0)+min_lod_clamp()`
  > and `sample_compare()+min_lod_clamp()` all **deterministically crash
  > `newComputePipelineStateWithFunction:`** — not the library compile, which succeeds — with
  > `AGXMetalG16G_B0 Code=2 ... XPC_ERROR_CONNECTION_INTERRUPTED`, i.e. a compiler-service process
  > crash, reproduced 5/5 in isolation. `level()+min_lod_clamp` and `gather+min_lod_clamp` have no
  > MSL overload at all. **Software-stack finding (this macOS/Metal build), not necessarily a
  > permanent silicon limitation; fragment stage NOT tested.**
  > **TEX-06 YES** — a 4-entry bindless argument-buffer texture array queried by 4 threads at
  > genuinely non-uniform per-lane indices returned `get_width() = [8,16,32,64]` and
  > `get_num_mip_levels() = [1,2,3,4]` — every lane its own texture's true dimensions, not a
  > broadcast. `txs`/`query_levels` need no special uniform-only ABI.
  > **TEX-07 NO** and **TEX-08 NO** — no `samples_identical`-equivalent and no prefetch primitive
  > exist anywhere in the MSL spec. Conservative-false lowering / ordinary-sample selection are
  > the only options at this API surface; a hidden HW-only primitive is a separate deferred
  > opcode-fuzzing question.
  > **TEX-09 YES (no native R32G32B32 format)** — cited from EXP-0095/EXP-M4-08: no
  > `MTLPixelFormatRGB32*` constant exists, and the closed 31/96-format code table has max texel
  > size 16 bytes with no 12-byte entries at any size class. Raw device-load fallback confirmed.
  > **TEX-10 NO for general conversion / YES for packed 4:2:2** — no Y'CbCr/planar sampler
  > conversion type exists in MSL; Metal exposes YUV only as packed native formats
  > (`gbgr422`/`bgrg422`, sizeclass `0x10`). General 2/3-plane conversion must be shader ALU.
  > **TEX-11 YES (no arbitrary border beyond 3 presets)** — cited from EXP-0015/EXP-M4-08: exactly
  > 3 presets in a 2-bit field, code 3 Metal-unreachable. The two-sample clamp-to-zero/one
  > emulation (including shadow-compare) is answered **analytically** from already-HW-validated
  > building blocks, **not empirically re-confirmed here** (declared scope trim).
  > **TEX-12 DEFERRED** — needs `MTLHeap`-backed sparse textures and `updateTextureMapping:`
  > residency lifecycle; EXP-O2B decoded the sparse-tier descriptor bit but never exercised
  > `sparse_sample`/`sparse_read`/`sparse_gather` residency codes.
  > **TEX-13 PARTIAL/CLOSED with a declared remainder** — new: a 4x4x4 `r8uint` 3D texture read at
  > `z=3` returns `3`, at `z=4` returns `0` (silent zero on the depth axis specifically, first
  > tested here). Prior coverage cited from EXP-0016 / EXP-0095 (array-layer fetch-vs-sample
  > divergence: `read()` silently zeroes, `sample()`/`gather()` clamp to the last legal layer;
  > 2D/cube image OOB read+write with zero corruption). **NOT exercised: MSAA sample-index OOB**
  > (MSL exposes no compute-side per-sample write path, so the case would be indistinguishable
  > from reading never-written content — a declared harness limitation, not a result).
  > **TEX-14 YES** — a freshly generated 65-argument `[[texture(0..64)]]` kernel with all 65 slots
  > simultaneously bound to distinguishable canaries read exactly `0xD00D0000, ...0007, ...0008,
  > ...000F, ...0010, ...001F, ...0020, ...003F, ...0040` at indices {0,7,8,15,16,31,32,63,64} —
  > zero cross-talk. Combined with EXP-0095's {0,63,127}, every boundary point the gap doc names
  > is now confirmed simultaneously live.
  > **TEX-15 — the question's PREMISE is falsified; `op+4` is not a texture selector.** EXP-0114:
  > a 128-arg kernel reading only textures 5, 50 and 100 compiles to `op4_sequence: [0, 128, 0]` —
  > neither the MSL binding index nor a compacted use-order index, and the first and third reads
  > share an `op+4` value while addressing different textures. **`op+4` is a short-lived,
  > compiler-reused register/uniform-slot reference, not a per-resource identifier.** What IS
  > closed by construction: `op+4` is a **4-bit field (upper nibble, bits 7:4)** whose lower
  > nibble is inert (12/12 constructed low-nibble values at both populated slots); a full 16-value
  > splice sweep shows the 2 populated nibbles ({0x0, 0x8}) select t0/t1 and **all 14 holes give a
  > deterministic silent zero — zero faults, zero aliasing, zero garbage**. Bidirectional positive
  > control passed (`0x80 -> 0x00` gives t0+t0; `0x00 -> 0x80` gives t1+t1). A register-pressure
  > census shows the compiler itself reaching 8 of 16 nibbles at N=127. **The true 0-127
  > binding-index-to-pointer mapping lives in a PRECEDING 4-byte pointer-materialization
  > instruction (byte0 low nibble `0xb`), which is NOT decoded.**
  > **TEX-16 YES (both halves)** — compile-time: a 129-argument kernel is an MSL error (EXP-0095).
  > Raw injection: EXP-0114's 14-hole sweep IS an out-of-population selector injection at the AGX
  > instruction level — deterministic silent zero every time, never a fault or an alias.
  > **TEX-17 YES** — 16 samplers simultaneously bound (even -> `clampToZero`, odd ->
  > `clampToEdge`), all sampling the same out-of-range coordinate `u=-0.25`: every even slot read
  > exactly `0.0`, every odd slot exactly `3.0`, perfect zero-cross-talk alternation across all 16.
  > (EXP-0063's own filter-distinction probe was **falsified** — texel-center and fully-OOB UVs do
  > not discriminate filter mode — but it established the address-mode technique used here.)
  > **TEX-18 YES** — a 17-sampler kernel fails `newLibraryWithSource:` with
  > `"'sampler' attribute parameter is out of bounds: must be between 0 and 15"` — a named,
  > deterministic compile-time rejection, first tested at exactly n=17.
  > **TEX-19 / TEX-20 / TEX-21 / TEX-22 DEFERRED** — EXP-0095 GLIMG-A02 closed the *shape* of the
  > texture answer (silent zero, no aliasing, no period-256 mirroring) at CAP=256/K=8 with
  > feasibility exploration to N=4096; confirming the documented 1,000,000 / 500,000 ceilings is a
  > large allocation-and-sweep campaign not attempted. **Target-discipline note: the sampler-side
  > prior evidence (EXP-O2B, `maxArgumentBufferSamplerCount = 500000`, dynamic heap indexing for a
  > handful of entries) is A18, not M4-validated.**
  > **TEX-23 YES** — varying ONE axis at a time, the last-legal value (16384 for 1D/2D/Cube; 2048
  > for 3D-width, 3D-depth, array-length) is always accepted and `+1` always fails identically
  > with a hard `validateWithDevice:` assertion (`SIGABRT`, exit `-6`, uncatchable), for every one
  > of the 6 axes. The limits are exactly correct and **independently enforced per axis**.
  > **TEX-24 YES (both halves)** — a 16384-wide texture with `mipmapLevelCount=15` is accepted,
  > `get_num_mip_levels()` returns 15, `read()` at level 14 returns the per-level canary and at
  > level 15 returns 0. Explicit dynamic `level()`: `-5.0 -> 0`, `99.0 -> 3`, `+Inf -> 3`,
  > `-Inf -> 0`, **`NaN -> 0`** (recorded `OBSERVED_NO_ORACLE` — no a-priori prediction was
  > committed). No fault, no hang, no out-of-range index for any value. **The NaN result is a
  > third data point in EXP-0094's open NaN-polarity question: `bias(NaN)` and now `level(NaN)`
  > clamp LOW, while `gradient(NaN)` clamps HIGH.**
  > **TEX-25 — the complete creatable MSAA set is {2,4}, NOT {1,2,4}, and there is a real
  > query/creation discrepancy.** `supportsTextureSampleCount(1)` returns **true** while
  > `MTLTextureType2DMultisample` creation at sampleCount=1 always **fails**
  > (`"sampleCount must be > 1 for multisample textures."`); 3 and 8 fail with a different, generic
  > `"not supported by device"` message; 2 and 4 succeed. All rejections are hard assertion aborts
  > before any GPU submission. **A driver must not use `supportsTextureSampleCount` alone to
  > predict whether an MS-typed descriptor will be accepted.**
  > **TEX-26 / TEX-27 PARTIAL (API half closed, raw-field half deferred)** — cited from EXP-M4-08
  > (M4+A18 cross-confirmed): requesting `maxAnisotropy=32` does NOT clamp to the 16x field value,
  > it clamps all the way to **field 0 (1x)**; requesting `lodMaxClamp > 14.0` saturates the field
  > at exactly `112` (14.0), not its 7-bit maximum 127 (15.875). **The raw 3-bit aniso field
  > holding 5/6/7 and the raw 7-bit lodMax field holding >112 remain genuinely untested** — both
  > are unreachable through any public Metal call and need write-capable descriptor injection.
  > EXP-0106 adds only an interpretive cross-reference (not new evidence): TEX-24's 15-level
  > maximum means mip index 14 is the highest any Apple9 texture can have, so a 14.0 LOD ceiling
  > may simply BE the maximum addressable mip index.
  > **TEX-28 DEFERRED** — address codes 4/6/7 and border code 3 remain untested. **Newly noted:**
  > MSL 4.0 adds a per-sampler `bias(float)` STATE field (spec §2.7), distinct from the
  > per-instruction `bias()` operand EXP-0094 characterized; its raw bit location is undecoded — a
  > concrete new probe target. Successor spec is written out in EXP-0106 §2 (EXP-M4-08's explicit
  > `MTLArgumentEncoder` path fails because the sampler slot is an opaque `gpuResourceID`; the
  > direct `[[sampler(n)]]` per-stage table is the untried path).
  > Open sub-items deliberately left UNKNOWN, beyond the DEFERRED items above: TEX-03's full
  > 256-pair sweep; TEX-04's raw operand-register field for a directly assembled dynamic offset;
  > TEX-05 in the fragment stage; TEX-11's empirical border-emulation confirmation; TEX-13's MSAA
  > sample-index OOB; TEX-15's preceding pointer-materialization instruction; EXP-0114's
  > `bundle_count` undercount at N=64 (32 of 64) and N=127 (84 of 127), which is unexplained and
  > recorded as open.
  > Evidence: `experiments/EXP-0106-m4-texture-isa-semantics/` and
  > `experiments/EXP-0114-m4-texture-deferred/` (HW-PROBE + OWN-SHADER + HW splice + PUBLIC MSL
  > spec API-surface checks; M4 target; A18 deferred).

---

### ANCHOR:   A `No` requires a distinct image/texture barrier legalization path.

  > **Answered 2026-08-28 — ATOM block. ATOM-01..06: EXP-0085, commit `2e693a58`. ATOM-07..11:
  > EXP-0093, commit `d3e7d1ba`** (which is EXP-0085's own named successor — EXP-0085 recorded
  > ATOM-07..11 as DEFERRED and they were closed by the later fence/barrier campaign).
  > **ATOM-01 YES — HW-VALIDATED.** Device atomic subtract has its own op selector `0x1b`,
  > distinct from add's `0x10` and from every other op, confirmed structurally (a single
  > `atomic_mem` instruction, no negate-then-add ALU pre-step) and functionally (per-slot finals
  > match `(init - delta) mod 2^32` exactly). Every M4 device selector equals exactly HALF the
  > corresponding EXP-0018 A18 `byte+12` value — the same hardware field at a different DB bit
  > offset, not a different encoding.
  > **ATOM-02 YES — HW-VALIDATED.** `atomic_tg` is a distinct instruction FORM (`byte+1` mode bits
  > `0x03` vs `0x01`/`0x11`) that reuses the identical op-selector encoding; the one-threadgroup
  > contention test (N=256, own-slot and shared-slot) matches the combine-order-independent
  > invariant exactly for add/sub/min/max.
  > **ATOM-03 YES — HW-VALIDATED, two independent invariant forms.** Own-slot (no contention):
  > every `old_out[i]` equals the init value exactly. Shared-slot (real contention to N=65536):
  > the multiset `{old_out} U {final}` equals exactly `{deltas/tags} U {init}` for every
  > RMW/exchange case — a bijective linearizable-history proof (no duplicate "old", no lost delta).
  > **ATOM-04 YES — HW-VALIDATED under real contention.** Uniform-address compare-exchange at
  > N=65536 (device) / N=256 (threadgroup): exactly ONE lane succeeds, the final value equals that
  > winner's tag, and every losing lane's observed `old` equals that same final value (never torn).
  > Structurally a **single** `atomic_mem[cmpxchg]` (selector `0x12`) with no backward branch —
  > no software retry loop.
  > **ATOM-05 YES, with a sharpened boundary — HW-VALIDATED.** The uniform-address SIMD
  > pre-combine (`simd_reduce -> elect -> atomic_rmw -> broadcast -> rebuild`) is applied and
  > functionally exact for every reducible op (add, xor, min, and by EXP-0018 or/max) — **but only
  > when the compiler can prove the address uniform at COMPILE time.** A data-dependent address
  > that merely happens to be runtime-uniform (loaded from an all-zero index buffer) is NOT
  > optimized; it takes the same per-lane path as a genuinely varying index. This is a sharper
  > boundary than EXP-0018 established.
  > **ATOM-06 YES — HW-VALIDATED structurally.** The pre-combine is unconditionally DISABLED for
  > exchange and compare-exchange even at a compile-time-provable uniform address — the compiler's
  > own codegen, not merely absence of a counterexample, shows the optimization is scoped to
  > reducible ops. The optimization is semantically invisible either way: every functional
  > invariant held identically with and without the reduce path.
  > **ATOM-07 YES — HW-VALIDATED (relaxed atomics carry NO implicit device fence).** Cross-core
  > message passing with fully relaxed atomics shows large-magnitude reproducible payload
  > corruption once concurrency exceeds ~4 producer/consumer pairs — **up to 100% of messages
  > corrupted** (`PAIRS=4` RR: 200/200 mismatches, both runs). At `PAIRS=1` no violation is
  > observed in any configuration, which **explains rather than contradicts** EXP-0051's earlier
  > null result: 1-2 threadgroups are too small a footprint to expose cross-core reordering.
  > Structurally, `memory_order_relaxed` emits no `0x07`-family op at all.
  > **ATOM-08 YES, but ONLY for SYMMETRIC fencing — HW-VALIDATED.** Both sides fenced (FF) is the
  > only configuration with **zero** mismatches at every tested scale (12/12 cells across both
  > runs). **Neither asymmetric configuration is a safe substitute:** producer-only (FR) and
  > consumer-only (RF) both still corrupt at `PAIRS>=4` (98% in all four `PAIRS=4` cells; 49-74%
  > at `PAIRS=8`). A compiler must emit the device-scope fence on BOTH the release and the acquire
  > side.
  > **ATOM-09 YES, and more strongly than the question implies: convergence is UNCONDITIONAL.**
  > `threadgroup_barrier(mem_none)` compiles to the identical instruction shape
  > (`07 04 54 41 09 00`) as `mem_threadgroup`/`mem_device` — NOT to "no instruction" — and still
  > provides full execution convergence and threadgroup-memory visibility (0/256 mismatches vs.
  > 128/256 for the no-barrier control). The `mem_scope` tag governs only which ADDITIONAL memory
  > class is fenced. **Note this is not in tension with SIMD-06: `simdgroup_barrier` is the op that
  > can compile away, `threadgroup_barrier` is not.**
  > **ATOM-10 YES, and the exact bit is identified — HW-VALIDATED BIDIRECTIONALLY.** `byte+3` bit0
  > (`0x85` barrier-with-fence vs `0x84` fence-only) is the execution-convergence enable bit:
  > splicing it OFF on a real barrier reintroduces the exact 128/256 no-barrier race; splicing it
  > ON on a real fence-only op (which races 128/256 on its own) eliminates the race entirely
  > (0/256), on an otherwise byte-identical instruction stream. A device-scope barrier and a
  > standalone device fence are NOT interchangeable at the encoding level. This upgrades
  > `tools/agx-isa/db.json`'s `mem_fence` entry from `inferred (byte-diff)` to `HW-VALIDATED`.
  > **ATOM-11 NO — HW-VALIDATED NEGATIVE; a distinct image/texture barrier legalization path IS
  > required.** Two independent demonstrations: (1) fragment raster-order-group protection uses a
  > dedicated acquire/release `pixel_order` pair (`byte+4=0x06`) for a TEXTURE resource but a
  > bracket-open-pair mechanism (shared with the ROG-index encoding, not a dedicated fence) for a
  > device BUFFER resource — each splice-proven causally load-bearing in its own case, and the two
  > are not interchangeable; (2) compute-side, a standalone `mem_texture` fence compiles to a
  > genuine two-instruction acquire/release PAIR, structurally unlike the single-instruction
  > `mem_device`/`mem_none`/`mem_threadgroup` forms.
  > **Operand-width / return-form findings folded in (EXP-0085):** 32-bit has the full op set with
  > a return form in both scopes; 32-bit float exposes only `fetch_add`; **64-bit exposes ONLY the
  > void, no-return `atomic_min/max_explicit` — there is no return-value-producing 64-bit atomic
  > RMW anywhere in this MSL surface** (`fetch_add`, `fetch_min/max`, even `atomic_load` on
  > `atomic_ulong` are all compiler-rejected). `atomic_store_explicit` and a return-discarded
  > `atomic_exchange_explicit` compile to **byte-identical** `atomic_mem[xchg]` instructions — the
  > "no-return store" is not a separate hardware operation. Only `memory_order_relaxed` is accepted
  > on an RMW call site (`seq_cst` rejected, `acq_rel` undeclared) — a language-exposure fact, not
  > a hardware ordering answer.
  > Open sub-items deliberately left UNKNOWN: ATOM-01's `and`/`or`/`xor`/`smin`/`smax` threadgroup
  > selectors were confirmed functionally but not separately re-tokenized; the raster-order-group
  > index `N` silently aliases to group 0 beyond `N` in {0,1,2} (a finite-resource limit with no
  > rejection); MSAA per-sample ROG granularity, multiple render targets, ROG nesting/repetition,
  > and discard/demote release-on-every-exit-path are all `UNKNOWN` (a build-time attempt at the
  > last was inconclusive — full-body compiler reshuffling defeated a prefix/suffix byte-diff);
  > forward-progress/deadlock behaviour under malformed ROG sequences is untested; a
  > `scoreboard_fence kind=0x22` seen around the SIMD-reduce election machinery is recorded as raw
  > evidence and explicitly NOT interpreted.
  > Evidence: `experiments/EXP-0085-m4-memory-interlock-atomics/` and
  > `experiments/EXP-0093-m4-fence-barrier-interlock/` (HW-PROBE + OWN-SHADER + HW splice +
  > STRUCTURAL; M4 target; A18 deferred).

---

### ANCHOR:   the discarded lane?**

  > **Answered 2026-08-28 (EXP-0111, M4/G16G, commit `9739d612`) — FS block.** 56 cases per run,
  > two runs, every `*.gated.json` record byte-identical; zero GPU faults, hangs, command-buffer
  > errors or host wedges across 112 case executions.
  > **FS-01 YES — HW splice, decisive.** `get_sr 0xa0` returns the fragment's integer pixel X and
  > `0xa1` the integer pixel Y. A single-pixel-coverage triangle writing fixed buffer slots gave
  > baseline `(x=2.5, y=1.5)`; splicing the first `get_sr`'s SR-select byte `0xa0 -> 0xa1` gave
  > `(1.5, 1.5)` and splicing the second `0xa1 -> 0xa0` gave `(2.5, 2.5)` — a clean mutual swap.
  > The compiler emits `cvt_i2f_src` immediately after, i.e. it treats the SR value as an INTEGER.
  > A backend can implement `load_pixel_coord` as a direct SR read with no conversion; the `+0.5`
  > float centre convention is the compiler's own downstream arithmetic, not the SR's value.
  > **FS-02 YES in both senses.** At N=2 and N=4 every per-sample invocation of a given pixel read
  > IDENTICAL raw `pos.xy` bits (0 deviations across 8+16 sample-invocations). A never-covered
  > ORIGINAL helper, relayed out via `quad_shuffle_xor`, read exactly `(1.5, py+0.5)` — the true
  > extrapolated grid coordinate, not zero, frozen or garbage.
  > **FS-03 PARTIAL.** Pixel-centre convention and axis origin are CLOSED: centre = `px+0.5`,
  > `py+0.5` (FS-01); origin is **UPPER-LEFT with y increasing DOWNWARD** (a triangle covering
  > NDC `y<0` colours framebuffer rows 2-3 of a 4x4; NDC `x<0` colours columns 0-1) — HW-confirmed
  > rather than asserted from documentation. **Exact raw MSAA sample POSITIONS remain UNKNOWN:**
  > MSL exposes no `gl_SamplePosition`-equivalent, so they cannot be queried through the public
  > API; a `gl_SamplePosition`/`VK_EXT_sample_locations` consumer must treat them as UNKNOWN
  > rather than assume any standard grid.
  > **FS-04 YES — decisive.** A step function differenced with `dfdx`/`dfdy` on a 4x4 target:
  > splitting WITHIN a quad column-pair gives `d=1000.0` for columns {0,1} and `0.0` for {2,3};
  > splitting exactly BETWEEN quad column-pairs gives `d=0.0` for **all 16 pixels** — the global
  > step is entirely invisible. Y axis identical, transposed. This is genuine 2x2-quad-scoped
  > computation, not merely "some neighbouring-pixel difference".
  > **FS-05 NO at the API/compiler surface; UNKNOWN at the ISA level.** MSL exposes exactly one
  > derivative granularity per axis — no `dFdxCoarse`/`dFdxFine` pair — so **no MSL-level probe can
  > distinguish "the hardware has one mode" from "the hardware has a second mode Metal never
  > emits"**; there is no compiler-reachable starting point to perturb. An undirected blind-bit
  > sweep of the `0x37` op's unexplored `byte+7/+8/+9` was explicitly declined as unfalsifiable.
  > Lower `fddx_coarse` and `fddx_fine` to the SAME primitive.
  > **FS-06 YES for both tested lane categories.** Demoted lanes: cited from EXP-0091 (a surviving
  > lane's `fwidth()` read exactly `999.0`, matching the discarded neighbour's post-discard
  > `+1000` mutation). Original never-covered helpers (this experiment's remainder, closing a gap
  > EXP-0091 explicitly flagged): the live lane's `dfdx(pos.x)` read exactly `1.0` at all 4 tested
  > rows. No separate legalization path is needed for the two helper categories.
  > **FS-07 YES (`scalarize_ddx = true`).** `dfdx()` on float1/2/3/4 with algebraically independent
  > components produced EXACTLY 1, 2, 3, 4 instances of the 10-byte `0x37`/`byte+2==0x54` op; a
  > combined `dfdx+dfdy` on float4 gave 8. Every instance handles one scalar component; no vector
  > width modifier was ever observed. **Genuine anomaly reported, NOT resolved:** every dfdx-ONLY
  > kernel (5/5, no `dfdy` anywhere in source) emitted axis byte `0x90` — not `0x92` as
  > `docs/isa/encoding-tables.md`'s "0x92=dfdx / 0x90=dfdy" labelling predicts — while a
  > ground-truth kernel calling both in one shader (HW-verified readback `[1.0, 0.0, 0.0, 1.0]`)
  > shows `0x92` for both dfdx calls and `0x90` for both dfdy calls. **The axis byte correlates
  > with call-site identity only when both appear in the same program.** Flagged for the `docs/isa`
  > owner as a correction candidate: the current table entry is INCOMPLETE, not simply wrong.
  > **FS-08 YES, with a significant API-behaviour anomaly.** Flat/smooth/no-perspective cited from
  > EXP-0029. New: centroid genuinely differs from centre under partial coverage (a pixel covered
  > by exactly 2 of 4 samples with its geometric centre provably outside the covered region read
  > `v_center = 0.0039215...` — within ~1/255 of the true unclamped extrapolated 0.0 — vs.
  > `v_centroid = -0.24705886...`). **`interpolate_at_offset` VIOLATES its documented contract:**
  > across >=17 offsets in X-only, Y-only and combined sweeps, every measured value matches, to
  > sub-ULP, the plane evaluated at an **absolute pixel-local coordinate equal to `(dx,dy)`
  > directly** — origin at the pixel's TOP-LEFT corner, y DOWNWARD — not MSL's documented signed
  > offset from the pixel CENTRE. `interpolate_at_offset(float2(0,0))` reads `-1.0` where
  > `interpolate_at_center()` and `center_perspective` both read `0.0` **in the same shader on the
  > same value** (the internal control ruling out a harness bug). No clamping or wraparound up to
  > `|offset| = 2.0`. **A backend must transform `(dx,dy) -> (dx+0.5, 0.5-dy)` (or equivalent)
  > before calling it.** Whether this is hardware wiring or an AIR->AGX backend bug on this
  > toolchain is not distinguished. **PARTIAL:** `sample` vs `centroid` were not behaviourally
  > separated from each other (EXP-0029's structural byte-diff `byte+7` `0x01` vs `0x03` is the
  > only evidence for that sub-claim).
  > **FS-09 YES — convergent interpolation is NOT provably bit-identical to flat.** Across 5
  > `(w0,w1,w2,attr)` configurations with an identical attribute at all 3 vertices, no-perspective
  > interpolation diverged from flat in 3 of 5 configurations (16/16 pixels each, 1-2 ULP);
  > perspective matched flat bit-exactly in 80/80 sampled pairs (a narrower observation, not
  > proven universal, and NOT a licence to fold it to flat either).
  > `nir_io_always_interpolate_convergent_fs_inputs` is justified and necessary. **Open curiosity
  > flagged, not chased:** config D (uniform w) shows no linear divergence despite sharing config
  > A's exact attribute value, and no-perspective interpolation is mathematically w-independent —
  > this w-dependence of its rounding is unexplained.
  > **FS-10 YES.** `arr[px%4]` with a runtime, non-foldable index gave exactly `[10,11,12,13]` for
  > `px=0..3`. The compile-scan shows an `icmp_pred`+`sel` ALU pair after the varying-read block
  > and ordinary fixed-slot `iter`/`iter_flat` instructions — no register-sourced slot field in
  > either the dynamic or the static-index control. Lower as "materialize every candidate via its
  > normal static interpolation instruction, then select", with no change to interpolation mode or
  > provoking-vertex behaviour. (A minor unexplained duplication — `iter_flat` count 2 for one
  > declared flat varying — is flagged, not load-bearing.)
  > **FS-11 YES for both sub-claims; PARTIAL on the ISA mechanism.** `struct FOut { float4
  > colors[2]; }` as a fragment return type is REJECTED (`"invalid return type 'FOut' for fragment
  > function"`) — MSL has no grammar path to even attempt a dynamically-indexed fragment output.
  > The branch-unrolled workaround with a genuinely per-fragment-DIVERGENT selector
  > (`(uint)pos.x & 1`) is correct on hardware: pixel(0,0) -> RT0 red / RT1 clear, pixel(1,0) ->
  > RT0 clear / RT1 green, exact 2/2 pixels x 2/2 RTs. **Structurally surprising and left
  > UNKNOWN:** the compiled program contains only **ONE** `frag_color_store` (`rt_index_bytes=[0]`,
  > `store_count=1`) and TWO `frag_tile_setup` brackets with selector bytes `0x0` and `0xc` (the
  > latter outside EXP-0029's `0x0`/`0x4`/`0x8` static-MRT table), yet both RTs receive correct
  > per-fragment-divergent data. Whether that is a genuine dynamic RT selector or an unmodelled
  > static encoding was NOT bit-decoded.
  > **FS-12 YES for every channel where a shader-driven write exists; PARTIAL for stencil.**
  > Color/depth/buffer/atomic cited from EXP-0091. New: a demoted lane's `[[sample_mask]]=0xF`
  > write is suppressed just as completely — the discarded pixel resolves to exactly `0.0` (fully
  > clear) while the survivor reads exactly `1.0`, with no partial mask leakage. **Stencil is
  > explicitly INFERRED, not HW-validated:** MSL exposes no fragment-writable stencil output at
  > all (only `[[color(n)]]`, `[[depth(qualifier)]]`, `[[sample_mask]]`), so there is no API
  > surface to attempt it; do not cite stencil suppression as HW-VALIDATED downstream.
  > Open sub-items deliberately left UNKNOWN: FS-03's exact MSAA sample positions; FS-05's
  > ISA-level coarse-mode question; FS-07's `0x90`/`0x92` axis-byte rule; FS-08's sample-vs-centroid
  > behavioural separation and the hardware-vs-compiler-bug attribution for `interpolate_at_offset`;
  > FS-09's config-D anomaly; FS-10's extra `iter_flat`; FS-11's single-store mechanism;
  > FS-12's stencil channel.
  > Evidence: `experiments/EXP-0111-m4-fragment-semantics/` (HW-PROBE + OWN-SHADER + HW splice +
  > encode/decode round trip; M4 target; A18 deferred).

---

### ANCHOR:   This is a compiler-output question; a `Yes` does not by itself prove API conformance.

  > **Answered 2026-08-28 (EXP-0103, M4/G16G, commit `bbb1e9fc`) — TRIG block.** Two runs, 47/47
  > cases byte-identical.
  > **TRIG-01 / TRIG-02 DEFERRED, as pre-registered.** Not attempted: the full operand/modifier
  > encoding of the native trig primitive and of the `0x2b` range-reduction op require field-level
  > splice validation beyond black-box MSL execution. `docs/isa/encoding-tables.md` already marks
  > the `0x2b` op's internals `INFERRED`.
  > **TRIG-03 / TRIG-04 PARTIAL, upgraded to HW-leaning STRUCTURAL — still short of a field-level
  > proof.** Numeric: a kernel feeding one `x` to both `fast::sin(x)` and `fast::cos(x)` is
  > self-consistent (380/400 exact; the 20 divergences are the TRIG-06 cliff, not a sharing
  > artifact). Structural: the shared-input kernel compiles to **198 bytes** vs **238 bytes** for
  > an otherwise-identical kernel taking two independent inputs — 40 bytes less work when sin and
  > cos of the same value are requested together, consistent with (but not proof of) a shared
  > range-reduction stage.
  > **TRIG-05 CHARACTERIZED — and `fast::` and `precise::` behave very differently.**
  > `precise::sin`/`cos`: **<=2 ULP over the entire tested range up to and including FLT_MAX**
  > (+/-3.4e38) — no accuracy cliff anywhere in the corpus (specials, magnitude sweep 2^-4..2^128,
  > 300 random samples); `sin` ULP histogram over 1294 samples is `{0: 972, 1: 302, 2: 8}`.
  > `fast::sin`/`cos`: **<=2 ULP for |x| <~ 6.588e6, then identically +/-0 for every input at or
  > above that threshold** (and for every NaN/Inf input). A 501-point dense follow-up sweep
  > (supplementary, outside the two-run contract) bracketed the transition to
  > **(6587824.0, 6588825.0]** — ~0.015% relative resolution. No relationship to a power of two or
  > a simple multiple of pi was found by inspection.
  > **TRIG-06 YES, for `fast::` only.** Every `fast::sin`/`fast::cos` input at or above ~6.588e6
  > returns exactly `+/-0` regardless of the true value — a total accuracy failure for that entire
  > half-line, not merely reduced accuracy. `precise::` shows no such failure anywhere tested up to
  > FLT_MAX. **This REFINES the CITED A18 result EXP-0026**, which reported `sin(2*pi)` error
  > ~5e5 ULP without separating fast from precise or locating a cliff. A software large-argument
  > reducer is required for `fast::`.
  > **TRIG-07 PARTIAL, as pre-registered.** Achieved accuracy over the reduced interval (small
  > |x|, e.g. |x|<10) is <=1 ULP for both namespaces — numerically the polynomial meets a tight
  > bound in range. **Exact coefficient bit patterns and evaluation order were deliberately NOT
  > extracted** (that would mean transcribing a compiler-generated fma chain, which clean-room
  > rule 5 forbids); `docs/isa/encoding-tables.md` flags them `not reconstructed`.
  > **TRIG-08 YES, fully characterized — and it is a genuine finding, not merely "expected NaN".**
  > `sin(+/-0) = +/-0` and `cos(+/-0) = +1` for both namespaces, matching the reference exactly.
  > **`fast::sin(NaN) = fast::sin(+/-Inf) = +0` — NOT NaN** (same for `cos`), while
  > `precise::sin(NaN) = precise::cos(NaN) = precise::sin(+/-Inf) = canonical qNaN 0x7FC00000`.
  > `precise::` propagates NaN correctly; `fast::` does not. Subnormal inputs behave as ordinary
  > small |x| with no distinct subnormal-specific behaviour.
  > **TRIG-09 PARTIAL, as pre-registered, but the numeric evidence is unusually strong.**
  > `sin_fast_f16`/`cos_fast_f16`: **1496/1552 exact against a correctly-rounded FP16 reference,
  > `max_ulp = 0`** — every finite non-special FP16 sin/cos in the corpus is exactly correctly
  > rounded; all 56 divergences are the same NaN/Inf -> `+0` special case seen in FP32. Fully
  > consistent with "compute at FP32 accuracy, narrow once", but the mechanism (vs. a native
  > FP16-width reduction that happens to also be exact) was not independently verified.
  > **TRIG-10 NO on this M4 — this UPDATES the CITED A18 result EXP-0026.** Numerically, `sin`
  > 742/1294 and `cos` 740/1294 outputs are identical between namespaces — i.e. the majority
  > differ. Structurally, compiled AGX byte lengths differ substantially (`sin`: 136 B fast vs
  > 456 B precise; `cos`: 138 B vs 462 B — precise is >3x longer) and the byte sequences diverge
  > **from the very first instruction**, not merely in a longer tail. Most divergence is the
  > NaN/Inf/cliff special-case handling plus a smaller population of ordinary 1-2 ULP in-range
  > differences. EXP-0026's A18 claim was evaluated on a much narrower input set and plausibly
  > never exercised this control flow — the two are not necessarily contradictory, **but the
  > driver-facing conclusion on M4 must be "not interchangeable", not "byte-identical".**
  > Open sub-items deliberately left UNKNOWN: TRIG-01/02 entirely; TRIG-03/04's field-level proof
  > of range-reduction sharing; TRIG-07's coefficients and evaluation order (deliberately, per
  > clean-room rule 5); TRIG-09's mechanism; the sin/cos cliff threshold is bracketed to ~1000 out
  > of ~6.59M, not pinned to the exact bit; FP16 `sin`/`cos` used a ~1500-point stratified sample,
  > not the 65536-point enumeration applied to `rcp`/`rsqrt`/`sqrt`.
  > Evidence: `experiments/EXP-0103-m4-fp-transcendental-semantics/` (HW-PROBE + OWN-SHADER +
  > PUBLIC MSL function names; M4 target; A18 deferred).

---

### ANCHOR:   APIs without an additional software correction path?**

  > **Answered 2026-08-28 (EXP-0103, M4/G16G, commit `bbb1e9fc`) — SFU block.** Two runs, 47/47
  > cases byte-identical.
  > **SFU-01 YES** — all nine (rcp, rsqrt, sqrt, exp2, log2, floor, ceil, trunc, round) compile,
  > dispatch and produce correct-shaped results as distinct MSL builtins/namespace calls.
  > **SFU-02 YES** — every SFU case's corpus includes the shared directed special block (+/-0,
  > +/-Inf, canonical/payload/signaling-pattern NaN, min/max subnormal, min/max normal); results
  > are itemized per function.
  > **HIGH-VALUE result: `rcp`/`rsqrt`/`sqrt` share division's DAZ+FTZ model exactly.** Every one
  > of `precise::rcp`/`rsqrt`/`sqrt`'s 30 / 77 / 77 divergences from a correctly-rounded IEEE-754
  > reference is subnormal-related, and **every one of those 184 divergences is exactly predicted
  > by the same DAZ+FTZ substitution model EXP-0074 found for division** (flush a subnormal
  > operand to signed zero before the op; flush a correctly-rounded subnormal result to a signed
  > zero). **Zero unexplained divergences; zero divergences at all outside the subnormal classes**
  > (1856/1886, 1809/1886, 1809/1886 exact). This closes `encoding-tables.md`'s `fspecial_est`
  > UNKNOWN flag for these three: their precise path IS correctly rounded, subject to the identical
  > DAZ+FTZ carve-out as division.
  > **`exp2`/`log2` have NO refined path at all** — categorically different, on two independent
  > kinds of evidence. `fast::` and `precise::` produce **byte-identical FP32 output for all 1362
  > cases each (0 differences)**, and their **compiled AGX byte streams are identical too (46 bytes
  > each)**. `precise::exp2`/`log2` is the same single SFU-estimate instruction as `fast::`.
  > Subnormal *inputs* still read as zero (1/1 and 73/73 subnormal-involving divergences match the
  > DAZ input-flush prediction), but there is no correctly-rounded result to flush, so FTZ is not
  > separately observable here.
  > **FP16 is a clean contrast:** `rcp`/`rsqrt`/`sqrt` (fast + precise) tested **EXHAUSTIVELY over
  > all 65536 bit patterns** show **zero** mismatches against a correctly-rounded non-flushing
  > reference — including 4094/4094 cases whose correctly-rounded result is a genuine FP16
  > subnormal, returned unflushed. **FP16 SFU ops neither DAZ nor FTZ; FP32 SFU ops do both.**
  > **SFU-03 PARTIAL, as pre-registered, with a comprehensive black-box determinism proof.**
  > **47/47 cases — every input in every case — byte-identical between run01 and run02**,
  > including all 65536x4 `rcp`/`rsqrt` FP16/FP32 fast+precise combinations. At the OUTPUT level
  > this hardware is deterministic for every bit pattern tested. Direct estimate-REGISTER readback
  > (proving the seed itself, pre-refinement, is deterministic — as CITED A18 EXP-0026 did via
  > splice) was NOT repeated on M4.
  > **SFU-04 DEFERRED, as pre-registered.** EXP-0026's A18 answer is an inferred
  > precision-doubling argument (8 -> 16 -> >=24 bits), explicitly not a literal instruction count
  > (clean-room rule 5). This experiment's 0-ULP precise-`rcp` result is *consistent* with
  > sufficient refinement but does not count iterations.
  > **SFU-05 YES (upgraded PARTIAL -> HW).** `precise::sqrt` is not simply `x * precise_rsqrt(x)`:
  > computed from the same `x` in the same dispatch, 1656/1884 identical, **228 differ**. Beyond
  > the trivial `x=0` structural case (9 instances), genuine non-trivial divergences exist for
  > ordinary finite `x` — e.g. `x=0x7F7FFFFE`: `sqrt = 0x5F7FFFFF` vs `x*rsqrt(x) = 0x5F800000`,
  > exactly 1 ULP apart.
  > **SFU-06 YES (upgraded PARTIAL -> HW).** `precise::divide` requires a correction beyond
  > `a * correctly_rounded_rcp(b)`: from the same `(a,b)` in the same dispatch, **650/820
  > identical, 170 (20.7%) differ, uniformly by exactly 1 ULP**. Since `precise::divide` is itself
  > 0-ULP correctly rounded (DAZ+FTZ aside) while `a * precise::recip(b)` is not always equal to
  > it, the divide path does something beyond reciprocal-then-multiply for ~1 in 5 random inputs —
  > consistent with CITED A18 EXP-0026's separate "remainder correction" finding.
  > **SFU-07 NO — bounded but never correctly rounded, in EITHER namespace.** `exp2`: <=1 ULP
  > always (1308/1362 exact, `max_ulp=1`). `log2`: <=2 ULP always (1036/1362 exact, `max_ulp=2`).
  > A consumer requiring correctly-rounded `exp2`/`log2` cannot rely on either namespace; 1-2 ULP
  > is the hardware ceiling. Special cases all matched exactly (`exp2(NaN)=NaN`,
  > `exp2(+Inf)=+Inf`, `exp2(-Inf)=+0`, `log2(+0)=-Inf`, `log2(negative)=NaN`, `log2(NaN)=NaN`,
  > `log2(+Inf)=+Inf`; 0 divergences in the special block).
  > **Supporting detail for SFU-01/02, `round_family_f32`:** `trunc` 1165/1172 exact (the only 7
  > divergences are NaN-payload canonicalization to `0x7FC00000`); `floor` 1140/1172 (7 NaN-canon +
  > **25 subnormal-input DAZ** — every negative subnormal gives `-0` instead of `-1`); `ceil`
  > 1118/1172 (7 NaN-canon + **47 subnormal-input DAZ**, mirror image); `round` 938/1172 —
  > **234 divergences, all sign-of-zero**: `round(-0.0)` and `round(any negative subnormal)`
  > return `+0` instead of `-0`. `round`'s zero-sign loss is a NEW, narrower finding: unlike
  > `floor`/`ceil` it loses the sign for `-0.0` itself, not merely as a DAZ side effect.
  > *(This section was rewritten after a disclosed post-freeze fix to the host oracle's
  > `floor`/`ceil` reference — which had used `trunc`'s rule. No hardware data changed.)*
  > Open sub-items deliberately left UNKNOWN: SFU-03's direct estimate-register readback on M4;
  > SFU-04 entirely (literal NR iteration count). No FP64, no non-default rounding modes (not
  > exposed by the public API), and no claim about behaviour inside a larger expression graph the
  > compiler might contract differently than these isolated single-op kernels.
  > Evidence: `experiments/EXP-0103-m4-fp-transcendental-semantics/` (HW-PROBE + OWN-SHADER +
  > PUBLIC MSL function names; M4 target; A18 deferred).

---

### ANCHOR: - **ENC-16 — Is scratch spill addressing and frame-size metadata fully known for generated shaders?**

  > **Answered 2026-08-28 (EXP-0105, M4/G16G, commit `79ab3da9`) — ENC block. Read the
  > supersession notes: this cluster's headline r64-95 result was overtaken by EXP-0112 (commit
  > `d5d8fbee`), and two adjacent claims were retracted by EXP-0101 (`2cf96b56`) and EXP-0099
  > (`de4e4a81`).** EXP-0105 itself: 16/16 cases per run, two runs, `01_results.jsonl`
  > byte-identical (sha256 `b193274a...`); 8/16 matched their oracle and every one of the other 8
  > is a deliberate positive control or a hypothesis-testing case whose oracle recorded a
  > *prediction*, not a pass/fail claim.
  > **ENC-02 REFUTED for `falu2`/`falu2i`'s packed source field at r64-95; UNKNOWN overall.**
  > Field value 67 (low 6 bits == 3, weight-64 bit set; register 67 never written) reads register
  > **3**'s seeded value 30.0, never the unwritten register 67's zero — by INDEPENDENT CONSTRUCTION
  > on `falu2i`, and reproduced on `falu2`'s own register-register form in a freshly built
  > carrier/harness. Two sibling instructions, two runs, deterministic. **SUPERSEDED /
  > STRENGTHENED by EXP-0112 (`d5d8fbee`):** a 28-point sweep of the consuming instruction's 7-bit
  > `srcA_reg` shows R = 0..63 correct (dense 15-point sweep), **R in [64,112] silently ALIASES to
  > `r(R mod 64)`** — proven by 4 poison-register controls that make the aliased read return the
  > poison value 30.0 rather than 0.0, i.e. it is genuine field aliasing, **not** the "silent zero"
  > EXP-0105 could not distinguish — and **R in {126,127} FAULTS the command buffer**, a second,
  > qualitatively different failure mode. Net: the field is 6 load-bearing bits in this context;
  > no mechanism has been found that reaches registers 64-95 through this family.
  > **ENC-06 PARTIAL, extended: 7 previously untested bits classified — 5 corrupting, 2 inert.**
  > `opflags` bit22, `opflags` bit23, `mod_hi` bit44, `ctrl` bit0 and `ctrl` bit1 each silently
  > change the read from 30.0 to exactly 0.0. Because the effect is IDENTICAL whether the register
  > field nominally selects 3 or 67, these are **general corruptors, not register-bank selectors**
  > — the `get_sr`-inspired "bank-unlock bit" hypothesis is REFUTED for all three cross-checked
  > candidates. `ctrl` bits 2 and 3 are the only two confirmed inert, for this construction only.
  > **ENC-07 PARTIAL, extended — general answer: NO, reserved bits are not safely known.** Five of
  > seven previously-unexamined bits turned out load-bearing. Policy reaffirmed with new specific
  > data: never synthesize or normalize an undocumented field in this family; emit only values
  > copied verbatim from a compiler-observed pattern for the same operand shape.
  > **ENC-10 OPEN, extended with a new negative data point.** A second, structurally different
  > register-addressing method (`iminmax`, plain 8-bit register fields) was attempted in EXP-0105's
  > pilot phase and **ABANDONED** after producing two unexplained, uninterpretable hardware
  > behaviours — recorded as a first-class unresolved negative, not dropped. **Partially offset by
  > EXP-0112 (`d5d8fbee`):** an independent program GENERATOR built 161 programs (DAG size 2-35
  > nodes, 44/100 main cases with more dataflow values than the 14-register pool, peak
  > `max_live_registers` 13) and ran **140/140 `expect_match` cases correct and 21/21
  > `expect_match=False` cases as predicted, 159 OK / 2 deliberate CMDBUF_ERROR** — a genuine
  > multi-instruction, multi-family generated-shader execution result, though not a census of
  > "every initial instruction family".
  > **ENC-01, ENC-04, ENC-05, ENC-08, ENC-09, ENC-11, ENC-12, ENC-13, ENC-14 — PARTIAL by
  > DESK-AUDIT (no new hardware evidence in this cluster).** ENC-01: several families remain
  > `db.json`-flagged inferred. ENC-04: float uniform sources covered by EXP-0020/RT-1a-FIX; the
  > integer ALU is still inferred. ENC-05: minifloat (EXP-0006) and `mov_imm` (EXP-0031) covered;
  > **NaN-literal handling is a gap not found documented anywhere.** ENC-08: ~87-91% tokenization
  > per the RT-ISA-FIX census. ENC-09: all 16 of this experiment's own cases round-trip. ENC-11:
  > compute closed (EXP-0003/EXP-0010 E4); other stages not. ENC-12: EXP-0010 E6 (jump) plus
  > EXP-0035/RT-ISA-FIX (call/jump_cond). ENC-13: substantially closed for tested depth
  > (EXP-0035/EXP-0038). ENC-14: compute doubly closed (EXP-0006/EXP-0020 + EXP-0092 GLIO-A02).
  > **ENC-03, ENC-15, ENC-16 UNKNOWN / DEFERRED.** ENC-03 was not probed. ENC-15 and ENC-16 are
  > `docs/isa/README.md`'s own disclosed gaps (ENC-16's sibling workstream is EXP-0107).
  > **Retractions that bear on this cluster and must not be lost:**
  > (a) **EXP-0101 (`2cf96b56`) refutes EXP-M4-13's `dst` formula.** The register a subsequent ALU
  > instruction must reference is `device_load`'s **`extmode` field divided by 2**
  > (`extmode = 2 * target_register`) — **NOT** the `dst_lo`/`dst_ext9`-derived value EXP-M4-13
  > predicted. `dst_lo`/`dst_ext9` remain real and independently required but must be **copied
  > verbatim** from a compiler-observed value for the same `addr_mode`/`ld_format` shape, never
  > derived from the target register; and `falu2i`'s own `mods` byte must be `0xC0` (not the naive
  > default 0) when the operand it modifies is load-sourced. HW-VALIDATED over two gated runs,
  > 6 positive constructions and 6 adversarial falsifications of the next-most-plausible repairs.
  > (b) **EXP-0099 (`de4e4a81`) refutes BOTH competing bit-15/31 lifetime models**, and the
  > attribution was retracted from `docs/isa` in commit `88fa4953`. `falu2`'s
  > `srcA_reg`/`srcB_reg` top bit (instruction bit 15 / bit 31) has **zero observed effect** on
  > either which register is read or on retention behaviour, in all 8 decisive cases across two
  > runs — a third outcome distinct from both models as stated. EXP-0099 also refuted the claimed
  > `mod_hi` bits 1-3 "consumer route" field (all 8 values) and all three candidate `reg_move`
  > fixes, and found by static analysis alone that the explainer's own 10-byte "retain source 0"
  > example does not decode under any `db.json` family.
  > Open sub-items deliberately left UNKNOWN: whether registers 64-95 are reachable through this
  > field family by ANY encoding not yet tried — the positive falsifier (a genuinely seeded,
  > distinctly-valued r67 read back through the same field) has never been achieved; `ctrl` bits
  > 0/1 were corruption-tested only at reg=3, not cross-checked at reg=67 (a disclosed time-boxed
  > narrowing); `reg_move` reading an ALU- or load-written GPR remains blocked (EXP-0090 blocker
  > #2), with the instruction's `src_flag=0` output HW-shown to depend only on `src_reg` quantized
  > in register PAIRS — the signature of a fixed per-kernel preloaded/uniform slot, not a GPR read;
  > ENC-03/15/16 entirely.
  > Evidence: `experiments/EXP-0105-m4-encoding-registers/` (HW splice, independently constructed),
  > with `experiments/EXP-0112-m4-program-generator/`, `experiments/EXP-0101-m4-synthesis-blockers/`
  > and `experiments/EXP-0099-m4-lifetime-field-model/` for the supersessions and retractions above
  > (HW-VALIDATED + OWN-SHADER + DESK-AUDIT mix; M4 target; A18 deferred).

---

### ANCHOR:   register allocator or late predicate allocator?**

  > **Answered 2026-08-28 (EXP-0104, M4/G16G, commit `574ee96f`; deferred items closed by
  > EXP-0115, commit `fec9315a`) — CF block.** EXP-0104: 92 cases per run x 2 runs, cross-run gate
  > 0 issues, 71 OK/MATCH, 0 mismatch, 4 contained `CMDBUF_ERROR`, 1 contained hang (8 s timeout,
  > zero host impact). EXP-0115: 308 cases per run x 2 runs, 295/308 byte-identical.
  > **CF-01 YES, with a sharp structural correction.** All 8 authored shapes (diamond join, 5-way
  > if-elseif chain, if-nested-in-else, a 21-point depth sweep, two nested-loop shapes) tokenize
  > with **0 leftover bytes** and match a Python host oracle exactly. The correction: the compiler
  > uses **two qualitatively different lowerings, selected by the presence of
  > `return`/`break`/`continue` — not by nesting shape or depth.** Ordinary if/else with no
  > early exit (`plain_join`) is **pure predication: 8 instructions, ZERO
  > `icmp_pred`/`if_push`/`pop_reconverge`** (a compare-select only). The same values with a
  > `return` (`ret_early`) is 13 instructions **with** the full mask-stack machinery. A kernel
  > designed to force two simultaneously-live predicates (two nested if/else regions each holding
  > a data-dependent loop, no early exit anywhere) tokenized to **ZERO `icmp_pred` instances** —
  > recorded as a genuine negative result, and the reason the CF-05 splice target had to move.
  > **CF-02 YES.** One data-dependent loop containing both a `continue` (k==3) and a `break`
  > (k==7) tokenizes cleanly and matches an exact host re-implementation
  > (`bc_a = [0,1,2,5,8,10,3,7]`). No dedicated loop-exit helper instruction exists or is needed.
  > **CF-03 PARTIAL — bounded from below by hardware, bounded from above only by the TOOLCHAIN.**
  > EXP-0104 found no failure to depth 128 (divergent-return if-chain), 64 (pure loop-nest) or 12
  > (genuinely divergent nested loops) — 21 depth points, all MATCH, both runs. EXP-0115 pushed to
  > the wall: **exact max-compilable depths are 254 (if-chain), 255 (pure loop-nest), 255
  > (bounded-divergent nest)**, all HW-dispatched correctly at their maximum, with the next depth
  > up a deterministic `COMPILE_FAIL` — `"bracket nesting level exceeded maximum of 256"`. **That
  > is Metal's Clang front end (`-fbracket-depth=256`), not AGX silicon**, and it is not adjustable
  > through the public `MTLCompileOptions` surface this project may use. **No AGX hardware fault,
  > hang, or silent-wrong-result was observed at ANY depth that compiled.** The true hardware
  > reconvergence-stack ceiling remains **UNKNOWN** beyond ~254-255. (An NIR-based Mesa backend
  > does not go through Clang's parser at all, so this specific limit is almost certainly not
  > inherited by that path.) *Disclosed defect: EXP-0115's `loopnestD2` oracle assumed additive
  > rather than multiplicative nested-loop growth, so all 9 of its depths show a deterministic,
  > understood MISMATCH in both runs; hand verification confirms the hardware output matches
  > `PRODUCT(1 + bit((j-1) mod 32)(v))` exactly. The load-bearing CF-03 fact — `STATUS OK` at every
  > depth — is unaffected, and run02 deliberately reused the unmodified oracle to keep the
  > cross-run determinism gate meaningful.*
  > **CF-04 YES, decisively.** `ret_early` (100 bytes, 13 instructions) uses
  > `icmp_pred`+`if_push`+`pop_reconverge`; the semantically equivalent `plain_join` without a
  > `return` (66 bytes, 8 instructions) uses ONLY a compare-select. **Neither contains the `0x8f`
  > subroutine CALL/RETURN opcode** (verified by full disassembly, not a raw byte scan), confirming
  > EXP-0035's finding that `0x8f` is reserved for real function calls. A `multi_return` kernel
  > with three early-return points at three nesting depths matched a 5-way host oracle exactly,
  > proving a genuinely shared epilogue. Lower divergent return as an execution-mask-narrowing
  > `if_push`, never as a call-frame return.
  > **CF-05 NO — there is no independently addressable predicate file.** Compiler census:
  > **18/18 `icmp_pred` instances across nesting depths 1-16 and an asymmetric if-in-else shape
  > have `dst_pred = 0`**, zero exceptions. HW splice (downstream read, not self-read): `dst_pred`
  > spliced to 1 gives a unique corruption `[-1003,-1003,-1001,-1001,-1001,-1001,-1001,-1001]`,
  > while 5 and 0xf both give `[-1001]*8` (every lane takes the outermost else). EXP-0115 extended
  > this to a **25-point joint (dst_pred, if_push.pred) matrix plus a full 0-15 `dst_pred`
  > census**, with a decisive result: **output depends ENTIRELY on `dst_pred` and NEVER on
  > `if_push.pred`** — the sibling `if_push_pred` opcode's 4-bit `pred` nibble is **completely
  > INERT at every value, matched or mismatched**. `dst_pred` splits exactly three ways: 0 correct,
  > 1 a unique corruption, {2..15} (14 values, zero exceptions) one uniform corruption. Both live
  > hypotheses are REFUTED: `if_push`'s predicate consumer is not parameterized by an independent
  > address at all, and nonzero `dst_pred` is ordinary wrong-operand-field corruption.
  > **Flagged for the `docs`/`tools` owner: `db.json`'s current `if_push_pred` "predicate-register
  > PUSH variant" characterization is not supported by this splice evidence for this
  > producer/consumer pairing.**
  > **CF-06 YES — but the answer is "there is nothing to allocate."** Always emit `dst_pred = 0`;
  > the real finite, lifetime-managed resource is the `if_push`/`pop_reconverge` execution-mask
  > STACK (LIFO by construction), which CF-03 stress-tested correctly to the toolchain ceiling. A
  > late-predicate-allocator pass is not needed for this ISA as currently understood.
  > **Branch reach (not a numbered item, but part of CF-01/CF-02's core question) — MAPPED, with a
  > major correction and a new first-class finding.** EXP-0104: a +4096 B forward perturbation ran
  > to completion with `STATUS OK` and **silently ZEROED output** — a driver must never treat
  > "no CMDBUF_ERROR" as proof a jump target is correct. EXP-0115's 162-point sweep sharpens it:
  > **forward has ZERO slack (delta=+1 already faults)**; **backward has exactly ONE alias hole
  > (delta=-2 is also fully correct)**; the region past the function's 146-byte extent is a genuine
  > **CHECKERBOARD** of fault / hang / silent-zero, not a threshold (e.g. +1024/+1536/+2048/+2176
  > silent-zero while +1280/+1408/+2432 fault, interleaved); **backward is uniformly fault/hang
  > with zero silent-zero points anywhere**; and **13 of 162 points (8%) are genuinely
  > NON-DETERMINISTIC run-to-run** — same compiled bytes (verified byte-identical from both runs'
  > independently compiled archives), different observable outcome, including `STATUS` flips
  > (`OK` silent-zero vs `HANG`) and GPU error-code flips (`PageFault` / `Hang` /
  > `InnocentVictim`). The `InnocentVictim` code additionally shows a command buffer can be
  > reported as the victim of a NEARBY dispatch's fault — real operational noise for any harness
  > firing many faulting dispatches back to back.
  > Open sub-items deliberately left UNKNOWN: the true hardware reconvergence-depth ceiling beyond
  > the toolchain wall; mixed if+loop nesting and nesting combined with real function calls;
  > `dst_pred`/`if_push.pred` were cross-matrixed at only 25 of 256 pairs and at exactly ONE
  > nesting position (the outermost `icmp_pred`/`if_push`, not a nested nonzero-`scope` occurrence);
  > the exact byte where a forward jump transitions from fault to silent-zero was not bisected; the
  > mechanism behind the 13 non-deterministic points is `INFERRED` only (landing on a real
  > instruction boundary via an unintended entry path, so the outcome depends on uninitialized
  > resident state); shapes with more than 2 simultaneously-live non-return-gated predicates were
  > never constructed.
  > Evidence: `experiments/EXP-0104-m4-controlflow-simd/` and
  > `experiments/EXP-0115-m4-controlflow-simd-deferred/` (HW-PROBE + OWN-SHADER + HW-VALIDATED
  > splice + clean tokenization; M4 target; A18 deferred).

---

### ANCHOR:   exposed to fragment shaders?**

  > **Answered 2026-08-28 (EXP-0104, M4/G16G, commit `574ee96f`; deferred items closed by
  > EXP-0115, commit `fec9315a`) — SIMD block.**
  > **SIMD-01 YES, for compute AND fragment.** EXP-0104 (compute): at tg=64 every thread reports
  > `threads_per_simdgroup = 32`; at **tg=48** (one full 32-thread group plus a **PARTIAL
  > 16-thread** final group) `thread_index_in_simdgroup` correctly resets to 0..15 and
  > `simdgroup_index_in_threadgroup` is 1, yet `threads_per_simdgroup` **still reports 32** — it is
  > a fixed architectural constant, not a live occupancy count. EXP-0115 closes the deferred
  > fragment sweep: `[[threads_per_simdgroup]]` compiles in the fragment stage (not previously
  > established here) and reports **32 at every one of 12 render-target sizes** from 1x1 (a single
  > real fragment) through 64x64, crossing the fixed 32x32 tile boundary repeatedly — **10784 total
  > pixel readings, zero exceptions.** Safe to constant-fold to 32 in both stages.
  > **SIMD-02 YES.** Three predicates genuinely derived from `thread_position_in_grid`
  > (`i%3==0`, `i%7<2`, `5<=i<19`) at grid=tg=32: all 32 lanes read the identical 32-bit mask and
  > it equals `SUM pred(j)*2^j` exactly. Bit `i` = lane `i`; no lane renumbering needed.
  > **SIMD-03 — defined and deterministic, but NOT a simple wraparound, and NOT uniform across the
  > family. THREE different out-of-range behaviours exist, and the static and dynamic encodings
  > disagree.** Dynamic (runtime-register index) `simd_shuffle`: for idx >= 32 the effective source
  > lane is **`idx & 0x1C`** — only bits 2-4 are used, bits 0-1 and every bit >= 5 dropped — fitting
  > all 14 out-of-range points with zero exceptions (32->0, 33->0, 40->8, 63->28, 64->0, 127->28,
  > 4095->28, 65535->28, plus a per-lane `idx=lane+32` case matching on all 32 lanes). **This is
  > NOT modulo-32** (which would predict 33->1, 63->31, 127->31 — all wrong), not clamping, not
  > pass-through, not a fault. Dynamic `simd_shuffle_xor` (masks 32,33,63) and dynamic
  > `quad_shuffle` (idx 4,5,8,255): **every lane reads a hard ZERO** — a qualitatively different
  > mode. EXP-0115 then closed the static/immediate form by splicing the raw `lane` byte directly
  > (the compiler PRE-MASKS an illegal literal, e.g. literal 40 compiles to `(40 & 0x1F) << 1`, so
  > only a raw splice tests the hardware): **static `simd_shuffle` gives HARD ZERO for all 28
  > out-of-range/odd raw values from 64 through 255 — it does NOT alias like the dynamic form** —
  > while static `simd_shuffle_xor` and `quad_shuffle` match their dynamic forms (hard zero either
  > way, the `quad_shuffle` case additionally confirmed via a naturally-compiled unmasked literal
  > `quad_shuffle(v,(ushort)7)`). **Two genuinely different hardware behaviours for what MSL
  > exposes as the same builtin**, depending only on which encoding the compiler chose. NIR
  > lowering must mask the index in software, or at minimum never assume any single fallback rule.
  > **SIMD-04 YES.** With odd lanes taking an `else` arm that calls NO subgroup op at all,
  > `simd_prefix_exclusive_sum`, `simd_prefix_inclusive_sum` and `simd_sum` on the even lanes all
  > match a closed-form active-lane-order oracle exactly (excl/incl = 0..15 at positions 0,2,..,30;
  > reduce = 16 at every active lane). No special legalization for the "some lanes skip the call"
  > divergence shape.
  > **SIMD-05 YES, fully resolved — on real 4x4 render-target geometry, all 16 pixels per kernel.**
  > `quad_shuffle_xor` mask **1 = horizontal `(x^1, y)`**, **2 = vertical `(x, y^1)`**,
  > **3 = diagonal `(x^1, y^1)`**. Within-quad linear order is **row-major**: lane0 top-left,
  > lane1 top-right, lane2 bottom-left, lane3 bottom-right. `quad_shuffle_up`/`_down`'s "fill"
  > clamps at the quad's own lane-0 / lane-3 boundary. Quads tile the screen in fixed
  > non-overlapping 2x2 blocks aligned to even (x,y) — confirmed by (2,0)/(3,0)/(2,1)/(3,1) forming
  > their own self-consistent quad. The compute linear half independently confirms
  > `thread_index_in_quadgroup = lane % 4`. `quad_swap_horizontal/vertical/diagonal` map directly
  > to masks 1/2/3.
  > **SIMD-06 — EXP-0104 said YES; EXP-0115 NARROWS that to "not universally".** EXP-0104
  > (structural): `sgbar_none`, `sgbar_memnone`, `sgbar_memtg`, `sgbar_memdev` all compile to the
  > **IDENTICAL 46-byte `_agc.main`**, byte for byte — `simdgroup_barrier` adds zero instructions
  > for every memory class, stronger than `threadgroup_barrier`, which EXP-0093 showed DOES emit a
  > real instruction even for `mem_none`. EXP-0104 itself flagged its functional corroboration as
  > weaker than the structural result (grid=tg=32 means the kernel's own control flow already
  > reconverged every lane before the cross-lane read, so the test could not distinguish "truly
  > unnecessary" from "never mattered here"). **EXP-0115 resolves that flag in the negative:**
  > under **DIVERGENT** call patterns the compiler retains real machinery — `sgbar_loop`
  > (per-lane divergent call COUNT) 124 vs 110 bytes and 18 vs 11 instructions; `sgbar_ifdiv`
  > (divergent call PRESENCE) 76 vs 46 bytes and 10 vs 5 instructions, the barrier-present twin
  > keeping a real `if_push`/`pop_reconverge` pair and a `scoreboard_fence` where the no-barrier
  > twin is entirely dead-code-eliminated. Under UNIFORM patterns (heavy register pressure, two
  > consecutive barriers, depth-8 non-divergent nesting) it stays byte-identical, reproducing
  > EXP-0104. **Honest caveat carried forward:** the mechanism may be the barrier acting as an
  > optimization barrier / side-effect anchor rather than proof of a dedicated opcode; both
  > readings support the same driver conclusion. Functionally, both deadlock-risk shapes dispatched
  > correctly under a hard 10 s timeout with exact oracle matches — no deadlock. **Net: treat
  > `simdgroup_barrier` as free only at non-divergent call sites.**
  > **SIMD-07 PARTIAL, with a genuine refutation — helper lanes are INCLUDED, not excluded.**
  > EXP-0104: with one fixed pixel discarding on a 4x4 target, every surviving pixel's **raw low-16
  > mask bits are `0xFFFF`, byte-identical to the no-discard baseline** — `simd_active_threads_mask()`
  > does NOT clear a just-demoted neighbour's bit. Combined with EXP-0091 (data-movement ops also
  > include the demoted lane), the narrower "vote ops exclude helpers" hypothesis is **REFUTED**.
  > EXP-0115 extends this to three more ops: `simd_all` still sees the demoted lane's FALSE
  > predicate, `simd_any` still sees its TRUE predicate, and an explicit `simd_ballot(predicate)`
  > reproduces the same behaviour. **The popcount 16 -> 24 puzzle is NARROWED, not resolved:** an
  > ordinary divergent `return` at the same pixel does **not** trigger the jump (survivors report
  > 16), decisively ruling out "generic to any divergent control flow"; two discards give the same
  > 24 as one (not count-proportional); moving the discard to pixel (1,1) gives the same 24 (not
  > location-dependent). The extra 8 bits live in mask bits 16-23, outside the raw R/G readback,
  > and the exact bit-level mechanism is **UNKNOWN** — the discard/return fragment prologue has
  > undecoded residue (an `<UNKNOWN>` byte0 `0xa6`/`0x54`-family leader absent from
  > `tools/agx-isa/db.json`). **The +8 magnitude must not be relied on for anything.**
  > Open sub-items deliberately left UNKNOWN: SIMD-03's sparse sample points between the tested raw
  > values (the "hard zero" pattern is assumed, not proven, to continue between them), and
  > `simd_shuffle_up/down`'s fill behaviour at out-of-range magnitudes (only the quad-scope up/down
  > fill was tested); SIMD-06's isolation of the barrier's own compiled cost from the
  > optimization-barrier confound; SIMD-07's exact bit mechanism, multi-quad-crossing discard
  > patterns, and a full byte-level decode of the discard/return fragment prologue.
  > Evidence: `experiments/EXP-0104-m4-controlflow-simd/` and
  > `experiments/EXP-0115-m4-controlflow-simd-deferred/` (HW-PROBE + OWN-SHADER + HW-VALIDATED
  > raw-byte splice; M4 target; A18 deferred).
