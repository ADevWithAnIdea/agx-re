// EXP-0106 public-Metal behavioral harness (OWN-SHADER + HW-PROBE). One
// process per case. Public Metal API only: no Apple binary, archive, BO, or
// private interface is ever touched. Architecture independently re-authored
// from the proven EXP-0072/EXP-0075/EXP-0079/EXP-0083/EXP-0095 pattern (our
// own prior work in this repository, not Apple's): exactly one locked
// print-then-flush-then-exit path in finish(); no completion is ever
// signalled before the record is durably printed; main blocks forever after
// both phase waits and never returns.
//
// Case parameters arrive as one JSON object on --args. Each family's
// handler reads only the keys it documents. Dispatch-based families share
// one 96-byte output buffer convention:
//   [0..16)   prefix guard, 0x5a
//   [16..80)  16 x uint32 LE "out" words, host-prefilled with 0xEEEEEEEE
//   [80..96)  suffix guard, 0xa5
// A kernel writes only the words CAPTURE_CONTRACT.json says it writes;
// unused words must still read back as the sentinel. Descriptor-only
// families (b_descriptor, b03_query) never compile a library or dispatch;
// they emit their own small JSON schema directly.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <dispatch/dispatch.h>
#include <pthread.h>
#include <sys/utsname.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <math.h>

static const char *g_family = "", *g_case = "", *g_source = "";
static NSDictionary *g_args = nil;

static void js(id v) {
    if (v == nil) { printf("null"); return; }
    NSData *d = [NSJSONSerialization dataWithJSONObject:v options:NSJSONWritingFragmentsAllowed error:nil];
    if (!d) { printf("null"); return; }
    fwrite(d.bytes, 1, d.length, stdout);
}
static void jstr(NSString *s) { js(s ?: @""); }
static void hex(const unsigned char *p, NSUInteger n) { for (NSUInteger i = 0; i < n; i++) printf("%02x", p[i]); }
static NSString *errstr(NSError *e) { return e ? [NSString stringWithFormat:@"%@|%ld|%@", e.domain, (long)e.code, e.localizedDescription] : @""; }

static NSString *S_library_error = @"";
static BOOL S_library_ok = NO;
static NSMutableArray *S_pipeline_names, *S_pipeline_oks, *S_pipeline_errors;
static BOOL S_resource_ok = YES; static NSString *S_resource_error = @"";
static long S_cb_status = 0; static NSString *S_cb_error = @"";
static NSString *S_device = @"";
static unsigned char *S_out = NULL; // 96 bytes, or NULL if never allocated

static void init_state(void) {
    S_pipeline_names = [NSMutableArray array];
    S_pipeline_oks = [NSMutableArray array];
    S_pipeline_errors = [NSMutableArray array];
}
static void note_pipeline(NSString *name, BOOL ok, NSError *e) {
    [S_pipeline_names addObject:name ?: @""];
    [S_pipeline_oks addObject:@(ok)];
    [S_pipeline_errors addObject:errstr(e)];
}

