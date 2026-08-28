// EXP-0134 cprobe.m -- M4 lossless-compression probe (DRV-P2-01).
//
// Clean-room: HW-PROBE (known pattern in, raw layout/state out) + OWN-SHADER (our MSL,
// compiled at runtime via newLibraryWithSource:) + DATA-TRACE (our own process's GPU
// buffer objects, snapshotted by the READ-ONLY tools/iotrace interposer -- built
// unmodified into work/iotrace.dylib, never edited). No Apple binary is disassembled,
// decompiled, or otherwise introspected anywhere in this file. Method follows the
// established EXP-0017 / EXP-M4-07 precedent (texprobe.m, typrobe2.m, wbtest.m,
// mssync.m) -- our own prior authored code, reused and extended, not Apple code.
//
// One case per process (SAFETY: illegal/edge-case texture configs and CPU-visible
// splices can fault the context). Protocol: STATUS/DEVICE/CONFIG/OBSERVED text lines
// on stdout (EXP-0098/EXP-0124 convention). Descriptor + aux bytes are NOT decoded
// here -- this binary only creates the resource, writes a known pattern via the render
// pipeline (image-store/ShaderWrite is deliberately never used for compression-eligible
// cases, since ShaderWrite itself disables compression -- see PRE_REGISTRATION), performs
// any requested CPU-visible operation, and SIGUSR1-dumps every registered BO for the
// host-side analyzer (harness/auxdecode.py) to decode. Every probe texture in the
// "probe" kind carries MTLTextureUsageShaderRead so its 32-byte sampled descriptor is
// captured by binding it into a tiny read kernel's Tier-2 argument buffer, exactly as
// EXP-0017/EXP-M4-07 established (see PRE_REGISTRATION scope note on RT-only/write-only
// non-ShaderRead resources).
//
// Build: clang -fobjc-arc -framework Metal -framework Foundation -o work/bin/cprobe harness/cprobe.m
// Usage: cprobe <kind> <json-params>
//   kind: "probe" (the only kind implemented; params select the sub-behavior)

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

// ---------------------------------------------------------------------------
static void emit_status(const char *s) { printf("STATUS %s\n", s); }
static void finish(void) { if (fflush(NULL) != 0) perror("fflush"); }
static void fail(const char *status, const char *msg, NSError *err) {
    emit_status(status);
    if (err)      printf("ERROR %s: %s\n", msg, [[err localizedDescription] UTF8String]);
    else if (msg) printf("ERROR %s\n", msg);
    finish();
    exit(1);
}

static NSDictionary *parseParams(const char *json) {
    NSData *d = [NSData dataWithBytes:json length:strlen(json)];
    NSError *err = nil;
    id obj = [NSJSONSerialization JSONObjectWithData:d options:0 error:&err];
    if (!obj || ![obj isKindOfClass:[NSDictionary class]]) fail("HARNESS_CRASH", "bad params json", err);
    return obj;
}
static long long pint(NSDictionary *p, NSString *k, long long defv)   { id v = p[k]; return v ? [v longLongValue]   : defv; }
static double     pdbl(NSDictionary *p, NSString *k, double defv)     { id v = p[k]; return v ? [v doubleValue]     : defv; }
static NSString  *pstr(NSDictionary *p, NSString *k, NSString *defv)  { id v = p[k]; return v ? v : defv; }
static BOOL       pbool(NSDictionary *p, NSString *k, BOOL defv)      { id v = p[k]; return v ? [v boolValue]       : defv; }

static void doDump(void) { finish(); kill(getpid(), SIGUSR1); usleep(600000); }

