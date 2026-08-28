// EXP-0122 harness (public Metal API only; OWN-SHADER + HW-PROBE clean-room categories).
//
// Single binary, one case per invocation (per repo convention: isolate fault-prone work in
// its own process). argv[1] selects the case class; argv[2] is a JSON object of parameters
// (schema defined and frozen by run.py, the single authoritative source -- this harness does
// not invent parameters). Exactly one JSON object is printed to stdout on one line, followed
// by a newline and an explicit fflush; all diagnostics go to stderr. Every record has three
// top-level keys: "meta" (case identity, echoes input), "gated" (facts this experiment
// expects to be deterministic hardware/software facts, safe to byte-compare across capture
// runs) and "raw" (anything that can vary run-to-run -- GPU virtual addresses above all --
// which is reported but never byte-compared). This split is enforced structurally here and
// re-checked by verify.py.
//
// In-process watchdogs: compile budget exit 97, dispatch budget exit 98 (matches the
// convention already used by EXP-0076/EXP-0100). The outer Python runner additionally wraps
// every process in a subprocess timeout as a second, independent belt.

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#import <mach/mach_time.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void diag(NSString *fmt, ...) NS_FORMAT_FUNCTION(1,2);
static void diag(NSString *fmt, ...) {
    va_list args;
    va_start(args, fmt);
    NSString *s = [[NSString alloc] initWithFormat:fmt arguments:args];
    va_end(args);
    fputs([s UTF8String], stderr);
    fputc('\n', stderr);
}

static void emit(NSDictionary *record) {
    NSError *err = nil;
    NSData *data = [NSJSONSerialization dataWithJSONObject:record options:0 error:&err];
    if (!data) {
        fprintf(stderr, "FATAL: JSON serialize failed: %s\n", err.localizedDescription.UTF8String);
        fflush(stderr);
        exit(3);
    }
    fwrite(data.bytes, 1, data.length, stdout);
    fputc('\n', stdout);
    fflush(stdout);
}

static NSString *hexOf(const void *bytes, size_t len) {
    static const char *hexd = "0123456789abcdef";
    NSMutableData *out = [NSMutableData dataWithLength:len * 2];
    char *o = (char *)out.mutableBytes;
    const unsigned char *b = (const unsigned char *)bytes;
    for (size_t i = 0; i < len; i++) {
        o[2*i]   = hexd[(b[i] >> 4) & 0xF];
        o[2*i+1] = hexd[b[i] & 0xF];
    }
    return [[NSString alloc] initWithData:out encoding:NSASCIIStringEncoding];
}

static NSString *decU64(uint64_t v) {
    return [NSString stringWithFormat:@"%llu", (unsigned long long)v];
}

static NSString *hex64(uint64_t v) {
    return [NSString stringWithFormat:@"0x%llx", (unsigned long long)v];
}

static uint64_t parseU64Dec(NSString *s) {
    return strtoull(s.UTF8String, NULL, 10);
}

// Fill buffer contents with the frozen pattern F(i) = (0xA5 + 0x1B*i) mod 256.
static void fillPattern(void *p, size_t len) {
    unsigned char *b = (unsigned char *)p;
    for (size_t i = 0; i < len; i++) b[i] = (unsigned char)((0xA5 + 0x1B * i) & 0xFF);
}
static void fillConst(void *p, size_t len, unsigned char v) {
    memset(p, v, len);
}
static BOOL allEqualConst(const void *p, size_t len, unsigned char v) {
    const unsigned char *b = (const unsigned char *)p;
    for (size_t i = 0; i < len; i++) if (b[i] != v) return NO;
    return YES;
}

// ---------------------------------------------------------------------------
// Watchdogs: fire _exit(code) if not cancelled within ms milliseconds.
// ---------------------------------------------------------------------------
static dispatch_source_t armWatchdog(NSUInteger ms, int code) {
    dispatch_source_t t = dispatch_source_create(DISPATCH_SOURCE_TYPE_TIMER, 0, 0,
                                                  dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_DEFAULT, 0));
    dispatch_source_set_timer(t, dispatch_time(DISPATCH_TIME_NOW, (int64_t)ms * NSEC_PER_MSEC),
                               DISPATCH_TIME_FOREVER, 0);
    dispatch_source_set_event_handler(t, ^{
        fprintf(stderr, "WATCHDOG fired code=%d\n", code);
        fflush(stderr);
        fflush(stdout);
        _exit(code);
    });
    dispatch_resume(t);
    return t;
}
static void disarmWatchdog(dispatch_source_t t) {
    dispatch_source_cancel(t);
}

// ---------------------------------------------------------------------------
// Kernel loading helper: reads MSL source from disk (OWN-SHADER, compiled at runtime).
// ---------------------------------------------------------------------------
static id<MTLLibrary> loadLibrary(id<MTLDevice> dev, NSString *path, NSUInteger watchdogMs, NSError **outErr) {
    NSError *rerr = nil;
    NSString *src = [NSString stringWithContentsOfFile:path encoding:NSUTF8StringEncoding error:&rerr];
    if (!src) { if (outErr) *outErr = rerr; return nil; }
    MTLCompileOptions *opts = [MTLCompileOptions new];
    opts.fastMathEnabled = NO;
    if (@available(macOS 13.0, *)) { opts.mathMode = MTLMathModeSafe; }
    dispatch_source_t wd = armWatchdog(watchdogMs, 97);
    NSError *cerr = nil;
    id<MTLLibrary> lib = [dev newLibraryWithSource:src options:opts error:&cerr];
    disarmWatchdog(wd);
    if (!lib && outErr) *outErr = cerr;
    return lib;
}

static NSDictionary *cbStatusInfo(id<MTLCommandBuffer> cb) {
    NSString *errDesc = cb.error ? cb.error.localizedDescription : @"";
    return @{ @"cb_status": @((long)cb.status), @"err": errDesc ?: @"" };
}

