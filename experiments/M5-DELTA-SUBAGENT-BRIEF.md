# M5 ISA delta-characterization — reusable subagent brief (Phase 1.3)

Template for each per-family subagent that resolves a diverging M5 opcode/family found by the
census (EXP-M5-02/03). One family per agent (e.g. "memory load/store byte0=0x18", "float ALU",
"control flow", "texture", "atomics/subgroup", "matrix", "ray-tracing", "mesh", "fragment/varying").

## Clean-room (inherit the Prime Directive — inviolable)
- ONLY compile/disassemble OUR OWN MSL (author minimal provocation kernels) or committed permissive
  thirdparty MSL. NEVER disassemble/introspect ANY Apple binary. No otool -tv, ghidra, lldb disasm.
- Document HARDWARE encoding/semantics; never lift Apple compiler instruction SEQUENCES as an algorithm.
- Better NO result than a TAINTED/FABRICATED one. Every field resolution must be HW-evidenced.
- Do NOT run git (main agent commits). Write artifacts to experiments/EXP-M5-1x-<family>/ and report.

## Device / tools (already deployed + built)
- SSH: `sshpass -p 'Password_1' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=20 user@192.168.170.253`
- Apple M5 / T8142 / macOS 27.0, passwordless sudo, CLT. Tools at `~/cleanroom_work/tools/{shdump,agxtest,agx-isa}` (all built).
- Compile: `./tools/shdump/shdump -o out.bin -f <fn> src.metal` (or `--render --vertex V --fragment F`). Extract: `python3 tools/shdump/agxparse.py out.bin --extract-hex`. Decode: `python3 tools/agx-isa/agxisa.py tokenize "<hex>"`.
- Splice-and-observe (VALIDATED on M5): `python3 tools/agxtest/agxtest.py --source k.metal --function k --grid N --tg T --buf i=... --out i=N --splice _agc.main@0xOFF=HEX [--expect i=...]` with `--shdump tools/shdump/shdump --agxrun tools/agxtest/agxrun --agxparse tools/shdump/agxparse.py`. Fast field sweeps: `agxrun_persist` + `persistrun.py`. Fragment→pixel: `agxrender`.
- Use your OWN device workdir `~/cleanroom_work/EXP-M5-1x-<family>/` to avoid collisions.
- **HARD-TIMEOUT EVERY device probe** (they hang occasionally). Correct idiom (note `alarm(shift)`, NOT
  `alarm(N)` — the latter makes perl try to exec a program named after the number and silently fails):
  `perl -e 'alarm(shift); exec @ARGV' 20 sshpass -p 'Password_1' ssh <opts> user@192.168.170.253 'bash -s' < script`.
  Also use `agxtest.py --run-timeout 12` for dispatch, and give any census/loop an internal wall-clock budget.
- **Fault protocol:** M5 GPU-fault containment is being characterized; assume a bad encoding *may*
  hang. If a dispatch wedges, from the HOST run `/Users/user/.local/bin/macvdmtool reboot`, wait ~25s
  (auto-login → SSH returns at .253), and resume. Isolate one hypothesis per dispatch. Note in your
  report whether faults were contained or forced a reboot (this is itself a first-class data point).

## Method (the A18 loop, re-run on M5)
1. Take the family's diverging byte0/leader from the census. Author minimal own-MSL kernels that
   provoke exactly that op (vary one operand/mode at a time). Compile → extract → tokenize.
2. Byte-diff sibling kernels to isolate which bytes are the leader / length / operand / mode / imm.
3. **Splice-and-observe on M5:** systematically vary the candidate field bytes, dispatch, read the
   output delta. A register index shifts which input is read; a mode/enum changes the operation; a
   no-effect bit is a first-class RESERVED/inert negative result.
4. Fix the descriptor in a COPY of `tools/agx-isa/isadb.py` (leader match, length rule, field
   types/enums, semantics, provenance = `HW-VALIDATED (splice, M5 EXP-M5-1x)`). Re-tokenize the family's
   corpus slice; confirm no desync and round-trip identity.
5. Deliver to experiments/EXP-M5-1x-<family>/: report.md (per-field evidence: inputs, spliced bytes @off,
   observed output, conclusion), the provocation .metal kernels, and a PATCH/PROPOSAL for isadb.py
   (as a diff or a descriptors JSON snippet the main agent merges — do NOT edit the shared tools/agx-isa
   in place; propose, main agent integrates + re-runs round-trip + census).
6. Report back structured: family, # fields resolved, before/after census coverage for that byte0 group,
   any honest negatives (inert bits → reserved), fault behavior observed, clean-room attestation.

## Integration contract (main agent)
Main agent merges proposals into `tools/agx-isa/isadb.py`, regenerates `db.json` + `docs/isa/encoding-tables.md`
(M5), runs `roundtrip_test.py` + re-census, and commits per family (`exp(M5-1x): <family> — N fields HW-validated`).