// ---------------------------------------------------------------------------
// Format table. bpp1/2/4(x3 families)/8/16, float+unorm+uint, spanning every
// aux/state case's needs.
typedef struct { const char *name; MTLPixelFormat pf; int bpp; int isUint; } Fmt;
static const Fmt FMTS[] = {
    {"r8unorm",     MTLPixelFormatR8Unorm,      1, 0},
    {"r16float",    MTLPixelFormatR16Float,     2, 0},
    {"rgba8unorm",  MTLPixelFormatRGBA8Unorm,   4, 0},
    {"r32uint",     MTLPixelFormatR32Uint,      4, 1},
    {"rgba8uint",   MTLPixelFormatRGBA8Uint,    4, 1},
    {"rgba16float", MTLPixelFormatRGBA16Float,  8, 0},
    {"rgba32float", MTLPixelFormatRGBA32Float, 16, 0},
};
static const int NFMT = sizeof(FMTS) / sizeof(FMTS[0]);
static const Fmt *findFmt(const char *n) { for (int i = 0; i < NFMT; i++) if (!strcmp(FMTS[i].name, n)) return &FMTS[i]; return NULL; }

// ---------------------------------------------------------------------------
static MTLTextureUsage parseUsage(NSString *s) {
    MTLTextureUsage u = 0;
    for (NSString *tok in [s componentsSeparatedByString:@","]) {
        if ([tok isEqualToString:@"read"])   u |= MTLTextureUsageShaderRead;
        if ([tok isEqualToString:@"write"])  u |= MTLTextureUsageShaderWrite;
        if ([tok isEqualToString:@"rt"])     u |= MTLTextureUsageRenderTarget;
        if ([tok isEqualToString:@"pfview"]) u |= MTLTextureUsagePixelFormatView;
    }
    return u;
}
static MTLStorageMode parseStorage(NSString *s) {
    if ([s isEqualToString:@"private"])    return MTLStorageModePrivate;
    if ([s isEqualToString:@"memoryless"]) return MTLStorageModeMemoryless;
    return MTLStorageModeShared;
}
static MTLTextureType parseType(NSString *s) {
    if ([s isEqualToString:@"2darray"]) return MTLTextureType2DArray;
    if ([s isEqualToString:@"cube"])    return MTLTextureTypeCube;
    if ([s isEqualToString:@"3d"])      return MTLTextureType3D;
    if ([s isEqualToString:@"2dms"])    return MTLTextureType2DMultisample;
    return MTLTextureType2D;
}

