# EXP-0082 results — M4 device_load/store memory-offset semantics (MEM-01..MEM-05)

**Status: CAPTURED / PROMOTED.** `verify.py --captured` PASSES (`raw/m4-20260828-run01`,
`raw/m4-20260828-run02`, 2164 cases each, `04_results.jsonl` byte-identical across runs,
`analysis.json` hand-validation set 7/7 matched, 0 issues). Target: local Apple M4 (G16G,
10 cores, macOS 26.6.2 build 25G82) through public Metal only. Git revision `ab874936`
(unchanged across both captures).

## OBSERVED

- Both runs: 2164/2164 cases completed, `status_counts {CMDBUF_ERROR: 2, OK: 2162}`,
  identical between runs. The 2 faults are `ld_idxreg_r0x7f`/`ld_idxreg_r0xff`
  (VAL-IDXREG family, `index_reg` spliced to 0x7F/0xFF — an out-of-range GPR selector
  reliably faults the command buffer; not part of MEM-01..05, non-load-bearing).
- `04_results.jsonl` (the semantic payload) is **byte-identical** between run01 and run02
  (`results_sha256 b29f905a44de38ef4759a38c94fe45bfabdc668a6aa901b4942a3b8f12f9a76c`, both
  runs). `04_timing.jsonl` (GPU time, wall time, raw stdout/stderr) **differs** between runs
  as expected (`timing_sha256 794fb5f6...` vs `d4aca82b...`) — direct hardware confirmation
  that the EXP-0081 root fix works: the observation is reproducible, only the timing isn't,
  and the cross-run gate now correctly cares about only the former.
- All 7 retained hand-validation entries (`ld_ctrl_idx64`, `ld_ctrl_idx1`, `ld_scale1_code4`,
  `ld_scale1_code0`, `ld_off1_code3_idx0`, `ld_range_f0000`, `ld_range_f0001`) matched exactly.
- MEM-03 dense sweep (`idx=1024`, `idx_off` full 0..2047, load, default 4-byte element):
  2048/2048 field values match the **unsigned** model exactly, 0 anomalies, 0 holes. The
  signed (two's-complement) model matches only for f=0..1023 and diverges starting exactly at
  f=1024 (`first_field_value_missed_by_signed_model: 1024`).
- MEM-03 negative-side cross-check (`idx=64`, `idx_off` in {0x3FE,0x3FF,0x400,0x401,0x402,
  0x7FE,0x7FF}): all 7 match the unsigned model; none match the signed model past f=0x3FF.
- MEM-02 discriminating cases that combine a non-default `elem_size` with a non-zero
  `idx_off` (`ld_off2_code2_idx0`, `ld_off3_code2_idx2`, `ld_off1_code1_idx0`,
  `ld_off4_code1_idx0`, `ld_off1_code4_idx1`) all match the formula
  `byte_offset = idx*ELEM_SCALE[code] + idx_off*4` exactly, and none match pure H-ELEM
  (offset scaled by the same `ELEM_SCALE[code]` as the index) or pure H-BYTE (offset
  unscaled). This is why the pure-H-ELEM/H-BYTE hypothesis scoreboard in `analysis.json`
  reads 3/12 and 0/12 respectively for MEM-02 — those two named hypotheses were both
  incomplete; the 5 cases above falsify both and directly reveal the correct third rule.
- MEM-01: `elem_size` codes 0 (16B), 3 (4B, compiler default), 4 (8B) scale the GPR index
  exactly linearly across every probed index (1,3,5,17) — `byte_offset = idx * scale`,
  zero exceptions. Codes 1 (nominal 1B) and 2 (nominal 2B) do **not**: the observed byte
  offset in every one of 5 probed (idx, code) pairs equals
  `floor(idx*nominal_scale / 4) * 4` — the raw sub-word element address is computed, then the
  actual access rounds down to the nearest 4-byte (word) boundary. This reproduces and fully
  explains EXP-0081's `ld_scale1_code1`/`ld_scale1_code2` hand-set divergences (see
  "Resolution of EXP-0081 divergences" below).
