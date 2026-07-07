# Tools

Reusable clean-room RE tooling we build (all **ours**; no Apple code). Planned:

- `shdump/` — MSL source → runtime `MTLLibrary` → `MTLBinaryArchive` → **our** parser that
  isolates the raw AGX machine-code bytes. (OWN-SHADER pipeline.)
- `disasm/` — the AGX disassembler: starts from public dougallj/applegpu + Mesa `src/asahi/isa`
  (open source) and gets extended for the A18 Pro ISA as we validate encodings on hardware.
- `iotrace/` — `DYLD_INSERT_LIBRARIES` interposer over the Metal↔kernel IOKit/IOGPU path,
  logging *data* (command buffers, descriptors) crossing the boundary. (DATA-TRACE.)
- `probe/` — compute-shader harness: known pattern in → read back, for tiling and
  instruction-behavior probing. (HW-PROBE.)

These are exploration tools that live in this repo. They are **not** the Mesa driver and are
**not** the deliverable — `docs/` is. Nothing here may incorporate disassembly of Apple binaries.
