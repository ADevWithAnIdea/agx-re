// EXP-0133 harness. One process per case (capability|conversion|layout|sparse
// mode), fresh MTLDevice/library/pipelines/textures each time, synchronous
// command-buffer waits (no completion-handler races -- a single print, flush,
// exit path). Public Metal API only; no Apple binary is inspected, no private
// interface is used. Clean-room category: HW-PROBE / OWN-SHADER / PUBLIC API.
//
// Modes:
//   --mode capability --id N --name NAME --kind KIND --family FAMILY   full 12-axis per-format sweep
//   --mode conversion --case ID                                        bounded bit-exact conversion probes (see runConversion)
//   --mode layout --id N --name NAME                                    public-API alignment/pitch probe
//   --mode sparse --id N --name NAME                                    representative sparse-heap probe
// --source PATH gives the .metal file to compile (kernels/capability.metal for capability/layout/sparse,
// kernels/conversion.metal for conversion).
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static NSString *hexData(NSData *d) {
    if (!d) return @"";
    const unsigned char *b = d.bytes;
    NSMutableString *s = [NSMutableString stringWithCapacity:d.length * 2];
    for (NSUInteger i = 0; i < d.length; i++) [s appendFormat:@"%02x", b[i]];
    return s;
}

static NSString *argVal(NSArray<NSString *> *argv, NSString *flag) {
    NSUInteger idx = [argv indexOfObject:flag];
    if (idx == NSNotFound || idx + 1 >= argv.count) return nil;
    return argv[idx + 1];
}

static void emitAndExit(NSDictionary *payload) {
    NSError *err = nil;
    NSData *j = [NSJSONSerialization dataWithJSONObject:payload options:NSJSONWritingSortedKeys error:&err];
    if (!j) {
        fprintf(stdout, "{\"harness_fatal\":\"json serialize failed: %s\"}\n", err.localizedDescription.UTF8String ?: "?");
        fflush(stdout);
        exit(2);
    }
    fwrite(j.bytes, 1, j.length, stdout);
    fputc('\n', stdout);
    fflush(stdout);
    fflush(NULL);
    exit(0);
}

// ---------------------------------------------------------------- Metal helpers

static id<MTLLibrary> compileLibrary(id<MTLDevice> dev, NSString *sourcePath, NSString **errOut) {
    NSError *err = nil;
    NSString *src = [NSString stringWithContentsOfFile:sourcePath encoding:NSUTF8StringEncoding error:&err];
    if (!src) { *errOut = err.localizedDescription ?: @"read failed"; return nil; }
    MTLCompileOptions *opts = [MTLCompileOptions new];
    opts.fastMathEnabled = NO;
    id<MTLLibrary> lib = [dev newLibraryWithSource:src options:opts error:&err];
    if (!lib) { *errOut = err.localizedDescription ?: @"compile failed"; return nil; }
    return lib;
}

static id<MTLComputePipelineState> makePSO(id<MTLDevice> dev, id<MTLLibrary> lib, NSString *fname, NSString **errOut) {
    id<MTLFunction> fn = [lib newFunctionWithName:fname];
    if (!fn) { *errOut = @"function not found in library"; return nil; }
    NSError *err = nil;
    id<MTLComputePipelineState> pso = [dev newComputePipelineStateWithFunction:fn error:&err];
    if (!pso) { *errOut = err.localizedDescription ?: @"pipeline creation failed"; return nil; }
    return pso;
}

// Runs one compute dispatch (1 threadgroup, 1 thread) against `tex` (may be nil to
// skip texture binding, e.g. none needed) and an optional sampler, writing outWords
// 32-bit little-endian words to an owned output buffer, returning a result dict.
// Never throws: Metal misuse is caught via NSException where the API can raise one,
// and command-buffer failure is read from the completed buffer's status/error.
static NSDictionary *dispatchOne(id<MTLDevice> dev, id<MTLComputePipelineState> pso,
                                  id<MTLTexture> tex, id<MTLSamplerState> smp,
                                  id<MTLBuffer> constBuf, NSUInteger outWords) {
    NSMutableDictionary *r = [NSMutableDictionary dictionary];
    id<MTLBuffer> outBuf = [dev newBufferWithLength:MAX(outWords * 4, (NSUInteger)16) options:MTLResourceStorageModeShared];
    memset(outBuf.contents, 0xEE, outBuf.length);
    id<MTLCommandQueue> q = [dev newCommandQueue];
    if (!q) { r[@"status"] = @"queue_rejected"; return r; }
    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
    [enc setComputePipelineState:pso];
    if (tex) [enc setTexture:tex atIndex:0];
    if (smp) [enc setSamplerState:smp atIndex:0];
    if (constBuf) [enc setBuffer:constBuf offset:0 atIndex:0];
    [enc setBuffer:outBuf offset:0 atIndex:(constBuf ? 1 : 0)];
    // storage_write kernels take the constant as buffer(0) and write no output buffer;
    // storage_read/sample/atomic kernels take output as buffer(0). Caller controls this
    // via constBuf being nil (output-only) or non-nil (constant-then-output at index 1)
    // -- write kernels pass constBuf non-nil and outWords==0 so no output buffer index
    // collision occurs (see callers).
    [enc dispatchThreadgroups:MTLSizeMake(1, 1, 1) threadsPerThreadgroup:MTLSizeMake(1, 1, 1)];
    [enc endEncoding];
    [cb commit];
    [cb waitUntilCompleted];
    r[@"command_buffer_status"] = @(cb.status);
    r[@"command_buffer_error"] = cb.error ? (cb.error.localizedDescription ?: @"") : @"";
    if (cb.status == MTLCommandBufferStatusCompleted) {
        r[@"status"] = @"ok";
        if (outWords > 0) r[@"output_hex"] = hexData([NSData dataWithBytes:outBuf.contents length:outWords * 4]);
    } else {
        r[@"status"] = @"cb_error";
    }
    return r;
}

static NSString *sampleKernelFor(NSString *kind, NSString *family) {
    if ([family isEqualToString:@"depth"] || [family isEqualToString:@"depthstencil"]) return @"k_sample_depth";
    if ([kind isEqualToString:@"uint"]) return @"k_sample_uint";
    if ([kind isEqualToString:@"int"]) return @"k_sample_int";
    return @"k_sample_float";
}
static NSString *readKernelFor(NSString *kind) {
    if ([kind isEqualToString:@"uint"]) return @"k_read_uint";
    if ([kind isEqualToString:@"int"]) return @"k_read_int";
    return @"k_read_float";
}
static NSString *writeKernelFor(NSString *kind) {
    if ([kind isEqualToString:@"uint"]) return @"k_write_uint";
    if ([kind isEqualToString:@"int"]) return @"k_write_int";
    return @"k_write_float";
}

typedef struct { MTLPixelFormat fmt; NSString *kind; NSString *family; NSUInteger dim; NSInteger bpp; } FmtCtx;

static id<MTLTexture> tryTexture(id<MTLDevice> dev, MTLPixelFormat fmt, NSUInteger w, NSUInteger h,
                                  MTLTextureUsage usage, MTLStorageMode storage, NSUInteger sampleCount,
                                  NSString **errOut) {
    @try {
        MTLTextureDescriptor *td;
        if (sampleCount > 1) {
            td = [MTLTextureDescriptor new];
            td.textureType = MTLTextureType2DMultisample;
            td.pixelFormat = fmt; td.width = w; td.height = h; td.sampleCount = sampleCount;
        } else {
            td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:fmt width:w height:h mipmapped:NO];
        }
        td.usage = usage;
        td.storageMode = storage;
        id<MTLTexture> t = [dev newTextureWithDescriptor:td];
        if (!t) { *errOut = @"newTextureWithDescriptor returned nil"; return nil; }
        return t;
    } @catch (NSException *e) {
        *errOut = [NSString stringWithFormat:@"%@: %@", e.name, e.reason ?: @""];
        return nil;
    }
}