// ---------------------------------------------------------------------------
// Case: caps -- device capability query, no dispatch.
// ---------------------------------------------------------------------------
static void case_caps(id<MTLDevice> dev, NSDictionary *params) {
    mach_timebase_info_data_t tb; mach_timebase_info(&tb);
    NSMutableDictionary *families = [NSMutableDictionary dictionary];
    NSArray *famNames = @[@"apple1",@"apple2",@"apple3",@"apple4",@"apple5",@"apple6",
                          @"apple7",@"apple8",@"apple9",@"apple10"];
    MTLGPUFamily famVals[] = {MTLGPUFamilyApple1,MTLGPUFamilyApple2,MTLGPUFamilyApple3,
        MTLGPUFamilyApple4,MTLGPUFamilyApple5,MTLGPUFamilyApple6,MTLGPUFamilyApple7,
        MTLGPUFamilyApple8,MTLGPUFamilyApple9,MTLGPUFamilyApple10};
    for (NSUInteger i = 0; i < famNames.count; i++) {
        families[famNames[i]] = @([dev supportsFamily:famVals[i]]);
    }
    NSUInteger tileBase = dev.sparseTileSizeInBytes;
    NSUInteger tile16 = 0, tile64 = 0, tile256 = 0;
    BOOL havePageSizeAPI = NO;
    if (@available(macOS 13.0, *)) {
        havePageSizeAPI = YES;
        tile16  = [dev sparseTileSizeInBytesForSparsePageSize:MTLSparsePageSize16];
        tile64  = [dev sparseTileSizeInBytesForSparsePageSize:MTLSparsePageSize64];
        tile256 = [dev sparseTileSizeInBytesForSparsePageSize:MTLSparsePageSize256];
    }
    NSDictionary *gated = @{
        @"device_name": dev.name ?: @"",
        @"has_unified_memory": @(dev.hasUnifiedMemory),
        @"max_buffer_length": decU64(dev.maxBufferLength),
        @"sparse_tile_size_in_bytes_default": @(tileBase),
        @"have_page_size_api": @(havePageSizeAPI),
        @"sparse_tile_size_in_bytes_page16": @(tile16),
        @"sparse_tile_size_in_bytes_page64": @(tile64),
        @"sparse_tile_size_in_bytes_page256": @(tile256),
        @"gpu_families": families,
        @"mach_timebase_numer": @(tb.numer),
        @"mach_timebase_denom": @(tb.denom),
    };
    NSDictionary *raw = @{
        @"recommended_max_working_set_size": decU64(dev.recommendedMaxWorkingSetSize),
        @"registry_id": decU64(dev.registryID),
    };
    emit(@{ @"meta": @{@"case": @"caps"}, @"gated": gated, @"raw": raw });
}

// ---------------------------------------------------------------------------
// Case: align -- heapBufferSizeAndAlign sweep + actual allocation, no dispatch.
// params: {"cases":[{"length":N,"mode":"shared"|"private"}, ...]}
// ---------------------------------------------------------------------------
static MTLResourceOptions optsForMode(NSString *mode) {
    if ([mode isEqualToString:@"private"]) return MTLResourceStorageModePrivate;
    return MTLResourceStorageModeShared;
}

static void case_align(id<MTLDevice> dev, NSDictionary *params) {
    NSArray *cases = params[@"cases"];
    NSMutableArray *gatedRows = [NSMutableArray array];
    NSMutableArray *rawRows = [NSMutableArray array];
    for (NSDictionary *c in cases) {
        unsigned long long length = [c[@"length"] unsignedLongLongValue];
        NSString *mode = c[@"mode"];
        MTLResourceOptions opt = optsForMode(mode);
        MTLSizeAndAlign sa = [dev heapBufferSizeAndAlignWithLength:(NSUInteger)length options:opt];
        id<MTLBuffer> buf = [dev newBufferWithLength:(NSUInteger)length options:opt];
        BOOL ok = (buf != nil);
        [gatedRows addObject:@{
            @"length": decU64(length), @"mode": mode,
            @"heap_size": decU64(sa.size), @"heap_align": decU64(sa.align),
            @"alloc_ok": @(ok),
        }];
        [rawRows addObject:@{
            @"length": decU64(length), @"mode": mode,
            @"gpu_addr_hex": ok ? hex64(buf.gpuAddress) : @"0x0",
        }];
        buf = nil;
    }
    emit(@{ @"meta": @{@"case": @"align", @"n": @(cases.count)},
            @"gated": @{@"rows": gatedRows}, @"raw": @{@"rows": rawRows} });
}

// ---------------------------------------------------------------------------
// Case: addrsurvey -- repeated alloc/dealloc sequence, address reuse survey.
// params: {"seq":[{"length":N,"mode":"shared"|"private"}, ...], "passes": 2}
// ---------------------------------------------------------------------------
static void case_addrsurvey(id<MTLDevice> dev, NSDictionary *params) {
    NSArray *seq = params[@"seq"];
    NSUInteger passes = [params[@"passes"] unsignedIntegerValue];
    NSMutableArray *passesRaw = [NSMutableArray array];
    NSMutableArray *passesGated = [NSMutableArray array];
    for (NSUInteger p = 0; p < passes; p++) {
        @autoreleasepool {
            NSMutableArray *bufs = [NSMutableArray array];
            NSMutableArray *rawEntries = [NSMutableArray array];
            NSMutableArray *gatedEntries = [NSMutableArray array];
            for (NSDictionary *e in seq) {
                unsigned long long length = [e[@"length"] unsignedLongLongValue];
                NSString *mode = e[@"mode"];
                id<MTLBuffer> b = [dev newBufferWithLength:(NSUInteger)length options:optsForMode(mode)];
                BOOL ok = (b != nil);
                uint64_t addr = ok ? b.gpuAddress : 0;
                [rawEntries addObject:@{@"length": decU64(length), @"mode": mode,
                                         @"gpu_addr_hex": hex64(addr)}];
                [gatedEntries addObject:@{@"length": decU64(length), @"mode": mode,
                                           @"alloc_ok": @(ok),
                                           @"addr_mod_16384": @(ok ? (long long)(addr % 16384) : -1)}];
                if (ok) [bufs addObject:b];
            }
            [passesRaw addObject:rawEntries];
            [passesGated addObject:gatedEntries];
            [bufs removeAllObjects];
        }
    }
    emit(@{ @"meta": @{@"case": @"addrsurvey", @"passes": @(passes), @"n": @(seq.count)},
            @"gated": @{@"passes": passesGated}, @"raw": @{@"passes": passesRaw} });
}

