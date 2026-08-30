#!/usr/bin/env python3
"""One-shot patcher: EXP-0163 harness/gfrun2.m -> EXP-0168 harness/gfrun3.m.

Kept in work/ (calibration/build scaffolding, NOT evidence) so the exact
transformation from the parent file is auditable rather than being a hand
retype. Run once; gfrun3.m is the committed artifact.
"""
import re
import sys

SRC = "harness/gfrun3.m"
t = open(SRC).read()
orig = t


def sub1(old, new, tag):
    global t
    n = t.count(old)
    if n != 1:
        sys.exit("PATCH %s: expected 1 occurrence, found %d" % (tag, n))
    t = t.replace(old, new)


# ---------------------------------------------------------------- header ----
hdr_end = t.index("#import <Metal/Metal.h>")
NEWHDR = r'''// gfrun3.m -- EXP-0168 authored render + splice + readback harness (G17P).
//
// LINEAGE (all of it OUR OWN code in this repository; no Apple source anywhere):
//   tools/agxtest/agxrender.m                       render splice-and-observe (EXP-0008)
//   tools/agxtest/agxrun_persist.m                  persistent request loop  (EXP-0005)
//   experiments/EXP-0129-.../harness/fsrun.m        MRT / depth / occlusion / buffers
//   experiments/EXP-0142-.../harness/*persist.m     texture binding + ERRDOM fault class
//   experiments/EXP-0143-.../harness/frun.m         persistent RENDER loop + the
//                                                   FIELD-SWEEP-PROTOCOL sec.7
//                                                   poison / sentinel / fresh-scratch
//                                                   mitigations
//   experiments/EXP-0155-.../harness/gfrun.m        sampled + writable texture arms
//   experiments/EXP-0163-.../harness/gfrun2.m       <-- DIRECT PARENT of this file:
//                                                   --rt-array, the five writable
//                                                   texture kinds, OUTBUF on render
//                                                   passes, PIX<rt>_S<slice>
//
// gfrun3.m is gfrun2.m VERBATIM plus exactly four additions, each required by a
// carrier in EXP-0168's RENDER arm and by nothing else. Everything gfrun2.m had
// is preserved unchanged: --samples, --resolve, MRT, --rt-array, depth,
// occlusion, the five writable-texture kinds, --out-buf, --buf-u32, absolute
// -offset splicing for the vertex / fragment / compute stages, the 0xDEADBEEF
// read-back poison, the re-read-and-memcmp integrity sentinel,
// MTLPipelineOptionFailOnBinaryArchiveMiss, the per-request fresh MTLLibrary and
// fresh scratch archive path, and the ERRDOM fault-classification print.
//
//   (1) --instances N
//       drawPrimitives:...instanceCount:N. REQUIRED by the pixel_order arm and
//       not optional: raster_order_group orders fragments that cover the SAME
//       pixel, so the only deterministic ordered carrier is a 1x1 target drawn N
//       times (N primitives, N fragments, one pixel). A WxH target with one
//       instance has W*H fragments at DIFFERENT pixels, between which the
//       hardware guarantees no order at all -- that carrier would measure noise.
//       This reproduces the shape EXP-0162 used for its `pixel_order` proof.
//
//   (2) --texw-reset r,g,b,a  /  --texwu-reset a,b,c,d
//       The per-request reset value of the RGBA32Float writable texture at
//       [[texture(1)]] and the RGBA32Uint writable texture at [[texture(9)]].
//       gfrun2.m hard-codes (-1,-2,-3,-4) / (0xFFFFFFF1..F4). The ordered-RMW
//       carriers accumulate INTO those textures, so their starting value is an
//       experiment parameter: it fixes the host-computed oracle and it is what
//       keeps "wrote nothing" distinguishable from "wrote zero". The defaults
//       are gfrun2.m's values, so an unparameterized run is byte-identical.
//
//   (3) per-request overrides, appended to the existing request grammar:
//           @inst=<n>              override --instances for THIS request
//           @buf<idx>=<hexbytes>   overwrite the leading bytes of the
//                                  --buf-u32 buffer bound at <idx>
//       This buys a DATA LADDER: re-running the byte-identical unmutated
//       program with different uniform data must move the observation. That is
//       a detection-power demonstration with ZERO splice hazard, which matters
//       because EXP-0163 measured 88 device resets in 50 s and nearly all of
//       them came from control splices into opcode / register-number bytes.
//       Unknown or unbound indices are reported as `OVR <idx> skipped` rather
//       than silently ignored. Requests with no '@' token behave exactly as in
//       gfrun2.m.
//
//   (4) TARGET line at startup: the device name reported by Metal, so the
//       target of a capture is recorded from the live device and never from a
//       literal in a harness (EXP-0138 hard-coded its host string; EXP-0168
//       does not repeat that).
//
// CLEAN-ROOM: public Metal API only, on shaders compiled from OUR OWN MSL.
// No Apple binary is disassembled, decompiled, symbol-dumped or introspected.
//
// Build (on the G17P, which has full Xcode):
//   clang -fobjc-arc -framework Metal -framework Foundation -O2 -o gfrun3 gfrun3.m
//
// One-shot:
//   ./gfrun3 --source S.metal --vertex V --fragment F --archive base.bin \
//            --scratch work/scratch.bin --color-format 125 --width 8 --height 8 \
//            --splice 0x1234=2f0d54...
// Persistent (stdin request loop, one live MTLDevice for the process lifetime):
//   ./gfrun3 ... --persist
//   request:  <reqid> <nsplices> [<off>=<hex> ...] [@inst=<n>] [@buf<i>=<hex>]
//   response: REQ id / STATUS ... / SENTINEL ... / [OVR ...] / PIX <hex>
//             / [PIX<rt>_S<slice> <hex>] / [DEPTH <hex>] / [OCC n]
//             / [TEXW <hex>] [TEXWA<n> <hex>] [TEXW3 <hex>] [TEXWH <hex>]
//             / [TEXWU <hex>] / [OUTBUF <hex>] / DONE id
//
// STATUS values: OK | COMPILE_FAIL | FUNCTION_MISSING | ARCHIVE_FAIL |
//                PIPELINE_MISS | PIPELINE_FAIL | CMDBUF_ERROR | BAD_REQUEST |
//                SENTINEL_FAIL

'''
t = NEWHDR + t[hdr_end:]

