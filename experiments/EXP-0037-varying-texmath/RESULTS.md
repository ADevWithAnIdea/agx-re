# EXP-0037 Results — varying-store `0x57` + texture coord/interp math (`0x2e/0x92/0x26`, `0xb0`)

Clean-room: **OWN-SHADER** (+ PUBLIC ISA DB). Every byte is the compiled form of MSL we wrote;
splice-and-observe on the real A18 Pro via `agxrender` (`PIPELINE_SOURCE archive` proves the
spliced code ran). No GPU wedge / reboot. HW-validated = a dispatch/render confirmed it; inferred
= byte-diff + tokenize-to-0-leftover with byte-exact re-serialization.

---

## 1. Vertex/mesh varying-store — the op is **`0x57`** (8 bytes) [HW-VALIDATED]

The traditional **vertex stage** writes `[[position]]` + user varyings to the UVS / vertex-parameter
buffer (the coefficients the FS then interpolates via the `0x2f` `iter` op, EXP-0029) with a
dedicated **8-byte memory-family store, byte0 `0x57`** (low-nibble 7 — the store family alongside
`0x67` load / `0xe7` store / `0xd7` tex-write). Encoding:

```
57 h1 h2 SRC SLOT 40 h6 00
```

| byte | field | meaning | status |
|---|---|---|---|
| +0 | opcode | `0x57` | ✅ |
| +1 | hint1 | source last-use/liveness (splice-inert; `0x06` varying, one-hot hi-nibble for position) | ✅ inert |
| +2 | hint2 | `0x54` base + source-mod low bits (`0x55/0x56`; splice-inert) | ✅ inert |
| +3 | **src** | **source GPR** (the scalar value emitted) | ✅ HW |
| +4 | **out_slot** | **destination output slot**, `index<<5` | ✅ HW |
| +5 | — | `0x40` (const observed) | ✅ |
| +6 | hint6 | liveness/cache hint (splice-inert) | ✅ inert |
| +7 | — | `0x00` | ✅ |

One op per **scalar component** (a `float4` varying = 4 stores). **`[[position]].xyzw` occupy
output slots 0-3** (byte+4 `0x00/0x20/0x40/0x60`); **user varyings follow at slots 4+** (`0x80/…`).

**Position vs varying is NOT a distinct opcode — it is the output-slot RANGE.** HW-proven
(`raw/hw_validations.txt §1`, 4×4 target, `vary.metal`, va = RGB gradient, FS reads va):

- **byte+4 = output slot.** Redirecting va.z's store slot `0xc0 → 0x80` (= va.x's slot) makes the
  FS **red** channel show va.z's **blue** gradient (`R: 0.498→0.149 … 0.800→0.149`), and va.z's own
  slot goes stale (B=1.0). Setting a varying store's byte+4 to `0x00` aliases position slot 0 →
  the triangle degenerates (mostly black). **Splice-proof of the output-slot field.**
- **byte+3 = source register.** `store4.b3 0x08 → 0x00` zeroes exactly the **red** channel (that
  store feeds va.x); `→ 0x0c` makes red take va.z's value. **Splice-proof of the source field.**
- **position stores drive geometry.** Corrupting a position store's source (`byte+3 → 0x00`) or
  moving a position component out of slots 0-3 (`byte+4 → 0x80`) turns the **entire output black** —
  a degenerate triangle — while varying-store splices only change colour. **Position-vs-varying
  proven.**
- **byte+6 is inert** (→`0x00` on all 4 varying stores: no change) — a last-use hint, not the source.

**`0x05` / `0x06` are NOT a varying-store family** (they were lumped in by EXP-0008/EXP-0036 from
early flagging): **`0x05` = `psel`** (branchless select, already in the DB) — in the VS it *computes*
the per-vertex varying values that `0x57` then stores; **`0x06`** is not a distinct leader — it is the
`byte+1` sub-op of the already-decoded `0f06` reconverge and resync noise adjacent to the **mesh**
`0xe7` emit stores (mesh emits via `0xe7`, EXP-0030, not `0x57`). Confirmed by fully tokenizing the
VS + mesh `_agc.main` (`raw/vertex_mains.txt`): the only genuine varying/position store leader is
`0x57`.

Length `0x57` → 8 tokenizes all VS stores with **0 leftover** and re-serializes byte-exact.

---

## 2. Texture coordinate / interpolation math and the `0xb0` fix

### `0xb0` / `0x90` = the 10-byte sampler op — a **gating fix**, not a new length [HW-context]

`0xb0`/`0x90` is the **second half of the EXP-0016 14-byte sample bundle** (4-byte companion +
10-byte sampler op). The census mis-tokenized it because the `tex_sample` companion gate required
`byte+1 == 0x80` **exactly**, so it missed the **chained-companion** forms that precede the 2nd..Nth
sample op in multi-sample kernels:

```
1st sample:  05 80 0c CC  b0 ...        (byte+1 = 0x80, matched)
chained:     25 84 0c CC  b0 ...        (byte+1 = 0x84  ← MISSED → resync lands on the 0xb0 op)
             45 82 0c CC  30 ...        (byte+1 = 0x82  ← MISSED)
```

**Fix: widen the companion gate to `(byte+1 & 0xf0) == 0x80`** (high-nibble 8; the low bits
`0x02/0x04` are the chained / coordinate-source flags). That makes the 14-byte bundle absorb the
`0xb0`/`0x90` op again, removing the census's standalone `0xb0/0x90/0x25/0x45` undecoded leaders.
(A tightly-gated standalone `0x30/0x90/0xb0 → 10` length is added as a resync fallback.)

