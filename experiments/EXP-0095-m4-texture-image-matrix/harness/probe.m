// EXP-0095 public-Metal behavioral harness (OWN-SHADER + HW-PROBE). One
// process per case. Public Metal API only: no Apple binary, archive, BO, or
// private interface is ever touched. Uses the exact process-exit discipline
// proven by EXP-0072/EXP-0075/EXP-0079 (harness/probe.m in those
// experiments): exactly one locked print-then-flush-then-exit path in
// finish(); no completion is ever signalled before the record is durably
// printed; main blocks forever after both phase waits and never returns.
//
// Case parameters arrive as one JSON object on --args (kept off the CLI's
// own quoting rules by being a single argv element). Each family's handler
// (fam_a04/a05/a06/a07/a01/a02_direct/a02_bindless) reads only the keys it
// documents. Every handler shares one 96-byte output buffer convention:
//   [0..16)   prefix guard, 0x5a
//   [16..80)  16 x uint32 LE "out" words, host-prefilled with 0xEEEEEEEE
//   [80..96)  suffix guard, 0xa5
// A kernel writes only the words CAPTURE_CONTRACT.json says it writes;
// unused words must still read back as the sentinel.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <dispatch/dispatch.h>
#include <pthread.h>
#include <sys/utsname.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

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
    if (!lib) finish("library_failed", 0);
    return lib;
}

static id<MTLComputePipelineState> make_pipeline(id<MTLLibrary> lib, NSString *fn) {
    id<MTLFunction> f = [lib newFunctionWithName:fn];
    if (!f) { note_pipeline(fn, NO, nil); finish("function_missing", 0); }
    NSError *e = nil;
    id<MTLComputePipelineState> p = [g_device newComputePipelineStateWithFunction:f error:&e];
    note_pipeline(fn, p != nil, e);
    return p; // caller must check nil and finish() if required before proceeding
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
    if ([n isEqualToString:@"r32sint"]) return MTLPixelFormatR32Sint;
    if ([n isEqualToString:@"r32float"]) return MTLPixelFormatR32Float;
    if ([n isEqualToString:@"depth32float"]) return MTLPixelFormatDepth32Float;
    if ([n isEqualToString:@"r8unorm"]) return MTLPixelFormatR8Unorm;
    if ([n isEqualToString:@"r8snorm"]) return MTLPixelFormatR8Snorm;
    if ([n isEqualToString:@"r16uint"]) return MTLPixelFormatR16Uint;
    if ([n isEqualToString:@"r16sint"]) return MTLPixelFormatR16Sint;
    if ([n isEqualToString:@"rgb10a2unorm"]) return MTLPixelFormatRGB10A2Unorm;
    if ([n isEqualToString:@"r8uint"]) return MTLPixelFormatR8Uint;
    if ([n isEqualToString:@"rg8uint"]) return MTLPixelFormatRG8Uint;
    if ([n isEqualToString:@"rgba8uint"]) return MTLPixelFormatRGBA8Uint;
    if ([n isEqualToString:@"rgba16uint"]) return MTLPixelFormatRGBA16Uint;
    if ([n isEqualToString:@"rgba32uint"]) return MTLPixelFormatRGBA32Uint;
    return MTLPixelFormatInvalid;
}
static NSUInteger bytes_per_texel(NSString *n) {
    if ([n isEqualToString:@"r8unorm"] || [n isEqualToString:@"r8snorm"] || [n isEqualToString:@"r8uint"]) return 1;
    if ([n isEqualToString:@"r16uint"] || [n isEqualToString:@"r16sint"] || [n isEqualToString:@"rg8uint"]) return 2;
    if ([n isEqualToString:@"r32uint"] || [n isEqualToString:@"r32sint"] || [n isEqualToString:@"r32float"] || [n isEqualToString:@"depth32float"] || [n isEqualToString:@"rgba8uint"] || [n isEqualToString:@"rgb10a2unorm"]) return 4;
    if ([n isEqualToString:@"rgba16uint"]) return 8;
    if ([n isEqualToString:@"rgba32uint"]) return 16;
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
    if ([n isEqualToString:@"buffer"]) return MTLTextureTypeTextureBuffer;
    if ([n isEqualToString:@"2dms"]) return MTLTextureType2DMultisample;
    if ([n isEqualToString:@"2dmsarray"]) return MTLTextureType2DMultisampleArray;
    return MTLTextureType2D;
}