# ------------------------------------------------------------- structures ----
sub1("""typedef struct { size_t off; unsigned char *bytes; size_t len; } SpliceSpec;
typedef struct { int idx; unsigned n; unsigned *vals; } BufU32Spec;
""",
"""typedef struct { size_t off; unsigned char *bytes; size_t len; } SpliceSpec;
typedef struct { int idx; unsigned n; unsigned *vals; } BufU32Spec;

// EXP-0168 addition (3): per-request overrides. A request that carries none of
// these behaves exactly as an EXP-0163 request did.
#define MAX_BUF_OVR 8
typedef struct { int idx; unsigned char *bytes; size_t len; } BufOvr;
typedef struct {
    int have_inst; long inst;
    int nbo; BufOvr bo[MAX_BUF_OVR];
} ReqOv;
static void reqov_free(ReqOv *ov) {
    for (int i = 0; i < ov->nbo; i++) free(ov->bo[i].bytes);
    ov->nbo = 0;
}
""", "structs")

# ----------------------------------------------------------------- globals ---
sub1("static BufU32Spec gBufs[8]; static int gNBufs = 0;",
     "static BufU32Spec gBufs[8]; static int gNBufs = 0;\n"
     "// EXP-0168 addition (1): instance count for the ordered-RMW carriers.\n"
     "static long gInstances = 1;", "ginstances")