static void prefix(const char *status) {
    printf("{\"schema\":1,\"family\":"); jstr(@(g_family));
    printf(",\"case\":"); jstr(@(g_case));
    printf(",\"status\":"); jstr(@(status));
    printf(",\"library_ok\":%s,\"library_error\":", S_library_ok ? "true" : "false"); js(S_library_error);
    printf(",\"pipelines\":[");
    for (NSUInteger i = 0; i < S_pipeline_names.count; i++) {
        if (i) printf(",");
        printf("{\"name\":"); jstr(S_pipeline_names[i]);
        printf(",\"ok\":%s,\"error\":", [S_pipeline_oks[i] boolValue] ? "true" : "false"); js(S_pipeline_errors[i]);
        printf("}");
    }
    printf("]");
    printf(",\"resource_ok\":%s,\"resource_error\":", S_resource_ok ? "true" : "false"); js(S_resource_error);
    printf(",\"command_buffer_status\":%ld,\"command_buffer_error\":", S_cb_status); js(S_cb_error);
    printf(",\"device\":"); js(S_device);
}
static void tail(void) {
    struct utsname u; uname(&u);
    printf(",\"machine\":"); js(@(u.machine));
    printf(",\"os\":"); js(NSProcessInfo.processInfo.operatingSystemVersionString);
    if (S_out) {
        printf(",\"prefix_guard_ok\":%s", (memcmp(S_out, "\x5a\x5a\x5a\x5a\x5a\x5a\x5a\x5a\x5a\x5a\x5a\x5a\x5a\x5a\x5a\x5a", 16) == 0) ? "true" : "false");
        printf(",\"suffix_guard_ok\":%s", (memcmp(S_out + 80, "\xa5\xa5\xa5\xa5\xa5\xa5\xa5\xa5\xa5\xa5\xa5\xa5\xa5\xa5\xa5\xa5", 16) == 0) ? "true" : "false");
        printf(",\"out_hex\":\""); hex(S_out, 96); printf("\"");
        const uint32_t *w = (const uint32_t *)(S_out + 16);
        printf(",\"out_words\":[");
        for (int i = 0; i < 16; i++) { if (i) printf(","); printf("%u", w[i]); }
        printf("]");
    } else {
        printf(",\"prefix_guard_ok\":true,\"suffix_guard_ok\":true,\"out_hex\":\"");
        for (int i = 0; i < 16; i++) printf("5a");
        for (int i = 0; i < 64; i++) printf("00");
        for (int i = 0; i < 16; i++) printf("a5");
        printf("\",\"out_words\":[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]");
    }
    printf("}\n");
}
static pthread_mutex_t g_exit_lock = PTHREAD_MUTEX_INITIALIZER;
static void finish(const char *status, int code) {
    pthread_mutex_lock(&g_exit_lock);
    prefix(status);
    tail();
    fflush(stdout);
    fflush(NULL);
    exit(code);
}

static id<MTLDevice> g_device = nil;

static id<MTLBuffer> make_out_buffer(void) {
    id<MTLBuffer> b = [g_device newBufferWithLength:96 options:MTLResourceStorageModeShared];
    if (!b) { S_resource_ok = NO; S_resource_error = @"out buffer alloc failed"; finish("resource_failed", 3); }
    unsigned char *p = b.contents;
    memset(p, 0x5a, 16);
    memset(p + 16, 0xEE, 64);
    memset(p + 80, 0xa5, 16);
    S_out = p;
    return b;
}

static id<MTLLibrary> compile_library(void) {
    NSError *e = nil;
    NSString *src = [NSString stringWithContentsOfFile:@(g_source) encoding:NSUTF8StringEncoding error:&e];
    if (!src) { S_library_error = @"source read failed"; finish("source_failed", 3); }
    MTLCompileOptions *opt = [MTLCompileOptions new];
    id<MTLLibrary> lib = [g_device newLibraryWithSource:src options:opt error:&e];
    S_library_ok = lib != nil;
    S_library_error = errstr(e);
    if (!lib) finish("library_failed", 0); // a contracted, non-harness-fault outcome for expect_status="library_failed" cases
    return lib;
}

// -------- small helpers for args dict --------
static NSInteger ai(NSString *k, NSInteger dflt) { id v = g_args[k]; return v ? [v integerValue] : dflt; }
static double ad(NSString *k, double dflt) { id v = g_args[k]; return v ? [v doubleValue] : dflt; }
static NSString *as_(NSString *k, NSString *dflt) { id v = g_args[k]; return [v isKindOfClass:NSString.class] ? v : dflt; }
static BOOL ab(NSString *k, BOOL dflt) { id v = g_args[k]; return v ? [v boolValue] : dflt; }
static NSArray *aarr(NSString *k) { id v = g_args[k]; return [v isKindOfClass:NSArray.class] ? v : @[]; }

