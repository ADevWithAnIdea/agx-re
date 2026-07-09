# AGX G16/17 Clean Room Reverse Engineering

This repo contains our work in reverse engineering the userspace of the G16/17
AGX.  It was created entirely via llm driven live probing.

## Legal

Copyright (c) 2026 Cody Ho

All files in this repository are licensed as follows:

- **Code** — all source, scripts, and machine-readable data (Python, Objective-C,
  C, shell, `.metal` shaders, XML encoding tables, and hex/byte-trace captures) is
  licensed under the **GNU General Public License v3.0** (`GPL-3.0`); full text in
  [`LICENSE`](LICENSE).
- **Documentation** — all prose docs (the Markdown files, primarily under `docs/`)
  is licensed under **Creative Commons Attribution-NonCommercial-ShareAlike 4.0
  International** (`CC-BY-NC-SA-4.0`); full text in [`docs/LICENSE`](docs/LICENSE).
- **Third-party** — everything under [`thirdparty/`](thirdparty/) is upstream
  open-source shader source, collected **unmodified** only as disassembler
  coverage-test inputs. Each such project **retains its ORIGINAL license** (all
  permissive — Apache-2.0, BSD-3-Clause, MIT, Unlicense); the GPL-3.0 / CC terms
  above do **not** apply to it. Every `thirdparty/<project>/` carries that
  project's own `LICENSE` and a `PROVENANCE.md` (repo, commit, SPDX id); see
  [`thirdparty/README.md`](thirdparty/README.md) for the per-project list. No
  Apple code and no proprietary or copyleft shaders are included.
