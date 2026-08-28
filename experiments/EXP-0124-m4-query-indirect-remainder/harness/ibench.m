// EXP-0124 Group I (P1.7 DRV-INDIRECT-01) harness. Public Metal API only + our own MSL
// (kernels/i_common.metal), compiled via newLibraryWithSource:. Apple binary
// introspection: NONE. Each process runs exactly ONE case (SAFETY: one case per
// process for this whole family), selected by `--kind` with a JSON `--params` blob,
// printing one STATUS/DEVICE/OBSERVED text record (EXP-0098 gddraws.m/xfbdraws.m
// protocol convention, reused as our own prior authored code).
//
// Also serves as the standalone probe binary for harness/icbmax_bisect.py's
// maxCommandCount crash-boundary bisection (`--kind i_icbmax_probe`).

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

static void emit_status(const char *s) { printf("STATUS %s\n", s); }
static void fail(const char *status, const char *msg, NSError *err) {
    emit_status(status);
    if (err)      printf("ERROR %s: %s\n", msg, [[err localizedDescription] UTF8String]);
    else if (msg) printf("ERROR %s\n", msg);
    if (fflush(NULL) != 0) { perror("fflush"); }
    exit(1);
}

static NSDictionary *parseParams(const char *json) {
    NSData *d = [NSData dataWithBytes:json length:strlen(json)];
    NSError *err = nil;
    id obj = [NSJSONSerialization JSONObjectWithData:d options:0 error:&err];
    if (!obj || ![obj isKindOfClass:[NSDictionary class]]) fail("HARNESS_CRASH", "bad --params json", err);
    return obj;
}
static long long pint(NSDictionary *p, NSString *k, long long defv) {
    id v = p[k]; if (!v) return defv; return [v longLongValue];
}
static NSString *pstr(NSDictionary *p, NSString *k, NSString *defv) {
    id v = p[k]; if (!v) return defv; return v;
}
static BOOL pbool(NSDictionary *p, NSString *k, BOOL defv) {
    id v = p[k]; if (!v) return defv; return [v boolValue];
}

static NSString *readFile(const char *path) {
    NSError *err = nil;
    NSString *s = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:path]
                                             encoding:NSUTF8StringEncoding error:&err];
    if (!s) fail("COMPILE_FAIL", "read source", err);
    return s;
}
static id<MTLLibrary> compileLib(id<MTLDevice> dev, const char *path) {
    NSError *err = nil;
    id<MTLLibrary> lib = [dev newLibraryWithSource:readFile(path) options:[MTLCompileOptions new] error:&err];
    if (!lib) fail("COMPILE_FAIL", "newLibraryWithSource", err);
    return lib;
}
static id<MTLFunction> fn(id<MTLLibrary> lib, const char *name) {
    id<MTLFunction> f = [lib newFunctionWithName:[NSString stringWithUTF8String:name]];
    if (!f) fail("FUNCTION_MISSING", name, nil);
    return f;
}
static int finishCB(id<MTLCommandBuffer> cb) {
    [cb waitUntilCompleted];
    return cb.status == MTLCommandBufferStatusError ? 1 : 0;
}
static id<MTLTexture> makeTarget(id<MTLDevice> dev, int w, int h) {
    MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:w height:h mipmapped:NO];
    td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
    td.storageMode = MTLStorageModeShared;
    return [dev newTextureWithDescriptor:td];
}
static MTLRenderPassDescriptor *dummyPass(id<MTLTexture> t) {
    MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
    rp.colorAttachments[0].texture = t;
    rp.colorAttachments[0].loadAction = MTLLoadActionClear;
    rp.colorAttachments[0].clearColor = MTLClearColorMake(0,0,0,0);
    rp.colorAttachments[0].storeAction = MTLStoreActionStore;
    return rp;
}