// ---------------------------------------------------------------------------
// Case: maxlen_boundary -- allocate at/around device.maxBufferLength.
// ---------------------------------------------------------------------------
static void tryAlloc(id<MTLDevice> dev, NSString *label, unsigned long long length, NSString *mode,
                      NSMutableArray *gated, NSMutableArray *raw) {
    MTLResourceOptions opt = optsForMode(mode);
    id<MTLBuffer> b = [dev newBufferWithLength:(NSUInteger)length options:opt];
    BOOL ok = (b != nil);
    [gated addObject:@{@"label": label, @"mode": mode, @"requested_length": decU64(length), @"alloc_ok": @(ok)}];
    [raw addObject:@{@"label": label, @"mode": mode, @"gpu_addr_hex": ok ? hex64(b.gpuAddress) : @"0x0"}];
}

static void case_maxlen_boundary(id<MTLDevice> dev, NSDictionary *params) {
    unsigned long long maxlen = dev.maxBufferLength;
    MTLSizeAndAlign sa = [dev heapBufferSizeAndAlignWithLength:(NSUInteger)maxlen options:MTLResourceStorageModePrivate];
    NSMutableArray *gated = [NSMutableArray array];
    NSMutableArray *raw = [NSMutableArray array];
    for (NSString *mode in @[@"shared", @"private"]) {
        tryAlloc(dev, @"max", maxlen, mode, gated, raw);
        tryAlloc(dev, @"max_plus_1", maxlen + 1, mode, gated, raw);
        tryAlloc(dev, @"max_plus_align", maxlen + sa.align, mode, gated, raw);
        tryAlloc(dev, @"max_minus_1", maxlen - 1, mode, gated, raw);
        tryAlloc(dev, @"huge_1<<40", (1ULL << 40), mode, gated, raw);
    }
    emit(@{ @"meta": @{@"case": @"maxlen_boundary", @"max_buffer_length": decU64(maxlen),
                       @"heap_align": decU64(sa.align)},
            @"gated": @{@"rows": gated}, @"raw": @{@"rows": raw} });
}