#define TESTDIM 16

// ---------------------------------------------------------------- axis implementations (capability mode)

static NSDictionary *axisSample(id<MTLDevice> dev, id<MTLLibrary> lib, FmtCtx c, BOOL linearFilter) {
    NSMutableDictionary *r = [NSMutableDictionary dictionary];
    NSString *kname = sampleKernelFor(c.kind, c.family);
    NSString *perr = nil;
    id<MTLComputePipelineState> pso = makePSO(dev, lib, kname, &perr);
    if (!pso) { r[@"status"] = @"pipeline_rejected"; r[@"detail"] = perr ?: @""; r[@"kernel"] = kname; return r; }
    MTLTextureUsage usage = MTLTextureUsageShaderRead;
    if ([c.family isEqualToString:@"depth"] || [c.family isEqualToString:@"stencil"] || [c.family isEqualToString:@"depthstencil"] || [c.family isEqualToString:@"stencil_view"])
        usage |= MTLTextureUsageRenderTarget;
    NSString *terr = nil;
    id<MTLTexture> tex = tryTexture(dev, c.fmt, TESTDIM, TESTDIM, usage, MTLStorageModeShared, 1, &terr);
    if (!tex) { r[@"status"] = @"texture_rejected"; r[@"detail"] = terr ?: @""; return r; }
    MTLSamplerDescriptor *sd = [MTLSamplerDescriptor new];
    sd.minFilter = linearFilter ? MTLSamplerMinMagFilterLinear : MTLSamplerMinMagFilterNearest;
    sd.magFilter = linearFilter ? MTLSamplerMinMagFilterLinear : MTLSamplerMinMagFilterNearest;
    sd.mipFilter = MTLSamplerMipFilterNotMipmapped;
    id<MTLSamplerState> smp = [dev newSamplerStateWithDescriptor:sd];
    if (!smp) { r[@"status"] = @"sampler_rejected"; return r; }
    NSDictionary *d = dispatchOne(dev, pso, tex, smp, nil, 4);
    [r addEntriesFromDictionary:d];
    r[@"kernel"] = kname;
    return r;
}

static NSDictionary *axisReadWrite(id<MTLDevice> dev, id<MTLLibrary> lib, FmtCtx c, BOOL isWrite) {
    NSMutableDictionary *r = [NSMutableDictionary dictionary];
    NSString *kname = isWrite ? writeKernelFor(c.kind) : readKernelFor(c.kind);
    NSString *perr = nil;
    id<MTLComputePipelineState> pso = makePSO(dev, lib, kname, &perr);
    if (!pso) { r[@"status"] = @"pipeline_rejected"; r[@"detail"] = perr ?: @""; r[@"kernel"] = kname; return r; }
    MTLTextureUsage usage = isWrite ? MTLTextureUsageShaderWrite : MTLTextureUsageShaderRead;
    if ([c.family isEqualToString:@"depth"] || [c.family isEqualToString:@"stencil"] || [c.family isEqualToString:@"depthstencil"] || [c.family isEqualToString:@"stencil_view"])
        usage |= MTLTextureUsageRenderTarget;
    NSString *terr = nil;
    id<MTLTexture> tex = tryTexture(dev, c.fmt, TESTDIM, TESTDIM, usage, MTLStorageModeShared, 1, &terr);
    if (!tex) { r[@"status"] = @"texture_rejected"; r[@"detail"] = terr ?: @""; return r; }
    id<MTLBuffer> constBuf = nil;
    if (isWrite) {
        if ([c.kind isEqualToString:@"uint"]) { uint32_t v[4] = {11, 22, 33, 44}; constBuf = [dev newBufferWithBytes:v length:16 options:MTLResourceStorageModeShared]; }
        else if ([c.kind isEqualToString:@"int"]) { int32_t v[4] = {-5, 7, -9, 3}; constBuf = [dev newBufferWithBytes:v length:16 options:MTLResourceStorageModeShared]; }
        else { float v[4] = {0.5f, 0.25f, 0.75f, 1.0f}; constBuf = [dev newBufferWithBytes:v length:16 options:MTLResourceStorageModeShared]; }
    }
    NSDictionary *d;
    if (isWrite) {
        // write kernels take (constant buffer(0)); no output buffer is bound.
        NSMutableDictionary *rr = [NSMutableDictionary dictionary];
        id<MTLCommandQueue> q = [dev newCommandQueue];
        id<MTLCommandBuffer> cb = [q commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
        [enc setComputePipelineState:pso];
        [enc setTexture:tex atIndex:0];
        [enc setBuffer:constBuf offset:0 atIndex:0];
        [enc dispatchThreadgroups:MTLSizeMake(1, 1, 1) threadsPerThreadgroup:MTLSizeMake(1, 1, 1)];
        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];
        rr[@"command_buffer_status"] = @(cb.status);
        rr[@"command_buffer_error"] = cb.error ? (cb.error.localizedDescription ?: @"") : @"";
        rr[@"status"] = (cb.status == MTLCommandBufferStatusCompleted) ? @"ok" : @"cb_error";
        if (cb.status == MTLCommandBufferStatusCompleted) {
            // best-effort CPU readback of the written texel (uncompressed, shared-storage only)
            if (!c.family || ([c.family rangeOfString:@"compressed"].location == NSNotFound && ![c.family isEqualToString:@"yuv422"])) {
                @try {
                    unsigned char buf[32]; memset(buf, 0, sizeof(buf));
                    MTLRegion reg = MTLRegionMake2D(0, 0, 1, 1);
                    [tex getBytes:buf bytesPerRow:32 fromRegion:reg mipmapLevel:0];
                    rr[@"texel0_hex"] = hexData([NSData dataWithBytes:buf length:16]);
                } @catch (NSException *e) { rr[@"texel0_readback_error"] = e.reason ?: @""; }
            }
        }
        d = rr;
    } else {
        d = dispatchOne(dev, pso, tex, nil, nil, 4);
    }
    [r addEntriesFromDictionary:d];
    r[@"kernel"] = kname;
    return r;
}

static NSDictionary *axisAtomic(id<MTLDevice> dev, id<MTLLibrary> lib, FmtCtx c) {
    NSMutableDictionary *r = [NSMutableDictionary dictionary];
    if (![c.kind isEqualToString:@"uint"] && ![c.kind isEqualToString:@"int"]) {
        r[@"status"] = @"not_applicable";
        r[@"detail"] = @"MSL provides texture atomics only on integer (uint/int) element types; this format's kind is not integer";
        return r;
    }
    NSString *kname = [c.kind isEqualToString:@"uint"] ? @"k_atomic_uint" : @"k_atomic_int";
    NSString *perr = nil;
    id<MTLComputePipelineState> pso = makePSO(dev, lib, kname, &perr);
    if (!pso) { r[@"status"] = @"pipeline_rejected"; r[@"detail"] = perr ?: @""; r[@"kernel"] = kname; return r; }
    MTLTextureUsage usage = MTLTextureUsageShaderRead | MTLTextureUsageShaderWrite;
    if ([c.family isEqualToString:@"stencil"] || [c.family isEqualToString:@"stencil_view"]) usage |= MTLTextureUsageRenderTarget;
    NSString *terr = nil;
    id<MTLTexture> tex = tryTexture(dev, c.fmt, TESTDIM, TESTDIM, usage, MTLStorageModeShared, 1, &terr);
    if (!tex) { r[@"status"] = @"texture_rejected"; r[@"detail"] = terr ?: @""; return r; }
    NSDictionary *d = dispatchOne(dev, pso, tex, nil, nil, 2);
    [r addEntriesFromDictionary:d];
    r[@"kernel"] = kname;
    return r;
}