// ---------------------------------------------------------------------------
// Fragment source generators. All render-path (never ShaderWrite/image-store),
// so compression eligibility is never self-defeated by the write.
static NSString *vsrc(void) {
    return @"struct VO { float4 pos [[position]]; };\n"
            "vertex VO v_main(uint vid [[vertex_id]]) {\n"
            "  float2 p[3]={float2(-1,-3),float2(-1,1),float2(3,1)};\n"
            "  VO o; o.pos=float4(p[vid],0,1); return o; }\n";
}
static NSString *retType(int isUint) { return isUint ? @"uint4" : @"float4"; }
static NSString *fsrc(NSString *pattern, int isUint, NSDictionary *p) {
    NSString *rt = retType(isUint);
    NSString *body = nil;
    if ([pattern isEqualToString:@"gradient"]) {
        body = isUint
            ? @"uint4((x&0xffu),(y&0xffu),170u,205u)"
            : @"float4(float(x&0xff)/255.0,float(y&0xff)/255.0,170.0/255.0,205.0/255.0)";
        return [NSString stringWithFormat:@"%@fragment %@ f_main(VO in [[stage_in]]) {\n"
                "  uint x=uint(in.pos.x), y=uint(in.pos.y); return %@; }\n", vsrc(), rt, body];
    }
    if ([pattern isEqualToString:@"noise"]) {
        NSString *hash = @"uint h=(x*73856093u)^(y*19349663u); h^=h>>13; h*=0x5bd1e995u; h^=h>>15;\n";
        body = isUint ? @"uint4(h&0xffu,(h>>8)&0xffu,(h>>16)&0xffu,(h>>24)&0xffu)"
                       : @"float4(float(h&0xff)/255.0,float((h>>8)&0xff)/255.0,float((h>>16)&0xff)/255.0,float((h>>24)&0xff)/255.0)";
        return [NSString stringWithFormat:@"%@fragment %@ f_main(VO in [[stage_in]]) {\n"
                "  uint x=uint(in.pos.x), y=uint(in.pos.y); %@ return %@; }\n", vsrc(), rt, hash, body];
    }
    if ([pattern isEqualToString:@"split"]) {
        long sx = (long)pint(p, @"splitx", 32);
        double br = pdbl(p,@"br",0.5), bg = pdbl(p,@"bg",0.5), bb = pdbl(p,@"bb",0.5), ba = pdbl(p,@"ba",1.0);
        NSString *hash = @"uint h=(x*73856093u)^(y*19349663u); h^=h>>13; h*=0x5bd1e995u; h^=h>>15;\n";
        NSString *noiseVal = isUint ? @"uint4(h&0xffu,(h>>8)&0xffu,(h>>16)&0xffu,(h>>24)&0xffu)"
                                     : @"float4(float(h&0xff)/255.0,float((h>>8)&0xff)/255.0,float((h>>16)&0xff)/255.0,float((h>>24)&0xff)/255.0)";
        NSString *baseVal = isUint ? [NSString stringWithFormat:@"uint4(%lldu,%lldu,%lldu,%lldu)",(long long)br,(long long)bg,(long long)bb,(long long)ba]
                                    : [NSString stringWithFormat:@"float4(%g,%g,%g,%g)",br,bg,bb,ba];
        return [NSString stringWithFormat:@"%@fragment %@ f_main(VO in [[stage_in]]) {\n"
                "  uint x=uint(in.pos.x), y=uint(in.pos.y); %@ if (x<%ldu) return %@; return %@; }\n",
                vsrc(), rt, hash, sx, baseVal, noiseVal];
    }
    if ([pattern isEqualToString:@"outlier"]) {
        long ox = (long)pint(p, @"ox", 4), oy = (long)pint(p, @"oy", 2);
        double br=pdbl(p,@"br",0.5), bg=pdbl(p,@"bg",0.5), bb=pdbl(p,@"bb",0.5), ba=pdbl(p,@"ba",1.0);
        double orr=pdbl(p,@"orr",1.0), og=pdbl(p,@"og",0.0), ob=pdbl(p,@"ob",0.0), oa=pdbl(p,@"oa",1.0);
        NSString *baseVal, *otherVal;
        if (isUint) {
            baseVal  = [NSString stringWithFormat:@"uint4(%lldu,%lldu,%lldu,%lldu)",(long long)br,(long long)bg,(long long)bb,(long long)ba];
            otherVal = [NSString stringWithFormat:@"uint4(%lldu,%lldu,%lldu,%lldu)",(long long)orr,(long long)og,(long long)ob,(long long)oa];
        } else {
            baseVal  = [NSString stringWithFormat:@"float4(%g,%g,%g,%g)",br,bg,bb,ba];
            otherVal = [NSString stringWithFormat:@"float4(%g,%g,%g,%g)",orr,og,ob,oa];
        }
        return [NSString stringWithFormat:@"%@fragment %@ f_main(VO in [[stage_in]]) {\n"
                "  uint x=uint(in.pos.x), y=uint(in.pos.y);\n"
                "  if (x==%ldu && y==%ldu) return %@;\n  return %@; }\n",
                vsrc(), rt, ox, oy, otherVal, baseVal];
    }
    return nil; // "clear" needs no fragment shader
}

