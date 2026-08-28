// descpatch.m -- EXP-0136 direct resource-descriptor byte patcher.
//
// Technique (own, new code; reuses tools/iotrace UNCHANGED as a data source):
//   1. Build a real MTLSamplerState/MTLTexture via the PUBLIC Metal API with
//      explicit, Metal-legal parameters (our own choice) -- this makes Metal
//      itself allocate + populate its internal texture/sampler descriptor pool
//      and an (also Metal-internal) Tier-2 argument buffer, exactly as EXP-0011/
//      EXP-0015 already characterized (DATA-TRACE, read-only, via tools/iotrace).
//   2. Run ONE baseline compute dispatch to completion (waitUntilCompleted) so
//      the GPU is fully idle and every relevant byte is final and stable.
//   3. Trigger tools/iotrace's existing (unmodified, read-only) SIGUSR1 BO-dump
//      mechanism from THIS SAME live process. Parse the resulting bo_*.hex files
//      (plain text) to locate: (a) which BO holds the Tier-2 argument buffer (by
//      searching for our own output buffer's PUBLIC .gpuAddress as an 8-byte LE
//      needle -- a value we already know, not reverse-engineered here), and from
//      that (b) the 8-byte GPU VA pointer to the sampler (or texture) descriptor,
//      and (c) which dumped BO's [gpu_va,gpu_va+size) window contains that
//      pointer.
//   4. Because "client GPU memory is regular userspace VM registered into the GPU
//      VM" (EXP-0009 finding, re-derived structurally here from the same BODUMP
//      cpu= field iotrace already logs), the descriptor's CPU address in THIS
//      process is simply matched_bo.cpu + (desc_gpu_va - matched_bo.gpu_va) --
//      an ordinary pointer into our OWN process's address space. We read the
//      live bytes there (self-check against the dump-file copy), overwrite ONE
//      byte with (old & ~mask) | (value & mask) -- a surgical single-field
//      mutation, leaving every other bit exactly as Metal itself wrote it -- and
//      read back to confirm the write landed.
//   5. Encode + commit + waitUntilCompleted a SECOND, fresh dispatch reusing the
//      SAME MTLSamplerState/MTLTexture objects (so Metal reuses/repoints the
//      same descriptor slot) and read back the result.
//
// This is HW-PROBE (direct memory write; live hardware execution of a value we
// constructed) + DATA-TRACE (locating the write target via tools/iotrace's
// existing, unmodified, read-only capture) + OWN-SHADER (our own MSL, generated
// per-case). No Apple binary is disassembled, decompiled, or introspected
// anywhere in this file; only DATA (call parameters, buffer contents, our own
// compiled shader bytes) is read or written.
//
// Protocol: one JSON case file in argv[1]; exactly one JSON line on stdout.
// Requires DYLD_INSERT_LIBRARIES=<...>/iotrace.dylib and IOTRACE_DUMP_DIR set
// in the environment by the caller (run.py). This binary calls kill(getpid(),
// SIGUSR1) itself at the right moment(s) -- it does not send signals to any
// other process and never touches any Apple binary or process.
//
// Build:
//   clang -fobjc-arc -framework Metal -framework Foundation -O1 -o descpatch descpatch.m

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <dirent.h>
#include <time.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

static NSMutableDictionary *gResult;
static void setStatus(NSString *s) { gResult[@"status"] = s; }
static void setErrFromNSError(NSError *err, NSString *key) {
    if (err) {
        NSString *flat = [[err localizedDescription] stringByReplacingOccurrencesOfString:@"\n" withString:@" | "];
        gResult[key] = flat;
    }
}
static void emitAndExit(int code) {
    NSError *jerr = nil;
    NSData *d = [NSJSONSerialization dataWithJSONObject:gResult options:0 error:&jerr];
    if (!d) fprintf(stdout, "{\"status\":\"HARNESS_JSON_FAIL\",\"jerr\":\"%s\"}\n",
                    jerr ? [[jerr localizedDescription] UTF8String] : "?");
    else { fwrite([d bytes], 1, [d length], stdout); fprintf(stdout, "\n"); }
    fflush(stdout);
    exit(code);
}