static NSDictionary *renderPipelineTry(id<MTLDevice> dev, id<MTLLibrary> lib, MTLPixelFormat colorFmt,
                                        MTLPixelFormat depthFmt, MTLPixelFormat stencilFmt,
                                        NSString *fragKernel, NSUInteger sampleCount,
                                        BOOL blend, NSString **pipelineErr) {
    id<MTLFunction> vfn = [lib newFunctionWithName:(depthFmt != MTLPixelFormatInvalid || stencilFmt != MTLPixelFormatInvalid) ? @"vs_fullscreen_z" : @"vs_fullscreen"];
    id<MTLFunction> ffn = fragKernel ? [lib newFunctionWithName:fragKernel] : nil;
    MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
    pd.vertexFunction = vfn;
    pd.fragmentFunction = ffn;
    pd.rasterSampleCount = sampleCount;
    if (colorFmt != MTLPixelFormatInvalid) {
        pd.colorAttachments[0].pixelFormat = colorFmt;
        if (blend) {
            pd.colorAttachments[0].blendingEnabled = YES;
            pd.colorAttachments[0].rgbBlendOperation = MTLBlendOperationAdd;
            pd.colorAttachments[0].alphaBlendOperation = MTLBlendOperationAdd;
            pd.colorAttachments[0].sourceRGBBlendFactor = MTLBlendFactorSourceAlpha;
            pd.colorAttachments[0].destinationRGBBlendFactor = MTLBlendFactorOneMinusSourceAlpha;
            pd.colorAttachments[0].sourceAlphaBlendFactor = MTLBlendFactorOne;
            pd.colorAttachments[0].destinationAlphaBlendFactor = MTLBlendFactorZero;
        }
    }
    if (depthFmt != MTLPixelFormatInvalid) pd.depthAttachmentPixelFormat = depthFmt;
    if (stencilFmt != MTLPixelFormatInvalid) pd.stencilAttachmentPixelFormat = stencilFmt;
    NSError *err = nil;
    id<MTLRenderPipelineState> pso = nil;
    @try {
        pso = [dev newRenderPipelineStateWithDescriptor:pd error:&err];
    } @catch (NSException *e) {
        *pipelineErr = [NSString stringWithFormat:@"%@: %@", e.name, e.reason ?: @""];
        return @{@"status": @"pipeline_rejected", @"detail": *pipelineErr};
    }
    if (!pso) { *pipelineErr = err.localizedDescription ?: @"pipeline nil"; return @{@"status": @"pipeline_rejected", @"detail": *pipelineErr}; }
    return @{@"status": @"pipeline_ok"};
}

// Full draw: builds attachments matching the requested color/depth/stencil formats,
// runs one draw of the fullscreen triangle, waits, and reports command-buffer status.
// resolveFmt/resolveTarget non-nil requests an MSAA-with-resolve pass.
static NSDictionary *renderDrawTry(id<MTLDevice> dev, id<MTLLibrary> lib,
                                    MTLPixelFormat colorFmt, MTLPixelFormat depthFmt, MTLPixelFormat stencilFmt,
                                    NSString *fragKernel, NSUInteger sampleCount, BOOL blend, BOOL resolve) {
    NSMutableDictionary *r = [NSMutableDictionary dictionary];
    NSString *perr = nil;
    id<MTLFunction> vfn = [lib newFunctionWithName:(depthFmt != MTLPixelFormatInvalid || stencilFmt != MTLPixelFormatInvalid) ? @"vs_fullscreen_z" : @"vs_fullscreen"];
    id<MTLFunction> ffn = fragKernel ? [lib newFunctionWithName:fragKernel] : nil;
    if (!vfn || (fragKernel && !ffn)) { r[@"status"] = @"library_rejected"; return r; }
    MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
    pd.vertexFunction = vfn;
    pd.fragmentFunction = ffn;
    pd.rasterSampleCount = sampleCount;
    if (colorFmt != MTLPixelFormatInvalid) {
        pd.colorAttachments[0].pixelFormat = colorFmt;
        if (blend) {
            pd.colorAttachments[0].blendingEnabled = YES;
            pd.colorAttachments[0].rgbBlendOperation = MTLBlendOperationAdd;
            pd.colorAttachments[0].alphaBlendOperation = MTLBlendOperationAdd;
            pd.colorAttachments[0].sourceRGBBlendFactor = MTLBlendFactorSourceAlpha;
            pd.colorAttachments[0].destinationRGBBlendFactor = MTLBlendFactorOneMinusSourceAlpha;
            pd.colorAttachments[0].sourceAlphaBlendFactor = MTLBlendFactorOne;
            pd.colorAttachments[0].destinationAlphaBlendFactor = MTLBlendFactorZero;
        }
    }
    if (depthFmt != MTLPixelFormatInvalid) pd.depthAttachmentPixelFormat = depthFmt;
    if (stencilFmt != MTLPixelFormatInvalid) pd.stencilAttachmentPixelFormat = stencilFmt;
    NSError *err = nil;
    id<MTLRenderPipelineState> pso = nil;
    @try { pso = [dev newRenderPipelineStateWithDescriptor:pd error:&err]; }
    @catch (NSException *e) { r[@"status"] = @"pipeline_rejected"; r[@"detail"] = e.reason ?: @""; return r; }
    if (!pso) { r[@"status"] = @"pipeline_rejected"; r[@"detail"] = err.localizedDescription ?: @""; return r; }

    id<MTLTexture> colorTex = nil, resolveTex = nil, depthTex = nil, stencilTex = nil;
    NSString *terr = nil;
    if (colorFmt != MTLPixelFormatInvalid) {
        MTLTextureUsage u = MTLTextureUsageRenderTarget;
        colorTex = tryTexture(dev, colorFmt, TESTDIM, TESTDIM, u, MTLStorageModePrivate, sampleCount, &terr);
        if (!colorTex) { r[@"status"] = @"texture_rejected"; r[@"detail"] = terr ?: @""; return r; }
        if (resolve) {
            resolveTex = tryTexture(dev, colorFmt, TESTDIM, TESTDIM, MTLTextureUsageRenderTarget, MTLStorageModePrivate, 1, &terr);
            if (!resolveTex) { r[@"status"] = @"resolve_texture_rejected"; r[@"detail"] = terr ?: @""; return r; }
        }
    }
    if (depthFmt != MTLPixelFormatInvalid) {
        depthTex = tryTexture(dev, depthFmt, TESTDIM, TESTDIM, MTLTextureUsageRenderTarget, MTLStorageModePrivate, sampleCount, &terr);
        if (!depthTex) { r[@"status"] = @"depth_texture_rejected"; r[@"detail"] = terr ?: @""; return r; }
    }
    if (stencilFmt != MTLPixelFormatInvalid) {
        if (stencilFmt == depthFmt) stencilTex = depthTex;
        else { stencilTex = tryTexture(dev, stencilFmt, TESTDIM, TESTDIM, MTLTextureUsageRenderTarget, MTLStorageModePrivate, sampleCount, &terr);
               if (!stencilTex) { r[@"status"] = @"stencil_texture_rejected"; r[@"detail"] = terr ?: @""; return r; } }
    }

    MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
    if (colorTex) {
        rp.colorAttachments[0].texture = colorTex;
        rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 0);
        if (resolve) { rp.colorAttachments[0].resolveTexture = resolveTex; rp.colorAttachments[0].storeAction = MTLStoreActionMultisampleResolve; }
        else rp.colorAttachments[0].storeAction = MTLStoreActionStore;
    }
    if (depthTex) {
        rp.depthAttachment.texture = depthTex;
        rp.depthAttachment.loadAction = MTLLoadActionClear;
        rp.depthAttachment.clearDepth = 0.8;
        rp.depthAttachment.storeAction = MTLStoreActionStore;
    }
    if (stencilTex) {
        rp.stencilAttachment.texture = stencilTex;
        rp.stencilAttachment.loadAction = MTLLoadActionClear;
        rp.stencilAttachment.clearStencil = 0;
        rp.stencilAttachment.storeAction = MTLStoreActionStore;
    }
    id<MTLCommandQueue> q = [dev newCommandQueue];
    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLRenderCommandEncoder> enc = nil;
    @try { enc = [cb renderCommandEncoderWithDescriptor:rp]; }
    @catch (NSException *e) { r[@"status"] = @"encoder_rejected"; r[@"detail"] = e.reason ?: @""; return r; }
    if (!enc) { r[@"status"] = @"encoder_rejected"; return r; }
    [enc setRenderPipelineState:pso];
    if (depthFmt != MTLPixelFormatInvalid || stencilFmt != MTLPixelFormatInvalid) {
        MTLDepthStencilDescriptor *dsd = [MTLDepthStencilDescriptor new];
        if (depthFmt != MTLPixelFormatInvalid) { dsd.depthCompareFunction = MTLCompareFunctionLess; dsd.depthWriteEnabled = YES; }
        if (stencilFmt != MTLPixelFormatInvalid) {
            MTLStencilDescriptor *sd = [MTLStencilDescriptor new];
            sd.stencilCompareFunction = MTLCompareFunctionAlways;
            sd.depthStencilPassOperation = MTLStencilOperationReplace;
            dsd.frontFaceStencil = sd; dsd.backFaceStencil = sd;
        }
        id<MTLDepthStencilState> dss = [dev newDepthStencilStateWithDescriptor:dsd];
        [enc setDepthStencilState:dss];
        [enc setStencilReferenceValue:0x5A];
        float z = 0.3f;
        id<MTLBuffer> zbuf = [dev newBufferWithBytes:&z length:4 options:MTLResourceStorageModeShared];
        [enc setVertexBuffer:zbuf offset:0 atIndex:0];
    }
    [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
    [enc endEncoding];
    [cb commit];
    [cb waitUntilCompleted];
    r[@"command_buffer_status"] = @(cb.status);
    r[@"command_buffer_error"] = cb.error ? (cb.error.localizedDescription ?: @"") : @"";
    r[@"status"] = (cb.status == MTLCommandBufferStatusCompleted) ? @"ok" : @"cb_error";
    return r;
}