sub1("static const float TEXW_RESET[4] = {-1.0f, -2.0f, -3.0f, -4.0f};",
"""// EXP-0168 addition (2): the writable-texture reset values are parameters, not
// constants, because the ordered-RMW carriers accumulate into them and the host
// oracle is a function of the starting value. Defaults reproduce EXP-0163.
static float TEXW_RESET[4] = {-1.0f, -2.0f, -3.0f, -4.0f};

// IEEE-754 binary32 -> binary16, round-to-nearest-even, in exact integer
// arithmetic (overflow -> inf, subnormals handled). Needed only so the half
// writable texture's reset tracks --texw-reset. Our own code; the algorithm is
// the published IEEE-754 rule.
static unsigned short f32_to_f16(float f) {
    unsigned u; memcpy(&u, &f, 4);
    unsigned s = (u >> 16) & 0x8000u;
    int e = (int)((u >> 23) & 0xFFu);
    unsigned m = u & 0x7FFFFFu;
    if (e == 0xFF) return (unsigned short)(s | (m ? 0x7E00u : 0x7C00u));
    int ne = e - 127 + 15;
    if (ne >= 0x1F) return (unsigned short)(s | 0x7C00u);
    if (ne > 0) {
        unsigned r = ((unsigned)ne << 10) | (m >> 13);
        unsigned rem = m & 0x1FFFu;
        if (rem > 0x1000u || (rem == 0x1000u && (r & 1u))) r++;
        return (unsigned short)((s | r) & 0xFFFFu);
    }
    int shift = 14 - ne;
    if (shift > 31) return (unsigned short)s;
    unsigned mm = m | 0x800000u;
    unsigned r = mm >> shift;
    unsigned rem = mm & ((1u << shift) - 1u);
    unsigned half = 1u << (shift - 1);
    if (rem > half || (rem == half && (r & 1u))) r++;
    return (unsigned short)((s | r) & 0xFFFFu);
}""", "texwreset")

sub1("""static const unsigned TEXWU_RESET[4] = {0xFFFFFFF1u, 0xFFFFFFF2u,
                                        0xFFFFFFF3u, 0xFFFFFFF4u};""",
     """static unsigned TEXWU_RESET[4] = {0xFFFFFFF1u, 0xFFFFFFF2u,
                                  0xFFFFFFF3u, 0xFFFFFFF4u};""", "texwureset")

# --------------------------------------------------- half reset from float ---
sub1("""        // half sentinel (-1,-2,-3,-4): exact in half, so no quantisation noise.
        const unsigned short H4[4] = {0xBC00, 0xC000, 0xC200, 0xC400};""",
     """        // EXP-0168: the half sentinel now TRACKS --texw-reset instead of being
        // the frozen (-1,-2,-3,-4) bit pattern, so a carrier that accumulates
        // into the half texture has a host-computable starting value. With the
        // default reset this yields 0xBC00/0xC000/0xC200/0xC400 exactly as in
        // EXP-0163.
        unsigned short H4[4];
        for (int q = 0; q < 4; q++) H4[q] = f32_to_f16(TEXW_RESET[q]);""",
     "halfreset")

# ------------------------------------------------------ doRender signature ---
sub1("static int doRender(const char *rid, SpliceSpec *spl, int nspl) {",
     "static int doRender(const char *rid, SpliceSpec *spl, int nspl, const ReqOv *ov) {",
     "dorender-sig")

# ------------------------------------------------------- buffer overrides ----
sub1("""    id<MTLBuffer> mbufs[8]; memset(mbufs, 0, sizeof(mbufs));
    for (int i = 0; i < gNBufs; i++) {
        mbufs[i] = [gDev newBufferWithLength:gBufs[i].n * 4 options:MTLResourceStorageModeShared];
        memcpy([mbufs[i] contents], gBufs[i].vals, gBufs[i].n * 4);
    }""",
"""    id<MTLBuffer> mbufs[8]; memset(mbufs, 0, sizeof(mbufs));
    for (int i = 0; i < gNBufs; i++) {
        mbufs[i] = [gDev newBufferWithLength:gBufs[i].n * 4 options:MTLResourceStorageModeShared];
        memcpy([mbufs[i] contents], gBufs[i].vals, gBufs[i].n * 4);
    }
    // EXP-0168 addition (3): per-request uniform overrides (the zero-hazard
    // DATA LADDER). Applied AFTER the --buf-u32 seed so an override replaces
    // only the leading bytes it names. Every override reports applied/skipped,
    // so a ladder case can never be scored as inert because its data silently
    // did not change.
    if (ov) {
        for (int k = 0; k < ov->nbo; k++) {
            int hit = -1;
            for (int i = 0; i < gNBufs; i++) if (gBufs[i].idx == ov->bo[k].idx) hit = i;
            if (hit < 0 || ov->bo[k].len > (size_t)gBufs[hit].n * 4) {
                printf("OVR %d skipped\\n", ov->bo[k].idx);
                continue;
            }
            memcpy([mbufs[hit] contents], ov->bo[k].bytes, ov->bo[k].len);
            printf("OVR %d applied %zu\\n", ov->bo[k].idx, ov->bo[k].len);
        }
    }""", "bufovr")