// ---------------------------------------------------------------- BO dump parsing
typedef struct { uint64_t gpu_va, cpu, size; uint8_t *data; uint64_t data_len; char path[1024]; } BO;
#define MAX_BOS 256
static BO gBOs[MAX_BOS];
static int gNBOs = 0;

static int hexval(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

// Parse one bo_*.hex file written by tools/iotrace's dump_all_bos(). Format:
//   # BODUMP reason=... handle=N gpu_va=0xHEX cpu=0xHEX size=0xHEX read=0xHEX
//   00000000: XXXX XXXX XXXX XXXX ...
static int parse_bo_file(const char *path, BO *out) {
    FILE *f = fopen(path, "r");
    if (!f) return 0;
    char line[8192];
    memset(out, 0, sizeof(*out));
    strncpy(out->path, path, sizeof(out->path) - 1);
    uint8_t *buf = malloc(2 * 1024 * 1024);
    uint64_t len = 0;
    int haveHeader = 0;
    while (fgets(line, sizeof(line), f)) {
        if (line[0] == '#') {
            const char *p;
            if ((p = strstr(line, "gpu_va=0x"))) out->gpu_va = strtoull(p + 9, NULL, 16);
            if ((p = strstr(line, " cpu=0x")))   out->cpu    = strtoull(p + 7, NULL, 16);
            if ((p = strstr(line, "size=0x")))   out->size   = strtoull(p + 7, NULL, 16);
            haveHeader = 1;
            continue;
        }
        // "OFFSET: hex hex hex ..." -- hex bytes may have space separators every 4 bytes
        char *colon = strchr(line, ':');
        if (!colon) continue;
        const char *p = colon + 1;
        while (*p) {
            while (*p == ' ' || *p == '\n' || *p == '\r') p++;
            int hi = hexval(*p);
            if (hi < 0) break;
            int lo = hexval(*(p + 1));
            if (lo < 0) break;
            if (len < 2 * 1024 * 1024) buf[len++] = (uint8_t)((hi << 4) | lo);
            p += 2;
        }
    }
    fclose(f);
    out->data = buf;
    out->data_len = len;
    return haveHeader;
}

static void load_all_bo_dumps(const char *dumpdir) {
    DIR *d = opendir(dumpdir);
    if (!d) return;
    struct dirent *e;
    while ((e = readdir(d)) != NULL && gNBOs < MAX_BOS) {
        if (strncmp(e->d_name, "bo_", 3) != 0) continue;
        char path[1200];
        snprintf(path, sizeof(path), "%s/%s", dumpdir, e->d_name);
        if (parse_bo_file(path, &gBOs[gNBOs])) gNBOs++;
    }
    closedir(d);
}

static uint64_t rd64le(const uint8_t *p) {
    uint64_t v = 0;
    for (int i = 0; i < 8; i++) v |= (uint64_t)p[i] << (8 * i);
    return v;
}

// find 8-byte LE needle anywhere across all loaded BO dumps; returns bo index
// and byte offset within that BO, or -1 if not found.
static int find_needle(uint64_t needle, int *out_off) {
    uint8_t nb[8];
    for (int i = 0; i < 8; i++) nb[i] = (uint8_t)(needle >> (8 * i));
    for (int b = 0; b < gNBOs; b++) {
        BO *bo = &gBOs[b];
        if (bo->data_len < 8) continue;
        for (uint64_t o = 0; o + 8 <= bo->data_len; o++) {
            if (memcmp(bo->data + o, nb, 8) == 0) { *out_off = (int)o; return b; }
        }
    }
    return -1;
}

static int find_bo_containing_va(uint64_t va) {
    for (int b = 0; b < gNBOs; b++) {
        if (gBOs[b].size > 0 && va >= gBOs[b].gpu_va && va < gBOs[b].gpu_va + gBOs[b].size) return b;
    }
    return -1;
}

// Wait (bounded poll, no arbitrary long sleep) for at least N new bo_*.hex
// files matching a fresh mtime to appear in dumpdir after we raise SIGUSR1.
static int count_bo_files(const char *dumpdir) {
    DIR *d = opendir(dumpdir);
    if (!d) return 0;
    int n = 0;
    struct dirent *e;
    while ((e = readdir(d)) != NULL) if (strncmp(e->d_name, "bo_", 3) == 0) n++;
    closedir(d);
    return n;
}

// Empirically (debug spike, EXP-0136 work/spike/debug1.m): the AGX resource
// (selector-9) registration for Metal's internal Tier-2 argument-buffer BO is
// not synchronous with -endEncoding returning on this thread -- a dump fired
// immediately after -endEncoding can race ahead of it. A single SIGUSR1 dump
// after a fixed ~300ms settle reliably captured it in the spike (4/4 tap
// points, including pre-commit). So: trigger repeatedly with a real settle
// delay each time, and only stop once TWO CONSECUTIVE dumps report the same
// bo-file count (registry has stopped growing) -- bounded to ~3s total.
static void trigger_dump_and_wait(const char *dumpdir) {
    struct timespec settle = {0, 150 * 1000 * 1000}; // 150ms
    int prev = -1;
    for (int tries = 0; tries < 20; tries++) { // up to ~3s
        kill(getpid(), SIGUSR1);
        nanosleep(&settle, NULL);
        int n = count_bo_files(dumpdir);
        if (n > 0 && n == prev) return; // stabilized
        prev = n;
    }
}

static NSString *hex8(const uint8_t *b) {
    NSMutableString *s = [NSMutableString string];
    for (int i = 0; i < 8; i++) [s appendFormat:@"%02x", b[i]];
    return s;
}
static NSString *hexN(const uint8_t *b, int n) {
    NSMutableString *s = [NSMutableString string];
    for (int i = 0; i < n; i++) [s appendFormat:@"%02x", b[i]];
    return s;
}

// ------------------------------------------------------------------ MSL source
// EXACTLY the EXP-0011/EXP-0015 proven 3-slot binding shape (texture(0),
// sampler(0), buffer(0)=output ONLY -- no second buffer) so the Tier-2
// argument-buffer table layout (+0x00 tex ptr, +0x08 sampler ptr, +0x10
// inline buffer VA) is exactly what those experiments already characterized.
// uv/gradient values are baked in as source literals (per-case, like
// genkernels.py elsewhere in this repo) instead of a second bound buffer.
static NSString *kernelSourceSampler(NSString *texType, NSString *pixelDataType,
                                      float u, float v, float dx, float dy) {
    return [NSString stringWithFormat:
      @"#include <metal_stdlib>\n"
       "using namespace metal;\n"
       "kernel void k(%@<%@> t [[texture(0)]], sampler s [[sampler(0)]],\n"
       "              device float4* o [[buffer(0)]]) {\n"
       "  float2 uv = float2(%.9ff, %.9ff);\n"
       "  float2 grad_dx = float2(%.9ff, 0.0);\n"
       "  float2 grad_dy = float2(0.0, %.9ff);\n"
       "  o[0] = t.sample(s, uv, gradient2d(grad_dx, grad_dy));\n"
       "}\n", texType, pixelDataType, u, v, dx, dy];
}

// ------------------------------------------------------------------ main op
static void run_case(NSDictionary *c, id<MTLDevice> dev, const char *dumpdir) {
    NSError *err = nil;

    // ---- texture: NxN rgba8unorm, per-case authored pattern ----
    NSString *pattern = c[@"pattern"] ?: @"grid";
    int texW = [c[@"tex_w"] ?: @4 intValue];
    int texH = [c[@"tex_h"] ?: @4 intValue];
    int mipCount = [c[@"mip_count"] ?: @1 intValue];

    MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm
                                                                                    width:texW height:texH mipmapped:(mipCount > 1)];
    td.mipmapLevelCount = mipCount;
    td.usage = MTLTextureUsageShaderRead;
    td.storageMode = MTLStorageModeShared;
    id<MTLTexture> tex = [dev newTextureWithDescriptor:td];
    if (!tex) { setStatus(@"TEXTURE_CREATE_FAIL"); emitAndExit(1); }

    int w = texW, h = texH;
    for (int mip = 0; mip < mipCount; mip++) {
        uint8_t *px = malloc((size_t)w * h * 4);
        for (int y = 0; y < h; y++) {
            for (int x = 0; x < w; x++) {
                uint8_t r, g, b, a;
                if ([pattern isEqualToString:@"grid"]) {
                    r = (uint8_t)((y * texW + x) * 255 / (texW * texH - 1 > 0 ? texW * texH - 1 : 1));
                    g = 200; b = (uint8_t)(x * 20); a = 255;
                } else { // "ystripe": constant across X, alternates per row at mip0; box-filter
                         // averaging (which we author by hand, matching what a real box filter
                         // would produce) makes every mip>=1 uniformly 127 automatically because
                         // adjacent 0/255 row pairs average exactly.
                    int baseY = y << mip; // row in mip0 space (mip has half the rows each level)
                    // recompute directly: value = 127 if mip>0 else (row%2? 255:0)
                    if (mip == 0) { r = (baseY % 2) ? 255 : 0; } else { r = 127; }
                    g = 30; b = 30; a = 255;
                }
                px[(y * w + x) * 4 + 0] = r; px[(y * w + x) * 4 + 1] = g;
                px[(y * w + x) * 4 + 2] = b; px[(y * w + x) * 4 + 3] = a;
            }
        }
        MTLRegion region = MTLRegionMake2D(0, 0, w, h);
        [tex replaceRegion:region mipmapLevel:mip withBytes:px bytesPerRow:(NSUInteger)w * 4];
        free(px);
        w = w > 1 ? w / 2 : 1; h = h > 1 ? h / 2 : 1;
    }

    // ---- sampler: build via PUBLIC API with explicit Metal-legal params ----
    MTLSamplerDescriptor *sd = [MTLSamplerDescriptor new];
    NSDictionary *sp = c[@"sampler"] ?: @{};
    NSString *minf = sp[@"min_filter"] ?: @"nearest", *magf = sp[@"mag_filter"] ?: @"nearest", *mipf = sp[@"mip_filter"] ?: @"notMipmapped";
    sd.minFilter = [minf isEqualToString:@"linear"] ? MTLSamplerMinMagFilterLinear : MTLSamplerMinMagFilterNearest;
    sd.magFilter = [magf isEqualToString:@"linear"] ? MTLSamplerMinMagFilterLinear : MTLSamplerMinMagFilterNearest;
    if ([mipf isEqualToString:@"nearest"]) sd.mipFilter = MTLSamplerMipFilterNearest;
    else if ([mipf isEqualToString:@"linear"]) sd.mipFilter = MTLSamplerMipFilterLinear;
    else sd.mipFilter = MTLSamplerMipFilterNotMipmapped;

    NSDictionary *addrMap = @{@"clampToEdge": @(MTLSamplerAddressModeClampToEdge),
                               @"repeat": @(MTLSamplerAddressModeRepeat),
                               @"mirrorRepeat": @(MTLSamplerAddressModeMirrorRepeat),
                               @"clampToBorderColor": @(MTLSamplerAddressModeClampToBorderColor),
                               @"mirrorClampToEdge": @(MTLSamplerAddressModeMirrorClampToEdge)};
    NSString *as = sp[@"address_s"] ?: @"clampToEdge", *at = sp[@"address_t"] ?: @"clampToEdge";
    sd.sAddressMode = (MTLSamplerAddressMode)[addrMap[as] unsignedIntegerValue];
    sd.tAddressMode = (MTLSamplerAddressMode)[addrMap[at] unsignedIntegerValue];
    sd.maxAnisotropy = [sp[@"aniso"] ?: @1 unsignedIntegerValue];
    NSString *border = sp[@"border"];
    if (border) {
        if ([border isEqualToString:@"opaqueBlack"]) sd.borderColor = MTLSamplerBorderColorOpaqueBlack;
        else if ([border isEqualToString:@"opaqueWhite"]) sd.borderColor = MTLSamplerBorderColorOpaqueWhite;
        else sd.borderColor = MTLSamplerBorderColorTransparentBlack;
    }
    sd.normalizedCoordinates = YES;
    sd.lodMinClamp = 0.0f;
    sd.lodMaxClamp = (float)mipCount;
    id<MTLSamplerState> smp = [dev newSamplerStateWithDescriptor:sd];
    if (!smp) { setStatus(@"SAMPLER_CREATE_FAIL"); emitAndExit(1); }

    // ---- pipeline ----
    NSArray<NSNumber *> *uvgArr = c[@"uvg"] ?: @[@0.5, @0.5, @0.03125, @0.03125];
    NSString *msl = kernelSourceSampler(@"texture2d", @"float",
                                         [uvgArr[0] floatValue], [uvgArr[1] floatValue],
                                         [uvgArr[2] floatValue], [uvgArr[3] floatValue]);
    gResult[@"metal_source"] = msl;
    id<MTLLibrary> lib = [dev newLibraryWithSource:msl options:nil error:&err];
    if (!lib) { setStatus(@"COMPILE_FAIL"); setErrFromNSError(err, @"error"); emitAndExit(1); }
    id<MTLFunction> fn = [lib newFunctionWithName:@"k"];
    id<MTLComputePipelineState> pso = [dev newComputePipelineStateWithFunction:fn error:&err];
    if (!pso) { setStatus(@"PIPELINE_FAIL"); setErrFromNSError(err, @"error"); emitAndExit(1); }

    id<MTLBuffer> outBuf = [dev newBufferWithLength:16 options:MTLResourceStorageModeShared];
    memset([outBuf contents], 0xEE, 16);
    uint64_t outVA = (uint64_t)[outBuf gpuAddress];
    gResult[@"out_gpu_va"] = @(outVA);

    id<MTLCommandQueue> queue = [dev newCommandQueue];

    // ---- dispatch #1: baseline (unpatched). Locate the descriptor by dumping
    // BETWEEN endEncoding and commit -- i.e. BEFORE any submission to the GPU
    // and before Metal has any occasion to recycle a per-command-buffer
    // transient argument-buffer allocation (empirically: dumping AFTER
    // waitUntilCompleted sometimes misses the arg-buffer table entirely, most
    // likely because Metal's transient-pool allocator had already reused that
    // region for other work by the time the signal-driven dump ran; dumping
    // pre-commit removes that race for the READ side entirely, since nothing
    // has been submitted to the GPU yet). ----
    id<MTLCommandBuffer> cb1 = [queue commandBuffer];
    id<MTLComputeCommandEncoder> enc1 = [cb1 computeCommandEncoder];
    [enc1 setComputePipelineState:pso];
    [enc1 setTexture:tex atIndex:0];
    [enc1 setSamplerState:smp atIndex:0];
    [enc1 setBuffer:outBuf offset:0 atIndex:0];
    [enc1 dispatchThreads:MTLSizeMake(1, 1, 1) threadsPerThreadgroup:MTLSizeMake(1, 1, 1)];
    [enc1 endEncoding];

    trigger_dump_and_wait(dumpdir);
    gNBOs = 0;
    load_all_bo_dumps(dumpdir);
    gResult[@"n_bos_loaded"] = @(gNBOs);

    if (gNBOs == 0) { setStatus(@"NO_BO_DUMPS"); emitAndExit(1); }

    int slot2off = -1;
    int argBOidx = find_needle(outVA, &slot2off);
    if (argBOidx < 0) { setStatus(@"ARGBUF_NOT_FOUND"); emitAndExit(1); }
    gResult[@"arg_bo_gpu_va"] = @(gBOs[argBOidx].gpu_va);
    gResult[@"arg_bo_cpu"] = @(gBOs[argBOidx].cpu);
    gResult[@"slot2_off"] = @(slot2off);

    // slot order for this kernel shape (texture(0), sampler(0), buffer(0)=out,
    // buffer(1)=uvg): [[texture0 ptr]] @ slot2off-16, [[sampler0 ptr]] @ slot2off-8,
    // [[buffer0]] inline VA @ slot2off (found), [[buffer1]] inline VA @ slot2off+8.
    BO *argbo = &gBOs[argBOidx];
    if (slot2off < 16 || (uint64_t)slot2off + 8 > argbo->data_len) { setStatus(@"SLOT_LAYOUT_OOB"); emitAndExit(1); }
    uint64_t texPtr = rd64le(argbo->data + slot2off - 16);
    uint64_t smpPtr = rd64le(argbo->data + slot2off - 8);
    gResult[@"tex_desc_gpu_va"] = @(texPtr);
    gResult[@"smp_desc_gpu_va"] = @(smpPtr);

    NSString *target = c[@"target"] ?: @"sampler";
    uint64_t descVA = [target isEqualToString:@"texture"] ? texPtr : smpPtr;
    int descBOidx = find_bo_containing_va(descVA);
    if (descBOidx < 0) { setStatus(@"DESC_BO_NOT_FOUND"); emitAndExit(1); }
    BO *descbo = &gBOs[descBOidx];
    uint64_t descOffInBO = descVA - descbo->gpu_va;
    gResult[@"desc_bo_gpu_va"] = @(descbo->gpu_va);
    gResult[@"desc_bo_cpu"] = @(descbo->cpu);
    gResult[@"desc_off_in_bo"] = @(descOffInBO);

    if (descOffInBO + 8 > descbo->data_len) { setStatus(@"DESC_OOB_IN_DUMP"); emitAndExit(1); }
    uint8_t *descCPU = (uint8_t *)(uintptr_t)(descbo->cpu + descOffInBO); // LIVE pointer, our own process
    uint8_t dumpCopy[8];
    memcpy(dumpCopy, descbo->data + descOffInBO, 8);
    gResult[@"desc_bytes_from_dump"] = hex8(dumpCopy);
    uint8_t liveBaseline[8];
    memcpy(liveBaseline, descCPU, 8);
    gResult[@"desc_bytes_live_baseline"] = hex8(liveBaseline);
    gResult[@"dump_vs_live_match"] = @(memcmp(dumpCopy, liveBaseline, 8) == 0);

    // ---- apply patch(es) NOW, still pre-commit (list of {byte, mask, value}).
    // CRITICAL (established by a pilot spike, see PRE_REGISTRATION.md / RESULTS.md
    // "technique note"): patching AFTER a dispatch has already completed and then
    // reusing the SAME MTLSamplerState object in a FRESH encode/dispatch does NOT
    // work -- a spike showed Metal's -setSamplerState:atIndex: on the SECOND
    // encoder rewrites the descriptor pool entry back to the object's canonical
    // (creation-time) bytes before the second dispatch ever runs, silently
    // reverting the patch (a real, load-bearing negative finding in its own
    // right: the descriptor pool entry is not stable free-standing memory across
    // re-encodes of the same object -- Metal re-materializes it on every bind).
    // So: patch the SAME command buffer's descriptor bytes here, between
    // -endEncoding and -commit of the ONE dispatch we are about to run, and
    // never touch setSamplerState/setTexture again afterward. A separate
    // process run with an EMPTY patch list is the "baseline"/"control" case for
    // comparison (run.py invokes one process per case; verify.py diffs
    // patched-case vs its paired control-case pixel). ----
    uint8_t patched[8]; memcpy(patched, liveBaseline, 8);
    NSArray *patches = c[@"patch"];
    for (NSDictionary *p in patches) {
        int byteIdx = [p[@"byte"] intValue];
        uint8_t mask = (uint8_t)[p[@"mask"] intValue];
        uint8_t value = (uint8_t)[p[@"value"] intValue];
        if (byteIdx < 0 || byteIdx > 7) { setStatus(@"BAD_PATCH_SPEC"); emitAndExit(1); }
        patched[byteIdx] = (uint8_t)((patched[byteIdx] & ~mask) | (value & mask));
    }
    gResult[@"desc_bytes_patched_intended"] = hex8(patched);
    memcpy(descCPU, patched, 8); // LIVE in-process write, pre-commit
    uint8_t verify[8]; memcpy(verify, descCPU, 8);
    gResult[@"desc_bytes_patched_readback"] = hex8(verify);
    gResult[@"patch_write_verified"] = @(memcmp(verify, patched, 8) == 0);

    // ---- commit + run the (now patched, or unpatched if patch==[]) dispatch ----
    [cb1 commit];
    [cb1 waitUntilCompleted];
    NSString *st1 = @"OK";
    if ([cb1 status] == MTLCommandBufferStatusError) {
        st1 = @"CMDBUF_ERROR";
        setErrFromNSError([cb1 error], @"error");
    }
    float outPixel[4] = {-9, -9, -9, -9};
    if ([st1 isEqualToString:@"OK"]) memcpy(outPixel, [outBuf contents], 16);
    gResult[@"pixel"] = @[@(outPixel[0]), @(outPixel[1]), @(outPixel[2]), @(outPixel[3])];

    // ---- post-check: re-dump, confirm bytes were not silently reverted by
    // anything else during commit/execution (self-consistency, not a re-encode) ----
    trigger_dump_and_wait(dumpdir);
    uint8_t postBytes[8]; memcpy(postBytes, descCPU, 8);
    gResult[@"desc_bytes_post_commit"] = hex8(postBytes);
    gResult[@"bytes_stable_across_commit"] = @(memcmp(postBytes, patched, 8) == 0);

    setStatus(st1);
    emitAndExit([st1 isEqualToString:@"OK"] ? 0 : 1);
}

int main(int argc, char *argv[]) {
    @autoreleasepool {
        gResult = [NSMutableDictionary dictionary];
        if (argc < 2) { fprintf(stderr, "usage: descpatch CASE.json\n"); return 2; }
        NSData *cd = [NSData dataWithContentsOfFile:[NSString stringWithUTF8String:argv[1]]];
        if (!cd) { fprintf(stderr, "cannot read %s\n", argv[1]); return 2; }
        NSError *jerr = nil;
        NSDictionary *c = [NSJSONSerialization JSONObjectWithData:cd options:0 error:&jerr];
        if (!c) { fprintf(stderr, "bad json: %s\n", jerr ? [[jerr localizedDescription] UTF8String] : "?"); return 2; }
        gResult[@"case_id"] = c[@"case_id"] ?: @"?";
        const char *dumpdir = getenv("IOTRACE_DUMP_DIR");
        if (!dumpdir) { fprintf(stderr, "IOTRACE_DUMP_DIR not set\n"); return 2; }
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) { setStatus(@"NO_DEVICE"); emitAndExit(1); }
        run_case(c, dev, dumpdir);
    }
    return 0;
}