// minimumLinearTextureAlignmentForPixelFormat:'s own header doc says it "throws" for
// depth/stencil/compressed formats; empirically (work/explore/, pre-registration
// exploration) this is a hard abort() -- NOT a catchable NSException, and it ALSO
// fires for the YUV 4:2:2 formats (GBGR422/BGRG422), which the header doesn't
// mention. Since this cannot be caught, the family must be excluded BEFORE the call
// is ever made; the exclusion set below is derived from that empirical finding, not
// merely the header's (incomplete) documented set.
static BOOL familyLinearIneligible(NSString *family) {
    static NSSet<NSString *> *ineligible;
    static dispatch_once_t once;
    dispatch_once(&once, ^{
        ineligible = [NSSet setWithArray:@[@"depth", @"stencil", @"depthstencil", @"stencil_view",
                                            @"compressed_bc", @"compressed_pvrtc", @"compressed_etc",
                                            @"compressed_astc_ldr", @"compressed_astc_hdr", @"yuv422"]];
    });
    return [ineligible containsObject:family];
}

static BOOL queryLinearAlign(id<MTLDevice> dev, MTLPixelFormat fmt, NSString *family, NSUInteger *out, NSString **excReason) {
    if (familyLinearIneligible(family)) {
        *excReason = @"format family excluded pre-call (empirically confirmed hard-abort family; see familyLinearIneligible)";
        return NO;
    }
    @try { *out = [dev minimumLinearTextureAlignmentForPixelFormat:fmt]; return YES; }
    @catch (NSException *e) { *excReason = [NSString stringWithFormat:@"%@: %@", e.name, e.reason ?: @""]; return NO; }
}

static NSDictionary *axisLinear(id<MTLDevice> dev, FmtCtx c) {
    NSMutableDictionary *r = [NSMutableDictionary dictionary];
    NSUInteger align = 0; NSString *exc = nil;
    if (!queryLinearAlign(dev, c.fmt, c.family, &align, &exc)) {
        r[@"status"] = @"not_applicable";
        r[@"detail"] = [NSString stringWithFormat:@"minimumLinearTextureAlignmentForPixelFormat inapplicable/would-abort for this family: %@", exc ?: @""];
        return r;
    }
    r[@"minimum_linear_texture_alignment"] = @(align);
    if (align == 0) { r[@"status"] = @"not_applicable"; r[@"detail"] = @"minimumLinearTextureAlignmentForPixelFormat returned 0"; return r; }
    // bytesPerRow must be >= the row's true byte footprint AND a multiple of `align`
    // (the query gives a granularity, not a literal minimum row size -- confirmed
    // empirically: using `align` alone as bytesPerRow triggers a hard Metal
    // validation abort for formats wider than the alignment, e.g. RGBA8Unorm).
    NSUInteger rowBytesNeeded = ([c.family isEqualToString:@"yuv422"]) ? (TESTDIM / 2) * 4
                              : (c.bpp > 0) ? (NSUInteger)c.bpp * TESTDIM : align;
    NSUInteger bytesPerRow = ((rowBytesNeeded + align - 1) / align) * align;
    r[@"row_bytes_needed"] = @(rowBytesNeeded);
    r[@"bytes_per_row_used"] = @(bytesPerRow);
    NSUInteger bufLen = bytesPerRow * TESTDIM + 4096;
    id<MTLBuffer> buf = [dev newBufferWithLength:bufLen options:MTLResourceStorageModeShared];
    if (!buf) { r[@"status"] = @"buffer_rejected"; return r; }
    MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:c.fmt width:TESTDIM height:TESTDIM mipmapped:NO];
    td.usage = MTLTextureUsageShaderRead;
    td.storageMode = MTLStorageModeShared;
    id<MTLTexture> t = nil;
    @try { t = [buf newTextureWithDescriptor:td offset:0 bytesPerRow:bytesPerRow]; }
    @catch (NSException *e) { r[@"status"] = @"texture_rejected"; r[@"detail"] = e.reason ?: @""; return r; }
    if (!t) { r[@"status"] = @"texture_rejected"; r[@"detail"] = @"newTextureWithDescriptor:offset:bytesPerRow: returned nil"; return r; }
    r[@"status"] = @"ok";
    return r;
}