# ------------------------------------------------------------- draw call -----
sub1("    [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];",
"""    // EXP-0168 addition (1): instanced draw. instanceCount == 1 reproduces
    // EXP-0163's call exactly.
    NSUInteger ninst = (NSUInteger)((ov && ov->have_inst) ? ov->inst : gInstances);
    if (ninst < 1) ninst = 1;
    [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3
          instanceCount:ninst];""", "draw")

# ------------------------------------------------------------ request loop ---
sub1("""static void handle_request(char *line) {
    char *save = NULL;
    char *rid = strtok_r(line, " \\t\\r\\n", &save);
    if (!rid) return;
    char *sn = strtok_r(NULL, " \\t\\r\\n", &save);
    int n = sn ? (int)strtol(sn, NULL, 0) : 0;
    if (n < 0 || n > 32) { respond_fail(rid, "BAD_REQUEST", "nsplices out of range", nil); return; }
    SpliceSpec spl[32]; memset(spl, 0, sizeof spl);
    for (int i = 0; i < n; i++) {
        char *tok = strtok_r(NULL, " \\t\\r\\n", &save);
        if (!tok) { respond_fail(rid, "BAD_REQUEST", "missing splice", nil); goto cleanup; }
        char *eq = strchr(tok, '=');
        if (!eq) { respond_fail(rid, "BAD_REQUEST", "splice wants OFF=HEX", nil); goto cleanup; }
        *eq = 0;
        spl[i].off = strtoul(tok, NULL, 0);
        size_t blen = strlen(eq + 1) / 2;
        spl[i].bytes = malloc(blen ? blen : 1);
        for (size_t k = 0; k < blen; k++) { unsigned v; sscanf(eq + 1 + k * 2, "%2x", &v); spl[i].bytes[k] = (unsigned char)v; }
        spl[i].len = blen;
    }
    doRender(rid, spl, n);
cleanup:
    for (int i = 0; i < n; i++) free(spl[i].bytes);
}""",
"""static void handle_request(char *line) {
    char *save = NULL;
    char *rid = strtok_r(line, " \\t\\r\\n", &save);
    if (!rid) return;
    char *sn = strtok_r(NULL, " \\t\\r\\n", &save);
    int n = sn ? (int)strtol(sn, NULL, 0) : 0;
    ReqOv ov; memset(&ov, 0, sizeof ov);
    if (n < 0 || n > 32) { respond_fail(rid, "BAD_REQUEST", "nsplices out of range", nil); return; }
    SpliceSpec spl[32]; memset(spl, 0, sizeof spl);
    for (int i = 0; i < n; i++) {
        char *tok = strtok_r(NULL, " \\t\\r\\n", &save);
        if (!tok) { respond_fail(rid, "BAD_REQUEST", "missing splice", nil); goto cleanup; }
        char *eq = strchr(tok, '=');
        if (!eq) { respond_fail(rid, "BAD_REQUEST", "splice wants OFF=HEX", nil); goto cleanup; }
        *eq = 0;
        spl[i].off = strtoul(tok, NULL, 0);
        size_t blen = strlen(eq + 1) / 2;
        spl[i].bytes = malloc(blen ? blen : 1);
        for (size_t k = 0; k < blen; k++) { unsigned v; sscanf(eq + 1 + k * 2, "%2x", &v); spl[i].bytes[k] = (unsigned char)v; }
        spl[i].len = blen;
    }
    // EXP-0168 addition (3): optional trailing '@' override tokens.
    for (char *tok = strtok_r(NULL, " \\t\\r\\n", &save); tok;
         tok = strtok_r(NULL, " \\t\\r\\n", &save)) {
        if (tok[0] != '@') { respond_fail(rid, "BAD_REQUEST", "trailing token wants '@'", nil); goto cleanup; }
        char *eq = strchr(tok, '=');
        if (!eq) { respond_fail(rid, "BAD_REQUEST", "override wants @key=value", nil); goto cleanup; }
        *eq = 0;
        if (strcmp(tok, "@inst") == 0) {
            ov.have_inst = 1; ov.inst = strtol(eq + 1, NULL, 0);
        } else if (strncmp(tok, "@buf", 4) == 0) {
            if (ov.nbo >= MAX_BUF_OVR) { respond_fail(rid, "BAD_REQUEST", "too many @buf", nil); goto cleanup; }
            size_t blen = strlen(eq + 1) / 2;
            BufOvr *b = &ov.bo[ov.nbo++];
            b->idx = (int)strtol(tok + 4, NULL, 0);
            b->bytes = malloc(blen ? blen : 1);
            b->len = blen;
            for (size_t k = 0; k < blen; k++) { unsigned v; sscanf(eq + 1 + k * 2, "%2x", &v); b->bytes[k] = (unsigned char)v; }
        } else {
            respond_fail(rid, "BAD_REQUEST", "unknown override key", nil); goto cleanup;
        }
    }
    doRender(rid, spl, n, &ov);
cleanup:
    for (int i = 0; i < n; i++) free(spl[i].bytes);
    reqov_free(&ov);
}""", "handle_request")

