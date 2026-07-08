# EXP-M4-09 cmd3-mrt — MRT 5–8 attachments + mixed formats

**Gap (CMD-3):** the tiler-heap MRT color-descriptor array (`0x10000018200`, 0x20-byte per-attachment
records) was only diffed for 1–4 attachments; k=4..7 and per-attachment mixed formats were unvalidated.

**Hypothesis:** the 0x20-byte per-attachment record array extends cleanly to 8 attachments (LOAD
`+0x20+k·0x20`, STORE `+0x220+k·0x20`), and each record's format word is genuinely per-attachment.

**Method / clean-room category:** DATA-TRACE + OWN-SHADER. Runtime-compiled MSL (`mrtvar`, extended
with per-RT `--fmts`) drives 1..8 color attachments; `iotrace.dylib` interposes IOKit and snapshots
our own process's GPU BOs on SIGUSR1 (`IOTRACE_MAX_MAP=0x8000`). **No Apple binary disassembled.**
Runs on the LOCAL Apple **M4** host (Apple9). A18 cross-confirm items flagged in `RESULTS.md`.

**Result:** array extends cleanly to k=7 (verdicts (a),(b1),(c) CONFIRM). The doc's clear-color
sub-array claim `+0x500+k·0x18` in BO `0x10000018200` is a **vertex-buffer alias** — CORRECT; real
clear colors are a float4 (0x10-stride) array in a separate tiler BO. See `RESULTS.md`.

**Reproduce:**
```
clang -arch arm64e -dynamiclib -o iotrace.dylib iotrace.c -framework IOKit -framework CoreFoundation
clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o mrtvar mrtvar.m
./run.sh
python3 arr.py caps/mrt8 --records 8
python3 arr.py caps/mixA --records 8
```