// Compute-path axes ONLY (sampled/filtered/storage_read/storage_write/atomic/linear).
// Empirically, these six always fail gracefully (nil + NSError) even for formats that
// cannot support them -- verified across compressed/depth/stencil/YUV/PVRTC formats
// during pre-registration exploration (work/explore/). They are safe to bundle into
// one process per format.
//
// The other five axes (renderable/blendable/msaa/resolve/depth_stencil) are NOT safe
// to bundle: Metal's render-pipeline-descriptor validation calls abort() (SIGABRT, not
// a catchable NSException, and unaffected by MTL_DEBUG_LAYER/METAL_DEVICE_WRAPPER_TYPE)
// for a statically-non-renderable/non-blendable pixel format -- confirmed empirically
// against MTLPixelFormatBC1_RGBA ("is not color renderable"), MTLPixelFormatR32Uint
// ("is not blendable"), and every depth/stencil/compressed/YUV format tried. This is
// itself a documented finding (RESULTS.md): render/blend/MSAA/resolve attachment
// eligibility is enforced as a fatal host-side precondition, not a soft runtime
// negotiation. Each of those five axes therefore runs as its OWN process per format
// (mode capability --axis <name>), so a hard abort loses only that one axis's record.
// EVERY axis (not just the render-pipeline ones) runs as its own process per
// format. Pre-registration exploration found a THIRD hard-abort class beyond
// F1 (render-pipeline validation) and F2 (minimumLinearTextureAlignmentFor...):
// bare `newTextureWithDescriptor:` itself hard-aborts ("MTLTextureDescriptor
// has invalid pixelFormat (N)") for a pixel format this specific device does
// not support AT ALL (observed for MTLPixelFormatDepth24Unorm_Stencil8,
// id 255 -- corroborating the prior EXP-M4-08 finding, docs/descriptors/
// format-table.md, that depth24unorm_stencil8/x24_stencil8 are the two
// formats Metal rejects on this hardware) -- and this bypasses @try/@catch
// exactly like F1/F2 (SIGABRT, not a catchable NSException). Since ANY axis
// can hit this on its very first texture-creation call, no axis grouping is
// safe to bundle into one process; every (format, axis) pair is isolated.
static NSDictionary *runCapabilityAxis(id<MTLDevice> dev, id<MTLLibrary> lib, FmtCtx c, NSString *axis) {
    if ([axis isEqualToString:@"sampled"]) return axisSample(dev, lib, c, NO);
    if ([axis isEqualToString:@"filtered"]) return axisSample(dev, lib, c, YES);
    if ([axis isEqualToString:@"storage_read"]) return axisReadWrite(dev, lib, c, NO);
    if ([axis isEqualToString:@"storage_write"]) return axisReadWrite(dev, lib, c, YES);
    if ([axis isEqualToString:@"atomic"]) return axisAtomic(dev, lib, c);
    if ([axis isEqualToString:@"linear"]) return axisLinear(dev, c);
    NSString *fragKernel = [c.kind isEqualToString:@"uint"] ? @"fs_color_uint" : [c.kind isEqualToString:@"int"] ? @"fs_color_int" : @"fs_color_float";
    if ([axis isEqualToString:@"renderable"]) return renderDrawTry(dev, lib, c.fmt, MTLPixelFormatInvalid, MTLPixelFormatInvalid, fragKernel, 1, NO, NO);
    if ([axis isEqualToString:@"blendable"]) return renderDrawTry(dev, lib, c.fmt, MTLPixelFormatInvalid, MTLPixelFormatInvalid, fragKernel, 1, YES, NO);
    if ([axis isEqualToString:@"msaa"]) return renderDrawTry(dev, lib, c.fmt, MTLPixelFormatInvalid, MTLPixelFormatInvalid, fragKernel, 4, NO, NO);
    if ([axis isEqualToString:@"resolve"]) return renderDrawTry(dev, lib, c.fmt, MTLPixelFormatInvalid, MTLPixelFormatInvalid, fragKernel, 4, NO, YES);
    if ([axis isEqualToString:@"depth_stencil"]) {
        BOOL dsFamily = [c.family isEqualToString:@"depth"] || [c.family isEqualToString:@"stencil"] || [c.family isEqualToString:@"depthstencil"] || [c.family isEqualToString:@"stencil_view"];
        if (!dsFamily) return @{@"status": @"not_applicable", @"detail": @"format is not in the depth/stencil family"};
        MTLPixelFormat depthFmt = ([c.family isEqualToString:@"depth"] || [c.family isEqualToString:@"depthstencil"]) ? c.fmt : MTLPixelFormatInvalid;
        MTLPixelFormat stencilFmt = ([c.family isEqualToString:@"stencil"] || [c.family isEqualToString:@"depthstencil"] || [c.family isEqualToString:@"stencil_view"]) ? c.fmt : MTLPixelFormatInvalid;
        return renderDrawTry(dev, lib, MTLPixelFormatInvalid, depthFmt, stencilFmt, @"fs_depth_only", 1, NO, NO);
    }
    return @{@"status": @"unknown_axis"};
}

// ---------------------------------------------------------------- sparse mode (bounded representative subset)

static NSDictionary *runSparse(id<MTLDevice> dev, MTLPixelFormat fmt) {
    NSMutableDictionary *r = [NSMutableDictionary dictionary];
    r[@"device_sparse_tile_size_in_bytes"] = @(dev.sparseTileSizeInBytes);
    MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:fmt width:256 height:256 mipmapped:NO];
    td.usage = MTLTextureUsageShaderRead | MTLTextureUsageShaderWrite;
    td.storageMode = MTLStorageModePrivate;
    MTLSizeAndAlign sa;
    @try { sa = [dev heapTextureSizeAndAlignWithDescriptor:td]; }
    @catch (NSException *e) { r[@"status"] = @"size_query_rejected"; r[@"detail"] = e.reason ?: @""; return r; }
    r[@"heap_size"] = @(sa.size); r[@"heap_align"] = @(sa.align);
    MTLHeapDescriptor *hd = [MTLHeapDescriptor new];
    hd.type = MTLHeapTypeSparse;
    hd.storageMode = MTLStorageModePrivate;
    hd.size = MAX(sa.size, (NSUInteger)dev.sparseTileSizeInBytes);
    id<MTLHeap> heap = nil;
    @try { heap = [dev newHeapWithDescriptor:hd]; }
    @catch (NSException *e) { r[@"status"] = @"heap_rejected"; r[@"detail"] = e.reason ?: @""; return r; }
    if (!heap) { r[@"status"] = @"heap_rejected"; r[@"detail"] = @"newHeapWithDescriptor returned nil"; return r; }
    id<MTLTexture> t = nil;
    @try { t = [heap newTextureWithDescriptor:td]; }
    @catch (NSException *e) { r[@"status"] = @"sparse_texture_rejected"; r[@"detail"] = e.reason ?: @""; return r; }
    if (!t) { r[@"status"] = @"sparse_texture_rejected"; r[@"detail"] = @"heap newTextureWithDescriptor returned nil"; return r; }
    r[@"status"] = @"ok";
    r[@"sparse_page_size"] = @([dev sparseTileSizeInBytes]);
    return r;
}

// ---------------------------------------------------------------- layout mode

