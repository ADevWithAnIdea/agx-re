# EXP-0186 — drafted documentation text, ready to paste

Grouped by **destination file**, ordered by **rank** within each group. Every block below is
traced to a committed experiment artifact; the per-fact trace, evidence label, target and
caveat list is `docs_gap.json`. Nothing here is drafted from `EXP-0183`/`EXP-0184`/`EXP-0185`
(no `RESULTS.md` — live) and nothing is drafted from a `PROVENANCE.md` row alone.

**Read `docs_gap.json` → `provenance_defects` before applying D01.** The committed
`PROVENANCE.md` row for `EXP-0179` states the *withdrawn* first version of `call.b6`. The
draft in §A.4 below follows the experiment, not the row.

---

## A. `docs/isa/README.md`

### A.0 — the "silent zero, not a fault" list (line ~78) — HIGHEST-LEVERAGE SINGLE EDIT

*This existing list is the one place in the deliverable where an implementer is told that
Apple9's dominant failure mode is quiet. It currently ends at the 2026-08-28 M4 wave. Four of
tonight's G17P results belong in it, and one of them makes the list's own premise sharper.
Append after the `falu2.mod_lo` bullet:*

```markdown
Added by the 2026-08-30 G17P wave — these are `target: G17P`, and the last one changes how the
list must be read:

- **The half-ALU family's destination is byte0's high nibble, and `db.json` models it as a
  source** — an emitter following the descriptor writes **`r1`** every time, with no fault
  (EXP-0180, DEF-0180-1).
- **`n3_mov`'s source-register field is one bit off in `db.json`** — write the register number
  where the descriptor says and the hardware reads register `S >> 1` at half `S & 1`: **the wrong
  register *and* the wrong half**, silently (EXP-0174, DEF-0174-1).
- **A `device_store` through an unbound binding slot is silently dropped** — 254 of 256
  `base_slot` values store nothing at all, with **0 faults and 0 hangs**, no stray write and no
  diagnostic. Binding validity must be guaranteed by construction in userspace (EXP-0169 §14).
- **`vary_store.hint6` bit 4 makes the entire fragment output read `0.0`** — the whole varying
  block is lost, not just the component being stored (EXP-0163 §4).
- **`tex_sample.coord` pointed at a register the program does not keep live** returns the
  previous result unchanged, never a fault — and the fragment-stage register index **aliases with
  period 16**, so a "safe-looking" high register is not safe (EXP-0172 §2.1).
- ⚠️ **`instance_id` is not base-inclusive while `vertex_id` is** — a back end that treats them
  alike gets instanced draws with a non-zero `baseInstance` silently wrong (EXP-0178 §3.5).

> **And the premise sharpened: absence of a fault is not evidence the operation happened.**
> Across **256 `rt_index` values on four `tile_read`/`tile_read_mrt` carriers in two gated runs
> there is not a single fault** (EXP-0178 §5), and the `device_store` unbound-slot sweep produced
> **0 faults and 0 hangs over its full 256-value range** (EXP-0169 §14) — a hazard its own
> pre-registration had warned was the likeliest thing left to wedge the device. **A status code
> can never be the oracle on this hardware; the read-back must be poisoned before the run and
> checked after it.** Two instruction families, two experiments, same conclusion.
```

*The `⚠️ Read "emittable" strictly` block just above (line ~63) also needs its example replaced:
the `reg_move_*` / `uniform_mov` cluster is no longer the clearest example of the distinction,
because the general GPR→GPR move it names as "an open hard negative" is now **closed** by
`n3_mov` (EXP-0174; see §A.6 and §C.1). Pick a still-open example, or restate the sentence as
history with a pointer to the closure.*

### A.1 — emitter-safety block, new ⛔ bullet (rank 1)

*Insert into the `**Negative and safety results**` ⛔ list, immediately after the `fspecial`
pair and before the `imad` bullet. Note that the surrounding list header reads
`target: G16G`; this entry is **G17P** and says so inline, as the `fspecial` entries do.*

```markdown
- ⛔ **The half-ALU family's DESTINATION is byte0's high nibble, and `db.json` models it as a
  source — an emitter following the descriptor can only ever write `r1`.** `target: G17P`.
  For the `0x10`/`0x11` leaders (`half_alu`, `half_alu_ext8`, `half_alu_fma12`):

  | field | what it actually is |
  |---|---|
  | **byte0 high nibble** | **destination register `n`.** `byte0 = n<<4` writes **`r[n]`'s LOW 16 bits** and **preserves `r[n]`'s HIGH 16 bits** |
  | `db.json`'s `dst` (bits 8..15) | appears in the arithmetic as a **SOURCE** |
  | byte+4 | does **not** appear in the arithmetic at all — it is the **length selector** (see the length rule below) |

  `db.json` pins all eight bits of byte0 in `match`, so a descriptor-driven emitter has no way
  to name a destination and every half-ALU result lands in `r1`. There is no fault: the program
  runs and writes the wrong register. Confirmed **three independent ways** on G17P — a dense
  destination-nibble sweep (`n = 0..15`, 16/16, two carriers, both gated runs, 100.0000%
  agreement); structurally (the seed program's 14 low-half writes land in `r_j` in **every one of
  33,470 gated cases**); and arithmetically (`r1.lo = 0x470f = 1.625 × 2.59375 + 2.84375` =
  byte+3 × byte+1 + byte+5). Two nibbles are excluded with cause and are harness artefacts, not
  exceptions: `n=15` is the store index register the harness re-seeds, and on the low carrier
  `n=13` is the second-consumer destination. This is the same defect class already documented one
  family over for `mov_zext16`, `n3_mov`, `cvt_f2h_dst` and `falu3`. `EXP-0180` (DEF-0180-1).
```

### A.2 — emitter-safety block, second new ⛔ bullet (rank 10, 12)

*Append to the same ⛔ list, after `op04_len8`.*