// ---------------------------------------------------------------------------
// Case: guard_read / guard_store -- fixed-width (32-bit) access at a runtime byte offset
// from a small owned buffer, at frozen boundary distances (including engineered
// address-space-wraparound values).
// params: {"base_len":64,"mode":"shared","off_dec":"<u64 decimal>","name":"...",
//          "compile_watchdog_ms":..., "dispatch_watchdog_ms":..., "kernel_path":"..."}
// ---------------------------------------------------------------------------
static void case_guard(id<MTLDevice> dev, NSDictionary *params, BOOL isStore) {
    NSString *name = params[@"name"];
    unsigned long long baseLen = [params[@"base_len"] unsignedLongLongValue];
    NSString *mode = params[@"mode"];
    uint64_t off = parseU64Dec(params[@"off_dec"]);
    NSUInteger cwd = [params[@"compile_watchdog_ms"] unsignedIntegerValue];
    NSUInteger dwd = [params[@"dispatch_watchdog_ms"] unsignedIntegerValue];
    NSString *kernelPath = params[@"kernel_path"];
    const uint32_t storePattern = 0xDEADBEEFu;

    NSError *lerr = nil;
    id<MTLLibrary> lib = loadLibrary(dev, kernelPath, cwd, &lerr);
    if (!lib) {
        emit(@{@"meta": @{@"case": isStore ? @"guard_store": @"guard_read", @"name": name, @"off_dec": params[@"off_dec"]},
               @"gated": @{@"status": @"compile_fail", @"width": @32},
               @"raw": @{@"err": lerr.localizedDescription ?: @""}});
        return;
    }
    NSString *fn = isStore ? @"guard_store_u32" : @"guard_load_u32";
    id<MTLFunction> f = [lib newFunctionWithName:fn];
    NSError *perr = nil;
    id<MTLComputePipelineState> pso = [dev newComputePipelineStateWithFunction:f error:&perr];
    if (!pso) {
        emit(@{@"meta": @{@"case": isStore ? @"guard_store": @"guard_read", @"name": name, @"off_dec": params[@"off_dec"]},
               @"gated": @{@"status": @"pipeline_fail", @"width": @32},
               @"raw": @{@"err": perr.localizedDescription ?: @""}});
        return;
    }

    MTLResourceOptions opt = optsForMode(mode);
    id<MTLBuffer> guard1 = [dev newBufferWithLength:256 options:opt];
    id<MTLBuffer> main_  = [dev newBufferWithLength:(NSUInteger)baseLen options:opt];
    id<MTLBuffer> result = [dev newBufferWithLength:32 options:opt];
    id<MTLBuffer> guard2 = [dev newBufferWithLength:256 options:opt];
    if (!guard1 || !main_ || !result || !guard2) {
        emit(@{@"meta": @{@"case": isStore ? @"guard_store": @"guard_read", @"name": name, @"off_dec": params[@"off_dec"]},
               @"gated": @{@"status": @"alloc_fail", @"width": @32}, @"raw": @{}});
        return;
    }
    fillConst(guard1.contents, 256, 0x5A);
    fillPattern(main_.contents, (size_t)baseLen);
    memset(result.contents, 0, 32);
    fillConst(guard2.contents, 256, 0xC3);
    NSData *mainBefore = [NSData dataWithBytes:main_.contents length:(NSUInteger)baseLen];

    id<MTLCommandQueue> q = [dev newCommandQueue];
    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
    [enc setComputePipelineState:pso];
    [enc setBuffer:main_ offset:0 atIndex:0];
    uint64_t offLE = off;
    [enc setBytes:&offLE length:sizeof(offLE) atIndex:1];
    if (isStore) {
        uint32_t pat = storePattern;
        [enc setBytes:&pat length:sizeof(pat) atIndex:2];
    } else {
        [enc setBuffer:result offset:0 atIndex:2];
    }
    [enc dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
    [enc endEncoding];

    dispatch_source_t wd = armWatchdog(dwd, 98);
    [cb commit];
    [cb waitUntilCompleted];
    disarmWatchdog(wd);

    NSDictionary *cbi = cbStatusInfo(cb);
    BOOL g1ok = allEqualConst(guard1.contents, 256, 0x5A);
    BOOL g2ok = allEqualConst(guard2.contents, 256, 0xC3);
    NSData *mainAfter = [NSData dataWithBytes:main_.contents length:(NSUInteger)baseLen];
    BOOL mainUnchanged = [mainBefore isEqualToData:mainAfter];
    NSString *obsHex = isStore ? @"" : hexOf(result.contents, 4);

    NSMutableDictionary *gated = [@{
        @"status": @"ok",
        @"width": @32,
        @"cb_status": cbi[@"cb_status"],
        @"g1_ok": @(g1ok),
        @"g2_ok": @(g2ok),
        @"main_unchanged": @(mainUnchanged),
    } mutableCopy];
    if (!isStore) gated[@"obs_hex"] = obsHex;
    NSDictionary *raw = @{
        @"err": cbi[@"err"],
        @"main_addr_hex": hex64(main_.gpuAddress),
        @"guard1_addr_hex": hex64(guard1.gpuAddress),
        @"guard2_addr_hex": hex64(guard2.gpuAddress),
        @"main_after_hex": hexOf(mainAfter.bytes, mainAfter.length),
    };
    emit(@{ @"meta": @{@"case": isStore ? @"guard_store": @"guard_read", @"name": name,
                       @"off_dec": params[@"off_dec"], @"base_len": decU64(baseLen), @"mode": mode},
            @"gated": gated, @"raw": raw });
}

// ---------------------------------------------------------------------------
// Sparse helpers
// ---------------------------------------------------------------------------
static MTLSparsePageSize pageSizeFromString(NSString *s) {
    if ([s isEqualToString:@"64"]) return MTLSparsePageSize64;
    if ([s isEqualToString:@"256"]) return MTLSparsePageSize256;
    return MTLSparsePageSize16;
}

static MTLTextureType textureTypeFromString(NSString *s) {
    if ([s isEqualToString:@"2darray"]) return MTLTextureType2DArray;
    if ([s isEqualToString:@"3d"]) return MTLTextureType3D;
    if ([s isEqualToString:@"cube"]) return MTLTextureTypeCube;
    return MTLTextureType2D;
}

static MTLPixelFormat pixelFormatFromString(NSString *s) {
    if ([s isEqualToString:@"r8unorm"]) return MTLPixelFormatR8Unorm;
    if ([s isEqualToString:@"rg8unorm"]) return MTLPixelFormatRG8Unorm;
    if ([s isEqualToString:@"rgba8unorm"]) return MTLPixelFormatRGBA8Unorm;
    if ([s isEqualToString:@"rgba16float"]) return MTLPixelFormatRGBA16Float;
    if ([s isEqualToString:@"rgba32float"]) return MTLPixelFormatRGBA32Float;
    if ([s isEqualToString:@"r32float"]) return MTLPixelFormatR32Float;
    if ([s isEqualToString:@"bgra8unorm"]) return MTLPixelFormatBGRA8Unorm;
    return MTLPixelFormatRGBA8Unorm;
}

// Case: sparse_caps -- sparseTileSize matrix, no dispatch.
// params: {"combos":[{"type":"2d","format":"rgba8unorm","samples":1}, ...]}
static void case_sparse_caps(id<MTLDevice> dev, NSDictionary *params) {
    NSArray *combos = params[@"combos"];
    NSMutableArray *gatedRows = [NSMutableArray array];
    for (NSDictionary *c in combos) {
        NSString *type = c[@"type"]; NSString *fmt = c[@"format"];
        NSUInteger samples = [c[@"samples"] unsignedIntegerValue];
        MTLTextureType tt = textureTypeFromString(type);
        MTLPixelFormat pf = pixelFormatFromString(fmt);
        MTLSize base = [dev sparseTileSizeWithTextureType:tt pixelFormat:pf sampleCount:samples];
        NSMutableDictionary *row = [@{@"type": type, @"format": fmt, @"samples": @(samples),
                                       @"tile_w": @(base.width), @"tile_h": @(base.height), @"tile_d": @(base.depth)} mutableCopy];
        if (@available(macOS 13.0, *)) {
            for (NSString *pg in @[@"16", @"64", @"256"]) {
                MTLSize ts = [dev sparseTileSizeWithTextureType:tt pixelFormat:pf sampleCount:samples
                                                   sparsePageSize:pageSizeFromString(pg)];
                row[[@"tile_page" stringByAppendingString:pg]] = @{@"w": @(ts.width), @"h": @(ts.height), @"d": @(ts.depth)};
            }
        }
        [gatedRows addObject:row];
    }
    emit(@{ @"meta": @{@"case": @"sparse_caps", @"n": @(combos.count)},
            @"gated": @{@"rows": gatedRows}, @"raw": @{} });
}

// Build a sparse heap+texture. Returns nil texture on failure; fills outHeap.
static id<MTLTexture> makeSparseTexture(id<MTLDevice> dev, NSUInteger w, NSUInteger h,
                                         MTLTextureType type, MTLPixelFormat fmt,
                                         MTLSparsePageSize pgsz, NSUInteger mipLevels,
                                         NSUInteger heapExtraBytes,
                                         id<MTLHeap> *outHeap, NSError **outErr) {
    MTLTextureDescriptor *td = [MTLTextureDescriptor new];
    td.textureType = type;
    td.pixelFormat = fmt;
    td.width = w; td.height = h; td.depth = 1;
    td.mipmapLevelCount = mipLevels;
    td.usage = MTLTextureUsageShaderRead | MTLTextureUsageShaderWrite;
    td.storageMode = MTLStorageModePrivate;
    MTLSizeAndAlign sa = [dev heapTextureSizeAndAlignWithDescriptor:td];

    MTLHeapDescriptor *hd = [MTLHeapDescriptor new];
    hd.type = MTLHeapTypeSparse;
    hd.storageMode = MTLStorageModePrivate;
    if (@available(macOS 13.0, *)) hd.sparsePageSize = pgsz;
    hd.size = sa.size + heapExtraBytes;
    id<MTLHeap> heap = [dev newHeapWithDescriptor:hd];
    if (!heap) { if (outErr) *outErr = [NSError errorWithDomain:@"exp0122" code:1
                     userInfo:@{NSLocalizedDescriptionKey: @"newHeapWithDescriptor failed"}]; return nil; }
    id<MTLTexture> tex = [heap newTextureWithDescriptor:td];
    if (outHeap) *outHeap = heap;
    if (!tex && outErr) *outErr = [NSError errorWithDomain:@"exp0122" code:2
                     userInfo:@{NSLocalizedDescriptionKey: @"heap newTextureWithDescriptor failed"}];
    return tex;
}

// Case: sparse_miptail -- create sparse textures, query tail geometry, no dispatch.
// params: {"cases":[{"width":W,"height":H,"page":"16","mips":N}]}
static void case_sparse_miptail(id<MTLDevice> dev, NSDictionary *params) {
    NSArray *cases = params[@"cases"];
    NSMutableArray *gated = [NSMutableArray array];
    NSMutableArray *raw = [NSMutableArray array];
    for (NSDictionary *c in cases) {
        NSUInteger w = [c[@"width"] unsignedIntegerValue];
        NSUInteger h = [c[@"height"] unsignedIntegerValue];
        NSUInteger mips = [c[@"mips"] unsignedIntegerValue];
        NSString *pg = c[@"page"];
        id<MTLHeap> heap = nil;
        NSError *err = nil;
        id<MTLTexture> tex = makeSparseTexture(dev, w, h, MTLTextureType2D, MTLPixelFormatRGBA8Unorm,
                                                pageSizeFromString(pg), mips, 4u*1024*1024, &heap, &err);
        BOOL ok = (tex != nil);
        [gated addObject:@{
            @"width": @(w), @"height": @(h), @"mips": @(mips), @"page": pg,
            @"tex_alloc_ok": @(ok), @"heap_alloc_ok": @(heap != nil),
            @"first_mipmap_in_tail": ok ? @(tex.firstMipmapInTail) : @(-1),
            @"tail_size_in_bytes": ok ? decU64(tex.tailSizeInBytes) : @"-1",
        }];
        [raw addObject:@{
            @"width": @(w), @"height": @(h),
            @"heap_current_allocated_size": heap ? decU64(heap.currentAllocatedSize) : @"0",
            @"heap_used_size": heap ? decU64(heap.usedSize) : @"0",
            @"err": err.localizedDescription ?: @"",
        }];
    }
    emit(@{ @"meta": @{@"case": @"sparse_miptail", @"n": @(cases.count)},
            @"gated": @{@"rows": gated}, @"raw": @{@"rows": raw} });
}

static NSArray<NSValue *> *coordsFromParams(NSArray *coordPairs) {
    NSMutableArray *out = [NSMutableArray array];
    for (NSArray *xy in coordPairs) {
        uint32_t x = [xy[0] unsignedIntValue];
        uint32_t y = [xy[1] unsignedIntValue];
        uint32_t packed[2] = {x, y};
        [out addObject:[NSValue valueWithBytes:packed objCType:@encode(uint32_t[2])]];
    }
    return out;
}

// Reads texel values at coords via sparse_read_rgba8; returns array of hex float4 (16B each)
// and the command-buffer status dict. dispatch_watchdog_ms bounds the wait.
static NSDictionary *readCoords(id<MTLDevice> dev, id<MTLCommandQueue> q, id<MTLComputePipelineState> readPSO,
                                 id<MTLTexture> tex, NSArray<NSValue *> *coords, NSUInteger dwd) {
    NSUInteger n = coords.count;
    id<MTLBuffer> coordBuf = [dev newBufferWithLength:n * sizeof(uint32_t) * 2 options:MTLResourceStorageModeShared];
    uint32_t *cp = (uint32_t *)coordBuf.contents;
    for (NSUInteger i = 0; i < n; i++) {
        uint32_t packed[2]; [coords[i] getValue:packed];
        cp[2*i] = packed[0]; cp[2*i+1] = packed[1];
    }
    id<MTLBuffer> outBuf = [dev newBufferWithLength:n * sizeof(float) * 4 options:MTLResourceStorageModeShared];
    memset(outBuf.contents, 0xEE, outBuf.length); // poison, so an untouched slot is visible

    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
    [enc setComputePipelineState:readPSO];
    [enc setTexture:tex atIndex:0];
    [enc setBuffer:coordBuf offset:0 atIndex:0];
    [enc setBuffer:outBuf offset:0 atIndex:1];
    [enc dispatchThreads:MTLSizeMake(n,1,1) threadsPerThreadgroup:MTLSizeMake(n,1,1)];
    [enc endEncoding];
    dispatch_source_t wd = armWatchdog(dwd, 98);
    [cb commit];
    [cb waitUntilCompleted];
    disarmWatchdog(wd);
    NSDictionary *cbi = cbStatusInfo(cb);
    NSMutableArray *hexVals = [NSMutableArray array];
    float *fp = (float *)outBuf.contents;
    for (NSUInteger i = 0; i < n; i++) {
        [hexVals addObject:hexOf(&fp[4*i], 16)];
    }
    return @{@"values_hex": hexVals, @"cb_status": cbi[@"cb_status"], @"err": cbi[@"err"]};
}

static NSDictionary *writeCoords(id<MTLDevice> dev, id<MTLCommandQueue> q, id<MTLComputePipelineState> writePSO,
                                  id<MTLTexture> tex, NSArray<NSValue *> *coords, float pattern[4], NSUInteger dwd) {
    NSUInteger n = coords.count;
    id<MTLBuffer> coordBuf = [dev newBufferWithLength:n * sizeof(uint32_t) * 2 options:MTLResourceStorageModeShared];
    uint32_t *cp = (uint32_t *)coordBuf.contents;
    for (NSUInteger i = 0; i < n; i++) {
        uint32_t packed[2]; [coords[i] getValue:packed];
        cp[2*i] = packed[0]; cp[2*i+1] = packed[1];
    }
    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
    [enc setComputePipelineState:writePSO];
    [enc setTexture:tex atIndex:0];
    [enc setBuffer:coordBuf offset:0 atIndex:0];
    [enc setBytes:pattern length:sizeof(float)*4 atIndex:1];
    [enc dispatchThreads:MTLSizeMake(n,1,1) threadsPerThreadgroup:MTLSizeMake(n,1,1)];
    [enc endEncoding];
    dispatch_source_t wd = armWatchdog(dwd, 98);
    [cb commit];
    [cb waitUntilCompleted];
    disarmWatchdog(wd);
    NSDictionary *cbi = cbStatusInfo(cb);
    return @{@"cb_status": cbi[@"cb_status"], @"err": cbi[@"err"]};
}

static BOOL mapTiles(id<MTLDevice> dev, id<MTLCommandQueue> q, id<MTLTexture> tex,
                      NSArray *tiles, NSUInteger tw, NSUInteger th, MTLSparseTextureMappingMode mode,
                      NSUInteger dwd, NSDictionary **cbiOut) {
    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLResourceStateCommandEncoder> enc = [cb resourceStateCommandEncoder];
    for (NSArray *txy in tiles) {
        NSUInteger tx = [txy[0] unsignedIntegerValue];
        NSUInteger ty = [txy[1] unsignedIntegerValue];
        MTLRegion r = MTLRegionMake2D(tx*tw, ty*th, tw, th);
        [enc updateTextureMapping:tex mode:mode region:r mipLevel:0 slice:0];
    }
    [enc endEncoding];
    dispatch_source_t wd = armWatchdog(dwd, 98);
    [cb commit];
    [cb waitUntilCompleted];
    disarmWatchdog(wd);
    if (cbiOut) *cbiOut = cbStatusInfo(cb);
    return cb.status == MTLCommandBufferStatusCompleted;
}

// Case: sparse_unmapped_read -- leave the whole sparse texture unmapped; read coords.
// params: {"width":W,"height":H,"page":"16","coords":[[x,y],...],"compile_watchdog_ms":..,"dispatch_watchdog_ms":..,"kernel_path":".."}
static void case_sparse_unmapped_read(id<MTLDevice> dev, NSDictionary *params) {
    NSUInteger w = [params[@"width"] unsignedIntegerValue];
    NSUInteger h = [params[@"height"] unsignedIntegerValue];
    NSString *pg = params[@"page"];
    NSUInteger cwd = [params[@"compile_watchdog_ms"] unsignedIntegerValue];
    NSUInteger dwd = [params[@"dispatch_watchdog_ms"] unsignedIntegerValue];

    NSError *lerr = nil;
    id<MTLLibrary> lib = loadLibrary(dev, params[@"kernel_path"], cwd, &lerr);
    if (!lib) {
        emit(@{@"meta": @{@"case": @"sparse_unmapped_read"}, @"gated": @{@"status": @"compile_fail"},
               @"raw": @{@"err": lerr.localizedDescription ?: @""}});
        return;
    }
    id<MTLFunction> rf = [lib newFunctionWithName:@"sparse_read_rgba8"];
    NSError *perr = nil;
    id<MTLComputePipelineState> readPSO = [dev newComputePipelineStateWithFunction:rf error:&perr];
    if (!readPSO) {
        emit(@{@"meta": @{@"case": @"sparse_unmapped_read"}, @"gated": @{@"status": @"pipeline_fail"},
               @"raw": @{@"err": perr.localizedDescription ?: @""}});
        return;
    }
    id<MTLHeap> heap = nil; NSError *terr = nil;
    id<MTLTexture> tex = makeSparseTexture(dev, w, h, MTLTextureType2D, MTLPixelFormatRGBA8Unorm,
                                            pageSizeFromString(pg), 1, 4u*1024*1024, &heap, &terr);
    if (!tex) {
        emit(@{@"meta": @{@"case": @"sparse_unmapped_read"}, @"gated": @{@"status": @"texture_alloc_fail"},
               @"raw": @{@"err": terr.localizedDescription ?: @""}});
        return;
    }
    id<MTLCommandQueue> q = [dev newCommandQueue];
    NSArray<NSValue *> *coords = coordsFromParams(params[@"coords"]);
    NSDictionary *res = readCoords(dev, q, readPSO, tex, coords, dwd);
    emit(@{ @"meta": @{@"case": @"sparse_unmapped_read", @"width": @(w), @"height": @(h), @"page": pg},
            @"gated": @{@"status": @"ok", @"cb_status": res[@"cb_status"], @"values_hex": res[@"values_hex"]},
            @"raw": @{@"err": res[@"err"]} });
}

// Case: sparse_partial_map -- map a subset of tiles, write into one, read a coord set.
// params: {"width":W,"height":H,"tile_w":TW,"tile_h":TH,"page":"16",
//          "mapped_tiles":[[tx,ty],...], "write_coord":[x,y], "pattern_rgba":[r,g,b,a],
//          "read_coords":[[x,y],...], "compile_watchdog_ms":..,"dispatch_watchdog_ms":..,"kernel_path":".."}
static void case_sparse_partial_map(id<MTLDevice> dev, NSDictionary *params) {
    NSUInteger w = [params[@"width"] unsignedIntegerValue];
    NSUInteger h = [params[@"height"] unsignedIntegerValue];
    NSUInteger tw = [params[@"tile_w"] unsignedIntegerValue];
    NSUInteger th = [params[@"tile_h"] unsignedIntegerValue];
    NSString *pg = params[@"page"];
    NSUInteger cwd = [params[@"compile_watchdog_ms"] unsignedIntegerValue];
    NSUInteger dwd = [params[@"dispatch_watchdog_ms"] unsignedIntegerValue];

    NSError *lerr = nil;
    id<MTLLibrary> lib = loadLibrary(dev, params[@"kernel_path"], cwd, &lerr);
    if (!lib) {
        emit(@{@"meta": @{@"case": @"sparse_partial_map"}, @"gated": @{@"status": @"compile_fail"}, @"raw": @{@"err": lerr.localizedDescription ?: @""}});
        return;
    }
    id<MTLComputePipelineState> readPSO = [dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"sparse_read_rgba8"] error:nil];
    id<MTLComputePipelineState> writePSO = [dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"sparse_write_rgba8"] error:nil];
    if (!readPSO || !writePSO) {
        emit(@{@"meta": @{@"case": @"sparse_partial_map"}, @"gated": @{@"status": @"pipeline_fail"}, @"raw": @{}});
        return;
    }
    id<MTLHeap> heap = nil; NSError *terr = nil;
    id<MTLTexture> tex = makeSparseTexture(dev, w, h, MTLTextureType2D, MTLPixelFormatRGBA8Unorm,
                                            pageSizeFromString(pg), 1, 4u*1024*1024, &heap, &terr);
    if (!tex) {
        emit(@{@"meta": @{@"case": @"sparse_partial_map"}, @"gated": @{@"status": @"texture_alloc_fail"}, @"raw": @{@"err": terr.localizedDescription ?: @""}});
        return;
    }
    id<MTLCommandQueue> q = [dev newCommandQueue];
    NSDictionary *mapCbi = nil;
    BOOL mapOk = mapTiles(dev, q, tex, params[@"mapped_tiles"], tw, th, MTLSparseTextureMappingModeMap, dwd, &mapCbi);

    NSArray *wc = params[@"write_coord"];
    uint32_t wxy[2] = {[wc[0] unsignedIntValue], [wc[1] unsignedIntValue]};
    NSArray<NSValue *> *writeCoordArr = @[[NSValue valueWithBytes:wxy objCType:@encode(uint32_t[2])]];
    NSArray *pr = params[@"pattern_rgba"];
    float pattern[4] = {[pr[0] floatValue], [pr[1] floatValue], [pr[2] floatValue], [pr[3] floatValue]};
    NSDictionary *writeRes = writeCoords(dev, q, writePSO, tex, writeCoordArr, pattern, dwd);

    NSArray<NSValue *> *readCoordArr = coordsFromParams(params[@"read_coords"]);
    NSDictionary *readRes = readCoords(dev, q, readPSO, tex, readCoordArr, dwd);

    NSDictionary *gated = @{@"status": @"ok", @"map_ok": @(mapOk), @"map_cb_status": mapCbi[@"cb_status"] ?: @(-1),
                        @"write_cb_status": writeRes[@"cb_status"], @"read_cb_status": readRes[@"cb_status"],
                        @"read_values_hex": readRes[@"values_hex"],
                        @"heap_used_bytes_after_map": decU64(heap.usedSize)};
    emit(@{ @"meta": @{@"case": @"sparse_partial_map", @"width": @(w), @"height": @(h),
                       @"tile_w": @(tw), @"tile_h": @(th), @"page": pg},
            @"gated": gated,
            @"raw": @{@"map_err": mapCbi[@"err"] ?: @"", @"write_err": writeRes[@"err"], @"read_err": readRes[@"err"],
                      @"heap_current_allocated_size": decU64(heap.currentAllocatedSize)} });
}