# --------------------------------------------------------------- options -----
sub1("""       O_TEXSAMP, O_TEXWRITE, O_TEXEXTRA, O_TEXDEPTH,
       /* EXP-0163 */ O_RTARRAY, O_TWARR, O_TW3D, O_TWHALF, O_TWUINT };""",
     """       O_TEXSAMP, O_TEXWRITE, O_TEXEXTRA, O_TEXDEPTH,
       /* EXP-0163 */ O_RTARRAY, O_TWARR, O_TW3D, O_TWHALF, O_TWUINT,
       /* EXP-0168 */ O_INSTANCES, O_TWRESET, O_TWURESET };""", "enum")

sub1("""    {"tex-write-uint", required_argument, 0, O_TWUINT},
    {0, 0, 0, 0}""",
     """    {"tex-write-uint", required_argument, 0, O_TWUINT},
    /* EXP-0168 */
    {"instances", required_argument, 0, O_INSTANCES},
    {"texw-reset", required_argument, 0, O_TWRESET},
    {"texwu-reset", required_argument, 0, O_TWURESET},
    {0, 0, 0, 0}""", "longopts")

sub1("""        case O_TWUINT: gWantTexWUint = YES; sscanf(optarg, "%ld,%ld", &gTWU[0], &gTWU[1]); break;""",
     """        case O_TWUINT: gWantTexWUint = YES; sscanf(optarg, "%ld,%ld", &gTWU[0], &gTWU[1]); break;
        case O_INSTANCES: gInstances = strtol(optarg, NULL, 0); break;
        case O_TWRESET: sscanf(optarg, "%f,%f,%f,%f", &TEXW_RESET[0], &TEXW_RESET[1],
                               &TEXW_RESET[2], &TEXW_RESET[3]); break;
        case O_TWURESET: sscanf(optarg, "%u,%u,%u,%u", &TEXWU_RESET[0], &TEXWU_RESET[1],
                                &TEXWU_RESET[2], &TEXWU_RESET[3]); break;""", "optcases")

# --------------------------------------------------------------- one-shot ----
sub1("    if (!persist) { int rc = doRender(NULL, spl, nspl); return rc; }",
     "    ReqOv noov; memset(&noov, 0, sizeof noov);\n"
     "    if (!persist) { int rc = doRender(NULL, spl, nspl, &noov); return rc; }",
     "oneshot")

# ---------------------------------------------------------------- TARGET -----
sub1("""    printf("READY %s\\n", [[gDev name] UTF8String]);
    fflush(stdout);""",
     """    // EXP-0168 addition (4): the target identity is READ FROM THE LIVE DEVICE
    // and echoed, so a capture records what it actually ran on.
    printf("TARGET %s registryID=%llu instances=%ld\\n", [[gDev name] UTF8String],
           (unsigned long long)[gDev registryID], gInstances);
    printf("READY %s\\n", [[gDev name] UTF8String]);
    fflush(stdout);""", "target")

assert t != orig
open(SRC, "w").write(t)
print("patched OK, %d -> %d lines" % (orig.count("\n") + 1, t.count("\n") + 1))
