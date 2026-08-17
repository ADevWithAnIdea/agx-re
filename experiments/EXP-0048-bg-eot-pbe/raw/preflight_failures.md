# Append-only preflight record

The pre-registration already existed with SHA-256
`872ea37e256cc196d4e62e41a48d77f14eb9303c4fa7cc9509e63298941ffa78`
before these attempts.

## Rejected local cleanup command

An initial build-check shell command was rejected before execution because it
ended in `rm -rf` on a temporary directory. No experiment code ran in that
attempt. The command was reissued without cleanup.

## 2026-08-17 build check and untraced hardware baseline

The first compiler invocation exposed a source-level name collision between the
interposer variable `logf` and the SDK math function. `allowtrace.dylib` did not
build. The harness did build, and because the shell command did not use
`set -e`, it then performed one untraced baseline render. Exact output:

```text
experiments/EXP-0048-bg-eot-pbe/harness/allowtrace.c:38:14: error: redefinition of 'logf' as different kind of symbol
DEVICE Apple M4
CASE rgba8-clear-store-draw fmt0=rgba8 fmt1=rgba8 load=2 store=1 draw=1 blend=0 atomic=0 w=32 h=32 bpr=256
USER_VA counter=0x10000018200 rt0=0x10000019200 rt1=0x1000001b200
COMMAND status=4 error=none
FIRST rt0=4080bf80 u32=0x80bf8040
FIRST rt1=804020ff u32=0xff204080
RESULT rt0_fnv=0xe2f345635a80e383 rt1_fnv=0xb6b274a44f91a383 rt0_uniform=1 rt1_uniform=1 counter=0
BUILD_DIR /tmp/exp0048-build.dIuORO
```

This negative preflight also falsified an experimental setup assumption: a
small first user allocation can occupy GPU VA `0x10000018200`, so exact VA alone
does not imply the intended descriptor role under an arbitrary allocation
schedule. The harness was changed to use the previously correlated `0x4000`
allocation class for all user buffers, and the proper run must verify the
allowlisted BO's fixed record contents before interpreting it. This preflight is
excluded from the two-run matrix but retained as process evidence.