// Case: sparse_remap -- map, write, unmap, read-while-unmapped, remap, read-after-remap.
// params like sparse_partial_map but with a single tile and single coord.
static void case_sparse_remap(id<MTLDevice> dev, NSDictionary *params) {
    NSUInteger w = [params[@"width"] unsignedIntegerValue];
    NSUInteger h = [params[@"height"] unsignedIntegerValue];
    NSUInteger tw = [params[@"tile_w"] unsignedIntegerValue];
    NSUInteger th = [params[@"tile_h"] unsignedIntegerValue];
    NSString *pg = params[@"page"];
    NSUInteger cwd = [params[@"compile_watchdog_ms"] unsignedIntegerValue];
    NSUInteger dwd = [params[@"dispatch_watchdog_ms"] unsignedIntegerValue];

    NSError *lerr = nil;
    id<MTLLibrary> lib = loadLibrary(dev, params[@"kernel_path"], cwd, &lerr);
    if (!lib) {
        emit(@{@"meta": @{@"case": @"sparse_remap"}, @"gated": @{@"status": @"compile_fail"}, @"raw": @{@"err": lerr.localizedDescription ?: @""}});
        return;
    }
    id<MTLComputePipelineState> readPSO = [dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"sparse_read_rgba8"] error:nil];
    id<MTLComputePipelineState> writePSO = [dev newComputePipelineStateWithFunction:[lib newFunctionWithName:@"sparse_write_rgba8"] error:nil];
    if (!readPSO || !writePSO) {
        emit(@{@"meta": @{@"case": @"sparse_remap"}, @"gated": @{@"status": @"pipeline_fail"}, @"raw": @{}});
        return;
    }
    id<MTLHeap> heap = nil; NSError *terr = nil;
    id<MTLTexture> tex = makeSparseTexture(dev, w, h, MTLTextureType2D, MTLPixelFormatRGBA8Unorm,
                                            pageSizeFromString(pg), 1, 4u*1024*1024, &heap, &terr);
    if (!tex) {
        emit(@{@"meta": @{@"case": @"sparse_remap"}, @"gated": @{@"status": @"texture_alloc_fail"}, @"raw": @{@"err": terr.localizedDescription ?: @""}});
        return;
    }
    id<MTLCommandQueue> q = [dev newCommandQueue];
    NSArray *tile = params[@"tile"];
    NSArray *tilesArr = @[tile];

    NSDictionary *cbiMap1 = nil;
    BOOL map1ok = mapTiles(dev, q, tex, tilesArr, tw, th, MTLSparseTextureMappingModeMap, dwd, &cbiMap1);

    NSArray *coord = params[@"coord"];
    uint32_t cxy[2] = {[coord[0] unsignedIntValue], [coord[1] unsignedIntValue]};
    NSArray<NSValue *> *coordArr = @[[NSValue valueWithBytes:cxy objCType:@encode(uint32_t[2])]];
    NSArray *pr = params[@"pattern_rgba"];
    float pattern[4] = {[pr[0] floatValue], [pr[1] floatValue], [pr[2] floatValue], [pr[3] floatValue]};
    NSDictionary *writeRes = writeCoords(dev, q, writePSO, tex, coordArr, pattern, dwd);
    NSDictionary *readAfterWrite = readCoords(dev, q, readPSO, tex, coordArr, dwd);

    NSDictionary *cbiUnmap = nil;
    BOOL unmapOk = mapTiles(dev, q, tex, tilesArr, tw, th, MTLSparseTextureMappingModeUnmap, dwd, &cbiUnmap);
    NSDictionary *readAfterUnmap = readCoords(dev, q, readPSO, tex, coordArr, dwd);

    NSDictionary *cbiRemap = nil;
    BOOL remapOk = mapTiles(dev, q, tex, tilesArr, tw, th, MTLSparseTextureMappingModeMap, dwd, &cbiRemap);
    NSDictionary *readAfterRemap = readCoords(dev, q, readPSO, tex, coordArr, dwd);

    NSDictionary *gated2 = @{@"status": @"ok",
                        @"map1_ok": @(map1ok), @"unmap_ok": @(unmapOk), @"remap_ok": @(remapOk),
                        @"write_cb_status": writeRes[@"cb_status"],
                        @"read_after_write_hex": readAfterWrite[@"values_hex"],
                        @"read_after_unmap_hex": readAfterUnmap[@"values_hex"],
                        @"read_after_remap_hex": readAfterRemap[@"values_hex"],
                        @"heap_used_bytes_final": decU64(heap.usedSize)};
    emit(@{ @"meta": @{@"case": @"sparse_remap", @"width": @(w), @"height": @(h), @"tile_w": @(tw), @"tile_h": @(th), @"page": pg},
            @"gated": gated2,
            @"raw": @{@"write_err": writeRes[@"err"], @"unmap_err": cbiUnmap[@"err"] ?: @"",
                      @"remap_err": cbiRemap[@"err"] ?: @""} });
}

