# EXP-0067 pre-registration — M4 public typed format matrix

P1.2; local M4 only; public Metal plus complete authored source/readbacks only.
No Apple binary, archive, compiled-code byte, IOKit, BO, command/state, helper,
or private-interface inspection is allowed. Quarantined EXP-0062/0064 are not evidence.

Six 1x1 cases are frozen: RGBA8Unorm/BGRA8Unorm edge stores, RGBA8Unorm_sRGB
near-knee store, R16Unorm midpoint, RGBA16Float finite values, and R32Uint
`0xdeadbeef`. Each render store is followed by one typed compute texture read.
Two fresh six-process runs are required. No native, A18, Linux, descriptor, or
general capability claim is permitted.

Render backing is exactly 64 `0x5a` + 256 row + 64 `0xa5` = 384 bytes / 768 hex.
Compute backing is exactly 64 `0x5a` + 16 payload + 64 `0xa5` = 144 bytes / 288 hex.
Full buffers, guards, argv, status, stderr, target, OS, tool, and revision are retained.

Before build, committed `CAPTURE_CONTRACT.json` binds every authored blob, fixed
raw schema, argv/timeouts, environment fields, and payload grammar. Runner writes
and validates `00_provenance.json` before compilation; mismatch stops before GPU.
Evidence remains unstaged for independent audit.