// NOTE: this deliberately does NOT probe "one byte below the minimum" in-process --
// pre-registration exploration established that violating the minimum triggers a hard
// Metal validation abort() (_mtlValidateStrideTextureParameters), not a catchable
// NSException (see harness/probe.m familyLinearIneligible comment and RESULTS.md).
// That boundary is instead exercised once, as its own explicitly-expected-to-abort
// case (case id "linear_below_minimum_aborts"), not per format.
static NSDictionary *runLayout(id<MTLDevice> dev, MTLPixelFormat fmt, NSString *family, NSUInteger bpp) {
    NSMutableDictionary *r = [NSMutableDictionary dictionary];
    NSUInteger align = 0; NSString *exc = nil;
    if (queryLinearAlign(dev, fmt, family, &align, &exc)) {
        r[@"minimum_linear_texture_alignment"] = @(align);
    } else {
        r[@"minimum_linear_texture_alignment"] = [NSNull null];
        r[@"minimum_linear_texture_alignment_exception"] = exc ?: @"";
        align = 0;
    }
    if (familyLinearIneligible(family)) {
        r[@"minimum_texture_buffer_alignment"] = [NSNull null];
        r[@"minimum_texture_buffer_alignment_exception"] = @"family excluded pre-call (mirrors linear-texture exclusion; texture_buffer is 1D-only and not meaningful for this family in this experiment's scope)";
    } else {
        @try { r[@"minimum_texture_buffer_alignment"] = @([dev minimumTextureBufferAlignmentForPixelFormat:fmt]); }
        @catch (NSException *e) { r[@"minimum_texture_buffer_alignment"] = [NSNull null]; r[@"minimum_texture_buffer_alignment_exception"] = e.reason ?: @""; }
    }
    // Accepts-at-exactly-the-minimum is safe to test (it is, by the query's own
    // definition, a legal value) and is the positive half of the boundary pair.
    if (align > 0) {
        NSUInteger rowBytesNeeded = [family isEqualToString:@"yuv422"] ? (TESTDIM / 2) * 4 : (bpp > 0 ? bpp * TESTDIM : align);
        NSUInteger bytesPerRow = ((rowBytesNeeded + align - 1) / align) * align;
        id<MTLBuffer> buf = [dev newBufferWithLength:bytesPerRow * TESTDIM + 4096 options:MTLResourceStorageModeShared];
        MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:fmt width:TESTDIM height:TESTDIM mipmapped:NO];
        td.usage = MTLTextureUsageShaderRead; td.storageMode = MTLStorageModeShared;
        id<MTLTexture> tMin = nil;
        @try { tMin = [buf newTextureWithDescriptor:td offset:0 bytesPerRow:bytesPerRow]; } @catch (__unused NSException *e) {}
        r[@"accepts_bytesperrow_at_minimum_aligned_row"] = @(tMin != nil);
        r[@"bytes_per_row_used"] = @(bytesPerRow);
    } else {
        r[@"accepts_bytesperrow_at_minimum_aligned_row"] = [NSNull null];
    }
    return r;
}

// ---------------------------------------------------------------- conversion mode
// Each conversion case is self-contained: compiles its own tiny library (the source
// path is the shared kernels/conversion.metal, which defines one kernel per case,
// exactly mirroring EXP-0079's store+read pattern), runs a store then a typed read,
// and returns the same shape of record. BC1 decode-only cases skip the store phase
// and instead upload authored compressed bytes via replaceRegion.

static NSDictionary *runConversionStoreRead(id<MTLDevice> dev, id<MTLLibrary> lib, NSString *storeFn, NSString *readFn,
                                             MTLPixelFormat fmt, NSUInteger texelBytes) {
    NSMutableDictionary *r = [NSMutableDictionary dictionary];
    NSString *perr = nil;
    id<MTLComputePipelineState> spso = makePSO(dev, lib, storeFn, &perr);
    if (!spso) { r[@"status"] = @"store_pipeline_rejected"; r[@"detail"] = perr ?: @""; return r; }
    id<MTLComputePipelineState> rpso = makePSO(dev, lib, readFn, &perr);
    if (!rpso) { r[@"status"] = @"read_pipeline_rejected"; r[@"detail"] = perr ?: @""; return r; }
    MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:fmt width:1 height:1 mipmapped:NO];
    td.usage = MTLTextureUsageShaderWrite | MTLTextureUsageShaderRead;
    td.storageMode = MTLStorageModeShared;
    NSString *terr = nil;
    FmtCtx dummy = {fmt, @"float", @"", 1, -1};
    id<MTLTexture> tex = tryTexture(dev, fmt, 1, 1, td.usage, MTLStorageModeShared, 1, &terr);
    (void)dummy;
    if (!tex) { r[@"status"] = @"texture_rejected"; r[@"detail"] = terr ?: @""; return r; }
    id<MTLBuffer> outBuf = [dev newBufferWithLength:16 options:MTLResourceStorageModeShared];
    id<MTLCommandQueue> q = [dev newCommandQueue];
    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
    [enc setComputePipelineState:spso];
    [enc setTexture:tex atIndex:0];
    [enc dispatchThreadgroups:MTLSizeMake(1, 1, 1) threadsPerThreadgroup:MTLSizeMake(1, 1, 1)];
    [enc setComputePipelineState:rpso];
    [enc setTexture:tex atIndex:0];
    [enc setBuffer:outBuf offset:0 atIndex:0];
    [enc dispatchThreadgroups:MTLSizeMake(1, 1, 1) threadsPerThreadgroup:MTLSizeMake(1, 1, 1)];
    [enc endEncoding];
    [cb commit];
    [cb waitUntilCompleted];
    r[@"command_buffer_status"] = @(cb.status);
    r[@"command_buffer_error"] = cb.error ? (cb.error.localizedDescription ?: @"") : @"";
    if (cb.status != MTLCommandBufferStatusCompleted) { r[@"status"] = @"cb_error"; return r; }
    unsigned char texel[64]; memset(texel, 0, sizeof(texel));
    @try {
        MTLRegion reg = MTLRegionMake2D(0, 0, 1, 1);
        [tex getBytes:texel bytesPerRow:64 fromRegion:reg mipmapLevel:0];
    } @catch (NSException *e) { r[@"status"] = @"readback_exception"; r[@"detail"] = e.reason ?: @""; return r; }
    r[@"status"] = @"ok";
    r[@"physical_texel_hex"] = hexData([NSData dataWithBytes:texel length:texelBytes]);
    r[@"read_words_hex"] = hexData([NSData dataWithBytes:outBuf.contents length:16]);
    return r;
}

// BC1 decode-only: upload an authored 8-byte BC1 block via replaceRegion, sample-read it,
// no store phase (BC1 textures cannot be access::write).
static NSDictionary *runBC1Decode(id<MTLDevice> dev, id<MTLLibrary> lib, uint16_t color0, uint16_t color1, uint32_t indices) {
    NSMutableDictionary *r = [NSMutableDictionary dictionary];
    NSString *perr = nil;
    id<MTLComputePipelineState> pso = makePSO(dev, lib, @"k_read_bc1", &perr);
    if (!pso) { r[@"status"] = @"read_pipeline_rejected"; r[@"detail"] = perr ?: @""; return r; }
    MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBC1_RGBA width:4 height:4 mipmapped:NO];
    td.usage = MTLTextureUsageShaderRead;
    td.storageMode = MTLStorageModeShared;
    id<MTLTexture> tex = [dev newTextureWithDescriptor:td];
    if (!tex) { r[@"status"] = @"texture_rejected"; return r; }
    unsigned char block[8];
    block[0] = color0 & 0xFF; block[1] = (color0 >> 8) & 0xFF;
    block[2] = color1 & 0xFF; block[3] = (color1 >> 8) & 0xFF;
    block[4] = indices & 0xFF; block[5] = (indices >> 8) & 0xFF; block[6] = (indices >> 16) & 0xFF; block[7] = (indices >> 24) & 0xFF;
    MTLRegion reg = MTLRegionMake2D(0, 0, 4, 4);
    @try { [tex replaceRegion:reg mipmapLevel:0 withBytes:block bytesPerRow:8]; }
    @catch (NSException *e) { r[@"status"] = @"replaceregion_rejected"; r[@"detail"] = e.reason ?: @""; return r; }
    id<MTLBuffer> outBuf = [dev newBufferWithLength:16 options:MTLResourceStorageModeShared];
    id<MTLCommandQueue> q = [dev newCommandQueue];
    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
    [enc setComputePipelineState:pso];
    [enc setTexture:tex atIndex:0];
    [enc setBuffer:outBuf offset:0 atIndex:0];
    [enc dispatchThreadgroups:MTLSizeMake(1, 1, 1) threadsPerThreadgroup:MTLSizeMake(1, 1, 1)];
    [enc endEncoding];
    [cb commit];
    [cb waitUntilCompleted];
    r[@"command_buffer_status"] = @(cb.status);
    r[@"command_buffer_error"] = cb.error ? (cb.error.localizedDescription ?: @"") : @"";
    r[@"status"] = (cb.status == MTLCommandBufferStatusCompleted) ? @"ok" : @"cb_error";
    if (cb.status == MTLCommandBufferStatusCompleted) r[@"read_words_hex"] = hexData([NSData dataWithBytes:outBuf.contents length:16]);
    return r;
}