```markdown
- ⛔ **Three exact, contiguous illegal-encoding regions found by sweeps that deliberately ran
  without a hang budget.** `target: G17P`. Each was mapped over the *full* 256-value range with
  zero counterexamples; a per-field budget of 2 would have reported "two bad values" for all
  three (see `experiments/FIELD-SWEEP-PROTOCOL.md` §3(c)).

  | field | rule | region | class |
  |---|---|---|---|
  | `frag_color_pack.dst` | `dst[7:6] == 0b11` | `0xC0`–`0xFF`, **64 values** | **HANG** — `0x00`–`0xBF` are all clean, so the real encodable range is **192, not 256** |
  | `device_store.index_reg` | `(v & 0x60) == 0x60` | `0x60`–`0x7F` and `0xE0`–`0xFF`, **64 values** | fault (bit 7 is a don't-care — the `0x00`–`0x7F` map repeats exactly in `0x80`–`0xFF`) |
  | `device_store.extmode` | `v >= 0xFC` | `0xFC`–`0xFF`, **4 values** | fault |
  | `half_alu*.opflags` | `(byte+2 >> 3) >= 16 ∧ (byte+2 & 7) ∈ {4,5}` | opflags bit 4 set with `opsel` = hadd or hmul | fault, 128 cases, zero counterexamples |

  The three fault walls are **faults, not hangs** — per-command-buffer errors, fault-contained,
  no reset and no wedge, with the sweeps running through them at full speed. The
  `frag_color_pack.dst` wall **is** hangs: 64 of them, and the device survived all 64 with no
  reset. `EXP-0168` §8.1, `EXP-0169` §15, `EXP-0180` §4.
```

### A.3 — `Special-register enum + shader ABI` (line 1217), two additions (ranks 4, 6)

*Add as new bullets after the existing `⚠ threadgroups_per_grid` bullet.*

```markdown
- ⛔ **In a VERTEX shader every `sr_sel` with bit 7 clear FAULTS the command buffer** — all 128
  values `0x00`–`0x7F`, contiguous, zero counterexamples, both gated runs. Nothing at or above
  `0x80` faults in any stage. **A back end must never emit a bit-7-clear selector**, and must
  know that the failure mode is stage-dependent: **loud in vertex, near-silent in compute**,
  where the same encoding does not fault at all and instead writes **one lane of 64**, leaving
  the other 63 untouched. The single-lane effect is the *whole program* retiring one invocation,
  not the SR datapath: an integrity sentinel written by a separate `device_store` carrying no
  SR value lands on that same single lane. `HW-VALIDATED`, `target: G17P`, `EXP-0178` §3.1–§3.3
  (256 values × 3 stage carriers × 2 gated runs, 100.00% cross-run agreement, zero
  disagreements).

  > **This REFINES `EXP-0092`; it does not refute it.** That exhaustive M4 sweep found no
  > `sr_sel` value raising `STATUS != OK` — and it ran on a **compute** carrier, which
  > `EXP-0178`'s compute arm reproduces exactly (0 faults in 256 values, both runs). **The
  > divergence is STAGE, not target.** The M4 record is correct about what it measured. An
  > experiment can be exhaustive over the whole encodable range, densely swept and cross-run
  > agreed **and still be blind**, because one carrier cannot see a dimension it does not vary.

- ⚠ **`vertex_id` is base-inclusive in hardware; `instance_id` is NOT.** `0xdd` returns
  `index + baseVertex`; `0xd8` returns the **raw instance ordinal**, and `baseInstance` is added
  **in software**. A back end that assumes the two behave alike gets instanced draws with a
  non-zero `baseInstance` **silently wrong**. `HW-VALIDATED`, `target: G17P`, `EXP-0178` §3.5 —
  and the compiler-inserted constant was **measured, not assumed**: seven selectors with no
  vertex-stage meaning (`0x9c`, `0x9d`, `0x9e`, `0xa0`, `0xa1`, `0xa4`, `0xc5`) all read exactly
  `5`, seven independent zero-expectations agreeing on `K = baseInstance = 5`. Subtracting `K`,
  `0xdd` ramps `9, 10, 11` across three vertices (`baseVertex = 9`) and `0xd8` reads flat `2`.

  **Bounded, and the bound matters.** *In a vertex program that does not declare
  `[[base_vertex]]`/`[[base_instance]]`, selectors `0x88` and `0x8a` read 0 on G17P.* The
  alternative — that the driver only arms them when the shader declares the builtin — is **not
  excluded**, so this is deliberately **not** recorded as refuting the enum entry (unlike
  `0xa8`, where the shader asks for nothing and the register still contradicts its documented
  meaning). `EXP-0178`'s vertex arm is reported **differentially** for the same reason: its
  harness scored `0x8a` as correct because oracle and observation both said 5, which is a right
  answer for the wrong reason, and its two passes are not cited as validations of anything.
```

### A.4 — `Function calls / pointers / dynamic libraries ABI` (line 1371) (ranks 13, 14)

*Replace the existing `**CALL**` and `**RETURN**` bullets with the following, and append the
new ⛔ bullet. The existing calling-convention, function-pointer and dynamic-library bullets
are unaffected.*

