# M4 census — undecoded byte0-group investigation (starting notes)

## Context
Repeating the A18 RE on the **local Mac Mini M4** (Apple M4, Mac16,10, 10-core GPU, Metal 4, this host — NOT a remote device; compile/extract/splice run LOCALLY). M4 shares the A18 ISA: all 57 A18-corpus shaders compile on M4, and the A18 DB (`tools/agx-isa`) tokenizes them at **88.6% tokens / 91.5% bytes** — same as A18. But the resync census reports **~28 undecoded byte0 groups**. The user wants these driven to ~0 ("we shouldn't have any of those").

## What's established
- The census (`experiments/EXP-M4-01-isa-census/census/census.py`, reads `census/hex/*.hex`) resyncs by advancing ONE 2-byte parcel on a length failure — so a SINGLE length-mis-count cascades into MANY spurious "undecoded groups" until it re-aligns. The undecoded-group count is therefore inflated; the real cause is a small number of length bugs and/or genuinely-missing encodings.
- `0x2b` (the byte the user first noticed) is NOT a real group head — it appears only INSIDE resync samples (mid-instruction). Ignore it as a symptom, not a cause.
- **Integer multiply/MAD is NOT the gap in isolation:** minimal `o=a*b` / `o=a*b+c` / int `a*b` kernels (`work/mul.metal`) tokenize 100% clean — `imad` = byte0 `0x9f`/`0x1f`, **byte+2=0x56** (vs `iadd2` byte+2=0x54), 12 bytes, already in the DB. So the desyncs in dense kernels (`k_uint_arith` 83%, `k_int64` 81%, `k_transcend` 75%, `k_tex_atomic`/`k_tex_array_cube` 84%) come from something subtler — likely **imad/iadd LENGTH VARIANTS** (immediate operand or wider forms with a length ≠ 12), or other instructions.
- Recurring motif around the desyncs (see `raw/M4_census.txt` and a walk of `k_uint_arith`): `a7 07 54`, `27 07 54`, `81 27 80`, `32 80 25 8b`, `9f 00 54 …` with trailing `03 0c 8e` / `03 08 06` operand tails. These look like arithmetic/address-math instructions whose LENGTH the DB gets wrong, desyncing the walk.

## The task (for the subagent)
Drive the census to ~0 undecoded on the M4 corpus (and re-check on the A18 corpus — same ISA, so fixes should apply to both; A18 hex is in `experiments/EXP-0036-consolidation-census/hex/`).

Method per group: pick a shader with a desync (start with `k_uint_arith`, `k_int_arith`, `k_transcend`), walk it, find the FIRST instruction whose decoded length is wrong (the one right before the first `<UNDECODED>`), isolate that instruction by compiling a minimal provoking MSL kernel (`work/*.metal` + `shdump` built locally), byte-diff to pin its true length/fields, splice-and-run on the M4 (`tools/agxtest`, build locally) to HW-validate, then add/fix the descriptor + length rule in `tools/agx-isa`. Keep `roundtrip_test.py` GREEN. Re-run the census after each fix; watch the undecoded-group count collapse.

Distinguish: (a) length bug in an existing instruction (fix the length rule) vs (b) genuinely-missing instruction (add descriptor) vs (c) true resync artifact (rare). Most are expected to be (a).

Build harnesses locally: `clang -fobjc-arc -framework Metal -framework Foundation -o shdump tools/shdump/shdump.m` (already done in `census/` and `work/`); agxtest similarly.

---

# RESULTS (EXP-M4-01)

All fixes are in `tools/agx-isa/isadb.py` `instr_length` (pure length-tokenizer refinements;
no descriptor / `db.json` changes). `roundtrip_test.py` stays **GREEN (ALL PASS)**. Method for
every fix: **anchored segmentation** — bracket the unknown region between two high-confidence
anchors (get_sr / device_load / device_store / cvt_i2f `a7 07` / cvt_f2i `27 07` / iadd2/imad
`9f/1f .. 54` / stop), then the gap size = Σ enclosed op lengths pins each length. Isolation
kernels live in `work/*.metal`; harnesses in `work/` (`walk.py`, `solve.py`, `ab.py`,
`localize.py`, `patches.py`, `helper.sh`).

## Headline metric (own-shader census)