- MEM-01/04 element-size code-space census (load, 23 raw byte+12 values beyond the canonical
  5): codes producing a clean, decodable result are 0x4A/0x4C ("code5"/"code6", collapse to
  word0 like the 1B/2B case — nominal scale < 4B), 0x4E ("code7", word1 — nominal scale in
  [4,7)), 0x50 ("code8", word4 — nominal scale 16B), 0xC6 ("hi_c6", word1). Every other probed
  raw value (0x60, 0x00, 0x02, 0x06, the 6 odd-bit0 values 0x41/0x43/0x45/0x47/0x49/0x4F,
  0x86, 0xFF) produces `STATUS OK` but an **undecodable** raw value (no tag-pattern match —
  a garbage or unresolved-format read, not a fault). No probed value, decodable or not,
  is consistent with a non-power-of-two effective stride.
- MEM-04 store-side code-space probe (`st_elemcode_*`, 5 raw byte+12 values): 0x1A/0x1C
  ("code5"/"code6") undecodable (no write detected); 0x30 ("hi") and 0x10 ("c0") land the
  write at word0 (idx=1, i.e. an effective index scale < 4, echoing the load's sub-word
  collapse pattern); 0x13 ("odd") reproduces the unmodified baseline (word1). No non-power-
  of-two stride observed on the store side either.
- MEM-05 wrap family: **all 9** load cases (`ld_wrap_*`, indices at/near 0xFFFFFFFF,
  0x80000000, 0x7FFFFFFF, 0x40000000, 0xC0000000, 0x3FFFFFFF, with 0/+1/+2 `idx_off`) return
  raw `0x00000000`, decoded **undecodable** (not `a[0]`'s actual content `0x3CA50000`, and not
  matching any in-bounds tag window). Both store wrap cases (`st_wrap_ffffffff_p1`,
  `st_wrap_40000000`) show no detectable write. This is uniform: the cases designed to land at
  word 0 *only if* the arithmetic wraps mod 2^32, and the far-OOB controls that were never
  expected to wrap, are **indistinguishable** — none of the 11 cases show evidence of landing
  back inside the allocation.
- MEM-03 byte+11 bits2..7 ("format tail") inertness probes: 3 of 6 raw values (0x00, 0x60,
  0xC0) are inert (reproduce the unspliced baseline, word 1024). The other 3 (0x44, 0x48,
  0x50) are **not** inert: 0x44 relocates the read to word 3072 (not a simple offset shift —
  1024×3); 0x48 and 0x50 produce undecodable output. `dst_ext9` (byte+9 bits0..6, adjacent to
  but outside `idx_off`) probes: value 5 leaves the read address unaffected (still word 64)
  while value 0 produces undecodable output — consistent with this field affecting the load's
  destination/consumer wiring, not its address.
