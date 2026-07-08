# EXP-M4-12 S2-texture — ISA-census residue closure (texture-address / 0x54 family)

Provenance: EXP-M4-12 OWN-SHADER isolated compile (Apple M4 / A18 Pro, G17P). Every byte
traced is the compiled form of MSL we wrote ourselves. No Apple binary disassembled.

Method: isolate each texture form as a single-op kernel (`work/iso_*.metal`), compile with
`census/shdump`, extract the AGX main with `census/agxparse.py --extract-hex`, tokenize with
`census/tokenize_trace.py`. Candidate length rules tested via `work/probe.py` (monkey-patches
`isadb.instr_length`, re-walks the WHOLE corpus to prove closure + zero regression; the shared
DB was never edited). Baseline corpus undecoded bytes = 252; with the 5 rules below = 162.

## Closed residues (my four kernels)

| kernel | residue (baseline) | root cause | fix |
|---|---|---|---|
| k_tex_msaa | @0x12 40B | `17 05 54` coord-proj op lengthed 10 (should 12) | Rule 1 |
| k_tex_array_cube | @0x5a 4B | `17 01 54` coord-proj op lengthed 10 (should 12); `54 21 92 08` was its tail | Rule 1 |
| k_tex_array_cube | @0x66 28B | 0x2e float-ALU coord op lengthed 8 (should 12) + trailing `17 05 54` (12) | Rules 1+2 |
| k_tex_lod | @0x12 2B `2c cd` | 2-byte gradient/LOD compact float-imm unlengthed | Rule 3 |
| k_tex_atomic | @0x20 2B `20 00` | 2-byte compact select/zero-init unlengthed | Rule 4 |
| k_tex_atomic | @0x38 2B `ac 01` | 2-byte 0xNc mov-imm (dst r10) unlengthed | Rule 3 |
| k_tex_atomic | @0x3c4 6B | 0x90 texture-read sampler op lengthed 10 (should 16); `00 20 00 00 00 00` was its tail | Rule 5 |
| k_tex_atomic | @0x1e8 4B `20 80 32 8b` | UNRESOLVED (integer texel-address ALU, S3) — see below | flag |

## The five length predicates (paste into isadb.instr_length)

    # Rule 1 — texture coordinate-projection / sample-address setup, 12B.
    # b0=0x17, b1 in {0x01,0x05}, b2 in {0x54,0x56}. Distinct from simd_ballot (b1==0x07).
    if b0 == 0x17 and buf[off+1] in (0x01,0x05) and (buf[off+2] & ~0x02) == 0x54:
        return 12

    # Rule 2 — 12B float-ALU texture-coordinate transform, op-select 0x2e sibling of 0x3e.
    # Placed inside the lo==0x09 block's `if b2 in (0x26,0x2e):` branch, BEFORE its
    # `return 8 if (b4 & 0x02) else 6`.  Unique signature; hits no 6/10-byte form in corpus.
    if b0_low9 and b2 == 0x2e and buf[off+3] == 0x87 and buf[off+4] == 0x23 \
            and buf[off+6] == 0x42 and buf[off+7] == 0x00:
        return 12

    # Rule 3 — 0xNc compact mov-immediate, 2B (dst = high nibble). 2c cd (grad LOD coeff),
    # ac 01 (k_tex_atomic). Exclude get_sr (byte+3 lo-nibble 6), the 0x?c 0c 4-byte move
    # (b1==0x0c), tg_addr_compute 1c 02.. (b1==0x02), rt_intersect (b1==0xea).
    if (b0 & 0x0f) == 0x0c and buf[off+1] not in (0x0c,0x02,0xea) \
            and (buf[off+3] & 0x0f) != 0x06:
        return 2

    # Rule 4 — 2B compact select / move-zero (k_tex_atomic @0x20 `20 00`), also in
    # k_transcend / k_transcend_round.  Gate off the packed-half2 form (b2==0x24).
    if b0 == 0x20 and buf[off+1] == 0x00 and buf[off+2] != 0x24:
        return 2

    # Rule 5 — 16B texture-read SAMPLER op variant (k_tex_atomic @0x3c4). The standalone
    # fallback (0x30/0x90/0xb0, b2 in set) returns 10; this variant carries a trailing
    # 6-byte operand word. Gate: b1==0x00, b2==0x17, b4==0xa0 (plain read has b4==0x00 -> 10).
    if b0 in (0x30,0x90,0xb0) and buf[off+1] == 0x00 and buf[off+2] == 0x17 \
            and buf[off+4] == 0xa0:
        return 16

(b0_low9 == `(b0 & 0x0f) == 0x09`.)

## UNRESOLVED — k_tex_atomic @0x1e8 `20 80 32 8b` (4B)

Anchored bracket: op@0x1e0 `22 8b 27 1d 82 18 05 02` (8B, low-nibble-2 select, b2=0x27) —
`20 80 32 8b` — op@0x1ec `27 1d 82 1a 05 02 20 80` (8B iunary). This is the texture_buffer
texel-address computation (integer/select family, NOT the 0x54 texture family — S3 territory).
Two interpretations both resync cleanly at 0x1ec: (a) the 0x22 select op is 12B and absorbs
`20 80 32 8b` as operand tail; (b) `20 80 32 8b` is a standalone 4B 0x20-family compact op
(byte0 0x20, like Rule-4 `20 00` but b1=0x80). Could not disambiguate cleanly — the isolated
texture_buffer atomic (`work/iso_texbufadd.metal`) does not reproduce it (register-pressure
artifact of the combined kernel). Flag for the integer-address-ALU owner.