// Split depth/stencil aspect probe for Depth32Float_Stencil8: write depth via a render
// draw, write stencil via the same draw, then independently read the depth aspect
// (direct depth2d bind) and the stencil aspect (a texture view with pixelFormat
// X32_Stencil8, bound as texture2d<uint>) to confirm neither read observes the other.
static NSDictionary *runSplitDepthStencil(id<MTLDevice> dev, id<MTLLibrary> lib) {
    NSMutableDictionary *r = [NSMutableDictionary dictionary];
    MTLPixelFormat fmt = MTLPixelFormatDepth32Float_Stencil8;
    NSDictionary *draw = renderDrawTry(dev, lib, MTLPixelFormatInvalid, fmt, fmt, @"fs_depth_only", 1, NO, NO);
    r[@"draw"] = draw;
    if (![draw[@"status"] isEqualToString:@"ok"]) { r[@"status"] = @"draw_failed"; return r; }
    // Recreate identical texture + redo the draw so we can keep the texture object
    // for readback (renderDrawTry above didn't return its texture).
    id<MTLTexture> combo = tryTexture(dev, fmt, TESTDIM, TESTDIM, MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead | MTLTextureUsagePixelFormatView, MTLStorageModeShared, 1, &(NSString * __autoreleasing){nil});
    if (!combo) { r[@"status"] = @"texture_rejected_for_readback"; return r; }
    MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
    rp.depthAttachment.texture = combo; rp.depthAttachment.loadAction = MTLLoadActionClear; rp.depthAttachment.clearDepth = 0.8; rp.depthAttachment.storeAction = MTLStoreActionStore;
    rp.stencilAttachment.texture = combo; rp.stencilAttachment.loadAction = MTLLoadActionClear; rp.stencilAttachment.clearStencil = 0; rp.stencilAttachment.storeAction = MTLStoreActionStore;
    id<MTLFunction> vfn = [lib newFunctionWithName:@"vs_fullscreen_z"];
    id<MTLFunction> ffn = [lib newFunctionWithName:@"fs_depth_only"];
    MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
    pd.vertexFunction = vfn; pd.fragmentFunction = ffn;
    pd.depthAttachmentPixelFormat = fmt; pd.stencilAttachmentPixelFormat = fmt;
    NSError *err = nil;
    id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:pd error:&err];
    if (!pso) { r[@"status"] = @"pipeline_rejected_for_readback"; return r; }
    id<MTLCommandQueue> q = [dev newCommandQueue];
    id<MTLCommandBuffer> cb = [q commandBuffer];
    id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
    [enc setRenderPipelineState:pso];
    MTLDepthStencilDescriptor *dsd = [MTLDepthStencilDescriptor new];
    dsd.depthCompareFunction = MTLCompareFunctionLess; dsd.depthWriteEnabled = YES;
    MTLStencilDescriptor *sd = [MTLStencilDescriptor new];
    sd.stencilCompareFunction = MTLCompareFunctionAlways; sd.depthStencilPassOperation = MTLStencilOperationReplace;
    dsd.frontFaceStencil = sd; dsd.backFaceStencil = sd;
    id<MTLDepthStencilState> dss = [dev newDepthStencilStateWithDescriptor:dsd];
    [enc setDepthStencilState:dss];
    [enc setStencilReferenceValue:0x5A];
    float z = 0.3f;
    id<MTLBuffer> zbuf = [dev newBufferWithBytes:&z length:4 options:MTLResourceStorageModeShared];
    [enc setVertexBuffer:zbuf offset:0 atIndex:0];
    [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
    [enc endEncoding];
    [cb commit];
    [cb waitUntilCompleted];
    if (cb.status != MTLCommandBufferStatusCompleted) { r[@"status"] = @"cb_error_for_readback"; return r; }
    // Depth aspect: sample directly.
    id<MTLComputePipelineState> dpso = makePSO(dev, lib, @"k_sample_depth", &(NSString * __autoreleasing){nil});
    MTLSamplerDescriptor *smd = [MTLSamplerDescriptor new];
    smd.minFilter = MTLSamplerMinMagFilterNearest; smd.magFilter = MTLSamplerMinMagFilterNearest;
    id<MTLSamplerState> smp = [dev newSamplerStateWithDescriptor:smd];
    NSDictionary *depthRead = dispatchOne(dev, dpso, combo, smp, nil, 4);
    r[@"depth_aspect_read"] = depthRead;
    // Stencil aspect: view as X32_Stencil8, bind as texture2d<uint>, read.
    id<MTLTexture> stencilView = [combo newTextureViewWithPixelFormat:MTLPixelFormatX32_Stencil8];
    if (!stencilView) { r[@"status"] = @"stencil_view_rejected"; return r; }
    id<MTLComputePipelineState> spso = makePSO(dev, lib, @"k_read_uint", &(NSString * __autoreleasing){nil});
    NSDictionary *stencilRead = dispatchOne(dev, spso, stencilView, nil, nil, 4);
    r[@"stencil_aspect_read"] = stencilRead;
    r[@"status"] = @"ok";
    return r;
}