| corpus | metric | before | after |
|---|---|---|---|
| **M4** | distinct byte0 groups the DB CANNOT decode at all | **28** | **19** |
| M4 | byte coverage | 91.5% | 93.4% |
| M4 | tokens cleanly length-known | 88.6% | 91.4% |
| M4 | UNDECODED resync regions | 137 | 101 |
| **A18** (cross-check, same ISA) | never-decoded groups | 29 | 20 |
| A18 | byte coverage | 90.6% | 93.2% |
| A18 | UNDECODED regions | 158 | 112 |

**No per-kernel regression** vs the original committed `isadb.py` (total undecoded bytes 826→642,
verified kernel-by-kernel against `git show HEAD:…/isadb.py`).

## What each undecoded group actually was

The overwhelming majority of "undecoded groups" were **NOT missing instructions** — they were
operand-tail bytes (`0x00,0x54,0x80,0x92,0x96,0x03,0x06,0x1a,0x26,0x2a,0x42,…`) exposed when a
real op UPSTREAM was mis-lengthed and the resync walk landed mid-instruction. Fixing a small number
of length rules collapsed most of them:

1. **The `0x?2` (low-nibble-2) integer compare/min-max/select/carry group — THE root cause.**
   It is ONE family whose byte0 **high nibble = destination register (r0..r15)**, exactly like the
   low-nibble-9 float ALU. The DB hard-coded only dst r0..r3 (`0x02/0x12/0x22/0x32`) and left every
   higher-register form (`0x42,0x52,0x62,0x72,0x82,0x92,0xa2,0xb2,0xc2,0xd2,…`) UNDECODED — so every
   `max/select/carry/coord` writing r4+ desynced the walk. **HW-VALIDATED on this M4** (splice of
   `o=max(a,b)`): byte0 `0x02→0x12`(dst r1)/`0x02→0x42`(dst r4) flips output `10..80`→all-zeros
   (result lands in a different reg; store still reads r0), STATUS OK (valid encodings). Length is
   keyed on the byte+2 op-select (6=iminmax, 14=icmpsel-const, 10=coord/madd or reg-select, 8=
   quotient/wide-select); see the table in `docs/isa/README.md`. This single generalization is the
   biggest contributor and cleared 0x42/0x52/0x92/0xd2/… plus their downstream tails.

2. **Compact 4-byte float ALU** (low-nibble-9, byte+2 arith-enable bit clear): added byte+2 ∈
   `{0x19,0x21,0x31}` to the existing `{0x18,0x38}`. These are the div/sqrt-refinement 4-byte
   accumulate/move ops (`79 8d 21 97`, `09 05 19 01`) that mis-lengthed as 6 and desynced.

3. **`0x27` byte+1==0x02 → 12** (matrix-load prep). The old rule dropped it to the 8-byte
   else-branch, exposing its tail `f0 11 01 00` as the spurious **`0xf0`** group. k_matrix now 100%.

4. **`0x2c` byte+1==0x0c → 4** (compact move); **low-nibble-3 byte+2==0x27 → 10** (transcend/tex
   `33 8a 27 bf …`); **low-nibble-0/8 byte+2==0x24 → 6** (packed-half2 ALU); **byte+1==0xc2 tail
   `.. 80 08` → 8** (transcendental range-reduction select). Each cleared its group + tails.

## Justified irreducible residue (still undecoded, ≈101 regions / 6.6% bytes)

- **`k_tex_atomic` (27 regions, the single worst)** — the imageblock/texture-atomic sequence is
  interleaved with the **variable-length `0x0f` execution-mask control-flow ops** (`0f 06 04`,
  `0f 04 04`, `0f 01 54 <off>`), which `instr_length` intentionally leaves LEN_UNKNOWN (a documented
  follow-up for the mask push/pop family), plus the texture-atomic op itself (a genuinely new op not
  yet characterized). These produce the residual `0x00/0x54` tail groups.
- **`k_transcend` / `k_transcend_round` (≈15 regions)** — a long tail of distinct SFU
  range-reduction/polynomial helpers (byte+2 op-selects `0x39,0x49,0x23,0x2f,0x25,…`); the two most
  frequent (`b1==0xc2` select, the `0x33` 10-byte op) are now fixed; the rest are each low-frequency
  and would each need its own isolation kernel.
- **`k_half2_pack` / `k_half_arith`** — a small half2 subsystem (0x18/0x38/0x30/0x20 with mixed
  op-selects) partially fixed (the byte+2==0x24 packed ALU); the remaining forms are a follow-up.

These are true instruction gaps or the known variable-length-CF follow-up, not length bugs — i.e.
the residue is now dominated by genuinely-uncharacterized ops rather than resync cascade artifacts.