- MEM-03 store-boundary probes (`idx=1024`, `idx_off` in {0x1FF,0x200,0x3FF,0x400,0x7FF} plus
  `idx=1023,idx_off=0x7FF`): **all 6** show no detectable write anywhere in the 8 KiB `tgt`
  buffer. Fully explained by the store offset-unit finding below (every one of these computed
  addresses exceeds `tgt`'s 8192-byte allocation once the offset unit is 16 bytes, not 4).

## INTERPRETED

- **Load address formula** (device_load, this scalar 32-bit `ld_format=17` form):
  `effective_byte_offset = (idx * ELEM_SCALE[elem_size_code] + idx_off * 4) mod 2^32`, where
  `ELEM_SCALE = {0:16, 3:4, 4:8}` bytes are exact/linear, and codes 1/2 (nominal 1/2 bytes)
  instead round the *index* term down to 4-byte granularity (equivalently: for codes 1/2,
  substitute `floor(idx*nominal_scale/4)*4` for the index term). `idx_off` is **always**
  4-byte-word-granular, independent of `elem_size` — it is neither "element units" in the
  general sense (H-ELEM as originally framed) nor raw byte units (H-BYTE); it is fixed-word
  units, which only coincides with "element units" when the element size is itself 4 bytes
  (the compiler's default 32-bit-scalar case — which is why the 2048-case dense sweep and the
  7-case negative-side sweep, both run at the default code, could not by themselves distinguish
  this from H-ELEM).
- **Store address formula** (device_store, this form): `effective_byte_offset =
  (idx * 4 + idx_off * 16) mod 2^32` for the baseline/default byte+12 encoding (0x11). The
  index term uses 4-byte (word) granularity like the load's default; the *offset* term uses
  16-byte granularity — a different, larger fixed unit than the load's. This formula predicts
  every one of the 6 MEM-03 store-boundary probes to land beyond `tgt`'s 8192-byte allocation
  (e.g. `idx=1024, idx_off=0x1FF`: `1024*4 + 511*16 = 12272 > 8192`), exactly matching the
  observed "no detectable write" in all 6 — the store side of MEM-03 is fully explained as
  genuine (silently-discarded) out-of-allocation stores under this formula, not a gap or a
  contract defect.
- **idx_off signedness**: unsigned, 0..2047 (11 bits), no internal holes, confirmed by an
  exhaustive dense sweep at one base index plus a 7-point cross-check at a different base
  index — both agree on every tested value. There is no "first-invalid value" *of the field's
  own encoding*: every one of the 2048 representable values behaves exactly per the formula
  above. Whether a given (index, offset) pair lands inside the actual allocation is a separate,
  buffer-size-dependent question (see MEM-05/OOB below), not a property of the field.
- **32-bit wrap**: refuted. `idx=0xFFFFFFFF, idx_off=+1` (and every other case designed to
  test wraparound) does **not** land back at word 0 of the buffer; it behaves as a genuine
  out-of-allocation access (raw 0 for loads — consistent with the established MEM-08
  zero-fill-on-OOB-read behavior; silently discarded for stores — consistent with
  OOB-store-discard). The address arithmetic is therefore evaluated in a domain that does not
  silently truncate/fold back to a 32-bit index space before the bounds check; `idx + idx_off`
  going past `0xFFFFFFFF` is treated as genuinely out of range, not as `0`.
- **Stride space**: every decodable (index, elem_size-code) combination across MEM-01's 23 core
  cases and MEM-04's 25 exploration cases (48 total, load + store) is consistent with a
  power-of-two per-index granularity (4, 8, or 16 bytes after the sub-word collapse rule is
  applied; nominal "1B"/"2B" codes never produce true sub-word addressing). No case, decodable
  or not, produced or suggested a non-power-of-two stride (e.g. 3). Many raw byte+12 values
  outside the canonical table produce `STATUS OK` with an undecodable result — a fault-free but
  semantically unresolved/unsafe encoding, not evidence of any additional stride.
- **byte+11 bits 2..7** ("format tail", outside `idx_off`'s own 2 LSBs there): NOT
  uniformly inert as the pre-registration assumed for the field-boundary check. This does not
  change the MEM-03 answer (which concerns `idx_off`'s own bits, confirmed correctly bounded
  to byte+11 bits 0..1 by the dense/negative sweeps, which never set bits above that), but it
  is flagged `UNKNOWN` / follow-up: the exact semantics of byte+11 bits 2..7 for this
  instruction form are not established by this experiment.

## Resolution of EXP-0081's hand-set expectation divergences

- **`ld_scale1_code1`** (EXP-0081 hand-set expectation: byte offset 1, hex `0x013CA500`) —
  **RESOLVED, hand-set expectation was wrong.** EXP-0082's independently captured, byte-exact
  reproducible observation is `0x0000A53C` (byte offset 0), matching
  `floor(1*1/4)*4 = 0` under the load address formula above. The naive assumption that
  `elem_size` code 1 provides true 1-byte-granularity addressing is falsified; sub-word codes
  compute a raw element address at their nominal scale but the hardware access itself is
  4-byte-aligned-down. This is the SAME class of behavior independently established for a
  different addressing path in EXP-0076 ("buffer access = aligned units w/ align-down
  addressing").
- **`ld_scale1_code2`** (expectation: byte offset 2, hex `0x00013CA5`) — **RESOLVED, same
  root cause.** Observed `0x0000A53C` (byte offset 0), matching `floor(1*2/4)*4 = 0`.
  Confirmed as an instance of the same align-down rule, not a separate anomaly (cross-checked
  against `ld_scale3_code2`, idx=3: predicted `floor(3*2/4)*4=4`=word1, observed word1 —
  exact match).
- **`ld_wrap_ffffffff_p1`** (a THIRD EXP-0081 divergence this registration independently found
  in EXP-0081's own raw data beyond the two named above, and re-registered as hypothesis
  H-DIV-3 — see `PRE_REGISTRATION.md`) — **RESOLVED as a refutation of H-W32.** EXP-0082's
  fresh capture reproduces the exact same raw `0x00000000`/undecodable observation, now backed
  by 8 additional corroborating MEM-05 cases (11 total, 0 exceptions) rather than a single
  datum. MEM-05's answer is No: 32-bit address arithmetic does not wrap.

## Per-item verdict blocks (`APPLE9_RE_IMPLEMENTATION_GAPS.md` Part-II format)

- **MEM-01 — Does `device_load/store` interpret its GPR index as an element index scaled by
  the encoded element size?**
  **Yes, for element-size codes 0 (16B), 3 (4B, the compiler's default), and 4 (8B)** —
  confirmed exact linear scaling (`byte_offset = idx * scale`) across every probed index,
  HW-VALIDATED, zero exceptions. **Partially/effectively No for codes 1 (nominal 1B) and 2
  (nominal 2B)**: the index is scaled by the nominal size internally, but the resulting
  address is then rounded down to the nearest 4-byte boundary before the access happens —
  these codes do not provide genuine sub-word-granularity addressing for this scalar 32-bit
  load form. Store-side default index scale confirmed at 4 bytes; the store's byte+12 field
  uses a disjoint numeric encoding from the load's and its full code space is not resolved by
  this experiment (most probed alternate values simply suppress the write rather than
  changing scale predictably — flagged for follow-up, not required for the MEM-01 core
  answer).

- **MEM-02 — Is the in-instruction immediate offset added in element units rather than
  bytes?**
  **No — neither.** The immediate offset (`idx_off`) is added in a **fixed 4-byte (one
  machine word) unit for `device_load`, and a fixed 16-byte unit for `device_store`**,
  independent of the instruction's own `elem_size` scale for the index. This was directly
  falsified against both pure hypotheses by 5 discriminating cases that combine a non-default
  `elem_size` with a non-zero `idx_off` (all 5 match `idx*scale + idx_off*4` exactly, 0
  matching pure element-scaled or pure byte-scaled predictions). The offset coincides with
  "element units" only in the special case where the element size itself is 4 bytes (the
  compiler's typical 32-bit-scalar default), which is why a sweep confined to that default
  code alone cannot distinguish the two hypotheses.

- **MEM-03 — Is the complete signedness and legal range of the immediate element offset known
  and hardware-validated?**
  **Yes.** `idx_off` is an **unsigned 11-bit field, legal range 0..2047 (0x000..0x7FF)
  inclusive, with no internal holes** — confirmed by an exhaustive 2048-value dense sweep at
  one base index (100% fit to the unsigned model, 0 anomalies) plus a 7-point cross-check at a
  different base index (100% fit). The signed (two's-complement) interpretation is refuted:
  it only coincides with the data for field values 0..1023 and diverges at every value from
  1024 up. There is **no first-invalid encoded value** within the field's own 11-bit domain —
  every one of the 2048 values behaves exactly per the address formula. "First invalid" in the
  finite-resource sense instead depends on the runtime (base index, buffer size): once
  `idx*scale + idx_off*unit` exceeds the actual allocation, the **observed failure mode is
  silent zero-fill for loads and silent discard for stores** (both fault-free, `STATUS OK`),
  matching the previously-established MEM-08 out-of-allocation behavior — never a command-
  buffer fault for a merely-large-but-legally-encoded offset value. (Caveat, not part of the
  core answer: byte+11 bits 2..7, outside `idx_off`'s own bits, are not uniformly inert —
  flagged `UNKNOWN`/follow-up, does not affect the `idx_off` range/signedness finding above,
  which never sets those bits.)

- **MEM-04 — Can `device_load/store` directly encode `base + index * stride + offset` for
  arbitrary vertex strides?**
  **No.** Across the full explored `elem_size` code space (23 MEM-01 cases + 25 MEM-04
  exploration cases, load and store), every decodable combination is consistent with a
  power-of-two per-index granularity (4, 8, or 16 bytes; nominal 1B/2B codes collapse to
  4-byte-aligned addressing rather than providing true sub-word/non-power-of-two strides).
  No probed encoding, decodable or not, produced or suggested a stride of 3 or any other
  non-power-of-two value. **Compiler consequence confirmed**: arbitrary vertex-stride
  multiplication must be lowered to ALU/IMAD before the memory instruction; the old
  `has_amul`-style rationale for a wider encodable-stride assumption is not supported by this
  hardware form.

- **MEM-05 — Does 32-bit address/index arithmetic wrap in exactly the way required for legal
  NIR buffer offsets?**
  **No.** All 9 load cases and both store cases designed to test `(index + offset)` crossing
  `0xFFFFFFFF` show **no evidence of wraparound**: instead of landing back inside the buffer
  (e.g. at word 0), every case behaves as a genuine out-of-allocation access (zero-fill read /
  discarded store), indistinguishable from the far-OOB controls that were never expected to
  wrap. **Compiler consequence**: NIR 32-bit buffer-offset arithmetic that relies on exact
  mod-2^32 wraparound semantics **cannot** be emitted as-is and handed directly to this
  addressing form; the driver must not assume the hardware silently truncates an overflowing
  address back into range.

## Exact tested range

- `elem_size` (load, byte+12): canonical codes {0,1,2,3,4} (5 values) × representative indices
  {1,3,5,17}; extended raw byte-value census over {0x40,0x42,0x44,0x46,0x48,0x4A,0x4C,0x4E,
  0x50,0x58,0x00,0x02,0x06,0x41,0x43,0x45,0x47,0x49,0x4F,0xC6,0x86,0xFF} at idx=1 (+1 at
  idx=3). `elem_size` (store, byte+12): raw values {0x00,0x10,0x11,0x12,0x14,0x18,0x1A,0x1C,
  0x30,0x40,0x42,0x44,0x46,0x48,0x4A} at idx=1.
- `idx_off` (11-bit field): **exhaustive** 0..2047 at idx=1024 (load); {0x3FE,0x3FF,0x400,
  0x401,0x402,0x7FE,0x7FF} at idx=64 (load); {1,2,3,4} combined with non-default `elem_size`
  at idx∈{0,1,2} (load, MEM-02); {0x1,0x2,0x1FF,0x200,0x3FF,0x400,0x7FF} at idx∈{0,1,64,1023,
  1024} (store).
  index (`idx`/`j`, via `idxbuf[0]`): 0, 1, 2, 3, 5, 17, 64, 1023, 1024, 2047, 0x3FFFFFFF,
  0x40000000, 0x7FFFFFFF, 0x80000000, 0xC0000000, 0xFFFFFFFF.
- `index_reg` (byte+5): 0x00..0x07, 0x80/0x81/0x85 (bit7 variants), 0x40, 0x7F, 0xFF (14
  values) — non-load-bearing M4 re-validation, 2 of 14 (0x7F, 0xFF) faulted the command
  buffer, the rest read back the expected source register.
- `space` (byte+1): 0x02, 0x10. `access_desc` (byte+6): 0x00, 0xFF. `ldform_hi11` (byte+11
  bits 2..7 window): 0x00, 0x44, 0x48, 0x50, 0x60, 0xC0. `dst_ext9` (byte+9 bits 0..6): 0, 5.
- 2164 cases total; 2 faults (`CMDBUF_ERROR`, both `index_reg` out-of-range selectors,
  VAL-IDXREG family); 0 timeouts; 0 hangs.

## Target and scope label

M4 / G16G, local host, public Metal API only — splice evidence on our own compiled kernels
(`kernels/ld_bank.metal`, `kernels/st_bank.metal`), binary-archive splice via
`tools/agxtest`, decoded with `tools/agx-isa`. No A18 (G17P) inference (hands-off per
standing directive); no Linux/UAPI claim; no M5 evidence. Scope is this scalar 32-bit
(`ld_format`/`st_format` = 17) `device_load`/`device_store` addressing form specifically —
other formats (vector widths, other `ld_format`/`st_format` codes, other addressing modes
such as `addr_mode` values other than 0x44/0x54) are not covered and may differ.

Evidence label: **HW-VALIDATED** for MEM-01 (codes 0/3/4), MEM-02, MEM-03, MEM-05, and the
MEM-04 null (no non-power-of-two stride) — each independently generated (not merely decoded
from a captured template), spliced, dispatched, and observed to change live hardware behavior
exactly as predicted, with a clean byte-exact repeat across two independent runs.
**STRUCTURAL/INFERRED** for the store-side `elem_size` code-space's exact bit semantics and
for byte+11 bits 2..7 — both flagged `UNKNOWN`, explicitly out of scope for MEM-01..05's core
answers, and named as follow-up targets for a successor experiment.

```text
Clean-room provenance: HW-PROBE / OWN-SHADER
Inputs inspected: authored MSL (kernels/), authored harness/runner/verifier/
  analysis/matrix/baseline, and the compiled bytes of our own kernels only
Apple binary introspection: NONE
Reproduction: see README.md command sequence
Evidence: raw/m4-20260828-run01, raw/m4-20260828-run02, analysis.json, manifest.json
```