// ---------------------------------------------------------------- main

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        NSMutableArray<NSString *> *args = [NSMutableArray array];
        for (int i = 1; i < argc; i++) [args addObject:[NSString stringWithUTF8String:argv[i]]];
        NSString *mode = argVal(args, @"--mode");
        NSString *sourcePath = argVal(args, @"--source");
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        NSMutableDictionary *out = [NSMutableDictionary dictionary];
        out[@"mode"] = mode ?: @"";
        out[@"device"] = dev.name ?: @"";
        out[@"machine"] = @"arm64";
        NSProcessInfo *pi = [NSProcessInfo processInfo];
        out[@"os"] = pi.operatingSystemVersionString ?: @"";
        if (!dev) { out[@"status"] = @"no_device"; emitAndExit(out); }
        NSString *libErr = nil;
        id<MTLLibrary> lib = sourcePath ? compileLibrary(dev, sourcePath, &libErr) : nil;
        if (sourcePath && !lib) { out[@"status"] = @"library_rejected"; out[@"detail"] = libErr ?: @""; emitAndExit(out); }
        out[@"msl_language_version"] = @(lib ? 1 : 0);

        if ([mode isEqualToString:@"capability"]) {
            NSInteger fid = [argVal(args, @"--id") integerValue];
            NSString *name = argVal(args, @"--name") ?: @"";
            NSString *kind = argVal(args, @"--kind") ?: @"float";
            NSString *family = argVal(args, @"--family") ?: @"";
            NSString *bppArg = argVal(args, @"--bpp");
            NSInteger bpp = (bppArg && ![bppArg isEqualToString:@"none"]) ? [bppArg integerValue] : -1;
            FmtCtx c = {(MTLPixelFormat)fid, kind, family, 2, bpp};
            NSString *axis = argVal(args, @"--axis");
            out[@"id"] = @(fid);
            out[@"name"] = name;
            out[@"kind"] = kind;
            out[@"family"] = family;
            if (!axis) { out[@"status"] = @"missing_axis"; emitAndExit(out); }
            out[@"group"] = axis;
            out[@"axes"] = @{axis: runCapabilityAxis(dev, lib, c, axis)};
            out[@"status"] = @"ok";
            emitAndExit(out);
        } else if ([mode isEqualToString:@"layout"]) {
            NSInteger fid = [argVal(args, @"--id") integerValue];
            NSString *name = argVal(args, @"--name") ?: @"";
            NSString *family = argVal(args, @"--family") ?: @"";
            NSString *bppArg = argVal(args, @"--bpp");
            NSUInteger bpp = (bppArg && ![bppArg isEqualToString:@"none"]) ? (NSUInteger)[bppArg integerValue] : 0;
            out[@"id"] = @(fid);
            out[@"name"] = name;
            if ([args containsObject:@"--below-minimum"]) {
                // Deliberately adversarial, expected to hard-abort (that abort IS the
                // result -- run once as its own dedicated case, not per format).
                NSUInteger align = 0; NSString *exc = nil;
                if (!queryLinearAlign(dev, (MTLPixelFormat)fid, family, &align, &exc) || align <= 1) {
                    out[@"status"] = @"skipped_not_applicable"; out[@"detail"] = exc ?: @"align <= 1";
                    emitAndExit(out);
                }
                id<MTLBuffer> buf = [dev newBufferWithLength:align * TESTDIM + 4096 options:MTLResourceStorageModeShared];
                MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:(MTLPixelFormat)fid width:TESTDIM height:TESTDIM mipmapped:NO];
                td.usage = MTLTextureUsageShaderRead; td.storageMode = MTLStorageModeShared;
                // No @try/@catch: pre-registration exploration established this specific
                // violation is a hard abort(), not a catchable NSException. If Metal's
                // behavior has changed and this now returns nil gracefully instead, that
                // is itself new information the record below will capture.
                id<MTLTexture> tBelow = [buf newTextureWithDescriptor:td offset:0 bytesPerRow:(align - 1)];
                out[@"status"] = @"ok_no_abort";
                out[@"unexpected_success"] = @(tBelow != nil);
                out[@"minimum_linear_texture_alignment"] = @(align);
                emitAndExit(out);
            }
            [out addEntriesFromDictionary:runLayout(dev, (MTLPixelFormat)fid, family, bpp)];
            out[@"status"] = @"ok";
            emitAndExit(out);
        } else if ([mode isEqualToString:@"sparse"]) {
            NSInteger fid = [argVal(args, @"--id") integerValue];
            NSString *name = argVal(args, @"--name") ?: @"";
            out[@"id"] = @(fid);
            out[@"name"] = name;
            [out addEntriesFromDictionary:runSparse(dev, (MTLPixelFormat)fid)];
            emitAndExit(out);
        } else if ([mode isEqualToString:@"conversion"]) {
            NSString *cs = argVal(args, @"--case") ?: @"";
            out[@"case"] = cs;
            NSDictionary *result = nil;
            if ([cs isEqualToString:@"r16unorm_sep_a"]) result = runConversionStoreRead(dev, lib, @"s_r16unorm_sep_a", @"k_read_float2", MTLPixelFormatR16Unorm, 2);
            else if ([cs isEqualToString:@"r16unorm_sep_b"]) result = runConversionStoreRead(dev, lib, @"s_r16unorm_sep_b", @"k_read_float2", MTLPixelFormatR16Unorm, 2);
            else if ([cs isEqualToString:@"r16unorm_nontie"]) result = runConversionStoreRead(dev, lib, @"s_r16unorm_nontie", @"k_read_float2", MTLPixelFormatR16Unorm, 2);
            else if ([cs isEqualToString:@"r16snorm_m100"]) result = runConversionStoreRead(dev, lib, @"s_r16snorm_m100", @"k_read_float2", MTLPixelFormatR16Snorm, 2);
            else if ([cs isEqualToString:@"r16snorm_p100"]) result = runConversionStoreRead(dev, lib, @"s_r16snorm_p100", @"k_read_float2", MTLPixelFormatR16Snorm, 2);
            else if ([cs isEqualToString:@"rgba16unorm_sep"]) result = runConversionStoreRead(dev, lib, @"s_rgba16unorm_sep", @"k_read_float8", MTLPixelFormatRGBA16Unorm, 8);
            else if ([cs isEqualToString:@"srgb8_low"]) result = runConversionStoreRead(dev, lib, @"s_srgb8_low", @"k_read_float4", MTLPixelFormatRGBA8Unorm_sRGB, 4);
            else if ([cs isEqualToString:@"srgb8_mid"]) result = runConversionStoreRead(dev, lib, @"s_srgb8_mid", @"k_read_float4", MTLPixelFormatRGBA8Unorm_sRGB, 4);
            else if ([cs isEqualToString:@"srgb8_high"]) result = runConversionStoreRead(dev, lib, @"s_srgb8_high", @"k_read_float4", MTLPixelFormatRGBA8Unorm_sRGB, 4);
            else if ([cs isEqualToString:@"int_filter_r32uint"]) {
                // Adversarial: attempt a LINEAR-filter sample against an integer format.
                id<MTLComputePipelineState> pso = makePSO(dev, lib, @"k_sample_uint4", &(NSString * __autoreleasing){nil});
                NSMutableDictionary *rr = [NSMutableDictionary dictionary];
                if (!pso) { rr[@"status"] = @"pipeline_rejected"; result = rr; }
                else {
                    MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatR32Uint width:2 height:2 mipmapped:NO];
                    td.usage = MTLTextureUsageShaderRead; td.storageMode = MTLStorageModeShared;
                    id<MTLTexture> t = [dev newTextureWithDescriptor:td];
                    MTLSamplerDescriptor *sd = [MTLSamplerDescriptor new];
                    sd.minFilter = MTLSamplerMinMagFilterLinear; sd.magFilter = MTLSamplerMinMagFilterLinear;
                    id<MTLSamplerState> smp = nil;
                    @try { smp = [dev newSamplerStateWithDescriptor:sd]; } @catch (NSException *e) { rr[@"sampler_exception"] = e.reason ?: @""; }
                    if (!smp) { rr[@"status"] = @"sampler_rejected"; }
                    else { result = dispatchOne(dev, pso, t, smp, nil, 4); }
                    if (!result) result = rr;
                }
            } else if ([cs isEqualToString:@"bc1_white_opaque"]) {
                result = runBC1Decode(dev, lib, 0xFFFF, 0x0000, 0x00000000);
            } else if ([cs isEqualToString:@"bc1_red565_opaque"]) {
                result = runBC1Decode(dev, lib, 0xF800, 0x0000, 0x00000000);
            } else if ([cs isEqualToString:@"split_depth_stencil"]) {
                result = runSplitDepthStencil(dev, lib);
            } else {
                result = @{@"status": @"unknown_case"};
            }
            [out addEntriesFromDictionary:result];
            emitAndExit(out);
        } else {
            out[@"status"] = @"unknown_mode";
            emitAndExit(out);
        }
    }
    return 0;
}