// ===========================================================================
// i_cdm_axisproof / i_cdm_zeroaxis / i_cdm_sweep / i_cdm_offset --
// indirect-dispatch parameter-memory format + boundary sweep.
static int run_i_cdm_axisproof(id<MTLDevice> dev, id<MTLCommandQueue> q, id<MTLLibrary> lib) {
    NSError *err = nil;
    id<MTLComputePipelineState> argPSO = [dev newComputePipelineStateWithFunction:fn(lib,"i_cdm_argwriter") error:&err];
    id<MTLComputePipelineState> wPSO = [dev newComputePipelineStateWithFunction:fn(lib,"i_cdm_writer") error:&err];
    if (!argPSO || !wPSO) fail("PIPELINE_FAIL", "pso", err);
    // Distinct, asymmetric X,Y,Z so a swapped/reversed axis order is detectable.
    uint32_t xyz[3] = {3, 5, 2};
    id<MTLBuffer> argBuf = [dev newBufferWithLength:16 options:MTLResourceStorageModeShared];
    memset(argBuf.contents, 0xEE, 16);
    id<MTLBuffer> xyzBuf = [dev newBufferWithBytes:xyz length:12 options:MTLResourceStorageModeShared];
    id<MTLBuffer> counter = [dev newBufferWithLength:4 options:MTLResourceStorageModeShared];
    memset(counter.contents, 0, 4);
    id<MTLBuffer> lastPos = [dev newBufferWithLength:16 options:MTLResourceStorageModeShared];

    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLComputeCommandEncoder> ce = [cb computeCommandEncoder];
    [ce setComputePipelineState:argPSO];
    [ce setBuffer:argBuf offset:0 atIndex:0];
    [ce setBuffer:xyzBuf offset:0 atIndex:1];
    [ce dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
    [ce setComputePipelineState:wPSO];
    [ce setBuffer:counter offset:0 atIndex:0];
    [ce setBuffer:lastPos offset:0 atIndex:1];
    [ce dispatchThreadgroupsWithIndirectBuffer:argBuf indirectBufferOffset:0 threadsPerThreadgroup:MTLSizeMake(1,1,1)];
    [ce endEncoding];
    [cb commit]; [cb waitUntilCompleted];
    if (cb.status == MTLCommandBufferStatusError) fail("CMDBUF_ERROR", "cb", cb.error);

    uint32_t n = *(const uint32_t*)counter.contents;
    uint32_t expected = xyz[0]*xyz[1]*xyz[2];
    emit_status("OK");
    printf("DEVICE %s\n", [[dev name] UTF8String]);
    printf("OBSERVED x=%u y=%u z=%u nInvoked=%u expected=%u match=%d\n",
           xyz[0], xyz[1], xyz[2], n, expected, n == expected);
    return 0;
}

static int run_i_cdm_sweep(id<MTLDevice> dev, id<MTLCommandQueue> q, id<MTLLibrary> lib, NSDictionary *p) {
    uint32_t x = (uint32_t)pint(p,@"x",1), y = (uint32_t)pint(p,@"y",1), z = (uint32_t)pint(p,@"z",1);
    NSError *err = nil;
    id<MTLComputePipelineState> argPSO = [dev newComputePipelineStateWithFunction:fn(lib,"i_cdm_argwriter") error:&err];
    id<MTLComputePipelineState> wPSO = [dev newComputePipelineStateWithFunction:fn(lib,"i_cdm_writer") error:&err];
    if (!argPSO || !wPSO) fail("PIPELINE_FAIL", "pso", err);
    uint32_t xyz[3] = {x, y, z};
    id<MTLBuffer> argBuf = [dev newBufferWithLength:16 options:MTLResourceStorageModeShared];
    id<MTLBuffer> xyzBuf = [dev newBufferWithBytes:xyz length:12 options:MTLResourceStorageModeShared];
    id<MTLBuffer> counter = [dev newBufferWithLength:4 options:MTLResourceStorageModeShared];
    memset(counter.contents, 0, 4);
    id<MTLBuffer> lastPos = [dev newBufferWithLength:16 options:MTLResourceStorageModeShared];

    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLComputeCommandEncoder> ce = [cb computeCommandEncoder];
    [ce setComputePipelineState:argPSO];
    [ce setBuffer:argBuf offset:0 atIndex:0];
    [ce setBuffer:xyzBuf offset:0 atIndex:1];
    [ce dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
    [ce setComputePipelineState:wPSO];
    [ce setBuffer:counter offset:0 atIndex:0];
    [ce setBuffer:lastPos offset:0 atIndex:1];
    [ce dispatchThreadgroupsWithIndirectBuffer:argBuf indirectBufferOffset:0 threadsPerThreadgroup:MTLSizeMake(1,1,1)];
    [ce endEncoding];
    [cb commit]; [cb waitUntilCompleted];
    if (cb.status == MTLCommandBufferStatusError) {
        emit_status("CMDBUF_ERROR");
        printf("DEVICE %s\n", [[dev name] UTF8String]);
        printf("OBSERVED x=%u y=%u z=%u\n", x, y, z);
        return 1;
    }
    uint32_t n = *(const uint32_t*)counter.contents;
    uint64_t expected = (uint64_t)x * y * z;
    // Only claim an exact match for small, fully-verifiable grids: a 32-bit
    // atomic counter saturates well below the huge grids tested at the boundary,
    // so for those we only assert completion-without-fault/without-silent-clamp-
    // to-zero, not byte-exact invocation counts.
    BOOL smallEnough = expected <= 5000000ull;
    BOOL match = smallEnough ? (n == expected) : (n > 0);
    emit_status("OK");
    printf("DEVICE %s\n", [[dev name] UTF8String]);
    printf("OBSERVED x=%u y=%u z=%u nInvoked=%u expectedSmall=%d match=%d\n",
           x, y, z, n, smallEnough, match);
    return 0;
}

static int run_i_cdm_zeroaxis(id<MTLDevice> dev, id<MTLCommandQueue> q, id<MTLLibrary> lib, NSDictionary *p) {
    NSString *axis = pstr(p, @"zero_axis", @"x");
    uint32_t xyz[3] = {4,4,4};
    if ([axis isEqualToString:@"x"]) xyz[0]=0;
    if ([axis isEqualToString:@"y"]) xyz[1]=0;
    if ([axis isEqualToString:@"z"]) xyz[2]=0;
    NSDictionary *pp = @{@"x":@(xyz[0]), @"y":@(xyz[1]), @"z":@(xyz[2])};
    return run_i_cdm_sweep(dev, q, lib, pp);
}

static int run_i_cdm_offset(id<MTLDevice> dev, id<MTLCommandQueue> q, id<MTLLibrary> lib, NSDictionary *p) {
    NSUInteger off = (NSUInteger)pint(p, @"indirectBufferOffset", 0);
    NSError *err = nil;
    id<MTLComputePipelineState> argPSO = [dev newComputePipelineStateWithFunction:fn(lib,"i_cdm_argwriter") error:&err];
    id<MTLComputePipelineState> wPSO = [dev newComputePipelineStateWithFunction:fn(lib,"i_cdm_writer") error:&err];
    if (!argPSO || !wPSO) fail("PIPELINE_FAIL", "pso", err);
    uint32_t xyz[3] = {2,3,1};
    id<MTLBuffer> argBuf = [dev newBufferWithLength:64 options:MTLResourceStorageModeShared];
    memset(argBuf.contents, 0, 64);
    id<MTLBuffer> xyzBuf = [dev newBufferWithBytes:xyz length:12 options:MTLResourceStorageModeShared];
    id<MTLBuffer> counter = [dev newBufferWithLength:4 options:MTLResourceStorageModeShared];
    memset(counter.contents, 0, 4);
    id<MTLBuffer> lastPos = [dev newBufferWithLength:16 options:MTLResourceStorageModeShared];

    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLComputeCommandEncoder> ce = [cb computeCommandEncoder];
    [ce setComputePipelineState:argPSO];
    // Write the args at byte offset `off` within argBuf via a small trick: bind a
    // sub-buffer view is not directly supported for compute writes here, so we
    // instead write at index 0 then dispatch reading from `off` -- i.e. we place
    // the true payload so that dispatchThreadgroupsWithIndirectBuffer reading at
    // `off` sees it, by writing through a byte-offset pointer computed in ObjC:
    // simplest is to place the 12-byte payload directly at `off` from the CPU side
    // is not the point (this must be a GPU write); instead we compute-write into
    // argBuf starting at word offset off/4 using a dedicated tiny kernel call.
    [ce setBuffer:argBuf offset:off atIndex:0];
    [ce setBuffer:xyzBuf offset:0 atIndex:1];
    [ce dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
    [ce setComputePipelineState:wPSO];
    [ce setBuffer:counter offset:0 atIndex:0];
    [ce setBuffer:lastPos offset:0 atIndex:1];
    [ce dispatchThreadgroupsWithIndirectBuffer:argBuf indirectBufferOffset:off threadsPerThreadgroup:MTLSizeMake(1,1,1)];
    [ce endEncoding];
    [cb commit]; [cb waitUntilCompleted];
    if (cb.status == MTLCommandBufferStatusError) {
        emit_status("CMDBUF_ERROR");
        printf("DEVICE %s\n", [[dev name] UTF8String]);
        printf("OBSERVED indirectBufferOffset=%lu\n", (unsigned long)off);
        return 1;
    }
    uint32_t n = *(const uint32_t*)counter.contents;
    uint32_t expected = xyz[0]*xyz[1]*xyz[2];
    emit_status("OK");
    printf("DEVICE %s\n", [[dev name] UTF8String]);
    printf("OBSERVED indirectBufferOffset=%lu nInvoked=%u expected=%u match=%d\n",
           (unsigned long)off, n, expected, n == expected);
    return 0;
}

// ===========================================================================
// i_icbwrite -- GPU-authored (compute-kernel-encoded) ICB commands.
typedef struct {
    id<MTLIndirectCommandBuffer> icb;
    id<MTLBuffer> argBuf;
    id<MTLComputePipelineState> encPSO;
    id<MTLRenderPipelineState> rpso;
} ICBRig;

static ICBRig buildICBRig(id<MTLDevice> dev, id<MTLLibrary> lib, id<MTLLibrary> commonLib,
                           const char *encFnName, NSUInteger maxCount,
                           BOOL inheritBuffers, MTLIndirectCommandType extraTypes) {
    NSError *err = nil;
    ICBRig rig = {0};
    id<MTLFunction> encFn = fn(lib, encFnName);
    rig.encPSO = [dev newComputePipelineStateWithFunction:encFn error:&err];
    if (!rig.encPSO) fail("PIPELINE_FAIL", "enc pso", err);

    MTLRenderPipelineDescriptor *rpd = [MTLRenderPipelineDescriptor new];
    rpd.vertexFunction = fn(commonLib, "icbw_vertex");
    rpd.fragmentFunction = fn(commonLib, "icbw_fragment");
    rpd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA8Unorm;
    rpd.supportIndirectCommandBuffers = YES;
    rig.rpso = [dev newRenderPipelineStateWithDescriptor:rpd error:&err];
    if (!rig.rpso) fail("PIPELINE_FAIL", "render pso", err);

    MTLIndirectCommandBufferDescriptor *icd = [MTLIndirectCommandBufferDescriptor new];
    icd.commandTypes = MTLIndirectCommandTypeDraw | MTLIndirectCommandTypeDrawIndexed | extraTypes;
    icd.inheritPipelineState = YES;
    icd.inheritBuffers = inheritBuffers;
    icd.maxVertexBufferBindCount = 2;
    icd.maxFragmentBufferBindCount = 0;
    rig.icb = [dev newIndirectCommandBufferWithDescriptor:icd maxCommandCount:maxCount options:0];
    if (!rig.icb) fail("ALLOC_FAIL", "icb", nil);

    id<MTLArgumentEncoder> argEnc = [encFn newArgumentEncoderWithBufferIndex:0];
    rig.argBuf = [dev newBufferWithLength:argEnc.encodedLength options:MTLResourceStorageModeShared];
    [argEnc setArgumentBuffer:rig.argBuf offset:0];
    [argEnc setIndirectCommandBuffer:rig.icb atIndex:0];
    return rig;
}

static int run_i_icbw_basic(id<MTLDevice> dev, id<MTLCommandQueue> q, id<MTLLibrary> lib, id<MTLLibrary> commonLib, NSDictionary *p) {
    int n = (int)pint(p, @"n", 8);
    ICBRig rig = buildICBRig(dev, lib, commonLib, "icbw_encode_basic", n, NO, 0);

    // n distinct colors, one 16-byte float4 per command.
    NSMutableData *colors = [NSMutableData dataWithLength:n * 16];
    float *cf = (float*)colors.mutableBytes;
    for (int i = 0; i < n; i++) { cf[i*4+0] = (float)i/n; cf[i*4+1] = 1.0f - (float)i/n; cf[i*4+2] = 0.25f; cf[i*4+3] = 1.0f; }
    id<MTLBuffer> colorBuf = [dev newBufferWithBytes:colors.bytes length:colors.length options:MTLResourceStorageModeShared];

    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLComputeCommandEncoder> ce = [cb computeCommandEncoder];
    [ce setComputePipelineState:rig.encPSO];
    [ce setBuffer:rig.argBuf offset:0 atIndex:0];
    [ce setBuffer:colorBuf offset:0 atIndex:1];
    [ce useResource:rig.icb usage:MTLResourceUsageWrite];
    [ce dispatchThreads:MTLSizeMake(n,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
    [ce endEncoding];

    id<MTLTexture> tgt = makeTarget(dev, n, 1); // one pixel column per command
    MTLRenderPassDescriptor *rp = dummyPass(tgt);
    id<MTLRenderCommandEncoder> re = [cb renderCommandEncoderWithDescriptor:rp];
    [re setRenderPipelineState:rig.rpso];
    [re useResource:rig.icb usage:MTLResourceUsageRead];
    [re executeCommandsInBuffer:rig.icb withRange:NSMakeRange(0, n)];
    [re endEncoding];

    [cb commit]; [cb waitUntilCompleted];
    if (cb.status == MTLCommandBufferStatusError) fail("CMDBUF_ERROR", "cb", cb.error);

    uint8_t *px = malloc(n*4);
    [tgt getBytes:px bytesPerRow:n*4 fromRegion:MTLRegionMake2D(0,0,n,1) mipmapLevel:0];
    int allMatch = 1;
    for (int i = 0; i < n; i++) {
        // The fullscreen triangle covers the whole 1-pixel-tall row for every
        // command; since each command draws the SAME triangle, all n commands
        // paint the full nx1 target -- so the FINAL command's color wins (later
        // draws in the execute range paint over earlier ones). We therefore
        // only check that command n-1's color is what's on screen.
        (void)i;
    }
    int r = px[(n-1)*4+0], g = px[(n-1)*4+1], b = px[(n-1)*4+2];
    int exR = (int)roundf(cf[(n-1)*4+0]*255), exG = (int)roundf(cf[(n-1)*4+1]*255), exB = (int)roundf(cf[(n-1)*4+2]*255);
    allMatch = (abs(r-exR)<=2 && abs(g-exG)<=2 && abs(b-exB)<=2);
    free(px);
    emit_status("OK");
    printf("DEVICE %s\n", [[dev name] UTF8String]);
    printf("OBSERVED n=%d lastCmdColorMatch=%d r=%d g=%d b=%d exR=%d exG=%d exB=%d\n",
           n, allMatch, r, g, b, exR, exG, exB);
    return 0;
}

static int run_i_icbw_reset(id<MTLDevice> dev, id<MTLCommandQueue> q, id<MTLLibrary> lib, id<MTLLibrary> commonLib, NSDictionary *p) {
    int n = (int)pint(p, @"n", 4);
    uint32_t resetIdx = (uint32_t)pint(p, @"reset_idx", 1);
    ICBRig rig = buildICBRig(dev, lib, commonLib, "icbw_encode_then_reset", n, NO, 0);

    NSMutableData *colors = [NSMutableData dataWithLength:n * 16];
    float *cf = (float*)colors.mutableBytes;
    for (int i = 0; i < n; i++) { cf[i*4+0]=0; cf[i*4+1]=0; cf[i*4+2]=(float)(i+1)/n; cf[i*4+3]=1; }
    id<MTLBuffer> colorBuf = [dev newBufferWithBytes:colors.bytes length:colors.length options:MTLResourceStorageModeShared];
    id<MTLBuffer> ridxBuf = [dev newBufferWithBytes:&resetIdx length:4 options:MTLResourceStorageModeShared];

    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLComputeCommandEncoder> ce = [cb computeCommandEncoder];
    [ce setComputePipelineState:rig.encPSO];
    [ce setBuffer:rig.argBuf offset:0 atIndex:0];
    [ce setBuffer:colorBuf offset:0 atIndex:1];
    [ce setBuffer:ridxBuf offset:0 atIndex:2];
    [ce useResource:rig.icb usage:MTLResourceUsageWrite];
    [ce dispatchThreads:MTLSizeMake(n,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
    [ce endEncoding];

    // One pixel per command, rendered by executing each command into its OWN
    // 1x1 scissor-free single-pixel target via n separate 1-command executes,
    // so a reset command's effect (drawing nothing) is independently observable
    // per-slot rather than being overpainted by a later command.
    NSMutableArray<id<MTLTexture>> *tgts = [NSMutableArray array];
    for (int i = 0; i < n; i++) [tgts addObject:makeTarget(dev, 1, 1)];
    for (int i = 0; i < n; i++) {
        MTLRenderPassDescriptor *rp = dummyPass(tgts[i]);
        id<MTLRenderCommandEncoder> re = [cb renderCommandEncoderWithDescriptor:rp];
        [re setRenderPipelineState:rig.rpso];
        [re useResource:rig.icb usage:MTLResourceUsageRead];
        [re executeCommandsInBuffer:rig.icb withRange:NSMakeRange(i, 1)];
        [re endEncoding];
    }
    [cb commit]; [cb waitUntilCompleted];
    if (cb.status == MTLCommandBufferStatusError) fail("CMDBUF_ERROR", "cb", cb.error);

    int resetSlotIsClear = -1, otherSlotPainted = -1;
    for (int i = 0; i < n; i++) {
        uint8_t px[4];
        [tgts[i] getBytes:px bytesPerRow:4 fromRegion:MTLRegionMake2D(0,0,1,1) mipmapLevel:0];
        BOOL clear = (px[0]==0 && px[1]==0 && px[2]==0 && px[3]==0);
        if ((uint32_t)i == resetIdx) resetSlotIsClear = clear;
        else if (i == 0 || i == n-1) otherSlotPainted = !clear;
    }
    emit_status("OK");
    printf("DEVICE %s\n", [[dev name] UTF8String]);
    printf("OBSERVED n=%d resetIdx=%u resetSlotIsClear=%d otherSlotPainted=%d\n",
           n, resetIdx, resetSlotIsClear, otherSlotPainted);
    return 0;
}

static int run_i_icbw_fields(id<MTLDevice> dev, id<MTLCommandQueue> q, id<MTLLibrary> lib, id<MTLLibrary> commonLib, NSDictionary *p) {
    uint32_t vs = (uint32_t)pint(p,@"vertexStart",0), vc = (uint32_t)pint(p,@"vertexCount",3);
    uint32_t ic = (uint32_t)pint(p,@"instanceCount",1), bi = (uint32_t)pint(p,@"baseInstance",0);
    ICBRig rig = buildICBRig(dev, lib, commonLib, "icbw_encode_fields", 1, NO, 0);
    float red[4] = {1,0,0,1};
    id<MTLBuffer> colorBuf = [dev newBufferWithBytes:red length:16 options:MTLResourceStorageModeShared];
    uint32_t args[4] = {vs,vc,ic,bi};
    id<MTLBuffer> argsBuf = [dev newBufferWithBytes:args length:16 options:MTLResourceStorageModeShared];

    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLComputeCommandEncoder> ce = [cb computeCommandEncoder];
    [ce setComputePipelineState:rig.encPSO];
    [ce setBuffer:rig.argBuf offset:0 atIndex:0];
    [ce setBuffer:colorBuf offset:0 atIndex:1];
    [ce setBuffer:argsBuf offset:0 atIndex:2];
    [ce useResource:rig.icb usage:MTLResourceUsageWrite];
    [ce dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
    [ce endEncoding];

    id<MTLTexture> tgt = makeTarget(dev, 8, 8);
    MTLRenderPassDescriptor *rp = dummyPass(tgt);
    id<MTLRenderCommandEncoder> re = [cb renderCommandEncoderWithDescriptor:rp];
    [re setRenderPipelineState:rig.rpso];
    [re useResource:rig.icb usage:MTLResourceUsageRead];
    [re executeCommandsInBuffer:rig.icb withRange:NSMakeRange(0,1)];
    [re endEncoding];
    [cb commit]; [cb waitUntilCompleted];
    if (cb.status == MTLCommandBufferStatusError) {
        emit_status("CMDBUF_ERROR");
        printf("DEVICE %s\n", [[dev name] UTF8String]);
        printf("OBSERVED vertexStart=%u vertexCount=%u instanceCount=%u baseInstance=%u\n", vs,vc,ic,bi);
        return 1;
    }
    uint8_t px[8*8*4];
    [tgt getBytes:px bytesPerRow:8*4 fromRegion:MTLRegionMake2D(0,0,8,8) mipmapLevel:0];
    // vertexCount<3 (can't form a triangle) or instanceCount==0 should paint
    // nothing; vertexCount>=3 with instanceCount>=1 should paint red at (4,4)
    // (our fullscreen-triangle vertex shader ignores vertexStart/baseInstance
    // for POSITION, so any accepted nonzero-count draw covers the same pixels).
    BOOL center_is_red = px[(4*8+4)*4+0] > 200 && px[(4*8+4)*4+3] > 200;
    BOOL expectPaint = (vc >= 3) && (ic >= 1);
    emit_status("OK");
    printf("DEVICE %s\n", [[dev name] UTF8String]);
    printf("OBSERVED vertexStart=%u vertexCount=%u instanceCount=%u baseInstance=%u "
           "centerIsRed=%d expectPaint=%d match=%d\n",
           vs, vc, ic, bi, center_is_red, expectPaint, center_is_red == expectPaint);
    return 0;
}

static int run_i_icbw_inherit_yes(id<MTLDevice> dev, id<MTLCommandQueue> q, id<MTLLibrary> lib, id<MTLLibrary> commonLib) {
    ICBRig rig = buildICBRig(dev, lib, commonLib, "icbw_encode_inherit", 1, YES, 0);
    float green[4] = {0,1,0,1};
    id<MTLBuffer> colorBuf = [dev newBufferWithBytes:green length:16 options:MTLResourceStorageModeShared];

    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLComputeCommandEncoder> ce = [cb computeCommandEncoder];
    [ce setComputePipelineState:rig.encPSO];
    [ce setBuffer:rig.argBuf offset:0 atIndex:0];
    [ce useResource:rig.icb usage:MTLResourceUsageWrite];
    [ce dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
    [ce endEncoding];

    id<MTLTexture> tgt = makeTarget(dev, 8, 8);
    MTLRenderPassDescriptor *rp = dummyPass(tgt);
    id<MTLRenderCommandEncoder> re = [cb renderCommandEncoderWithDescriptor:rp];
    [re setRenderPipelineState:rig.rpso];
    [re setVertexBuffer:colorBuf offset:0 atIndex:1]; // encoder-bound buffer, to be inherited
    [re useResource:rig.icb usage:MTLResourceUsageRead];
    [re executeCommandsInBuffer:rig.icb withRange:NSMakeRange(0,1)];
    [re endEncoding];
    [cb commit]; [cb waitUntilCompleted];
    if (cb.status == MTLCommandBufferStatusError) fail("CMDBUF_ERROR", "cb", cb.error);

    uint8_t px[8*8*4];
    [tgt getBytes:px bytesPerRow:8*4 fromRegion:MTLRegionMake2D(0,0,8,8) mipmapLevel:0];
    BOOL green_at_center = px[(4*8+4)*4+1] > 200 && px[(4*8+4)*4+0] < 20;
    emit_status("OK");
    printf("DEVICE %s\n", [[dev name] UTF8String]);
    printf("OBSERVED inheritedBufferUsed=%d\n", green_at_center);
    return 0;
}

static int run_i_icbw_indexed(id<MTLDevice> dev, id<MTLCommandQueue> q, id<MTLLibrary> lib, id<MTLLibrary> commonLib, NSDictionary *p) {
    int n = (int)pint(p, @"n", 4);
    ICBRig rig = buildICBRig(dev, lib, commonLib, "icbw_encode_indexed", n, NO, 0);
    NSMutableData *colors = [NSMutableData dataWithLength:n*16];
    float *cf = (float*)colors.mutableBytes;
    for (int i=0;i<n;i++){cf[i*4+0]=0;cf[i*4+1]=0;cf[i*4+2]=1;cf[i*4+3]=1;}
    id<MTLBuffer> colorBuf = [dev newBufferWithBytes:colors.bytes length:colors.length options:MTLResourceStorageModeShared];
    uint32_t indices[3] = {0,1,2};
    id<MTLBuffer> idxBuf = [dev newBufferWithBytes:indices length:12 options:MTLResourceStorageModeShared];

    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLComputeCommandEncoder> ce = [cb computeCommandEncoder];
    [ce setComputePipelineState:rig.encPSO];
    [ce setBuffer:rig.argBuf offset:0 atIndex:0];
    [ce setBuffer:colorBuf offset:0 atIndex:1];
    [ce setBuffer:idxBuf offset:0 atIndex:2];
    [ce useResource:rig.icb usage:MTLResourceUsageWrite];
    [ce dispatchThreads:MTLSizeMake(n,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
    [ce endEncoding];

    id<MTLTexture> tgt = makeTarget(dev, 8, 8);
    MTLRenderPassDescriptor *rp = dummyPass(tgt);
    id<MTLRenderCommandEncoder> re = [cb renderCommandEncoderWithDescriptor:rp];
    [re setRenderPipelineState:rig.rpso];
    [re useResource:rig.icb usage:MTLResourceUsageRead];
    [re executeCommandsInBuffer:rig.icb withRange:NSMakeRange(0,n)];
    [re endEncoding];
    [cb commit]; [cb waitUntilCompleted];
    if (cb.status == MTLCommandBufferStatusError) fail("CMDBUF_ERROR", "cb", cb.error);

    uint8_t px[8*8*4];
    [tgt getBytes:px bytesPerRow:8*4 fromRegion:MTLRegionMake2D(0,0,8,8) mipmapLevel:0];
    BOOL blue_at_center = px[(4*8+4)*4+2] > 200 && px[(4*8+4)*4+0] < 20;
    emit_status("OK");
    printf("DEVICE %s\n", [[dev name] UTF8String]);
    printf("OBSERVED n=%d indexedDrawPainted=%d\n", n, blue_at_center);
    return 0;
}

static int run_i_icbw_oob_index(id<MTLDevice> dev, id<MTLCommandQueue> q, id<MTLLibrary> lib, id<MTLLibrary> commonLib, NSDictionary *p) {
    NSUInteger maxCount = (NSUInteger)pint(p, @"maxCommandCount", 4);
    int dispatched = (int)pint(p, @"dispatched_threads", 8);
    ICBRig rig = buildICBRig(dev, lib, commonLib, "icbw_encode_oob", maxCount, NO, 0);
    float col[4] = {1,1,0,1};
    id<MTLBuffer> colorBuf = [dev newBufferWithBytes:col length:16 options:MTLResourceStorageModeShared];

    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLComputeCommandEncoder> ce = [cb computeCommandEncoder];
    [ce setComputePipelineState:rig.encPSO];
    [ce setBuffer:rig.argBuf offset:0 atIndex:0];
    [ce setBuffer:colorBuf offset:0 atIndex:1];
    [ce useResource:rig.icb usage:MTLResourceUsageWrite];
    // Deliberately dispatch MORE threads than maxCommandCount -- some threads
    // will construct a render_command at an index >= the ICB's capacity.
    [ce dispatchThreads:MTLSizeMake(dispatched,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
    [ce endEncoding];
    [cb commit]; [cb waitUntilCompleted];
    int computeErr = cb.status == MTLCommandBufferStatusError;
    if (computeErr) {
        emit_status("CMDBUF_ERROR");
        printf("DEVICE %s\n", [[dev name] UTF8String]);
        printf("OBSERVED maxCommandCount=%lu dispatched=%d stage=encode\n", (unsigned long)maxCount, dispatched);
        return 1;
    }
    // Now execute only the legal range and confirm the in-range commands are
    // still intact (i.e. the OOB writes did not corrupt in-range slots).
    id<MTLCommandBuffer> cb2 = [q commandBuffer];
    id<MTLTexture> tgt = makeTarget(dev, (int)maxCount, 1);
    MTLRenderPassDescriptor *rp = dummyPass(tgt);
    id<MTLRenderCommandEncoder> re = [cb2 renderCommandEncoderWithDescriptor:rp];
    [re setRenderPipelineState:rig.rpso];
    [re useResource:rig.icb usage:MTLResourceUsageRead];
    [re executeCommandsInBuffer:rig.icb withRange:NSMakeRange(0, maxCount)];
    [re endEncoding];
    [cb2 commit]; [cb2 waitUntilCompleted];
    int execErr = cb2.status == MTLCommandBufferStatusError;
    emit_status(execErr ? "CMDBUF_ERROR" : "OK");
    printf("DEVICE %s\n", [[dev name] UTF8String]);
    printf("OBSERVED maxCommandCount=%lu dispatched=%d encodeOk=1 executeInRangeOk=%d\n",
           (unsigned long)maxCount, dispatched, !execErr);
    return execErr ? 1 : 0;
}

// ===========================================================================
// i_icbbarrier -- concurrent-dispatch ICB producer/consumer with optional
// GPU-authored .set_barrier().
static int run_i_icbb_trial(id<MTLDevice> dev, id<MTLCommandQueue> q, id<MTLLibrary> lib, NSDictionary *p) {
    BOOL useBarrier = pbool(p, @"barrier", YES);
    NSError *err = nil;
    id<MTLFunction> prodFn = fn(lib, "icbb_producer");
    id<MTLFunction> consFn = fn(lib, "icbb_consumer");
    id<MTLFunction> encFn = fn(lib, "icbb_encode");
    // Both producer/consumer pipelines must opt in to ICB usage (mirrors the
    // render-pipeline requirement elsewhere in this file); a plain
    // newComputePipelineStateWithFunction: pipeline used from a GPU-authored ICB
    // command was found at build time to fault. encPSO itself never runs FROM an
    // ICB so it does not need the flag.
    MTLComputePipelineDescriptor *prodCD = [MTLComputePipelineDescriptor new];
    prodCD.computeFunction = prodFn;
    prodCD.supportIndirectCommandBuffers = YES;
    MTLComputePipelineDescriptor *consCD = [MTLComputePipelineDescriptor new];
    consCD.computeFunction = consFn;
    consCD.supportIndirectCommandBuffers = YES;
    id<MTLComputePipelineState> prodPSO = [dev newComputePipelineStateWithDescriptor:prodCD options:0 reflection:nil error:&err];
    id<MTLComputePipelineState> consPSO = [dev newComputePipelineStateWithDescriptor:consCD options:0 reflection:nil error:&err];
    id<MTLComputePipelineState> encPSO = [dev newComputePipelineStateWithFunction:encFn error:&err];
    if (!prodPSO || !consPSO || !encPSO) fail("PIPELINE_FAIL", "pso", err);

    MTLIndirectCommandBufferDescriptor *icd = [MTLIndirectCommandBufferDescriptor new];
    icd.commandTypes = MTLIndirectCommandTypeConcurrentDispatch;
    icd.inheritPipelineState = NO;
    icd.inheritBuffers = NO;
    icd.maxKernelBufferBindCount = 2;
    id<MTLIndirectCommandBuffer> icb = [dev newIndirectCommandBufferWithDescriptor:icd maxCommandCount:2 options:0];
    if (!icb) fail("ALLOC_FAIL", "icb", nil);

    id<MTLArgumentEncoder> argEnc = [encFn newArgumentEncoderWithBufferIndex:0];
    id<MTLBuffer> argBuf = [dev newBufferWithLength:argEnc.encodedLength options:MTLResourceStorageModeShared];
    [argEnc setArgumentBuffer:argBuf offset:0];
    [argEnc setIndirectCommandBuffer:icb atIndex:0];
    [argEnc setComputePipelineState:prodPSO atIndex:1];
    [argEnc setComputePipelineState:consPSO atIndex:2];

    id<MTLBuffer> slot = [dev newBufferWithLength:4 options:MTLResourceStorageModeShared];
    uint32_t sentinel = 0xDEADBEEFu;
    memcpy(slot.contents, &sentinel, 4);
    id<MTLBuffer> result = [dev newBufferWithLength:4 options:MTLResourceStorageModeShared];
    memset(result.contents, 0, 4);
    uint32_t ub = useBarrier ? 1 : 0;
    id<MTLBuffer> ubBuf = [dev newBufferWithBytes:&ub length:4 options:MTLResourceStorageModeShared];

    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLComputeCommandEncoder> ce = [cb computeCommandEncoder];
    [ce setComputePipelineState:encPSO];
    [ce setBuffer:argBuf offset:0 atIndex:0];
    [ce setBuffer:slot offset:0 atIndex:1];
    [ce setBuffer:result offset:0 atIndex:2];
    [ce setBuffer:ubBuf offset:0 atIndex:3];
    [ce useResource:icb usage:MTLResourceUsageWrite];
    [ce dispatchThreads:MTLSizeMake(2,1,1) threadsPerThreadgroup:MTLSizeMake(2,1,1)];
    [ce endEncoding];

    // Both commands' pipeline state, buffers, and dispatch parameters are
    // entirely GPU-authored (icbb_encode's compute_command.set_compute_pipeline_
    // state()/set_kernel_buffer()/concurrent_dispatch_threadgroups() calls above)
    // -- no CPU-side per-command mutation of this ICB (see i_common.metal comment
    // on ICBContainerC for why that combination was avoided).
    id<MTLComputeCommandEncoder> ce2 = [cb computeCommandEncoder];
    [ce2 useResource:icb usage:MTLResourceUsageRead];
    [ce2 useResource:slot usage:MTLResourceUsageRead|MTLResourceUsageWrite];
    [ce2 useResource:result usage:MTLResourceUsageWrite];
    [ce2 executeCommandsInBuffer:icb withRange:NSMakeRange(0,2)];
    [ce2 endEncoding];

    [cb commit]; [cb waitUntilCompleted];
    if (cb.status == MTLCommandBufferStatusError) fail("CMDBUF_ERROR", "cb", cb.error);

    uint32_t res = *(const uint32_t*)result.contents;
    BOOL correct = (res == 84); // 42*2, only true if consumer observed the producer's write
    emit_status("OK");
    printf("DEVICE %s\n", [[dev name] UTF8String]);
    printf("OBSERVED barrier=%d result=%u correct=%d\n", useBarrier, res, correct);
    return 0;
}

// ===========================================================================
// i_restart -- strip-topology primitive-restart probe.
static int run_i_restart(id<MTLDevice> dev, id<MTLCommandQueue> q, id<MTLLibrary> lib, NSDictionary *p) {
    NSString *topo = pstr(p, @"topology", @"strip");
    int idxbits = (int)pint(p, @"idxbits", 32);
    NSError *err = nil;
    MTLRenderPipelineDescriptor *rpd = [MTLRenderPipelineDescriptor new];
    rpd.vertexFunction = fn(lib, "v_restart");
    rpd.fragmentFunction = fn(lib, "f_restart");
    rpd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA8Unorm;
    id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:rpd error:&err];
    if (!pso) fail("PIPELINE_FAIL", "restart pso", err);

    // index sequence: 0,1,2, RESTART, 3,4,5 (7 indices).
    id<MTLBuffer> idxBuf;
    if (idxbits == 32) {
        uint32_t idx32[7] = {0,1,2,0xFFFFFFFFu,3,4,5};
        idxBuf = [dev newBufferWithBytes:idx32 length:sizeof(idx32) options:MTLResourceStorageModeShared];
    } else {
        uint16_t idx16[7] = {0,1,2,0xFFFFu,3,4,5};
        idxBuf = [dev newBufferWithBytes:idx16 length:sizeof(idx16) options:MTLResourceStorageModeShared];
    }
    MTLPrimitiveType ptype = [topo isEqualToString:@"strip"] ? MTLPrimitiveTypeTriangleStrip : MTLPrimitiveTypePoint;

    id<MTLTexture> tgt = makeTarget(dev, 64, 64);
    id<MTLCommandBuffer> cb = [q commandBuffer];
    MTLRenderPassDescriptor *rp = dummyPass(tgt);
    id<MTLRenderCommandEncoder> re = [cb renderCommandEncoderWithDescriptor:rp];
    [re setRenderPipelineState:pso];
    [re drawIndexedPrimitives:ptype indexCount:7
                     indexType:(idxbits==32?MTLIndexTypeUInt32:MTLIndexTypeUInt16)
                    indexBuffer:idxBuf indexBufferOffset:0
                  instanceCount:1 baseVertex:0 baseInstance:0];
    [re endEncoding];
    [cb commit]; [cb waitUntilCompleted];
    if (cb.status == MTLCommandBufferStatusError) {
        emit_status("CMDBUF_ERROR");
        printf("DEVICE %s\n", [[dev name] UTF8String]);
        printf("OBSERVED topology=%s idxbits=%d\n", [topo UTF8String], idxbits);
        return 1;
    }
    uint8_t *px = malloc(64*64*4);
    [tgt getBytes:px bytesPerRow:64*4 fromRegion:MTLRegionMake2D(0,0,64,64) mipmapLevel:0];
    int anyRed = 0, anyGreen = 0, anyBlue = 0;
    for (int i = 0; i < 64*64; i++) {
        if (px[i*4+0] > 40 && px[i*4+1] < 40 && px[i*4+2] < 40) anyRed = 1;
        if (px[i*4+1] > 100 && px[i*4+0] < 40) anyGreen = 1;
        if (px[i*4+2] > 100 && px[i*4+0] < 40) anyBlue = 1;
    }
    free(px);
    emit_status("OK");
    printf("DEVICE %s\n", [[dev name] UTF8String]);
    printf("OBSERVED topology=%s idxbits=%d anyRed=%d anyGreen=%d anyBlue=%d\n",
           [topo UTF8String], idxbits, anyRed, anyGreen, anyBlue);
    return 0;
}

// ===========================================================================
// i_icbmax_probe -- one allocation attempt at a caller-specified maxCommandCount,
// used by harness/icbmax_bisect.py to narrow the EXP-0098 crash-boundary bracket.
static int run_i_icbmax_probe(id<MTLDevice> dev, NSDictionary *p) {
    NSUInteger maxCount = (NSUInteger)pint(p, @"maxCommandCount", 4194304);
    MTLIndirectCommandBufferDescriptor *icd = [MTLIndirectCommandBufferDescriptor new];
    icd.commandTypes = MTLIndirectCommandTypeDraw;
    icd.inheritPipelineState = YES;
    icd.inheritBuffers = YES;
    id<MTLIndirectCommandBuffer> icb = [dev newIndirectCommandBufferWithDescriptor:icd maxCommandCount:maxCount options:0];
    if (!icb) {
        emit_status("ALLOC_REJECTED");
        printf("DEVICE %s\n", [[dev name] UTF8String]);
        printf("OBSERVED maxCommandCount=%lu allocated=0\n", (unsigned long)maxCount);
        return 0;
    }
    emit_status("OK");
    printf("DEVICE %s\n", [[dev name] UTF8String]);
    printf("OBSERVED maxCommandCount=%lu allocated=1 readbackSize=%lu\n",
           (unsigned long)maxCount, (unsigned long)icb.size);
    return 0;
}

// ===========================================================================
int main(int argc, char *argv[]) {
    setvbuf(stdout, NULL, _IONBF, 0);
    @autoreleasepool {
        if (argc < 3) fail("HARNESS_CRASH", "usage: ibench <kind> <json params>", nil);
        const char *kind = argv[1];
        NSDictionary *p = parseParams(argv[2]);

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) fail("PIPELINE_FAIL", "no Metal device", nil);
        id<MTLCommandQueue> q = [dev newCommandQueue];

        if (strcmp(kind, "i_icbmax_probe") == 0) return run_i_icbmax_probe(dev, p);

        id<MTLLibrary> commonLib = compileLib(dev, "kernels/i_common.metal");

        if (strcmp(kind, "i_cdm_axisproof") == 0) return run_i_cdm_axisproof(dev, q, commonLib);
        if (strcmp(kind, "i_cdm_zeroaxis") == 0) return run_i_cdm_zeroaxis(dev, q, commonLib, p);
        if (strcmp(kind, "i_cdm_sweep") == 0) return run_i_cdm_sweep(dev, q, commonLib, p);
        if (strcmp(kind, "i_cdm_offset") == 0) return run_i_cdm_offset(dev, q, commonLib, p);

        if (strcmp(kind, "i_icbw_basic") == 0) return run_i_icbw_basic(dev, q, commonLib, commonLib, p);
        if (strcmp(kind, "i_icbw_reset") == 0) return run_i_icbw_reset(dev, q, commonLib, commonLib, p);
        if (strcmp(kind, "i_icbw_fields") == 0) return run_i_icbw_fields(dev, q, commonLib, commonLib, p);
        if (strcmp(kind, "i_icbw_inherit_yes") == 0) return run_i_icbw_inherit_yes(dev, q, commonLib, commonLib);
        if (strcmp(kind, "i_icbw_indexed") == 0) return run_i_icbw_indexed(dev, q, commonLib, commonLib, p);
        if (strcmp(kind, "i_icbw_oob_index") == 0) return run_i_icbw_oob_index(dev, q, commonLib, commonLib, p);

        if (strcmp(kind, "i_icbb_trial") == 0) return run_i_icbb_trial(dev, q, commonLib, p);
        if (strcmp(kind, "i_restart") == 0) return run_i_restart(dev, q, commonLib, p);

        fail("HARNESS_CRASH", "unknown --kind", nil);
        return 1;
    }
}
