# A18 Pro (G17P) AGX Shader ISA

Clean-room documentation of the Apple G17P shader instruction set. All facts here come from
disassembling **shaders we compiled ourselves** (OWN-SHADER) + public references (PUBLIC) —
never from Apple binaries. See `../../CLAUDE.md`.

> **Status: early.** The extraction pipeline is validated. Encoding observations below are
> byte-level facts from differential compilation; **interpretations tagged "⏳ pending
> round-trip"** are not yet hardware-validated (that needs the Phase 0.4 testbed:
> assemble → run → observe). Do not treat ⏳ items as final.

## How we get the bytes (validated — EXP-0001)

Our own MSL → runtime `newLibraryWithSource:` → compute pipeline → `MTLBinaryArchive`
`serializeToURL:` → parse with **our own** parser (`tools/shdump/agxparse.py`):

- The serialized archive is a **Metal fat binary** (magic `0xCBFEBABE`).
- Inside, the **AppleGPU** image = Mach-O `cputype 0x1000013` (the native GPU code we want),
  distinct from the **AIR64** image `cputype 0x1000017` (LLVM bitcode; `MTLB`/`BC\xC0\xDE`).
- The AppleGPU image's `__TEXT,__compute` section is itself a **nested Mach-O**; its
  `__TEXT,__text` holds the code, split by symbols into:
  - `_agc.main` — the shader program.
  - `_agc.main.constant_program` — a fixed 64-byte prolog ("constant program").
- **Evidence it is machine code, not IR:** the AIR64 image carries the `BC\xC0\xDE` magic; the
  AppleGPU `__text` does not and does not parse as bitcode. An empty kernel's whole body is a
  single 4-byte word (raw instruction, not IR). Determinism: identical source → byte-identical
  `_agc.main` across repeated compiles (sha256-stable).

## Preliminary encoding observations (EXP-0001)

Byte-level facts (established) and their interpretations (⏳ pending round-trip validation):

- **Instruction parcels are 2 bytes.** All observed region lengths are even. ⏳ (variable-length
  instructions built from 2-byte parcels, as on G13, is the working hypothesis.)
- **Stop/end instruction:** `0e000000` (4 bytes) terminates every `_agc.main` and *is* the
  entire empty kernel. ⏳ strongly implied to be program end.
- **Fixed preamble:** every non-empty `_agc.main` begins `1c a0 10 06 …`. ⏳ role TBD.
- **Float ALU op-select:** float `a+b` vs `a*b` differ in exactly **one byte** (bit 0 of that
  byte: `1c`=add, `1d`=mul). ⏳ this byte selects the float ALU operation.
- **Packed float immediate:** `a+1.0` vs `a+2.0` differ in **one byte** (bits 4–6), and the
  value is **not** IEEE-754 (`3f800000`/`40000000` do not appear) — a compact/packed float
  immediate encoding. ⏳ exact encoding TBD (sweep needed).
- **Source-register selectors:** `a-b` vs `b-a` swap two bytes (complementary `00↔01`) → the
  two source operand fields. ⏳ register-index bit layout TBD.
- **Integer vs float ALU use different encoding paths** (int-add vs float-add differ in length
  and many bytes).

### Negative result (EXP-0001)
- **Buffer *binding index* is not in the shader code.** Writing `buffer(0)` vs `buffer(1)`
  produced byte-identical `_agc.main`, prolog, *and* `__TEXT,__descriptor`. The compiler assigns
  the referenced buffer a fixed uniform slot; the Metal binding index is resolved at bind time
  (argument/uniform table), outside the AGX program. → A cmdstream/descriptor-phase question.

## Confirmed: this is a wholly different ISA from G13/G14
The public dougallj/applegpu (G13) decoder produces `<disassembly failed>` or nonsense on G17P
bytes. applegpu is therefore a **structural template + ISA-agnostic testbed**, not a decoder to
extend. The A18 instruction database is built from scratch (Phase 1).

Source: `experiments/EXP-0001-shader-byte-extraction/`.
