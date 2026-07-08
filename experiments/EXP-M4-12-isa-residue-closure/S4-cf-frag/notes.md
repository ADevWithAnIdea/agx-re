# S4-cf-frag — control-flow / atomics / subgroup / fragment residue closure

Provenance for every byte below: **EXP-M4-12 OWN-SHADER isolated compile (M4)**.
Method: compile a minimal MSL kernel/render shader we wrote ourselves, extract the
AGX bytes (`agxparse.py --extract-hex [--stage fragment]`), and tokenize so the
offending op appears cleanly bracketed by known-length ops (the anchored gap gives
its true length). No Apple binary was disassembled. For the r_blend tile/unpack ops
we document only the per-instruction ENCODING/length — NOT the blend arithmetic
sequence (clean-room rule 5).

Isolated sources: `work/*.metal`. Patched-DB validation copy: `work/isadb_local.py`
(NOT the shared DB — main agent integrates serially). Evidence tokenizations were
produced with `work/tok_patched.py`.

All 12 target residues CLOSE. Whole-corpus validation with the combined patch:
net undecoded bytes 184 → 136, **no kernel gained undecoded bytes**, all 8 target
shaders tokenize cleanly to `stop`. One benign boundary-shift remains inside a
pre-existing S2 (k_tex_array_cube) resync region — see caveat at end.

---

## 1. k_cf_loop @0x44  `a0 00 00 00`  (4 bytes)
- Root cause: genuine 4-byte op, previously LEN_UNKNOWN. Appears once at the loop
  header of EVERY for-loop (reproduced in `cf_for.metal` @0x44 and `cf_break.metal`
  @0x36), bracketed: get_sr `5c a0 11 06` (4B) BEFORE, iadd2 `9f 11 54 ...` (10B)
  AFTER — anchored gap = exactly 4.
- Family/label: loop-header compact init op (byte0 0xa0, low-nibble-0 group; all-zero
  payload). Not caught by any prior rule.
- Length: **4**. Fields: operands not bit-decoded (payload all-zero).
- Predicate:
```python
if b0 == 0xa0 and off + 2 < len(buf) and buf[off + 1] == 0x00 and buf[off + 2] == 0x00:
    return 4                       # EXP-M4-12: loop-header compact init op
```

## 2. k_cf_loop @0x124  `06 02`  (2 bytes)
- Root cause: genuine 2-byte compact op (select/predicate helper) emitted right
  before the final `device_store`. In `cf_while.metal` the analogous slot is
  `06 02` (2B) + `80 06` (2B), where `80 06` is a sibling of the DOCUMENTED 2-byte
  compact move `80 04`; that forces `06 02` to be exactly 2 bytes. In k_cf_loop the
  preceding min/max-select `12 03 0f e4 81 04` is a solid 6-byte op (byte+2 0x0f is a
  valid <=0x3f op-select), so only 2 bytes remain before the store.
- Family/label: compact select/predicate helper (byte0 0x06, low-nibble 6; sibling of
  the 4-byte 0x05/0x16 selects). Fields: operands not bit-decoded.