// -------- format table (small, closed set actually used by CAPTURE_CONTRACT.json) --------
static MTLPixelFormat fmt_from_name(NSString *n) {
    if ([n isEqualToString:@"r32uint"]) return MTLPixelFormatR32Uint;
    if ([n isEqualToString:@"r32float"]) return MTLPixelFormatR32Float;
    if ([n isEqualToString:@"r8uint"]) return MTLPixelFormatR8Uint;
    if ([n isEqualToString:@"depth32float"]) return MTLPixelFormatDepth32Float;
    return MTLPixelFormatInvalid;
}
static NSUInteger bytes_per_texel(NSString *n) {
    if ([n isEqualToString:@"r8uint"]) return 1;
    if ([n isEqualToString:@"r32uint"] || [n isEqualToString:@"r32float"] || [n isEqualToString:@"depth32float"]) return 4;
    return 4;
}
static MTLTextureType type_from_name(NSString *n) {
    if ([n isEqualToString:@"1d"]) return MTLTextureType1D;
    if ([n isEqualToString:@"1darray"]) return MTLTextureType1DArray;
    if ([n isEqualToString:@"2d"]) return MTLTextureType2D;
    if ([n isEqualToString:@"2darray"]) return MTLTextureType2DArray;
    if ([n isEqualToString:@"3d"]) return MTLTextureType3D;
    if ([n isEqualToString:@"cube"]) return MTLTextureTypeCube;
    if ([n isEqualToString:@"cubearray"]) return MTLTextureTypeCubeArray;
    if ([n isEqualToString:@"2dms"]) return MTLTextureType2DMultisample;
    return MTLTextureType2D;
}

static NSMutableDictionary *g_textures; // id string -> id<MTLTexture>
static NSMutableDictionary *g_samplers;   // id string -> id<MTLSamplerState>
static NSMutableDictionary *g_ubuffers;   // id string -> id<MTLBuffer>
static NSMutableDictionary *g_argbuffers; // id string -> id<MTLBuffer>

static NSData *hexToData(NSString *h) {
    if (h.length == 0) return [NSData data];
    NSMutableData *d = [NSMutableData dataWithCapacity:h.length / 2];
    unsigned char cur = 0;
    for (NSUInteger i = 0; i < h.length; i++) {
        unichar c = [h characterAtIndex:i];
        int v = (c >= '0' && c <= '9') ? c - '0' : (c >= 'a' && c <= 'f') ? c - 'a' + 10 : (c >= 'A' && c <= 'F') ? c - 'A' + 10 : -1;
        if (v < 0) continue;
        if (i % 2 == 0) cur = v << 4; else { cur |= v; [d appendBytes:&cur length:1]; }
    }
    return d;
}

static void build_textures(void) {
    g_textures = [NSMutableDictionary dictionary];
    for (NSDictionary *td in aarr(@"textures")) {
        NSString *tid = td[@"id"];
        NSString *(^tds)(NSString *) = ^NSString *(NSString *k) { id v = td[k]; return [v isKindOfClass:NSString.class] ? v : nil; };
        NSInteger (^tdi)(NSString *, NSInteger) = ^NSInteger(NSString *k, NSInteger d) { id v = td[k]; return v ? [v integerValue] : d; };
        NSString *tt = tds(@"type") ?: @"2d";
        NSString *fmtName = tds(@"format") ?: @"r32uint";
        MTLPixelFormat fmt = fmt_from_name(fmtName);
        NSUInteger w = MAX(1, tdi(@"width", 1)), h = MAX(1, tdi(@"height", 1)), dep = MAX(1, tdi(@"depth", 1));
        NSUInteger arrayLen = MAX(1, tdi(@"arrayLength", 1));
        NSUInteger sampleCount = MAX(1, tdi(@"sampleCount", 1));
        NSUInteger mipLevels = MAX(1, tdi(@"mipLevelCount", 1));
        NSArray *usageList = td[@"usage"] ?: @[@"read"];
        MTLTextureUsage usage = 0;
        if ([usageList containsObject:@"read"]) usage |= MTLTextureUsageShaderRead;
        if ([usageList containsObject:@"write"]) usage |= MTLTextureUsageShaderWrite;
        MTLTextureDescriptor *desc = [MTLTextureDescriptor new];
        desc.textureType = type_from_name(tt);
        desc.pixelFormat = fmt;
        desc.width = w; desc.height = h; desc.depth = dep;
        desc.arrayLength = arrayLen;
        desc.sampleCount = sampleCount;
        desc.mipmapLevelCount = mipLevels;
        desc.usage = usage;
        desc.storageMode = MTLStorageModeShared;
        id<MTLTexture> t = [g_device newTextureWithDescriptor:desc];
        if (!t) { S_resource_ok = NO; S_resource_error = [NSString stringWithFormat:@"texture nil for %@", tid]; finish("texture_rejected", 0); }
        g_textures[tid] = t;
        NSUInteger texel = bytes_per_texel(fmtName);
        // CPU population: list of {"slice":int, "mip":int, "bytes_hex":hex}. slice/mip default 0.
        for (NSDictionary *pop in td[@"cpu_populate"] ?: @[]) {
            NSUInteger slice = [pop[@"slice"] unsignedIntegerValue];
            NSUInteger mip = [pop[@"mip"] unsignedIntegerValue];
            NSData *bytes = hexToData(pop[@"bytes_hex"]);
            NSUInteger mw = MAX(1, w >> mip), mh = MAX(1, h >> mip), md = MAX(1, dep >> mip);
            MTLRegion region = MTLRegionMake3D(0, 0, 0, mw, mh, md);
            @try {
                [t replaceRegion:region mipmapLevel:mip slice:slice withBytes:bytes.bytes bytesPerRow:mw * texel bytesPerImage:mw * mh * texel];
            } @catch (NSException *ex) {
                S_resource_ok = NO; S_resource_error = [NSString stringWithFormat:@"replaceRegion exception %@: %@", tid, ex.reason];
            }
        }
    }
}