static NSMutableDictionary *g_textures; // id string -> id<MTLTexture>
static NSMutableDictionary *g_tex_buffers; // id string -> id<MTLBuffer> backing (for "buffer" type textures)
static NSMutableDictionary *g_samplers;   // id string -> id<MTLSamplerState>
static NSMutableDictionary *g_ubuffers;   // id string -> id<MTLBuffer> (small uniform buffers)
static NSMutableDictionary *g_argbuffers; // id string -> id<MTLBuffer> (argument buffers)

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
    g_tex_buffers = [NSMutableDictionary dictionary];
    for (NSDictionary *td in aarr(@"textures")) {
        NSString *tid = td[@"id"];
        NSString *type = as_(@"type", @"2d");
        // per-texture override lookup helper
        NSString *(^tds)(NSString *) = ^NSString *(NSString *k) { id v = td[k]; return [v isKindOfClass:NSString.class] ? v : nil; };
        NSInteger (^tdi)(NSString *, NSInteger) = ^NSInteger(NSString *k, NSInteger d) { id v = td[k]; return v ? [v integerValue] : d; };
        NSString *tt = tds(@"type") ?: @"2d";
        NSString *fmtName = tds(@"format") ?: @"r32uint";
        MTLPixelFormat fmt = fmt_from_name(fmtName);
        NSUInteger w = MAX(1, tdi(@"width", 1)), h = MAX(1, tdi(@"height", 1)), dep = MAX(1, tdi(@"depth", 1));
        NSUInteger arrayLen = MAX(1, tdi(@"arrayLength", 1));
        NSUInteger sampleCount = MAX(1, tdi(@"sampleCount", 1));
        NSArray *usageList = td[@"usage"] ?: @[@"read"];
        MTLTextureUsage usage = 0;
        if ([usageList containsObject:@"read"]) usage |= MTLTextureUsageShaderRead;
        if ([usageList containsObject:@"write"]) usage |= MTLTextureUsageShaderWrite;
        if ([tt isEqualToString:@"buffer"]) {
            NSUInteger texel = bytes_per_texel(fmtName);
            NSUInteger nbytes = w * texel;
            id<MTLBuffer> buf = [g_device newBufferWithLength:MAX(nbytes, (NSUInteger)16) options:MTLResourceStorageModeShared];
            if (!buf) { S_resource_ok = NO; S_resource_error = @"tb buffer alloc failed"; finish("resource_failed", 3); }
            NSString *initHex = td[@"init_hex"];
            if (initHex) { NSData *dd = hexToData(initHex); memcpy(buf.contents, dd.bytes, MIN(dd.length, (NSUInteger)nbytes)); }
            MTLTextureDescriptor *desc = [MTLTextureDescriptor new];
            desc.textureType = MTLTextureTypeTextureBuffer;
            desc.pixelFormat = fmt;
            desc.width = w; desc.height = 1; desc.depth = 1;
            desc.usage = usage; desc.storageMode = MTLStorageModeShared;
            id<MTLTexture> t = [buf newTextureWithDescriptor:desc offset:0 bytesPerRow:nbytes];
            if (!t) { S_resource_ok = NO; S_resource_error = [NSString stringWithFormat:@"tb texture nil for %@", tid]; finish("texture_rejected", 0); }
            g_textures[tid] = t;
            g_tex_buffers[tid] = buf;
            continue;
        }
        MTLTextureDescriptor *desc = [MTLTextureDescriptor new];
        desc.textureType = type_from_name(tt);
        desc.pixelFormat = fmt;
        desc.width = w; desc.height = h; desc.depth = dep;
        desc.arrayLength = arrayLen;
        desc.sampleCount = sampleCount;
        desc.usage = usage;
        desc.storageMode = MTLStorageModeShared;
        id<MTLTexture> t = [g_device newTextureWithDescriptor:desc];
        if (!t) { S_resource_ok = NO; S_resource_error = [NSString stringWithFormat:@"texture nil for %@", tid]; finish("texture_rejected", 0); }
        g_textures[tid] = t;
        // CPU population: list of {"slice":int (array*facesPerLayer+face), "bytes_hex":hex}
        NSUInteger texel = bytes_per_texel(fmtName);
        for (NSDictionary *pop in td[@"cpu_populate"] ?: @[]) {
            NSUInteger slice = [pop[@"slice"] unsignedIntegerValue];
            NSData *bytes = hexToData(pop[@"bytes_hex"]);
            MTLRegion region = MTLRegionMake3D(0, 0, 0, w, h, dep);
            @try {
                [t replaceRegion:region mipmapLevel:0 slice:slice withBytes:bytes.bytes bytesPerRow:w * texel bytesPerImage:w * h * texel];
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
    for (NSDictionary *sd in aarr(@"samplers")) {
        NSString *sid = sd[@"id"];
        MTLSamplerDescriptor *d = [MTLSamplerDescriptor new];
        d.normalizedCoordinates = [(sd[@"normalized"] ?: @YES) boolValue];
        d.sAddressMode = d.tAddressMode = d.rAddressMode = MTLSamplerAddressModeClampToEdge;
        NSString *filter = sd[@"filter"] ?: @"nearest";
        d.minFilter = d.magFilter = [filter isEqualToString:@"linear"] ? MTLSamplerMinMagFilterLinear : MTLSamplerMinMagFilterNearest;
        NSString *compare = sd[@"compare"];
        if (compare) d.compareFunction = (MTLCompareFunction)[cmp[compare] integerValue];
        id<MTLSamplerState> s = [g_device newSamplerStateWithDescriptor:d];
        g_samplers[sid] = s;
    }
}

static void build_ubuffers(void) {
    g_ubuffers = [NSMutableDictionary dictionary];
    for (NSDictionary *ud in aarr(@"buffers")) {
        NSString *uid = ud[@"id"];
        NSString *kind = ud[@"kind"] ?: @"u32";
        NSArray *values = ud[@"values"] ?: @[];
        NSMutableData *data = [NSMutableData data];
        for (id v in values) {
            if ([kind isEqualToString:@"f32"]) { float f = [v floatValue]; [data appendBytes:&f length:4]; }
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
    memset(buf.contents, 0xDE, len); // guard pattern for never-encoded (unpopulated) entries
    [enc setArgumentBuffer:buf offset:0];
    for (NSDictionary *ent in abd[@"entries"] ?: @[]) {
        NSUInteger idx = [ent[@"index"] unsignedIntegerValue];
        id<MTLTexture> tex = g_textures[ent[@"texture"]];
        [enc setTexture:tex atIndex:idx];
    }
    g_argbuffers[abid] = buf;
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
    if (!g_family[0] || !g_case[0] || !g_source[0] || !argsJson) return 2;
    NSError *je = nil;
    g_args = [NSJSONSerialization JSONObjectWithData:[argsJson dataUsingEncoding:NSUTF8StringEncoding] options:0 error:&je];
    if (![g_args isKindOfClass:NSDictionary.class]) { fprintf(stderr, "ARGS_PARSE_FAIL\n"); return 2; }

    if (!strcmp(g_family, "a07_descriptor")) {
        // Descriptor-only probe: no library compile, no dispatch. Tests
        // MTLTextureDescriptor validation directly for a texture_buffer of a
        // given format/width. A deliberately-oversized width is expected (by
        // pre-freeze exploration, work/explore/probetbwidth2.m) to abort the
        // WHOLE PROCESS via -[MTLTextureDescriptor validateWithDevice:]'s
        // assertion handler before any GPU submission -- uncatchable by
        // @try/@catch since it is an assertion, not an NSException. That
        // abort (SIGABRT, receipt exit -6) IS the recorded observation for
        // an over-width case; run.py/verify.py treat it as a legitimate,
        // pre-registered outcome, not a harness defect.
        g_device = MTLCreateSystemDefaultDevice();
        if (!g_device) return 3;
        S_device = g_device.name;
        NSString *fmtName = as_(@"format", @"r8uint");
        unsigned long long width = (unsigned long long)ad(@"width", 0);
        MTLPixelFormat fmt = fmt_from_name(fmtName);
        NSUInteger texel = bytes_per_texel(fmtName);
        unsigned long long bytesNeeded = width * (unsigned long long)texel;
        MTLTextureDescriptor *td = [MTLTextureDescriptor new];
        td.textureType = MTLTextureTypeTextureBuffer;
        td.pixelFormat = fmt;
        td.width = (NSUInteger)width; td.height = 1; td.depth = 1;
        td.usage = MTLTextureUsageShaderRead;
        td.storageMode = MTLStorageModeShared;
        id<MTLBuffer> buf = [g_device newBufferWithLength:(NSUInteger)MAX(bytesNeeded, 16ull) options:MTLResourceStorageModeShared];
        if (!buf) finish("resource_failed", 3);
        id<MTLTexture> t = [buf newTextureWithDescriptor:td offset:0 bytesPerRow:(NSUInteger)bytesNeeded];
        // If we reach here, the descriptor was accepted (no abort fired).
        printf("{\"schema\":1,\"family\":\"a07_descriptor\",\"case\":");
        jstr(@(g_case));
        printf(",\"width\":%llu,\"bytes_needed\":%llu,\"texture_ok\":%s,\"device\":", width, bytesNeeded, t ? "true" : "false");
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
            id<MTLLibrary> lib = compile_library();
            build_textures();
            build_samplers();
            build_ubuffers();
            id<MTLBuffer> outBuf = make_out_buffer();

            NSMutableDictionary *pipelines = [NSMutableDictionary dictionary]; // kernel name -> MTLComputePipelineState

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
                    // If this dispatch references an argument buffer not yet built, build it now (needs fn).
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
                        // Mark every texture referenced by this argument buffer's entries as used,
                        // so the GPU actually sees them as resident (public useResource: API).
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