- Length: **2**.
- Predicate (tightly gated so it never fires on `06 02` bytes reached via an OTHER
  kernel's desync — e.g. k_transcend @0x6a where byte+2 = 0x72, not 0xe7):
```python
if b0 == 0x06 and off + 2 < len(buf) and buf[off + 1] == 0x02 and buf[off + 2] == 0xe7:
    return 2                       # EXP-M4-12: compact select/predicate helper (pre-store)
```

## 3. k_atomics @0x168  `02 00`  &  4. k_subgroup_shuffle @0x7c  `02 00`  (2 bytes each)
- Root cause: the SAME genuine 2-byte compact op in the low-nibble-2 icmp/select
  family with byte+1==0x00. Bracketed cleanly in BOTH:
  - k_atomics: scoreboard_fence `07 22 00 00` (4B, solid) BEFORE, frame_marker_compact
    `60 00` (2B) AFTER → gap = 2.
  - k_subgroup_shuffle: simd_shuffle `47 06 54 ...` (10B) BEFORE, iadd2 `9f 01 54 ...`
    (10B) AFTER → gap = 2 (a 4-byte read would mis-start the iadd2 at `54 00`).
  This is the atomic compare_exchange predication / shuffle-rotate result helper.
- Family/label: compact 2-byte select/predicate (low-nibble-2). Fields: not bit-decoded.
- Length: **2**. Distinguished from the real 6-byte iminmax (which always carries a
  <=0x3f op-select in byte+2) by byte+1==0x00 AND byte+2 > 0x3f.
- Predicate (place inside the existing `(b0 & 0x0f) == 0x02` block, after b1..b4 read):
```python
if b0 == 0x02 and b1 == 0x00 and not (0 <= b2 <= 0x3f):
    return 2                       # EXP-M4-12: compact 2-byte select/predicate helper
```

## 5. k_atomics_tg @0x80  `00 00 44 05 00 40 00 00`  (was flagged 8 bytes)
- Root cause: NOT a standalone op — it is the tail of a downstream cascade caused by
  ONE upstream mis-length. The threadgroup atomic load/store op `67 03 54 ...`
  (byte0 0x67, byte+1==0x03, byte+2==0x54) is **12 bytes**, but the generic
  `0x67/0xe7 -> 14` default over-read it by 2 bytes, swallowing the following
  `0f 06` (pop_reconverge) and desyncing everything through the barrier + result
  load. Reconstructed from solid anchors (barrier `07 04 54 61 09 00`; result
  device_load `67 02 54 ...`; store `e7 00 56 ...`): 0x62 op MUST end at 0x6e.
  Reproduced exactly in `tg_load.metal` @0x62. Fixing 0x62→12 cascades to fully clean
  tokenization; the `00 00 44 05 00 40 00 00` bytes become part of the 14-byte
  result-load `67 02 54 02 00 00 00 00 00 00 44 05 00 40` at 0x7a.
- Family/label: threadgroup atomic load/store (0x67 memory family, byte+1 0x03).
- Length of the CULPRIT op: **12** (byte+1==0x03, byte+2==0x54). Operands not bit-decoded.
- Predicate (place BEFORE the generic `if b0 in (0x67, 0xe7): return 14`):
```python
if b0 == 0x67 and (buf[off+1] if off+1 < len(buf) else -1) == 0x03 \
        and (buf[off+2] if off+2 < len(buf) else -1) == 0x54:
    return 12                      # EXP-M4-12: threadgroup atomic load/store
```

## 6. r_cent_f @0x4  `01 00 00 00`  (4 bytes)
- Root cause: genuine 4-byte fragment preamble, UNIQUE to centroid interpolation.
  Isolated `f_cent` (centroid) reproduces it @0x4; `f_deriv1/f_tex1/f_noblend`
  (perspective) do NOT emit it. Bracketed: fragment get_sr `04 c2 11 06` (4B) BEFORE,
  interpolate-at setup `af 14 54 ... 0a 01` (iter_at, 8B) AFTER → gap = 4. It pairs
  with the centroid `iter_at` barycentric setup.
- Family/label: fragment centroid interpolation setup / barycentric-mode preamble
  (byte0 0x01, low-nibble-1). Fields: not bit-decoded (all-zero payload).
- Length: **4**.
- Predicate (byte+3==0x00 gate excludes the k_half_arith `01 00 00 10` bytes that a
  pre-existing S3 0x10-half-ALU desync can land on):
```python
if b0 == 0x01 and off + 3 < len(buf) and buf[off + 1] == 0x00 \
        and buf[off + 2] == 0x00 and buf[off + 3] == 0x00:
    return 4                       # EXP-M4-12: fragment centroid interp setup preamble
```

## 7. r_deriv_f @0x9c  `00 00`   &   8. r_tex_f @0x96  `45 c2`
- Root cause: BOTH are tails of a desync caused by a **compact 4-byte float
  accumulate op-select missing from the DB set**:
  - r_deriv_f: `89 81 30 11` (byte+2 **0x30**) was lengthed 12 (fma, byte+4 0x37),
    swallowing the following tex_deriv `37 0f 54 ... 90 40 00 00` and leaving `00 00`.
    With 0x30→4, tex_deriv tokenizes at 0x94 and `00 00` vanishes. (isolated `f_derivf`)
  - r_tex_f: `19 03 39 11` (byte+2 **0x39**) was lengthed 12 (fma, byte+4 0x97),
    swallowing frag_color_pack `97 04 54 ... 45 c2` and leaving `45 c2` (the pack's
    tail). With 0x39→4, frag_color_pack tokenizes at 0x8e and `45 c2` vanishes. Also
    fixes `19 05 39 03` / `29 07 39 09` at 0xa8. (isolated `f_tex1` = clean; the `*in.col`
    multiply produces the 0x39 ops.)
- Family/label: compact 4-byte float accumulate (low-nibble-9 float ALU, byte+2 0x30/
  0x39 — the bit0-siblings of the already-present 0x31/0x38). Fields: not bit-decoded.
- Length: **4** (both). Anchored: each op is exactly 4 bytes between its neighbours.
- Predicate (extend the existing compact-accumulate set):
```python
if b2 in (0x18, 0x38, 0x19, 0x21, 0x31, 0x30, 0x39):   # +0x30,+0x39 (EXP-M4-12)
    return 4
```
- Validated globally-safe (each addition, individually AND combined with the 0x3e fix
  below, adds zero new gaps across the whole corpus).

## 9-12. r_blend_f @0x40, @0x52, @0xbe (`54 05`), @0xb4 (`80 0a`)
Two distinct root causes — NEITHER is a tilebuffer LOAD.

### (a) @0x40 `54 14 03 02 00 02 10 00`, @0x52 `54 12 03 04 00 02 10 00`
- Root cause: these are the **tails of `2f 05 54 ...` ITER ops** (varying
  interpolation of `in.col`), NOT tile loads. The real culprit is the **fragment
  tilebuffer-color UNPACK op `17 04 56/54 ... 14 ea`**, which was lengthed 10 (the
  COMPUTE simd_ballot rule) instead of 8, swallowing the `2f 05` head of the next iter
  and orphaning `54 14 ...`. Proof: isolated `f_noblend` (identical interpolation but
  NO `[[color(0)]]`) emits NO 0x17 op and NO `54 ..` residue → the 0x17 op is tied to
  the tilebuffer color (`dst`), and the actual programmable-blend framebuffer read is
  the separate `67 0e 54 ...` tile_read at 0xc. With 0x17→8: `17 04 56 ... 14 ea` (8B)
  then iter `2f 05 54 14 03 02 00 02 10 00` (10B) — clean.
- Family/label: FRAGMENT tilebuffer-color UNPACK/convert (byte0 0x17). We document
  ONLY its length/encoding signature; we do NOT transcribe the blend arithmetic
  sequence that consumes it (clean-room rule 5).
- Length: **8**. Fields: not bit-decoded. Signature byte+6==0x14, byte+7==0xea.
- Discriminator vs compute simd_ballot (10B): a corpus-wide census of all byte0==0x17
  ops confirms the fragment-unpack form is UNIQUELY identified by byte+6==0x14 AND
  byte+7==0xea; every compute/texture 0x17 (ballot/vote/cvt) has other byte+6/+7.
- Predicate (place BEFORE the generic `if b0 == 0x17: return 10`):
```python
if b0 == 0x17 and off + 7 < len(buf) and buf[off + 6] == 0x14 and buf[off + 7] == 0xea:
    return 8                       # EXP-M4-12: FRAGMENT tilebuffer-color UNPACK/convert
```

### (b) @0xb4 `80 0a`, @0xbe `54 05`
- Root cause: a second desync in the blend tail, from two float-ALU mis-lengths:
  1. `39 0d 39 0d` (byte+2 **0x39**) was lengthed 8 (fma, byte+4 0x09), realigned by
     the compact-accumulate fix above (0x39→4). Then `09 01 2e 89 80 0a` (6B, existing
     0x2e uniform-source rule) absorbs `80 0a` → @0xb4 closes.
  2. `19 03 3e 09 80 06` (byte+2 **0x3e**, byte+4 0x80) was lengthed 8 (fma default,
     byte+4 low2==0), but it is a **6-byte uniform-source falu** (same family as the
     0x2e `falu2_uni` ops with byte+4==0x80). With it at 6B, the frag_color_pack
     `97 04 54 05 02 00 08 d0 45 c2` tokenizes at 0xbc and absorbs `54 05` → @0xbe closes.
- Family/label: (1) compact float accumulate (0x39, covered above); (2) uniform-source
  falu (byte0 low-nibble-9, byte+2 0x3e, byte+4 0x80 = uniform/immediate source). Fields:
  not bit-decoded.
- Lengths: `39 0d 39 0d` = **4**; `19 03 3e 09 80 06` = **6**.
- Predicate for the 0x3e uniform-source case (TIGHTLY gated on byte+4==0x80; place
  before the generic fma branch in the low-nibble-9 block). Gating on b4==0x80 keeps
  the compute coord form `.. 3e .. 23 a0 42 ..` (byte+4 0x23) at its correct fma length:
```python
if b2 == 0x3e and (buf[off + 4] if off + 4 < len(buf) else -1) == 0x80:
    return 6                       # EXP-M4-12: fragment uniform-source falu (0x3e, b4=0x80)
```

---

## Whole-corpus validation (patched `work/isadb_local.py`)
- All 12 target residues RESOLVED; all 8 target shaders tokenize cleanly to `stop`.
- Net undecoded bytes across the corpus: 184 → 136. No kernel gained undecoded bytes.
- 0x30/0x39/0x3e-b4=80 float additions: verified individually AND combined = zero new
  gaps in any compute/texture kernel (the initial naive attempt regressed because it
  also added 0x36 — DROPPED, no fragment evidence — and used a loose 0x3e-in-uni-set
  that changed the compute coord form; the tight b4==0x80 gate avoids both).

### Caveat for the integrating agent
One benign boundary-shift remains: k_tex_array_cube @0x66. The loose `02 00` rule
(item 3/4) fires on `02 00` bytes at 0x68 that lie INSIDE a correctly-10-byte
coord_madf, reachable only via a **pre-existing S2-texture upstream desync** (before
0x60). It does NOT increase that kernel's undecoded total (it reduces the resync
region by 2 bytes) and disappears once S2 fixes the upstream coord-math desync. If the
integrating agent wants zero collateral before S2 lands, gate the `02 00` rule
additionally (e.g. require the following op to be a real op-start that is not a
low-nibble-9 falu), or integrate this rule after S2. Flagged, not hidden.