static void build_samplers(void) {
    g_samplers = [NSMutableDictionary dictionary];
    static NSDictionary *cmp;
    if (!cmp) cmp = @{ @"never": @(MTLCompareFunctionNever), @"less": @(MTLCompareFunctionLess), @"equal": @(MTLCompareFunctionEqual),
        @"lessequal": @(MTLCompareFunctionLessEqual), @"greater": @(MTLCompareFunctionGreater), @"notequal": @(MTLCompareFunctionNotEqual),
        @"greaterequal": @(MTLCompareFunctionGreaterEqual), @"always": @(MTLCompareFunctionAlways) };
    static NSDictionary *addr;
    if (!addr) addr = @{ @"clamptoedge": @(MTLSamplerAddressModeClampToEdge), @"clamptozero": @(MTLSamplerAddressModeClampToZero),
        @"repeat": @(MTLSamplerAddressModeRepeat), @"mirrorrepeat": @(MTLSamplerAddressModeMirrorRepeat) };
    for (NSDictionary *sd in aarr(@"samplers")) {
        NSString *sid = sd[@"id"];
        MTLSamplerDescriptor *d = [MTLSamplerDescriptor new];
        d.normalizedCoordinates = [(sd[@"normalized"] ?: @YES) boolValue];
        NSString *addrName = sd[@"address"] ?: @"clamptoedge";
        MTLSamplerAddressMode am = (MTLSamplerAddressMode)[addr[addrName] integerValue];
        d.sAddressMode = d.tAddressMode = d.rAddressMode = am;
        NSString *filter = sd[@"filter"] ?: @"nearest";
        d.minFilter = d.magFilter = [filter isEqualToString:@"linear"] ? MTLSamplerMinMagFilterLinear : MTLSamplerMinMagFilterNearest;
        NSString *mipFilter = sd[@"mipFilter"] ?: @"notmipmapped";
        d.mipFilter = [mipFilter isEqualToString:@"nearest"] ? MTLSamplerMipFilterNearest
                     : [mipFilter isEqualToString:@"linear"] ? MTLSamplerMipFilterLinear : MTLSamplerMipFilterNotMipmapped;
        NSString *compare = sd[@"compare"];
        if (compare) d.compareFunction = (MTLCompareFunction)[cmp[compare] integerValue];
        if (sd[@"lodMinClamp"]) d.lodMinClamp = [sd[@"lodMinClamp"] floatValue];
        if (sd[@"lodMaxClamp"]) d.lodMaxClamp = [sd[@"lodMaxClamp"] floatValue];
        id<MTLSamplerState> s = [g_device newSamplerStateWithDescriptor:d];
        g_samplers[sid] = s;
    }
}

static float parse_float_token(id v, double dflt) {
    if ([v isKindOfClass:NSString.class]) {
        NSString *s = [(NSString *)v lowercaseString];
        if ([s isEqualToString:@"nan"]) return NAN;
        if ([s isEqualToString:@"inf"] || [s isEqualToString:@"+inf"]) return INFINITY;
        if ([s isEqualToString:@"-inf"]) return -INFINITY;
        return [s floatValue];
    }
    if (v) return [v floatValue];
    return (float)dflt;
}

