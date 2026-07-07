#!/usr/bin/env bash
# EXP-0003 — reproduce the AGX hardware round-trip testbed end to end.
# Deploys the harness to the A18 device, builds it, and runs every stage,
# capturing text logs into raw/. Host-side; drives the device over SSH.
#
# Clean-room: OWN-SHADER + PUBLIC. Only our own MSL is compiled and only our own
# compiled shader bytes are spliced. No Apple binary is disassembled.
#
# Usage:  ./run_all.sh
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
DEV="user@192.168.170.254"
SSH="sshpass -p Password_1 ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15"
SCP="sshpass -p Password_1 scp -o StrictHostKeyChecking=no -o ConnectTimeout=15"
WORK="~/cleanroom_work/exp0003"

# Host-side hard timeout wrapper: kills the remote command if the GPU wedges SSH.
sshto() { python3 "$HERE/sshto.py" "$1" "$2"; }

mkdir -p "$HERE/raw"

echo "== deploy =="
$SSH $DEV "mkdir -p $WORK/kernels $WORK/work $WORK/raw"
$SCP "$REPO/tools/agxtest/agxrun.m"  "$REPO/tools/agxtest/agxtest.py" \
     "$REPO/tools/shdump/shdump.m"   "$REPO/tools/shdump/agxparse.py"  "$DEV:$WORK/"
$SCP "$HERE/kernels/add.metal" "$HERE/kernels/mul.metal" "$DEV:$WORK/kernels/"

echo "== build =="
$SSH $DEV "cd $WORK && \
  clang -fobjc-arc -framework Metal -framework Foundation -o shdump shdump.m && \
  clang -fobjc-arc -framework Metal -framework Foundation -o agxrun agxrun.m && echo built"

RUN="cd $WORK && python3 agxtest.py --source kernels/add.metal --function k --grid 8 --tg 8 \
  --buf 0=1,2,3,4,5,6,7,8 --buf 1=10,20,30,40,50,60,70,80 --out 2=8 --workdir work --dump-main"

echo "== stage 1: identity round-trip =="
sshto 45 "$RUN --expect 2=11,22,33,44,55,66,77,88 2>&1" | tee raw/stage1_identity.log

echo "== stage 1b: no-op identity splice (write-path fidelity) =="
sshto 45 "$RUN --expect 2=11,22,33,44,55,66,77,88 --splice _agc.main@0x22=1c 2>&1" | tee raw/stage1b_noop_splice.log

echo "== stage 3: op-select flip 1c->1d (expect a*b) =="
sshto 45 "$RUN --expect 2=10,40,90,160,250,360,490,640 --splice _agc.main@0x22=1d 2>&1" | tee raw/stage3_opselect_flip.log

echo "== cross-check: compiler native mul (must byte-match spliced 1d) =="
sshto 45 "cd $WORK && python3 agxtest.py --source kernels/mul.metal --function k --grid 8 --tg 8 \
  --buf 0=1,2,3,4,5,6,7,8 --buf 1=10,20,30,40,50,60,70,80 --out 2=8 --workdir work --dump-main \
  --expect 2=10,40,90,160,250,360,490,640 2>&1" | tee raw/stage3_crosscheck_native_mul.log

echo "== fault probes (device-fault characterization; host-protected) =="
sshto 45 "$RUN --splice _agc.main@0x34=00000000 2>&1" | tee raw/fault1_stop_zeroed.log
sshto 45 "$RUN --splice _agc.main@0x34=ffffffff 2>&1" | tee raw/fault2_stop_ff.log
sshto 45 "$RUN --splice _agc.main@0x22=ff 2>&1"       | tee raw/fault3_opselect_ff.log
FF56=$(python3 -c "print('ff'*56)")
sshto 50 "$RUN --splice _agc.main@0x00=$FF56 2>&1"    | tee raw/fault4_all_ff.log
echo "== recovery check after the fault(s) =="
sshto 45 "$RUN --expect 2=11,22,33,44,55,66,77,88 2>&1" | tee raw/fault_recovery_check.log

echo "== done; logs in raw/ =="