// ---------------------------------------------------------------------------
// Case: timestamp_ladder -- sampleTimestamps before/after known sleeps.
// params: {"sleeps_ms":[1,10,100,1000]}
// ---------------------------------------------------------------------------
static void case_timestamp_ladder(id<MTLDevice> dev, NSDictionary *params) {
    mach_timebase_info_data_t tb; mach_timebase_info(&tb);
    NSArray *sleeps = params[@"sleeps_ms"];
    NSMutableArray *rawRows = [NSMutableArray array];
    NSMutableArray *gatedRows = [NSMutableArray array];
    for (NSNumber *sms in sleeps) {
        MTLTimestamp cpu1 = 0, gpu1 = 0, cpu2 = 0, gpu2 = 0;
        [dev sampleTimestamps:&cpu1 gpuTimestamp:&gpu1];
        useconds_t us = (useconds_t)([sms unsignedIntegerValue] * 1000);
        usleep(us);
        [dev sampleTimestamps:&cpu2 gpuTimestamp:&gpu2];
        [rawRows addObject:@{@"sleep_ms": sms, @"cpu1": decU64(cpu1), @"gpu1": decU64(gpu1),
                              @"cpu2": decU64(cpu2), @"gpu2": decU64(gpu2)}];
        [gatedRows addObject:@{@"sleep_ms": sms,
                                @"cpu_monotonic": @(cpu2 > cpu1),
                                @"gpu_monotonic": @(gpu2 > gpu1)}];
    }
    emit(@{ @"meta": @{@"case": @"timestamp_ladder", @"n": @(sleeps.count)},
            @"gated": @{@"mach_timebase_numer": @(tb.numer), @"mach_timebase_denom": @(tb.denom),
                        @"rows": gatedRows},
            @"raw": @{@"rows": rawRows} });
}