static void build_ubuffers(void) {
    g_ubuffers = [NSMutableDictionary dictionary];
    for (NSDictionary *ud in aarr(@"buffers")) {
        NSString *uid = ud[@"id"];
        NSString *kind = ud[@"kind"] ?: @"u32";
        NSArray *values = ud[@"values"] ?: @[];
        NSMutableData *data = [NSMutableData data];
        for (id v in values) {
            if ([kind isEqualToString:@"f32"]) { float f = parse_float_token(v, 0); [data appendBytes:&f length:4]; }
            else if ([kind isEqualToString:@"i32"]) { int32_t i32 = (int32_t)[v intValue]; [data appendBytes:&i32 length:4]; }
            else { uint32_t u = (uint32_t)[v unsignedLongLongValue]; [data appendBytes:&u length:4]; }
        }
        if (data.length == 0) { uint32_t z = 0; [data appendBytes:&z length:4]; }
        id<MTLBuffer> b = [g_device newBufferWithBytes:data.bytes length:data.length options:MTLResourceStorageModeShared];
        g_ubuffers[uid] = b;
    }
}

static void build_argbuffer(NSDictionary *abd, id<MTLFunction> fn) {
    NSString *abid = abd[@"id"];
    id<MTLArgumentEncoder> enc = [fn newArgumentEncoderWithBufferIndex:0];
    if (!enc) { S_resource_ok = NO; S_resource_error = [NSString stringWithFormat:@"no argument encoder for %@", abid]; finish("resource_failed", 3); }
    NSUInteger len = enc.encodedLength;
    id<MTLBuffer> buf = [g_device newBufferWithLength:len options:MTLResourceStorageModeShared];
    if (!buf) { S_resource_ok = NO; S_resource_error = @"argbuffer alloc failed"; finish("resource_failed", 3); }
    memset(buf.contents, 0xDE, len);
    [enc setArgumentBuffer:buf offset:0];
    for (NSDictionary *ent in abd[@"entries"] ?: @[]) {
        NSUInteger idx = [ent[@"index"] unsignedIntegerValue];
        id<MTLTexture> tex = g_textures[ent[@"texture"]];
        [enc setTexture:tex atIndex:idx];
    }
    g_argbuffers[abid] = buf;
}

static void emit_descriptor_result(NSString *fam, BOOL textureOk, NSString *type, NSUInteger width, NSUInteger height,
                                    NSUInteger depth, NSUInteger arrayLength, NSUInteger sampleCount, NSUInteger actualSampleCount) {
    printf("{\"schema\":1,\"family\":"); jstr(fam);
    printf(",\"case\":"); jstr(@(g_case));
    printf(",\"type\":"); jstr(type);
    printf(",\"width\":%lu,\"height\":%lu,\"depth\":%lu,\"arrayLength\":%lu,\"sampleCount\":%lu,\"actualSampleCount\":%lu,\"texture_ok\":%s,\"device\":",
           (unsigned long)width, (unsigned long)height, (unsigned long)depth, (unsigned long)arrayLength,
           (unsigned long)sampleCount, (unsigned long)actualSampleCount, textureOk ? "true" : "false");
    js(S_device);
    printf("}\n");
    fflush(NULL);
}