// ---------------------------------------------------------------------------
int main(int argc, char **argv) {
  @autoreleasepool {
    if (argc < 3) { fail("HARNESS_CRASH", "usage: cprobe <kind> <json>", nil); }
    const char *kind = argv[1];
    NSDictionary *p = parseParams(argv[2]);

    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    if (!dev) fail("HARNESS_CRASH", "no device", nil);
    printf("DEVICE %s\n", [[dev name] UTF8String]);

    if (strcmp(kind, "replicate") == 0) {
        // Small (< one 16KiB-tile) compression-eligible textures are suballocated from
        // a SHARED heap BO (confirmed empirically: PROGRESS.md milestone 2), so the
        // "whole-BO-size minus offset" aux measurement used for standalone-BO sizes is
        // invalid there. Instead: allocate `count` IDENTICAL eligible textures in one
        // process, bind+read each (so each descriptor materializes), dump once, and let
        // the analyzer take consecutive base_va deltas as the per-object footprint
        // (main+aux, allocator-quantum rounded) -- a direct HW measurement, not a
        // formula extrapolation.
        NSString *fmtName = pstr(p, @"fmt", @"rgba8unorm");
        long W = (long)pint(p, @"w", 16), H = (long)pint(p, @"h", 16);
        long count = (long)pint(p, @"count", 8);
        NSString *usageName = pstr(p, @"usage", @"read");
        const Fmt *F = findFmt([fmtName UTF8String]);
        if (!F) fail("HARNESS_CRASH", "unknown fmt", nil);
        printf("CONFIG fmt=%s w=%ld h=%ld count=%ld usage=%s bpp=%d\n",
               F->name, W, H, count, [usageName UTF8String], F->bpp);
        MTLTextureDescriptor *td = [MTLTextureDescriptor new];
        td.pixelFormat = F->pf; td.width = W; td.height = H; td.depth = 1; td.arrayLength = 1;
        td.textureType = MTLTextureType2D; td.usage = parseUsage(usageName);
        td.storageMode = MTLStorageModeShared; td.mipmapLevelCount = 1;
        NSError *err = nil;
        NSString *elemT = F->isUint ? @"uint" : @"float";
        NSString *rk = [NSString stringWithFormat:
            @"#include <metal_stdlib>\nusing namespace metal;\n"
             "kernel void rd(texture2d<%@, access::read> t [[texture(0)]],\n"
             "  device %@* o [[buffer(0)]], uint i [[thread_position_in_grid]]) {\n"
             "  o[i]=t.read(uint2(i&7,(i>>3)&7)).x; }\n", elemT, elemT];
        id<MTLLibrary> lib = [dev newLibraryWithSource:rk options:nil error:&err];
        id<MTLFunction> fn = lib ? [lib newFunctionWithName:@"rd"] : nil;
        id<MTLComputePipelineState> pso = fn ? [dev newComputePipelineStateWithFunction:fn error:&err] : nil;
        if (!pso) fail("PIPELINE_FAIL", "replicate rk", err);
        id<MTLCommandQueue> q = [dev newCommandQueue];
        NSMutableArray *texes = [NSMutableArray array];
        int okCount = 0;
        for (long i = 0; i < count; i++) {
            id<MTLTexture> t = [dev newTextureWithDescriptor:td];
            if (!t) continue;
            [texes addObject:t];
            id<MTLBuffer> obuf = [dev newBufferWithLength:64*4 options:MTLResourceStorageModeShared];
            id<MTLCommandBuffer> cb = [q commandBuffer];
            id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
            [enc setComputePipelineState:pso];
            [enc setTexture:t atIndex:0];
            [enc setBuffer:obuf offset:0 atIndex:0];
            [enc dispatchThreads:MTLSizeMake(64,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];
            [enc endEncoding];
            [cb commit]; [cb waitUntilCompleted];
            if ([cb status] == MTLCommandBufferStatusCompleted) okCount++;
        }
        printf("REPLICATE_CREATED %ld\nREPLICATE_OK %d\n", (long)[texes count], okCount);
        emit_status("OK");
        if (pbool(p, @"dump", YES)) doDump();
        finish();
        return 0;
    }

    if (strcmp(kind, "probe") != 0) fail("HARNESS_CRASH", "unknown kind", nil);

    NSString *fmtName  = pstr(p, @"fmt", @"rgba8unorm");
    long W = (long)pint(p, @"w", 32), H = (long)pint(p, @"h", 32);
    long D = (long)pint(p, @"d", 1), mips = (long)pint(p, @"mips", 1), samples = (long)pint(p, @"samples", 1);
    NSString *typeName    = pstr(p, @"type", @"2d");
    NSString *usageName   = pstr(p, @"usage", @"read");
    NSString *storageName = pstr(p, @"storage", @"shared");
    NSString *pattern     = pstr(p, @"pattern", @"clear");
    NSString *cpuop       = pstr(p, @"cpuop", @"none");
    BOOL linear           = pbool(p, @"linear", NO);

    const Fmt *F = findFmt([fmtName UTF8String]);
    if (!F) fail("HARNESS_CRASH", "unknown fmt", nil);
    printf("CONFIG fmt=%s w=%ld h=%ld d=%ld mips=%ld samples=%ld type=%s usage=%s storage=%s "
           "pattern=%s cpuop=%s linear=%d bpp=%d\n",
           F->name, W, H, D, mips, samples, [typeName UTF8String], [usageName UTF8String],
           [storageName UTF8String], [pattern UTF8String], [cpuop UTF8String], linear, F->bpp);

    MTLTextureUsage usage   = parseUsage(usageName);
    MTLStorageMode storage  = parseStorage(storageName);
    MTLTextureType ttype    = linear ? MTLTextureType2D : parseType(typeName);

    MTLTextureDescriptor *td = [MTLTextureDescriptor new];
    td.pixelFormat = F->pf; td.width = W; td.height = H;
    td.textureType = ttype; td.usage = usage; td.storageMode = storage;
    if (ttype == MTLTextureType2DArray) { td.depth = 1; td.arrayLength = D; }
    else if (ttype == MTLTextureType3D) { td.depth = D; td.arrayLength = 1; }
    else { td.depth = 1; td.arrayLength = 1; }
    if (ttype == MTLTextureType2DMultisample) { td.sampleCount = samples; td.mipmapLevelCount = 1; }
    else { td.mipmapLevelCount = mips; }

    id<MTLBuffer> linBuf = nil; NSUInteger bpr = 0;
    id<MTLTexture> tex = nil;
    @try {
        if (linear) {
            NSUInteger align = [dev minimumLinearTextureAlignmentForPixelFormat:F->pf];
            bpr = (NSUInteger)(W * F->bpp);
            if (align) bpr = ((bpr + align - 1) / align) * align;
            NSUInteger total = bpr * (NSUInteger)H + 0x4000;
            linBuf = [dev newBufferWithLength:total options:MTLResourceStorageModeShared];
            tex = [linBuf newTextureWithDescriptor:td offset:0 bytesPerRow:bpr];
        } else {
            tex = [dev newTextureWithDescriptor:td];
        }
    } @catch (NSException *e) {
        printf("TEX_CREATE_OK 0\n"); printf("TEX_EXCEPTION %s\n", [[e reason] UTF8String]);
        emit_status("ALLOC_REJECTED"); finish(); return 0;
    }
    if (!tex) { printf("TEX_CREATE_OK 0\n"); emit_status("ALLOC_REJECTED"); finish(); return 0; }
    printf("TEX_CREATE_OK 1\n");

    id<MTLCommandQueue> q = [dev newCommandQueue];
    int writeOk = 1, cbStatus = -1;

    // ---- write the pattern via the RENDER path only (never ShaderWrite/image-store) ----
    if (![pattern isEqualToString:@"none"] && ttype != MTLTextureType3D && ttype != MTLTextureType2DArray
        && ttype != MTLTextureTypeCube) {
        NSError *err = nil;
        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
        rp.colorAttachments[0].texture = tex;
        rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].storeAction =
            [pstr(p, @"store_action", @"store") isEqualToString:@"dontcare"]
                ? MTLStoreActionDontCare : MTLStoreActionStore;
        double cr = pdbl(p, @"r", 0.5), cg = pdbl(p, @"g", 0.5), cbl = pdbl(p, @"b", 0.5), ca = pdbl(p, @"a", 1.0);
        rp.colorAttachments[0].clearColor = MTLClearColorMake(cr, cg, cbl, ca);
        id<MTLCommandBuffer> cb = [q commandBuffer];
        if ([pattern isEqualToString:@"clear"]) {
            id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
            [enc endEncoding];
        } else {
            NSString *src = fsrc(pattern, F->isUint, p);
            id<MTLLibrary> lib = [dev newLibraryWithSource:src options:nil error:&err];
            if (!lib) fail("COMPILE_FAIL", "pattern fsrc", err);
            MTLRenderPipelineDescriptor *rpd = [MTLRenderPipelineDescriptor new];
            rpd.vertexFunction = [lib newFunctionWithName:@"v_main"];
            rpd.fragmentFunction = [lib newFunctionWithName:@"f_main"];
            rpd.colorAttachments[0].pixelFormat = F->pf;
            rpd.rasterSampleCount = samples;
            id<MTLRenderPipelineState> rps = [dev newRenderPipelineStateWithDescriptor:rpd error:&err];
            if (!rps) fail("PIPELINE_FAIL", "pattern rps", err);
            id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
            [enc setRenderPipelineState:rps];
            [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
            [enc endEncoding];
        }
        [cb commit]; [cb waitUntilCompleted];
        cbStatus = (int)[cb status];
        writeOk = (cbStatus == MTLCommandBufferStatusCompleted);
        if (!writeOk && [cb error]) printf("CB_ERROR %s\n", [[[cb error] localizedDescription] UTF8String]);
    }
    printf("WRITE_OK %d\nCB_STATUS %d\n", writeOk, cbStatus);

    if (pbool(p, @"dump_after_write", NO)) doDump();

    // ---- optional CPU-visible operation ----
    int cpuOk = 1; NSString *cpuDetail = @"";
    if ([cpuop isEqualToString:@"replace"]) {
        NSUInteger rw = (NSUInteger)pint(p, @"rw", 8), rh = (NSUInteger)pint(p, @"rh", 8);
        NSUInteger rx = (NSUInteger)pint(p, @"rx", 0), ry = (NSUInteger)pint(p, @"ry", 0);
        int fillByte = (int)pint(p, @"fill_byte", 0x11);
        size_t n = rw * rh * (size_t)F->bpp;
        unsigned char *buf = malloc(n); memset(buf, fillByte, n);
        @try {
            [tex replaceRegion:MTLRegionMake2D(rx, ry, rw, rh) mipmapLevel:0
                      withBytes:buf bytesPerRow:(rw * (NSUInteger)F->bpp)];
            cpuDetail = @"ok";
        } @catch (NSException *e) {
            cpuOk = 0; cpuDetail = [e reason] ?: @"exception";
        }
        free(buf);
        printf("CPU_OP_OK %d\nCPU_DETAIL %s\n", cpuOk, [cpuDetail UTF8String]);
    } else if ([cpuop isEqualToString:@"getbytes"]) {
        NSUInteger rw = (NSUInteger)pint(p, @"rw", 8), rh = (NSUInteger)pint(p, @"rh", 8);
        size_t n = rw * rh * (size_t)F->bpp;
        unsigned char *buf = malloc(n); memset(buf, 0, n);
        @try {
            [tex getBytes:buf bytesPerRow:(rw * (NSUInteger)F->bpp)
               fromRegion:MTLRegionMake2D(0, 0, rw, rh) mipmapLevel:0];
            cpuDetail = @"ok";
            // gradient formula check for the first texel (0,0): expect (0,0,170,205) [/255 for float]
            if ([pattern isEqualToString:@"gradient"] && !F->isUint && F->bpp == 4) {
                unsigned char exp[4] = {0,0,170,205};
                int match = (memcmp(buf, exp, 4) == 0);
                printf("GETBYTES_TEXEL00_MATCH %d\n", match);
            }
        } @catch (NSException *e) {
            cpuOk = 0; cpuDetail = [e reason] ?: @"exception";
        }
        printf("CPU_OP_OK %d\nCPU_DETAIL %s\n", cpuOk, [cpuDetail UTF8String]);
        free(buf);
    } else if ([cpuop isEqualToString:@"blit"]) {
        id<MTLTexture> tex2 = [dev newTextureWithDescriptor:td];
        if (!tex2) { cpuOk = 0; cpuDetail = @"tex2 alloc failed"; }
        else {
            id<MTLCommandBuffer> cb = [q commandBuffer];
            id<MTLBlitCommandEncoder> bl = [cb blitCommandEncoder];
            [bl copyFromTexture:tex sourceSlice:0 sourceLevel:0
                     sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(W,H,1)
                        toTexture:tex2 destinationSlice:0 destinationLevel:0
                destinationOrigin:MTLOriginMake(0,0,0)];
            [bl endEncoding]; [cb commit]; [cb waitUntilCompleted];
            cpuOk = ([cb status] == MTLCommandBufferStatusCompleted);
            cpuDetail = [NSString stringWithFormat:@"blit_status=%ld", (long)[cb status]];
        }
        printf("CPU_OP_OK %d\nCPU_DETAIL %s\n", cpuOk, [cpuDetail UTF8String]);
    }

    // ---- bind (tex, and tex2 if it exists) into a tiny read kernel so the sampled
    //      descriptor lands in a Tier-2 argument buffer BO for the analyzer, and do
    //      a small correctness readback. Every "probe" texture carries ShaderRead. ----
    {
        NSError *err = nil;
        NSString *rk;
        NSString *acc = ttype == MTLTextureType2DArray ? @"texture2d_array" :
                         ttype == MTLTextureTypeCube    ? @"texturecube" :
                         ttype == MTLTextureType3D       ? @"texture3d" :
                         ttype == MTLTextureType2DMultisample ? @"texture2d_ms" : @"texture2d";
        NSString *coord = ttype == MTLTextureType2DArray ? @"uint2(i&7,(i>>3)&7), 0" :
                           ttype == MTLTextureTypeCube    ? @"uint2(i&7,(i>>3)&7), 0" :
                           ttype == MTLTextureType3D       ? @"uint3(i&7,(i>>3)&7,0)" :
                           ttype == MTLTextureType2DMultisample ? @"uint2(i&7,(i>>3)&7), 0" : @"uint2(i&7,(i>>3)&7)";
        NSString *elemT = F->isUint ? @"uint" : @"float";
        rk = [NSString stringWithFormat:
              @"#include <metal_stdlib>\nusing namespace metal;\n"
               "kernel void rd(%@<%@, access::read> t [[texture(0)]],\n"
               "  device %@* o [[buffer(0)]], uint i [[thread_position_in_grid]]) {\n"
               "  o[i]=t.read(%@).x; }\n", acc, elemT, elemT, coord];
        id<MTLLibrary> lib = [dev newLibraryWithSource:rk options:nil error:&err];
        id<MTLFunction> fn = lib ? [lib newFunctionWithName:@"rd"] : nil;
        id<MTLComputePipelineState> pso = fn ? [dev newComputePipelineStateWithFunction:fn error:&err] : nil;
        if (pso) {
            id<MTLBuffer> obuf = [dev newBufferWithLength:64 * MAX(F->bpp,4) options:MTLResourceStorageModeShared];
            id<MTLCommandBuffer> cb = [q commandBuffer];
            id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
            [enc setComputePipelineState:pso];
            [enc setTexture:tex atIndex:0];
            [enc setBuffer:obuf offset:0 atIndex:0];
            [enc dispatchThreads:MTLSizeMake(64,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];
            [enc endEncoding];
            [cb commit]; [cb waitUntilCompleted];
            printf("BIND_OK 1\nBIND_STATUS %ld\n", (long)[cb status]);
        } else {
            printf("BIND_OK 0\nBIND_ERR %s\n", err ? [[err localizedDescription] UTF8String] : "");
        }
    }

    emit_status("OK");
    if (pbool(p, @"dump", YES)) doDump();
    finish();
    return 0;
  }
}