**HW-confirmed bundle boundary** (`raw/hw_validations.txt §2`, `texvary.metal`, solid red texture):
splicing **inside** the bundle behaves as the bundle predicts — op+4 tex-slot index-bit `0x01→0x81`
→ **contained CMDBUF fault** (unbound tex1, matches EXP-0016), companion result-desc `0xb8→0xa0` →
**pixel changes** (`0.784,0.157,0.078 → 0.784,1.000,0.000,0.000`). Both prove the 14-byte
companion+sampler-op boundary. The sampler-op **semantics** were already HW-validated in EXP-0016;
EXP-0037 fixes the **tokenizer gating**.

### `0x2e` / `0x26` (and most census `0x92`) = float fused-mul **coordinate math** [inferred]

These are **not** a texture-only opcode — they are float-ALU fused multiply / mul-add ops that also
fill the **vertex matrix-vector product** (`mvp*pos`). The census undecoded them because the
float-ALU length rule (`8 if byte+2 bit1 else 6`) **mis-lengths the 6-byte fused-mul ops** whose
op-select `byte+2` is `0x26`/`0x2e` (both have bit1 set): it consumed 2 extra bytes, desynced, and
resynced onto operand bytes (`a0`, `26`, `2e`, `92`, `23`…) reported as bogus leaders.

**Fix (float-ALU op-select length, low-nibble 9):** `byte+2 ∈ {0x18,0x38} → 4` (compact
accumulate); `0x1e → 8` (fma); `{0x26,0x2e} → 8 if (byte+4 & 0x02) else 6` (fused mul / mul-add);
else `8 if byte+2 bit1 else 6`. Plus two coordinate-setup leader rules: **low-nibble-`b` with
`byte+2 ∈ {0x27,0x2f}` → 10** (texel-address / LOD / gather-offset setup, tail `.. 00 42 00 00 0X
00 00`) and **byte0 `0x2e`/`0x3e` (low-nibble e) → 10** (coordinate fused-mul leader form).

### Tokenization result (byte coverage, current rule → EXP-0037 fixes; all byte-exact)

| kernel | bytes | base | new |
|---|---|---|---|
| k_tex_gather | 162 | 74% | **100%** |
| k_tex_compare | 126 | 78% | **100%** |
| k_tex_rw / k_tex_sample | 100/58 | 100% | 100% |
| k_tex_lod | 210 | 70% | **99%** |
| k_tex_msaa | 124 | 71% | **97%** |
| k_tex_array_cube | 256 | 80% | **92%** |
| k_tex_atomic | 988 | 71% | 74% |
| v_basic vertex (matrix) | 258 | 74% | **97%** |
| r_tex vertex | 308 | 64% | **97%** |
| r_tex / r_deriv fragment | 214/266 | 97/94% | 97/95% |
| **TOTAL** | **3238** | **75%** | **89%** |

Every tokenized stream **re-serializes byte-exact**, and there are **zero regressions** on 6 core
compute kernels checked (k_matrix 95→100, k_float_arith 98→100, k_int_arith/k_subgroup_shuffle/
k_atomics unchanged, k_transcend 70→75) — total over all 19 stage programs 80% → 89%
(`raw/tokenization_report.txt`). The one guard that needed tightening: the `0x2e/0x3e` coordinate
leader rule is gated on `byte+2 == 0x23` so it never fires on bare low-nibble-e resync bytes.

---

## 3. Status, HW-validated vs inferred, recommended next

**HW-validated (splice/render on the A18 Pro):**
- `0x57` varying store — opcode/length, byte+3 = source, byte+4 = output slot, position = slots
  0-3, position-vs-varying, byte+6 inert. (`§1`)
- The 14-byte sample-bundle boundary + companion result-descriptor (`§2`) — grounds the `0xb0`
  gating fix on this harness; sampler-op field semantics from EXP-0016.

**Inferred (byte-diff + byte-exact clean tokenization):**
- `0x2e/0x26` fused-mul coordinate ops and the low-nibble-`b` coord/LOD setup ops — length rules
  proven by re-serialization; field bit layouts and the fused-mul semantics are byte-diff-inferred
  (a coordinate splice needs a non-uniform bound texture, which `agxrender`'s solid `--tex-fill`
  cannot provide).

**They now tokenize:** `0x57`, `0xb0/0x90`, `0x2e/0x26/0x92`, and the low-nibble-`b`/`e` coordinate
ops are all length-known with the fixes in `new_descriptors.json`; a re-run census over this corpus
goes 75% → 89% overall and 97-100% on the core texture/vertex kernels.

**Recommended next:**
1. Decode the VS per-vertex select family (`0x40/0x1a/0x21`) that feeds the `0x57` stores (the
   remaining vary/vertex residue; not a store — separate group).
2. Bit-decode the coordinate-math ALU (`coord_madf`/`tex_coord_setup`) with a multi-texel texture
   harness (EXP-0016 `texr.m`) so a coordinate splice is observable.
3. Close `k_tex_atomic`'s texel-address atomic-math residue (densest remaining).

## Clean-room status
Clean. Everything inspected/spliced is our own compiled MSL; tools are ours (`shdump`, `agxparse`,
`agxrender`, `vsplice`), the only third-party code is the public ISA DB applied to our own bytes.
`raw/` holds only hex/text — the `.bin` archives stay on the device.