int main(int argc, const char **argv) { @autoreleasepool {
    init_state();
    g_argbuffers = [NSMutableDictionary dictionary];
    NSString *argsJson = nil;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--family") && i + 1 < argc) g_family = argv[++i];
        else if (!strcmp(argv[i], "--case") && i + 1 < argc) g_case = argv[++i];
        else if (!strcmp(argv[i], "--source") && i + 1 < argc) g_source = argv[++i];
        else if (!strcmp(argv[i], "--args") && i + 1 < argc) argsJson = @(argv[++i]);
    }
    if (!g_family[0] || !g_case[0] || !argsJson) return 2;
    NSError *je = nil;
    g_args = [NSJSONSerialization JSONObjectWithData:[argsJson dataUsingEncoding:NSUTF8StringEncoding] options:0 error:&je];
    if (![g_args isKindOfClass:NSDictionary.class]) { fprintf(stderr, "ARGS_PARSE_FAIL\n"); return 2; }

    if (!strcmp(g_family, "b_descriptor")) {
        // Descriptor-only probe (TEX-23/TEX-25 creation half): no library
        // compile, no dispatch. Tests -[MTLDevice newTextureWithDescriptor:]
        // directly for the given type/dimensions/sampleCount. Pre-freeze
        // exploration (analysis/pilot/explore.m) determined every illegal
        // case here is a hard process abort via
        // -[MTLTextureDescriptor validateWithDevice:]'s assertion --
        // uncatchable by @try/@catch. That abort (SIGABRT, receipt exit -6)
        // IS the recorded observation for an illegal case; run.py/verify.py
        // treat it as a legitimate, pre-registered outcome.
        g_device = MTLCreateSystemDefaultDevice();
        if (!g_device) return 3;
        S_device = g_device.name;
        NSString *type = as_(@"type", @"2d");
        NSUInteger width = (NSUInteger)ai(@"width", 4);
        NSUInteger height = (NSUInteger)ai(@"height", 4);
        NSUInteger depth = (NSUInteger)ai(@"depth", 1);
        NSUInteger arrayLength = (NSUInteger)ai(@"arrayLength", 1);
        NSUInteger sampleCount = (NSUInteger)ai(@"sampleCount", 1);
        MTLTextureDescriptor *td = [MTLTextureDescriptor new];
        td.textureType = type_from_name(type);
        td.pixelFormat = [type isEqualToString:@"2dms"] ? MTLPixelFormatR32Uint : MTLPixelFormatR8Uint;
        td.width = width; td.height = height; td.depth = depth; td.arrayLength = arrayLength; td.sampleCount = sampleCount;
        td.usage = MTLTextureUsageShaderRead;
        td.storageMode = MTLStorageModeShared;
        id<MTLTexture> t = [g_device newTextureWithDescriptor:td];
        // If we reach here, the descriptor was accepted (no abort fired).
        emit_descriptor_result(@"b_descriptor", t != nil, type, width, height, depth, arrayLength, sampleCount, t ? t.sampleCount : 0);
        return 0;
    }
    if (!strcmp(g_family, "b03_query")) {
        // TEX-25 query half: device.supportsTextureSampleCount: only. No
        // texture creation, no library, always exits 0.
        g_device = MTLCreateSystemDefaultDevice();
        if (!g_device) return 3;
        S_device = g_device.name;
        NSUInteger sc = (NSUInteger)ai(@"sample_count", 1);
        BOOL supported = [g_device supportsTextureSampleCount:sc];
        printf("{\"schema\":1,\"family\":\"b03_query\",\"case\":");
        jstr(@(g_case));
        printf(",\"sample_count\":%lu,\"supported\":%s,\"device\":", (unsigned long)sc, supported ? "true" : "false");
        js(S_device);
        printf("}\n");
        fflush(NULL);
        return 0;
    }

    dispatch_semaphore_t sem_compile = dispatch_semaphore_create(0);
    dispatch_semaphore_t sem_dispatch = dispatch_semaphore_create(0);

    dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED, 0), ^{
        @try {
            g_device = MTLCreateSystemDefaultDevice();
            if (!g_device) finish("device_failed", 3);
            S_device = g_device.name;
            id<MTLLibrary> lib = compile_library(); // finish()es with status "library_failed" on a contracted compile-rejection case
            build_textures();
            build_samplers();
            build_ubuffers();
            id<MTLBuffer> outBuf = make_out_buffer();

            NSMutableDictionary *pipelines = [NSMutableDictionary dictionary];

            dispatch_semaphore_signal(sem_compile); // compile/resource phase complete; NOT a completion signal

            id<MTLCommandQueue> cq = [g_device newCommandQueue];
            if (!cq) finish("queue_failed", 3);
            id<MTLCommandBuffer> cb = [cq commandBuffer];
            if (!cb) finish("command_resource_failed", 3);

            for (NSDictionary *disp in aarr(@"dispatches")) {
                NSString *kname = disp[@"kernel"];
                id<MTLComputePipelineState> pso = pipelines[kname];
                if (!pso) {
                    id<MTLFunction> fn = [lib newFunctionWithName:kname];
                    if (!fn) { note_pipeline(kname, NO, nil); finish("function_missing", 0); }
                    for (NSString *abRef in [disp[@"buffers"] allValues]) {
                        if ([abRef hasPrefix:@"ARGBUF:"]) {
                            NSString *abid = [abRef substringFromIndex:7];
                            if (!g_argbuffers[abid]) {
                                NSDictionary *abd = nil;
                                for (NSDictionary *cand in aarr(@"argument_buffers")) if ([cand[@"id"] isEqualToString:abid]) abd = cand;
                                if (abd) build_argbuffer(abd, fn);
                            }
                        }
                    }
                    NSError *pe = nil;
                    pso = [g_device newComputePipelineStateWithFunction:fn error:&pe];
                    note_pipeline(kname, pso != nil, pe);
                    if (!pso) finish("pipeline_rejected", 0);
                    pipelines[kname] = pso;
                }
                id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
                [enc setComputePipelineState:pso];
                NSDictionary *texMap = disp[@"textures"] ?: @{};
                for (NSString *idxs in texMap) {
                    id<MTLTexture> t = g_textures[texMap[idxs]];
                    [enc setTexture:t atIndex:[idxs integerValue]];
                }
                NSDictionary *smpMap = disp[@"samplers"] ?: @{};
                for (NSString *idxs in smpMap) {
                    id<MTLSamplerState> s = g_samplers[smpMap[idxs]];
                    [enc setSamplerState:s atIndex:[idxs integerValue]];
                }
                NSDictionary *bufMap = disp[@"buffers"] ?: @{};
                for (NSString *idxs in bufMap) {
                    NSString *ref = bufMap[idxs];
                    id<MTLBuffer> b = nil;
                    if ([ref isEqualToString:@"OUT"]) b = outBuf;
                    else if ([ref hasPrefix:@"ARGBUF:"]) {
                        b = g_argbuffers[[ref substringFromIndex:7]];
                        NSDictionary *abd = nil;
                        for (NSDictionary *cand in aarr(@"argument_buffers")) if ([[@"ARGBUF:" stringByAppendingString:cand[@"id"]] isEqualToString:ref]) abd = cand;
                        for (NSDictionary *ent in abd[@"entries"] ?: @[]) {
                            id<MTLTexture> t = g_textures[ent[@"texture"]];
                            if (t) [enc useResource:t usage:MTLResourceUsageRead | MTLResourceUsageWrite];
                        }
                    }
                    else b = g_ubuffers[ref];
                    NSUInteger boff = [ref isEqualToString:@"OUT"] ? 16 : 0;
                    [enc setBuffer:b offset:boff atIndex:[idxs integerValue]];
                }
                NSUInteger tgw = MAX(1, [disp[@"threads"] integerValue]);
                [enc dispatchThreads:MTLSizeMake(tgw, 1, 1) threadsPerThreadgroup:MTLSizeMake(1, 1, 1)];
                [enc endEncoding];
            }
            [cb commit];
            [cb waitUntilCompleted];
            S_cb_status = (long)cb.status;
            S_cb_error = cb.error.localizedDescription ?: @"";
            if (cb.status != MTLCommandBufferStatusCompleted) finish("command_buffer_error", 0);
            finish("ok", 0);
        }
        @catch (NSException *ex) {
            S_resource_error = [NSString stringWithFormat:@"exception: %@: %@", ex.name, ex.reason];
            finish("exception", 7);
        }
    });

    if (dispatch_semaphore_wait(sem_compile, dispatch_time(DISPATCH_TIME_NOW, 60LL * NSEC_PER_SEC))) {
        fprintf(stderr, "compile-phase watchdog fired\n");
        finish("compile_timeout", 5);
    }
    if (dispatch_semaphore_wait(sem_dispatch, dispatch_time(DISPATCH_TIME_NOW, 120LL * NSEC_PER_SEC))) {
        fprintf(stderr, "dispatch-phase watchdog fired\n");
        finish("dispatch_timeout", 6);
    }
    for (;;) pause();
} }