```markdown
- **CALL is EMITTABLE — every byte generated, none copied.** `target: G17P`, `HW-VALIDATED`.
  192 distinct generated calls × 2 gated runs = **384/384 correct, zero faults, zero hangs, zero
  disagreements**; each `call`, callee and `ret` was produced from the descriptor's declared bit
  positions with nothing lifted from a compiled shader (`EXP-0179` §2–§3).

  ```
  CALL  = 0f 05 54 <b3> 8f <b5> <b6> <off48 LE, signed> <tail>          (14 B)
          b3    : the BRANCH-TAKEN selector — bits 5:2 only. Codes {6,8,9,10,11,12,13,15}
                  take the call; the other eight FALL THROUGH cleanly (callee never runs,
                  control continues and returns) and NEVER fault. Bits 1:0 and 7:6 inert.
                  The compiler's 0x1a is code 6.
          b5    : legal iff (b5 & 0x06) == 0  — 64 of 256 encodable.
                  bit 1 set -> CMDBUF_ERROR fault (128/128).
                  bit 2 set with bit 1 clear -> the call is not taken.
                  bits 0,3,4,5,6,7 inert.
          b6    : bit 1 (0x02) MUST BE SET. 128 of 256 legal; bits 0 and 2..7 don't-care.
          off48 : target = call_addr + 4 + offset.   Signed LE PC-relative.
          tail  : DON'T CARE (all 256 values legal on a generated leaf call AND on a
                  compiled non-leaf call).
    MUST be followed by   pop_reconverge  0f 06 <bank> 02 00 00
                          (scope_kind 0x02 closes the call; 0x01 does NOT — the callee runs
                           and never returns. The mask bank is a don't-care: 0x04/0x24/0x54.)
    The 43 00 00 01 frame marker before the call is OPTIONAL.

  RET   = 8f <linkmode> 54 <scoreboard>                                 (4 B)
          linkmode : 0x02 leaf / 0x12 non-leaf both return. 0x04 / 0x05 do NOT return.
  ```

  > **The `0f 06` reconverge after a call is REQUIRED; the `43 00 00 01` frame marker is
  > OPTIONAL.** Both carriers, both runs, unanimous: reconverge absent → **fault**, with or
  > without the marker. This is a direct consequence of `call` reusing the `0f 05` execution-mask
  > **push** — the push must be popped, and the marker is scaffolding. This constraint is new
  > and no previous document carried it.

  **`target = call_addr + 4 + offset` is now measured FORWARD.** Every call in this repository's
  corpus is **backward**, because in compiled code the callee always precedes the caller, so the
  forward direction had never been tried. Measured exact at **2-byte granularity across a ±8
  window** (−8→ladder rung 0, −6→1, −4→2, −2→3) plus 48 further displacements; `+2`/`+4` land
  inside the callee body and still return; `+6`/`+8` fault. A call aimed at a **bare `ret`**
  returns correctly, so the return machinery is independent of the callee body.

  **Not established, and stated as such:** a *generated* **backward** call — its jump-over
  carrier did not calibrate and was dropped rather than fudged. Backward displacements remain
  covered only by `EXP-0035`'s compiled evidence. `b3`'s codes were mapped for **whether** the
  call is taken, not for what each code **means**; `b5`'s fault bit was not characterised beyond
  "it faults"; and `b6`'s meaning is bounded, not explained — we know bit 1 must be set, not what
  it controls.

- ⛔ **A nested call without a properly established scratch frame destroys the outer return and
  runs forever.** All six correctly-formed depth-2 configurations **HANG** — with and without
  `link_save_restore`, with and without the frame marker — while the two retained `pop=0`
  controls **FAULT**. `target: G17P`, `EXP-0179` arm N. The positive discriminator is the
  faulting controls, not the hangs: a runner cascade cannot produce a clean `CMDBUF_ERROR` at
  index 0 before any watchdog fires.

  **`INFERRED`, explicitly awaiting falsification: that the return address is a single link
  register.** This result is *consistent with* that model and does **not** demonstrate it. The
  synthesized program emits no `frame_prologue`, and `link_save_restore` writes to per-thread
  scratch whose size comes from the carrier kernel's compiled metadata — which an overwritten
  `_agc.main` does not control and which may be zero. So even the `link=1` arm may have saved
  into unallocated scratch. A successor experiment is named.
```

### A.5 — `tile_read` / `tile_read_mrt` (line 1138), target + hazard sharpening (rank 7)

*Amend the section heading's target tag and append the following note after the existing
"single most useful driver fact" block-quote.*

Heading becomes:
`### ✅ \`tile_read\` / \`tile_read_mrt\` are EMITTABLE — and their failure mode is a black tile (EXP-0147, confirmed on G17P by EXP-0178) — \`target: G16G + G17P\``

```markdown
> **Confirmed on the documentation target, and the hazard is sharper than "no fault".**
> `EXP-0178` §5 re-measured every value set above on **G17P**, over **four** carriers (two per
> instruction, differing in attachment count, spatial extent, the arithmetic consuming the read,
> and the presence of a colour store that reads no tilebuffer at all) and two gated runs —
> 9,428 cases per run, zero measurement failures, zero innocent victims. The M4 sets were frozen
> into the analysis **before** the runs as the hypothesis under test, and **every one transfers
> unchanged**: `read_en` = byte+6 bit 0, `rt_index` correct only at `0x00/0x01/0x80/0x81`
> (`_mrt`: `0x08/0x09/0x88/0x89`), the `dst` fault wall **exactly `0xf6`–`0xff`, contiguous,
> byte-identical on all four carriers**, and `_mrt.fmt`'s eight legal encodings with **104 of
> 256 values silently zeroing**.
>
> **The sharpening: across all 256 `rt_index` values on four carriers in two runs there is NOT A
> SINGLE FAULT.** Absence of a fault proves nothing about whether the read landed. A poisoned
> read-back, never the status code, must be the oracle — the same lesson the `device_store`
> unbound-slot result teaches in a second instruction family.
>
> **Still not emittable, and why.** `tile_read` remains blocked by `b2`, `b4`, `b6_hi`, `b7`,
> `tail`; `tile_read_mrt` by `b4`, `b6_hi`, `tail`. `b2`/`b4`/`b6_hi` never moved on either
> carrier over their full ranges in both runs, but they stay `untested` **as a limit of the
> carriers, not as "the field is inert"** — the dimension a `raw`-typed byte controls is
> unknown. `b7` *moves* (229 of 256) but does **not reproduce** (91.0% cross-run agreement, 23
> disagreeing values), and that instability reproduces `EXP-0164`'s M4 instability, making it a
> property of the field rather than of one machine's weather.
```

### A.6 — new subsection: the GPR-to-GPR move (rank 2)

*Insert immediately after `### ✅ MOV / select / uniform-move families — emitter rules
(EXP-0140)` (line 632), and delete or amend the line-657 sentence "Do not read this section as
closing `nir_op_mov`." which this result closes.*

```markdown
### ✅ `nir_op_mov` IS CLOSED — `n3_mov` moves one GPR to a DIFFERENT GPR (EXP-0174/EXP-0175) — `target: G17P`

Evidence label **`HW-VALIDATED`, generated with zero copied bytes.** This closes the gap
`docs/isa/register-move-and-liveness.md` records an external compiler engineer hitting head-on.

`n3_mov` is a **16-bit half-register move** with independent source-half and destination-half
selection:

```
byte0  = (dst << 4) | 0x3      dst = destination GPR, r0..r15
byte+1 = (S << 1) | hs         S   = source GPR — byte+1 bits 1..7, ALIASING PERIOD 64
                               hs  = byte+1 bit 0: 0 -> read source's LOW 16 bits
                                                   1 -> read source's HIGH 16 bits
byte+2   & 0x03 == 1 and & 0xC0 == 0  -> MOVE
         bit 3 (0x08) -> RELEASE the source half read
         bits 2, 4, 5 -> don't care
byte+3   & 0x1E == 0                  -> the write happens
         bit 0 = 0 -> write destination's LOW 16 bits
               = 1 -> write destination's HIGH 16 bits
         bits 5..7 -> don't care

    r[dst] halfword hd := r[S] halfword hs      THE OTHER HALF OF r[dst] IS PRESERVED
```

**A full 32-bit `r[i] = r[j]` is TWO instructions**, in either order:

```
    i3  (2j+1)  01  01        ; r[i].hi := r[j].hi     (r[i].lo preserved)
    i3  (2j+0)  01  00        ; r[i].lo := r[j].lo     (r[i].hi preserved)
```

Worked example from the raw: `23 13 01 01 | 23 12 01 00` puts r9's full `0x40200000` into r2.

**The evidence is generation, not decoding.** All **240 ordered `(dst, src)` pairs with
`dst != src`** were built from the rules above, in both instruction orders, in two independent
register plans, and scored against a full host-computed 16-register prediction: **840 generated
32-bit copies matched and 0 failed**, in each of two gated runs, plus **1680 generated
half-moves, 0 failed**. All 16 destinations are covered.

**The source survives unless you ask for it not to.** `byte+2` bit 3 releases the source, and
the release is **half-granular** (with `r3 = 0x4020002F`, releasing the low half leaves
`0x40200000`, releasing the high half leaves `0x0000002F`). **`byte+2 = 0x01` is the safe
canonical non-destructive move.**

- ⛔ **`db.json`'s operand model for this instruction is one bit off, and the failure is
  silent.** It declares `srcA_reg` = byte+1 bits 0..6 with byte+1 bit 7 a GPR/uniform selector.
  Measured over a dense `0..255` sweep in two register plans and two runs at 100.000% agreement:
  the source register is bits **1..7**, bit **0** is the source-half select, and bit 7 is source-
  register **bit 6**. An emitter writing the source register number into bits 0..6 reads register
  `S >> 1` with half-select `S & 1` — **the wrong register *and* the wrong half, with no fault.**
  All 128 `(v, v+128)` pairs produced byte-identical dumps because the register file **aliases
  with period 64** — the same period `EXP-0112` measured on the ALU, measured here rather than
  assumed — and **no uniform-file value was ever reached through byte+1.** (DEF-0174-1.)
- **`subform`/`companion` are an operation selector and a destination-half select**, not the
  zero-extend companion `db.json` describes. Over the complete 256 × 256 cross-product (65,536
  encodings, run three times): byte+2 `& 0x07 == 0` is the in-place narrow (`r[dst] &= 0xFFFF`,
  byte+1 inert — the `mov_zext16` member), `& 0x03 == 1` is the move, `& 0x07 == 3` behaves as
  XOR and `== 4` as OR of the byte+1/byte+3 operands, bit 3 is the source release, bits 6..7 must
  be 0; byte+3 bit 0 selects the destination half and **preserves** the other one. (DEF-0174-2.)

**Bounds to carry.** The move is **16-bit granular**, so every 32-bit copy costs two
instructions and a back end's parallel-copy/phi lowering must budget for that. Whether some
other `byte+2` value performs a **single 32-bit** move is **NOT established** — it is recorded
inside `n3_mov.subform`'s note as an observation, not as a verdict.
```

### A.7 — fragment-shader ISA (line 1070): `iter_at.loc` and `vary_store.hint6` (ranks 8, 15)

*Append after the existing `centroid/sample` bullet at line 1078.*

```markdown
- **`iter_at.loc` is bit 1 ALONE — two classes of exactly 128 values.** `bit1 = 0` → **centroid**,
  `bit1 = 1` → **per-sample**; **bit 0 and bits 2..7 are don't-care** (`0x81` behaves exactly as
  `0x01`, `0x83` exactly as `0x03`). This **refines** the enum `{1: centroid, 3: sample}`: the
  enum lists two legal values, the hardware has one selector bit and seven free bits, which is
  strictly more useful to an emitter — it now knows what it may leave alone. `HW-VALIDATED`,
  `target: G17P`, `EXP-0163` §2. Read back at probe pixel (8,8) of a 4-sample resolved target,
  a `centroid_perspective` varying is `3249.99976` for `loc & 2 == 0` and `3312.49976` for
  `loc & 2 != 0`, other channels untouched.

  > **The field has NO EFFECT below 2 samples, and that is why it read inert for a whole wave.**
  > `0 / 256` values move at `rasterSampleCount == 1`; `128 / 256` move at 4. At one sample the
  > centroid, the sample point and the pixel centre are the same point, so no location selector
  > can move anything: the field was structurally unreachable, not inert. **Two carriers
  > identical in the dimension a field controls are one carrier.**
  >
  > *Method bound, corrected by the experiment against its own earlier draft:* the two builds are
  > **not** byte-identical. The vertex stage is (166 B, same sha256); the fragment stage is 174 B
  > at one sample and 482 B at four. This is a controlled comparison of the same source under one
  > changed pipeline parameter, **not** a byte-for-byte splice pair, and a reviewer should read it
  > that way. What is held constant is what the claim rests on: both `loc` values the compiler
  > itself chooses are present on both sides.

- ⛔ **`vary_store.hint6` bit 4 makes the ENTIRE fragment output read 0.0.** Bit 4 alone, two
  classes of 128, measured on **7 arms across 5 carriers** with "exactly the values with bit 4
  set" moving on every one and both runs agreeing. Setting it loses **all four fragment output
  channels — the whole varying block, not just this component.** The compiler's own values
  `0x48`–`0x4d` all have it clear. `HW-VALIDATED`, `target: G17P`, `EXP-0163` §4.
```

### A.8 — texture/sample family (line 851): `tex_sample.coord` (rank 9) and the `tex_coord_setup` bits (rank 17)

```markdown
- **`tex_sample.coord` is an operand byte of the form `(reg << 1) | is32`** — the same source-byte
  convention `db.json` already documents for `falu2`, where bit 0 selects the 32-bit operand and
  the upper 7 bits are a register index. `HW-VALIDATED`, `target: G17P`, `EXP-0172` §2.1: 256
  values on each of four arms over two gated runs at **100% per-value cross-run agreement**
  (`EXP-0155` got 73–93% and reported the field unstable; the instability was a rule, not noise).

  > **On the fragment stage the register index ALIASES WITH PERIOD 16** — the live registers recur
  > at `reg`, `reg+16`, … `reg+112`. That is a **smaller period than the mod-64 ALU aliasing**
  > `EXP-0112` HW-validated, and it is why 32 of 256 values move rather than 4. The moving set is
  > reproduced with zero exceptions in both runs by
  > `moved ⟺ (v & 1) == 1 ∧ ((v >> 1) mod 16) ∈ {6, 8, 10, 14}`.
  >
  > **A coordinate pointed at a register the program does not keep live produces a silent
  > unchanged result, never a fault** — the Apple9 silent-failure signature again.
  >
  > *Scope:* filtered, implicit-LOD sampling was **deliberately excluded**. That its
  > derivative/LOD dependence caused `EXP-0155`'s instability is **supported** (the derivative-free
  > carriers are 100% reproducible) but **not demonstrated on a filtered arm**. One arm of four
  > has detection power; the other three move at zero of 256.

- **Four bytes `db.json` declares inert or reserved are LIVE, and none of the effects is small**
  (`HW-VALIDATED`, `target: G17P`, `EXP-0163` §4). Each rule is **form-specific** and must be read
  with its form:
  - **`tex_coord_setup.b6` bits 2, 3, 4, 5 must ALL be clear** — exactly the 16 values with
    `(v & 0x3c) == 0` reproduce the baseline; any of those bits set and the addressed varying
    reads `0.0`.
  - **`tex_coord_setup.idx` bit 7** (on the byte+4 == `0x42` form): clear it and that one varying
    reads `0.0` while the other three are untouched — the byte really is that store's destination
    selector, as `db.json`'s own `dst<<2` note implies. **Inert over all 256 values on the
    byte+4 == `0x00` form.**
  - **`tex_coord_setup.b8` bit 3** (plus bit 4 on two arms): same signature, zeroing exactly the
    one varying the occurrence addresses. Live only on the `0x42` form.
  - **`tex_coord_setup.b5`** bits 0, 1, 2, 4 (+3 on the `0x42` form): bit 0 set → the varying reads
    `0.0`; bit 3 with `b6` clear shifts the varying's **value** slightly (6.08333 → 6.0918 /
    6.10946) — an address/offset perturbation rather than a kill.

- **`simd_shuffle.rsv9` is NOT reserved.** On the `mode == 0x06` rotate / shuffle-and-fill form,
  bits 6 and 7 change the fill **result value** (31 → 116 → 256 across the combinations, bit 2
  giving a further distinct value) and bit 1 suppresses the stores that follow; 240–248 of 256
  values move. **Inert on the `0x00` / `0x04` / `0x05` forms.** `HW-VALIDATED`, `target: G17P`,
  `EXP-0163` §4.
```

---

## B. `docs/isa/memory-model.md`

### B.1 — `base_slot` section (line ~101), new subsection (rank 3)

```markdown
### ⛔ An unbound binding slot is SILENTLY DROPPED — the hardware will not tell you

`HW-VALIDATED`, `target: G17P`, `EXP-0169` §14. A gated pair on an exclusively idle machine
(7,046 cases each, counter dictionaries **byte-identical between runs**, 0 hangs, 0 victims, 0
baseline failures) swept `device_store.base_slot` across the **full** `0..255` range on two
structurally different carriers.

| outcome | values | which |
|---|---|---|
| store lands, state matches baseline | **2** | `0x00` and `0x80` |
| store does not happen at all — **`stray == []`**, output buffer untouched | **254** | everything else |

> **A `device_store` through an unbound binding slot is SILENTLY DROPPED. It does not fault, it
> does not hang, and it does not wedge the device.** Bit 7 of `base_slot` is a **don't-care** —
> `0x00` and `0x80` both select binding slot 0. The experiment's own pre-registered hazard
> warning ("the likeliest thing left to wedge the device") was **wrong, and that is the result**:
> `base_slot` produced **0 faults and 0 hangs** over all 256 values on both carriers in both runs.

**Driver consequence, load-bearing:** an out-of-range or unbound `base_slot` gives **no
diagnostic at all**, so binding-slot validity must be guaranteed **by construction in
userspace**. The same shape appears in a second instruction family — see `tile_read`'s
`rt_index`, where 256 values across four carriers produce not one fault.

**Read the "254" correctly.** It is conditional on those slots being **unbound** in this
carrier, which binds one buffer. It is **not** a claim that `base_slot` has only two legal
values; `EXP-0141`'s M4 census records slots 1..30 returning their own bound buffer when they
*are* bound.

> ⚠ **UNRESOLVED CROSS-TARGET CONTRADICTION, recorded rather than smoothed.**
> `docs/compiler-readiness.md` records from the M4 wave that *"slot 128 writes are DISCARDED;
> the 128..255 mirror is load-only"*, while `EXP-0169` measures `0x80` (= 128) as one of only
> **two** values that **do** store on G17P. The two runs differ in **target** *and* in **how many
> buffers were bound**, so the likely reconciliation is the binding population rather than a
> hardware divergence — but that is a **hypothesis**, not a measurement, and no experiment has
> tested it. An emitter should treat the low slot number as canonical and not rely on the bit-7
> mirror for stores on either target.
```

### B.2 — `device_store` operand rules, new bullets (rank 11)

```markdown
- ⛔ **Two exact `device_store` fault walls, zero counterexamples over all 256 values on both
  carriers in both runs** (`HW-VALIDATED`, `target: G17P`, `EXP-0169` §15):
  **`index_reg` faults iff `(index_reg & 0x60) == 0x60`** — 64 values, `0x60`–`0x7F` and
  `0xE0`–`0xFF`, with **bit 7 a don't-care** (the `0x00`–`0x7F` map repeats exactly in
  `0x80`–`0xFF`) — and **`extmode` faults iff `extmode >= 0xFC`** — 4 values. All 136 faults per
  run are these two walls. They are **faults, not hangs**: fault-contained, no reset, no wedge,
  with the sweep running through them at full speed. The mask rule subsumes and explains the
  earlier sampled M4 points (`96, 97, 100, 111, 120, 127 uniformly FAULT`).
- ⚠ **A `device_store` reading a data register outside the established register file has a
  STABLE destination and a NON-DETERMINISTIC payload.** `device_store.extmode` misses the 99%
  cross-run bar (97.3% / 92.6%) and stays `untested` — but it is characterised, not dismissed: by
  **outcome** the two runs agree **256 of 256 on both carriers**, every digest disagreement
  selects a data register **≥ 31** (`extmode = 2 × data_reg`; the smallest disagreeing value is
  `0x3F`), and over `extmode 0x00`–`0x1F` agreement is **100%**. The store still lands at the
  right word; only the value differs run to run. `target: G17P`, `EXP-0169` §17.
```

---

## C. `docs/compiler-readiness.md`

### C.1 — the `nir_op_mov` opening (line 62) — REPLACE (rank 2)

*The paragraph beginning "**The first thing that stops a general back end is `nir_op_mov`.**"
through the verbatim `validation.json` retraction quote, and the two paragraphs after it, are
all now false. Replacement:*

```markdown
**`nir_op_mov` is CLOSED.** `EXP-0174` found and **generated** the register-to-register move that
`EXP-0087` → `EXP-0090` → `EXP-0101` → `EXP-0113` → `EXP-0140` had concluded did not exist:
`n3_mov` moves one GPR to a **different** GPR. All **240 ordered `(dst, src)` pairs with
`dst != src`** were generated from the descriptor's bit geometry in both instruction orders and
two independent register plans; of the 960 dispatched per run, **840 were decidable and all 840
matched a full host-computed 16-register prediction, with 0 failures** (the other 120 land on a
plan's blind or pad-masked slot and are covered by the other plan). Plus **1680 generated
half-moves matched, 0 failed.** Two gated runs, G17P. The encoding is in `docs/isa/README.md` (`n3_mov`).

The retracted `validation.json` note — *"AS OF 2026-08-28 NO VALIDATED GPR-TO-GPR MOVE EXISTS ON
APPLE9"* — was correct **about the `reg_move_*` family**, which really is one instruction with a
single 8-bit `byte+2` field and really is not a general move. It was wrong about the ISA. The
instruction was in the DB the whole time under a different descriptor, which is the same shape as
`fspecial` and `imad`: **the corpus contained the answer and the descriptor's field model hid
it.**

**Three bounds an implementer must budget for.** (1) The move is **16-bit granular**, so every
32-bit copy is **two instructions** — phi lowering, parallel-copy breaking and spill reload all
pay double. (2) `db.json`'s operand model for `n3_mov` is **one bit off** and fails silently (see
`docs/isa/README.md`); use bits 1..7 for the source register and treat bit 0 as the source-half
select. (3) Whether any `byte+2` value performs a **single 32-bit** move is **not established**.

`docs/isa/register-move-and-liveness.md` records that this repository received a report from an
external compiler engineer building a NIR→Apple9 back end who *"could not get a basic
register-to-register move to work."* That report is now answered.
```

*and in the NIR-construct table (line 91):*

```markdown
| 1 | `nir_op_mov` (GPR→GPR) | **CLOSED** | `n3_mov`, generated end-to-end on G17P (`EXP-0174`/`EXP-0175`); 16-bit granular, so a 32-bit copy is two instructions |
```

*and blocker row 1 of the table at line 1291 should be struck, with the note that `EXP-0112`'s
generator excluded `reg_move` deliberately and can now be extended.*

### C.2 — the `get_sr` block (line ~535) — AMEND (rank 6)

*Replace the `sr_sel` and `form` lines inside the code block:*

```
sr_sel     0x00..0xFF EXHAUSTIVE, 256 values x 2 runs.
           ** STAGE-DEPENDENT — the M4 census below was measured on a COMPUTE carrier. **
           COMPUTE  (M4 EXP-0092 and G17P EXP-0178, both): zero faults, zero hangs.
           VERTEX   (G17P EXP-0178): every value with bit 7 CLEAR faults the command buffer
                    -- all 128 values 0x00-0x7F, contiguous, zero counterexamples, both runs.
           FRAGMENT (G17P EXP-0178): no faults.
           0x80-0xFF reaches the special-register file (16 named, ~106 aliasing, 4 unclassified
           constants, 2 period-4 structured) and NEVER faults in any stage.
           0x00-0x7F is a distinct region: in compute it writes ONE lane of 64 and leaves the
           other 63 untouched (the whole program retires one invocation, not just the SR read);
           in vertex it faults. An emitter must never emit a bit-7-clear selector.
form       0, 1 -- inert on eight EXP-0172 arms and on G17P compute and fragment carriers;
           on the G17P VERTEX carrier form=0 MOVES the observation and form=1 does not,
           identically in both runs. Ruled `isolated-byte-diff`, NOT `hardware-run`:
           the movement is one value on one of three carriers and NOBODY HAS IDENTIFIED
           WHAT form=0 DOES. (EXP-0172 decline, EXP-0178 referral, orchestrator ruling.)
```

### C.3 — the `half_alu_ext8` bullet (line 560) — REPLACE (rank 5)

*The current bullet carries three claims that `EXP-0180` refuted. It traces to `EXP-M4-14`,
which `EXP-0164` established has **no `raw/` tree at all**.*

```markdown
- **`half_alu_ext8`** — `opsel` 6 selects the fma form (`byte+2 = 0x1e`), **but `opsel` is a
  length input and only 3 of its 8 values keep the 8-byte framing**. `dst`, `srcA`, `b5`, `rsv6`,
  `opflags`, `b7_lo`, `saturate`, `b7_mid` are `hardware-run` on G17P at full range
  (`EXP-0180`, gated pair, 16,735 cases each, 100.0000% cross-run agreement, zero
  disagreements). **Three previously documented semantic claims are REFUTED** — all three traced
  to `EXP-M4-14`, which has no `raw/` tree:
  - ⛔ **`saturate` is NOT a clamp.** On the high carrier (result `7.0586`) setting it yields
    **`2.84375`** — the third operand's value, not `1.0` — and on the low carrier (result
    `0.125`, where a clamp *must* be a no-op) it changes the result to **`0.46875`**, again the
    third operand. **A clamp cannot change a sub-unit result.** Bit 57 suppresses the multiply
    term. The two-carrier magnitude difference was designed to separate exactly this.
  - ⛔ **`op_valid_marker`'s bit-63 claim is false.** 0 of 2 values moved, two carriers, three
    arms, both runs. The op **is** nullable from byte+7 — but by **`b7_mid` bit 2 = instruction
    bit 60** (`b7_mid ∈ {4,5,6,7}` leaves the destination untouched), **not bit 63**. The bit is
    real; the committed bit number is wrong.
  - ⛔ **`rsv6` is not reserved and not inert.** LIVE at **252/256** and **248/256** on two
    carriers, with **13 distinct architectural results**. Its entire prior evidence was one
    clause of an `ext8.srcA` claim that documents a *different byte*.
  - **`srcB_desc`'s "`0x01` required" is a LENGTH requirement, not an operand one.** `byte+4 & 3`
    is the length selector; only **64 of 256** values keep the 8-byte framing, and inside that
    subset a same-length step to a different half-register **does not move on any arm** — byte+4
    has no detectable operand role.

  **Bound, and it is load-bearing:** the **add+saturate instance** had **no working carrier**.
  Its arm (`E8_ADD`) was **rejected for no detection power** — 0 of 3 falsifiers and 0 of 4 ladder
  steps, on both carriers in both runs, because its base writes nothing at all. The `b5` and
  `srcB_desc` claims are explicitly about that instance, so they are **refuted only in the fma
  instance**, and the record says so rather than generalising.
```

### C.4 — store `base_slot` / `index_reg` (line 255) — AMEND (ranks 3, 11)

```markdown
Store `base_slot`: probed on **M4** at 0, 3, 31, 32, 63, 127, 128, 255 — **slot 128 writes are
DISCARDED**; the 128..255 mirror is load-only. ⚠ **This does not reproduce on G17P**, where
`EXP-0169` measures `0x00` and `0x80` as the only two values that store at all and bit 7 as a
don't-care. The two carriers differ in target **and** in how many buffers are bound, so the
likely reconciliation is binding population rather than hardware — but that is untested. Treat
the low slot number as canonical on both targets. **And on either target an unbound slot is
SILENTLY DROPPED: 0 faults, 0 hangs, `stray == []`, no diagnostic** (`EXP-0169` §14, G17P,
256/256 on two carriers in both runs).

Store `index_reg`: on M4, r0..r95 round-trip; 96, 97, 100, 111, 120, 127 uniformly FAULT; **r112
is genuinely nondeterministic**. On **G17P** the rule is exact and subsumes those points:
**`fault ⟺ (index_reg & 0x60) == 0x60`** — 64 values, `0x60`–`0x7F` and `0xE0`–`0xFF`, bit 7 a
don't-care, zero counterexamples over 256/256 on two carriers in both runs (`EXP-0169` §15).
Also on G17P: **`extmode` faults iff `extmode >= 0xFC`.**
```

### C.5 — the field-status tables (lines 755, 820–826) — AMEND (ranks 8, 9, 10)

```markdown
| **`tex_sample`** | **`coord` is CLOSED** — `hardware-run` on G17P, `(reg << 1) \| is32`, fragment-stage register aliasing at **period 16** (`EXP-0172` §2.1). Still `untested`: `comp_flags`, `result_sel`, `tex_type`, `samp_extra`. |
| **`frag_color_pack`** | `dst` is `hardware-run` on G17P — 191 of 195 values move on all 8 arms, all 8 bits live — with an **illegal region `0xC0`–`0xFF` that HANGS**, so the encodable range is **192, not 256** (`EXP-0168` §8.1). Still `untested`: `src_desc`, `mode`, `comp_off`. `corpus-correlation`: `fmt_class`, `val`. |
| **`iter_at`** | `loc` is `hardware-run` on G17P — **bit 1 alone**, centroid vs per-sample, and **inert below 2 samples** (`EXP-0163` §2). `grp` stays `untested` **deliberately**: `EXP-0168` had a reproducible 3/3 observation and declined to promote it because that arm's ladder failed on both carriers. Still `untested`: `lead`, `dst`, `c4`, `b5`. |
| **`vary_store`** (VS output) | `hint6` is `hardware-run` on G17P — **bit 4 alone; setting it makes all four fragment output channels read 0.0** (`EXP-0163` §4). Still `untested`: `hint1`, `b7`; `corpus-correlation`: `hint2`, `out_slot_hi`; `single-template-inference`: `b5_tag`. |
```

### C.6 — control-flow field table (line ~733) — AMEND (ranks 13, 20)

```markdown
| `pop_reconverge` | **REQUIRED after a `call`** — omit it and the command buffer faults, with or without the frame marker (`EXP-0179` arm M, both carriers, both runs). `scope_kind = 0x02` closes a call; `0x01` does **not** (the callee runs and never returns), and `scope_kind = 0` remains the single fatal value. The mask **bank** is a don't-care (`0x04`/`0x24`/`0x54`). |
| `ret.scoreboard` | **DECLINED — and this is the strongest decline in the corpus, not another inconclusive.** Three earlier experiments declined it because they could not build an ordering observable. `EXP-0179` arm O **built one** out of `device_load` asynchrony, **proved it fires** as a clean monotone step (C1_flat lands from filler 10, C2_nested from 6, byte-identical in both runs), and the field **still did not move it** — exactly one distinct threshold per arm across all sixteen scoreboard values. Stays `corpus-correlation`, **bounded to a leaf return with one outstanding async load**. Fourth experiment to decline the family. |
```

---

## D. `docs/isa/encoding-tables.md`

### D.1 — the `get_sr.sr_sel` enum (line 531) (rank 16)

*The prose docs carry the `0xa8` caveat; the machine-readable enum an implementer would key off
does not. Amend the `0xa8` entry in place:*

```
`0xa8`=threadgroups_per_grid.x ⚠ SEE NOTE — a BARE `get_sr 0xa8` returns
threads_per_threadgroup.x, NOT the threadgroup count. The builtin is
`get_sr 0xa8` + a `device_load` + a divide. `0xa9`/`0xaa` ARE direct and correct,
so the enum is wrong on exactly this one entry. HW-VALIDATED on three targets:
RT-7 (A18), EXP-0092 (M4), EXP-0178 §3.4 (G17P, reads 64 = threads_per_threadgroup.x
in a single-threadgroup dispatch while 0xa9/0xaa read 1 and match).
```

---

## E. `docs/P0-P1-CLOSURE.md`

### E.1 — P0.8 ranked blockers (line 89) — three bullets are stale (defect D04)

*Blockers (1), (2) and (5) are closed or substantially advanced. Suggested replacement text:*

```markdown
**RANKED BLOCKERS — three of the five original blockers CLOSED on 2026-08-30, all on G17P.**
(1) ~~`get_sr.sr_sel` untested on G17P~~ **CLOSED:** `sr_sel`, `dp_width` and `dp_marker` are
`hardware-run` on G17P over three stage carriers (`EXP-0178`), and `get_sr` is EMITTABLE — with
the new stage rule that a bit-7-clear selector faults in vertex. (2) ~~no call can be emitted~~
**CLOSED:** `EXP-0179` generated 192 distinct calls with 384/384 correct and moved
`call.{b3,b5,b6,tail}` from `tokenization-only` to `hardware-run`; the emitter contract adds a
constraint nobody had — **`pop_reconverge` after a call is REQUIRED, the frame marker is
OPTIONAL**. `ret.scoreboard` remains declined, now on a control that **fired**. (3)
`vary_store.{hint1,b5_tag}` — **partly answered**: `hint6` is `hardware-run` (`EXP-0163`).
(4) `iter.b9` / `iter_at.grp` — **partly answered**: `iter_at.loc` is `hardware-run` and is bit 1
alone (`EXP-0163`); `grp` was deliberately not promoted. (5) ~~`tile_read`/`tile_read_mrt`
measured only on M4~~ **CLOSED as a measurement:** re-measured on G17P over four carriers with
every M4 value set transferring unchanged (`EXP-0178` §5) — though **neither instruction is
emittable**, `tile_read` still blocked by `b2`/`b4`/`b6_hi`/`b7`/`tail` and `tile_read_mrt` by
`b4`/`b6_hi`/`tail`.
```

### E.2 — board header (lines 4–8) (defect D03)

The header still reads *"using the local M4/G16G as the **sole test target**"* and *"the A18
Pro/G17P is hands-off"*. That directive was **lifted by the user on 2026-08-28** and both
`CLAUDE.md` and `CODEX.md` record the replacement. The board's own P0.6 and P0.8 rows are
written against G17P, so the header currently contradicts its own table.

---

## F. Not drafted, and why

- **`db.json` does not decode the fragment colour-store variant `byte+1 == 0x86`** and mis-reads
  it as a 14-byte compute `device_store`, silently omitting that form from every occurrence census
  ever run on the descriptor (`EXP-0163` §4b, with a proposed match fix). This is a
  **descriptor/tooling defect**, not a hardware capability, and `db.json` has an owner. Flagged,
  not drafted.
- **`EXP-0168`'s r15 finding** ("a write whose 4-bit destination nibble is 15 is discarded; r15
  is a bit bucket") is **self-retracted** and independently refuted by `EXP-0174` §5 (r15 holds
  its seed and all 15 generated 32-bit copies into it pass). It never reached `docs/`, and it
  must not. `EXP-0168`'s separate `regs[0] = 0` anomaly is **not** reproduced by `EXP-0174` and
  remains an open question about that experiment, not a finding of either.
- **`half_alu_fma12.opsel`, `.ext` and `falu2_uni.uni_mode` as "fields"** — each has exactly one
  legal value or is an instruction-identity bit, so each belongs in `match`. Corpus bookkeeping,
  already actioned in `db.json` by their owners.
