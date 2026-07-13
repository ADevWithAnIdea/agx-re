# EXP-M5-18 — M5 out-of-line FUNCTION-CALL ABI (call / call_indirect / ret / frame)

**Device:** Apple M5 / Apple10 / G17g / T8142. Every fact HW-evidenced: byte-diff of OUR OWN *linked* MSL,
splice-and-observe, and end-to-end round-trip executing the extracted machine code FROM the archive. No Apple
binary disassembled. Faults contained (0 reboots).

## Verdict: the M5 call ABI is now MAPPABLE — resolves REVIEW-M5-OBJ1-04 M-2
The blocker was **tooling**: shdump's single-symbol extraction of a `visible_function_table` caller returns a
4-byte STUB because the real call resolves at PIPELINE-LINK time. This built the LINKED pipeline, extracted the
real call site + callees, ran them on HW, and splice-mapped call/ret/frame. Direct (`[[noinline]]`) + indirect
(vft) out-of-line calls both round-trip exactly.

## New tooling (reusable)
- **`shdumplink.m`** — builds `MTLComputePipelineDescriptor.linkedFunctions = MTLLinkedFunctions(all [[visible]] fns)`,
  serializes the linked pipeline to an `MTLBinaryArchive`. The archive's nested Mach-O carries the kernel's real
  `_agc.main` (live call site, 64B not a 4B stub) + each callee as a separate `__text` symbol.
- **`agxrunlink.m`** — rebuilds the pipeline FROM the (spliced) linked archive (`FailOnBinaryArchiveMiss`),
  creates+fills an `MTLVisibleFunctionTable` (`--vft`), binds it, dispatches. Round-trips EXACT: indirect
  `c_dyn8` → 10 12…24, const `c_dync` → 100…107, direct `c_noinline` (3x+1) → 1 4…22.

## Encoding (HW-validated; call region byte-identical across arg-count + callee body ⇒ genuine ABI)
- `43 00 00 01` **frame_marker** (4B, inherited from A18) — splice byte0/companion→0 = SAME ⇒ runtime-inert marker.
- `9e 60 <type> 0e …` **call-setup** — byte+2 **type = 0x00 direct / 0x01 indirect** (only differing byte in the
  shared prefix). Direct: `9e 60 00 0e fe 1f f3 1e 1f 20` (target PC in the `fe…` tail, splice→0 zeros output).
  Indirect: `9e 60 01 0e …` + loads the callee code-VA from the vft via a preceding `m5_load 38 0a 10 e0 …`.
- **`ff c7 ff 7f be 03 40 0e` branch-and-link** (8B, the actual CALL, shared) = `m5_call`. splice→0:
  byte0/+1/+2/+3/+4/+7 → CMDBUF_ERROR (redirects branch); +5/+6 inert. [+ `m5_call_tail` `fb 1e 1f 00` 4B on indirect.]
- **ret** (callee epilogue) `27 00 04 00 20 00 a5 02` — invariant across callees; splice byte0(`27`)/byte+6(`a5`)
  → zero output (load-bearing; `a5 02` = ret marker). Callee can't use `stop`(0x0e).
- **Register convention:** args by-register, **no per-arg marshalling at the call site** (`c_dyn8` 1-arg ≡ `c_dyn8b`
  2-arg call region byte-identical); return value in a fixed reg. The A18 `0f 05…8f`/`0f 80`/`0x8f` forms all
  changed on M5; only the `43` marker + intra-shader control flow carried over.

## First-class negatives
- Metal **INLINES** most vft calls — a genuine out-of-line call needs ≥8 distinct fns behind a fully-runtime index
  (indirect) or `[[noinline]]` (direct). `c_id`/`c_add7`/`c_sel2` all inlined.
- The census `ef/ff 48 43` is **RT traversal, NOT a call** (`rt_prim` has no user fn/table) — the byte+2==0x43
  heuristic conflated RT ray-data marshalling with calls. The real call uses standalone `43 00 00 01` + `ff c7…`.

## DB patch (validated non-regressing)
Tightly-gated (3-4 byte gates) `m5_call` (0xff/`c7 ff 7f`→8B) + `m5_call_tail` (0xfb/`1e 1f 00`→4B, un-swallows the
branch on indirect). Round-trip ALL PASS; strict tokenization CLEAN with the call named; census flat (own 93.44%,
tp 95.51%); DB 189→191. The `9e 60` setup + `27…a5` ret are documented but NOT lengthed (segmentation needs a
callee-address-delta experiment) — proposed for a later census pass.

## Still open
Intra-setup bit-typing of `9e 60 <type> 0e` + direct target-PC tail (PC-rel vs absolute); exact ret-op family of
`a5`; register **spill** frame (needs a high-pressure callee).

## Clean-room attestation
Every byte inspected/spliced is our own on-device-compiled+linked MSL or bytes our own `agxrunlink` read from our
own buffers. No Apple binary introspected; no compiler sequence lifted; operands raw where unproven (rule 5).
Negatives (inlining, RT-vs-call) recorded as first-class.