// ---------------------------------------------------------------------------
int main(int argc, char **argv) {
    @autoreleasepool {
        if (argc < 2) { fprintf(stderr, "usage: probe <case> [json-params]\n"); return 2; }
        NSString *caseName = [NSString stringWithUTF8String:argv[1]];
        NSDictionary *params = @{};
        if (argc >= 3) {
            NSData *pd = [NSData dataWithBytes:argv[2] length:strlen(argv[2])];
            NSError *perr = nil;
            id parsed = [NSJSONSerialization JSONObjectWithData:pd options:0 error:&perr];
            if (![parsed isKindOfClass:[NSDictionary class]]) {
                fprintf(stderr, "bad json params: %s\n", perr.localizedDescription.UTF8String ?: "?");
                return 2;
            }
            params = parsed;
        }
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) { fprintf(stderr, "no metal device\n"); return 2; }

        if ([caseName isEqualToString:@"caps"]) { case_caps(dev, params); }
        else if ([caseName isEqualToString:@"align"]) { case_align(dev, params); }
        else if ([caseName isEqualToString:@"addrsurvey"]) { case_addrsurvey(dev, params); }
        else if ([caseName isEqualToString:@"maxlen_boundary"]) { case_maxlen_boundary(dev, params); }
        else if ([caseName isEqualToString:@"guard_read"]) { case_guard(dev, params, NO); }
        else if ([caseName isEqualToString:@"guard_store"]) { case_guard(dev, params, YES); }
        else if ([caseName isEqualToString:@"sparse_caps"]) { case_sparse_caps(dev, params); }
        else if ([caseName isEqualToString:@"sparse_miptail"]) { case_sparse_miptail(dev, params); }
        else if ([caseName isEqualToString:@"sparse_unmapped_read"]) { case_sparse_unmapped_read(dev, params); }
        else if ([caseName isEqualToString:@"sparse_partial_map"]) { case_sparse_partial_map(dev, params); }
        else if ([caseName isEqualToString:@"sparse_remap"]) { case_sparse_remap(dev, params); }
        else if ([caseName isEqualToString:@"timestamp_ladder"]) { case_timestamp_ladder(dev, params); }
        else { fprintf(stderr, "unknown case %s\n", argv[1]); return 2; }
    }
    return 0;
}
