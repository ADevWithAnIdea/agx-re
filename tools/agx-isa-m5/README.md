# agx-isa-m5 — Apple M5 (Apple10 / G17g) AGX ISA database

The **M5** clean-room (dis)assembler DB, **forked from `../agx-isa/`** (the A18 Pro / G17P DB) and
adjusted for the G17P→G17g deltas (EXP-M5-05). The A18 DB is a G17-family *sibling*, so ~84% of M5
bytes already decoded with it unmodified; this fork fixes the divergent length rules + leaders.

Same interface as the A18 tool:
- `python3 agxisa.py tokenize "<hex>"` — split an `_agc.main` hex stream into instructions.
- `python3 agxisa.py disasm "<hex>"` — decode one instruction (mnemonic + fields).
- `python3 agxisa.py asm <mnem> k=v …` — assemble one instruction.
- `python3 agxisa.py json` — emit the machine-readable DB (`db.json`).
- `python3 roundtrip_test.py` — `disassemble(assemble(x))==x` across the validated corpus (ALL PASS).

**Status (EXP-M5-05):** tokenization restored to **96.6% (own) / 98.0% (third-party)** byte coverage,
round-trip green, no hangs. Coverage = leader+length; **semantics of the M5-specific ops are
splice-TODO** (marked in `isadb.py`) — the next wave validates them on M5 hardware.

**Clean-room:** operates only on OUR OWN compiled shader bytes / our own table. Never introspects any
Apple binary. See `../../CLAUDE.md`.
