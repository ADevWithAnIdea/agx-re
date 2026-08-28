// rasterprobe.m -- EXP-0123 graphics-pipeline probe (render, multi-attachment,
// texture-creation, buffer/bytes/alignment binding limits).
//
// AUTHORED BY US for this experiment. Compiles OUR OWN MSL at runtime
// (newLibraryWithSource:), drives the public MTLRenderPipelineState /
// MTLRenderCommandEncoder / MTLTexture / MTLBuffer API, and reads back only
// public NSError text and public MTLTexture/MTLBuffer contents. No Apple
// binary is introspected anywhere. Risky API calls (out-of-range indices,
// oversized descriptors) are wrapped in @try/@catch so a rejection is
// reported as structured JSON rather than crashing the harness -- an
// uncaught crash (no JSON emitted) is itself a valid recorded outcome,
// classified by the calling run.py from the subprocess exit status.
//
// Invocation: rasterprobe CASE.json
// Output: exactly one line of JSON to stdout (the result record). All
// diagnostic chatter goes to stderr only.
//
// Build:
//   clang -fobjc-arc -framework Metal -framework Foundation -O1 -o rasterprobe rasterprobe.m

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

static NSMutableDictionary *gResult;

static void setStatus(NSString *s) { gResult[@"status"] = s; }
static void setError(NSString *e) { if (e) gResult[@"error"] = e; }
static void setErrFromNSError(NSError *err) {
    if (err) {
        NSString *flat = [[err localizedDescription] stringByReplacingOccurrencesOfString:@"\n" withString:@" | "];
        gResult[@"error"] = flat;
    }
}

static void emitAndExit(int code) {
    NSError *jerr = nil;
    NSData *d = [NSJSONSerialization dataWithJSONObject:gResult options:0 error:&jerr];
    if (!d) {
        fprintf(stdout, "{\"status\":\"HARNESS_JSON_FAIL\",\"error\":\"%s\"}\n",
                [[jerr localizedDescription] UTF8String]);
    } else {
        fwrite([d bytes], 1, [d length], stdout);
        fprintf(stdout, "\n");
    }
    fflush(stdout);
    exit(code);
}

static id<MTLLibrary> compileLib(id<MTLDevice> dev, NSString *path, BOOL *ok) {
    NSError *err = nil;
    NSString *src = [NSString stringWithContentsOfFile:path encoding:NSUTF8StringEncoding error:&err];
    if (!src) { setStatus(@"COMPILE_FAIL"); setErrFromNSError(err); *ok = NO; return nil; }
    MTLCompileOptions *co = [MTLCompileOptions new];
    id<MTLLibrary> lib = [dev newLibraryWithSource:src options:co error:&err];
    if (!lib) { setStatus(@"COMPILE_FAIL"); setErrFromNSError(err); *ok = NO; return nil; }
    *ok = YES;
    return lib;
}

static NSArray *readTexturePixelsF32(id<MTLTexture> tex, NSUInteger x0, NSUInteger y0, NSUInteger w, NSUInteger h, NSUInteger slice) {
    NSMutableArray *out = [NSMutableArray array];
    float *px = (float *)malloc(sizeof(float) * 4 * w * h);
    memset(px, 0, sizeof(float) * 4 * w * h);
    MTLRegion region = MTLRegionMake2D(x0, y0, w, h);
    @try {
        [tex getBytes:px bytesPerRow:(NSUInteger)(w * 4 * sizeof(float))
           bytesPerImage:(NSUInteger)(w * h * 4 * sizeof(float))
              fromRegion:region mipmapLevel:0 slice:slice];
    } @catch (NSException *ex) {
        free(px);
        return @[@{@"exception": [ex reason] ?: @"?"}];
    }
    for (NSUInteger yy = 0; yy < h; yy++) {
        for (NSUInteger xx = 0; xx < w; xx++) {
            float *p = px + (yy * w + xx) * 4;
            [out addObject:@{@"x": @(x0 + xx), @"y": @(y0 + yy),
                              @"r": @(p[0]), @"g": @(p[1]), @"b": @(p[2]), @"a": @(p[3])}];
        }
    }
    free(px);
    return out;
}

static MTLPrimitiveType topologyFromString(NSString *t, MTLPrimitiveTopologyClass *cls) {
    if ([t isEqualToString:@"point"]) { *cls = MTLPrimitiveTopologyClassPoint; return MTLPrimitiveTypePoint; }
    if ([t isEqualToString:@"line"]) { *cls = MTLPrimitiveTopologyClassLine; return MTLPrimitiveTypeLine; }
    if ([t isEqualToString:@"line_strip"]) { *cls = MTLPrimitiveTopologyClassLine; return MTLPrimitiveTypeLineStrip; }
    if ([t isEqualToString:@"triangle_strip"]) { *cls = MTLPrimitiveTopologyClassTriangle; return MTLPrimitiveTypeTriangleStrip; }
    *cls = MTLPrimitiveTopologyClassTriangle; return MTLPrimitiveTypeTriangle;
}

static MTLCompareFunction cmpFromString(NSString *s) {
    if ([s isEqualToString:@"always"]) return MTLCompareFunctionAlways;
    if ([s isEqualToString:@"never"]) return MTLCompareFunctionNever;
    if ([s isEqualToString:@"less"]) return MTLCompareFunctionLess;
    if ([s isEqualToString:@"lequal"]) return MTLCompareFunctionLessEqual;
    if ([s isEqualToString:@"greater"]) return MTLCompareFunctionGreater;
    if ([s isEqualToString:@"gequal"]) return MTLCompareFunctionGreaterEqual;
    if ([s isEqualToString:@"equal"]) return MTLCompareFunctionEqual;
    return MTLCompareFunctionAlways;
}

// ---------------------------------------------------------------- op:render
static void opRender(NSDictionary *c, id<MTLDevice> dev) {
    NSString *src = c[@"metal_source"];
    BOOL ok;
    id<MTLLibrary> lib = compileLib(dev, src, &ok);
    if (!ok) { emitAndExit(1); }
    id<MTLFunction> vf = [lib newFunctionWithName:c[@"vertex_fn"]];
    id<MTLFunction> ff = [lib newFunctionWithName:c[@"fragment_fn"]];
    if (!vf || !ff) { setStatus(@"FUNCTION_MISSING"); emitAndExit(1); }

    NSUInteger W = [c[@"width"] unsignedIntegerValue];
    NSUInteger H = [c[@"height"] unsignedIntegerValue];
    NSUInteger layers = [c[@"layers"] unsignedIntegerValue];
    NSUInteger sampleCount = c[@"sample_count"] ? [c[@"sample_count"] unsignedIntegerValue] : 1;
    BOOL wantDepth = [c[@"want_depth"] boolValue];
    BOOL wantOcclusion = [c[@"want_occlusion"] boolValue];
    BOOL alphaToCoverage = [c[@"alpha_to_coverage"] boolValue];
    NSString *fillMode = c[@"fill_mode"] ?: @"fill";
    NSString *depthClipMode = c[@"depth_clip_mode"];

    MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
    pd.vertexFunction = vf;
    pd.fragmentFunction = ff;
    pd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA32Float;
    if (alphaToCoverage) pd.alphaToCoverageEnabled = YES;
    MTLPrimitiveTopologyClass cls;
    MTLPrimitiveType ptype = topologyFromString(c[@"topology"] ?: @"triangle", &cls);
    pd.inputPrimitiveTopology = cls;
    pd.rasterSampleCount = sampleCount;
    if (wantDepth) pd.depthAttachmentPixelFormat = MTLPixelFormatDepth32Float;

    NSError *err = nil;
    id<MTLRenderPipelineState> pso = nil;
    @try {
        pso = [dev newRenderPipelineStateWithDescriptor:pd error:&err];
    } @catch (NSException *ex) {
        setStatus(@"EXCEPTION"); setError([NSString stringWithFormat:@"pso create: %@", [ex reason]]);
        emitAndExit(1);
    }
    if (!pso) { setStatus(@"PIPELINE_FAIL"); setErrFromNSError(err); emitAndExit(1); }

    id<MTLCommandQueue> queue = [dev newCommandQueue];
    MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor new];

    MTLTextureDescriptor *td = [MTLTextureDescriptor new];
    td.textureType = layers > 0 ? MTLTextureType2DArray : MTLTextureType2D;
    td.pixelFormat = MTLPixelFormatRGBA32Float;
    td.width = W; td.height = H; td.arrayLength = layers > 0 ? layers : 1;
    td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
    td.storageMode = MTLStorageModeShared;
    td.sampleCount = 1;
    id<MTLTexture> colorMS = nil;
    id<MTLTexture> target = [dev newTextureWithDescriptor:td];
    if (!target) { setStatus(@"TEXTURE_NIL"); emitAndExit(1); }
    if (layers > 0) rp.renderTargetArrayLength = layers;

    if (sampleCount > 1) {
        MTLTextureDescriptor *msd = [MTLTextureDescriptor new];
        msd.textureType = MTLTextureType2DMultisample;
        msd.pixelFormat = MTLPixelFormatRGBA32Float;
        msd.width = W; msd.height = H; msd.sampleCount = sampleCount;
        msd.usage = MTLTextureUsageRenderTarget;
        msd.storageMode = MTLStorageModeShared;
        colorMS = [dev newTextureWithDescriptor:msd];
        rp.colorAttachments[0].texture = colorMS;
        rp.colorAttachments[0].resolveTexture = target;
        rp.colorAttachments[0].storeAction = MTLStoreActionMultisampleResolve;
    } else {
        rp.colorAttachments[0].texture = target;
        rp.colorAttachments[0].storeAction = MTLStoreActionStore;
    }
    NSArray *cc = c[@"clear_color"];
    double cr = cc ? [cc[0] doubleValue] : -1, cg = cc ? [cc[1] doubleValue] : -1;
    double cblu = cc ? [cc[2] doubleValue] : -1, ca = cc ? [cc[3] doubleValue] : -1;
    rp.colorAttachments[0].loadAction = MTLLoadActionClear;
    rp.colorAttachments[0].clearColor = MTLClearColorMake(cr, cg, cblu, ca);

    id<MTLTexture> depthTex = nil;
    if (wantDepth) {
        MTLTextureDescriptor *dd = [MTLTextureDescriptor new];
        dd.textureType = sampleCount > 1 ? MTLTextureType2DMultisample : MTLTextureType2D;
        dd.pixelFormat = MTLPixelFormatDepth32Float;
        dd.width = W; dd.height = H; dd.sampleCount = sampleCount;
        dd.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
        dd.storageMode = MTLStorageModeShared;
        depthTex = [dev newTextureWithDescriptor:dd];
        rp.depthAttachment.texture = depthTex;
        rp.depthAttachment.loadAction = MTLLoadActionClear;
        rp.depthAttachment.clearDepth = c[@"depth_clear"] ? [c[@"depth_clear"] doubleValue] : 0.5;
        rp.depthAttachment.storeAction = MTLStoreActionStore;
    }

    id<MTLBuffer> visBuf = nil;
    if (wantOcclusion) {
        visBuf = [dev newBufferWithLength:8 options:MTLResourceStorageModeShared];
        memset([visBuf contents], 0, 8);
        rp.visibilityResultBuffer = visBuf;
    }

    id<MTLCommandBuffer> cb = [queue commandBuffer];
    id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
    [enc setRenderPipelineState:pso];
    [enc setTriangleFillMode:([fillMode isEqualToString:@"lines"] ? MTLTriangleFillModeLines : MTLTriangleFillModeFill)];
    if (depthClipMode) {
        @try {
            [enc setDepthClipMode:([depthClipMode isEqualToString:@"clamp"] ? MTLDepthClipModeClamp : MTLDepthClipModeClip)];
        } @catch (NSException *ex) {
            gResult[@"depth_clip_mode_exception"] = [ex reason] ?: @"?";
        }
    }
    if (wantDepth) {
        MTLDepthStencilDescriptor *dsd = [MTLDepthStencilDescriptor new];
        dsd.depthCompareFunction = cmpFromString(c[@"depth_compare"] ?: @"always");
        dsd.depthWriteEnabled = c[@"depth_write"] ? [c[@"depth_write"] boolValue] : YES;
        id<MTLDepthStencilState> dss = [dev newDepthStencilStateWithDescriptor:dsd];
        [enc setDepthStencilState:dss];
    }
    if (wantOcclusion) [enc setVisibilityResultMode:MTLVisibilityResultModeCounting offset:0];

    NSInteger viewportCount = c[@"viewport_count"] ? [c[@"viewport_count"] integerValue] : 0;
    NSString *viewportExc = nil;
    if (viewportCount > 0) {
        MTLViewport *vps = (MTLViewport *)malloc(sizeof(MTLViewport) * (size_t)viewportCount);
        double stripW = (double)W / (double)viewportCount;
        double znear = c[@"viewport_znear"] ? [c[@"viewport_znear"] doubleValue] : 0.0;
        double zfar = c[@"viewport_zfar"] ? [c[@"viewport_zfar"] doubleValue] : 1.0;
        for (NSInteger i = 0; i < viewportCount; i++) {
            vps[i] = (MTLViewport){ .originX = i * stripW, .originY = 0, .width = stripW, .height = (double)H,
                                     .znear = znear, .zfar = zfar };
        }
        @try {
            [enc setViewports:vps count:(NSUInteger)viewportCount];
        } @catch (NSException *ex) {
            viewportExc = [ex reason] ?: @"?";
        }
        free(vps);
    } else if (c[@"viewport_znear"] || c[@"viewport_zfar"]) {
        double znear = c[@"viewport_znear"] ? [c[@"viewport_znear"] doubleValue] : 0.0;
        double zfar = c[@"viewport_zfar"] ? [c[@"viewport_zfar"] doubleValue] : 1.0;
        MTLViewport vp = { 0, 0, (double)W, (double)H, znear, zfar };
        @try { [enc setViewport:vp]; } @catch (NSException *ex) { viewportExc = [ex reason] ?: @"?"; }
    }
    if (viewportExc) gResult[@"viewport_exception"] = viewportExc;

    NSUInteger vcount = [c[@"vcount"] unsignedIntegerValue];
    NSUInteger instanceCount = c[@"instance_count"] ? [c[@"instance_count"] unsignedIntegerValue] : 1;
    if (vcount > 0) {
        @try {
            if (instanceCount > 1)
                [enc drawPrimitives:ptype vertexStart:0 vertexCount:vcount instanceCount:instanceCount];
            else
                [enc drawPrimitives:ptype vertexStart:0 vertexCount:vcount];
        } @catch (NSException *ex) {
            gResult[@"draw_exception"] = [ex reason] ?: @"?";
        }
    }
    [enc endEncoding];
    [cb commit];
    [cb waitUntilCompleted];
    if ([cb status] == MTLCommandBufferStatusError) {
        setStatus(@"CMDBUF_ERROR");
        setErrFromNSError([cb error]);
        emitAndExit(1);
    }
    gResult[@"gputime_ns"] = @((unsigned long long)(([cb GPUEndTime] - [cb GPUStartTime]) * 1e9));

    NSString *readback = c[@"readback"] ?: @"grid";
    if ([readback isEqualToString:@"point"]) {
        float *px = (float *)malloc(sizeof(float) * 4 * W * H);
        [target getBytes:px bytesPerRow:(NSUInteger)(W * 4 * sizeof(float))
              fromRegion:MTLRegionMake2D(0, 0, W, H) mipmapLevel:0];
        long xmin = W, ymin = H, xmax = -1, ymax = -1, count = 0;
        for (NSUInteger y = 0; y < H; y++) {
            for (NSUInteger x = 0; x < W; x++) {
                float *p = px + (y * W + x) * 4;
                BOOL isClear = (p[0] == (float)cr && p[1] == (float)cg && p[2] == (float)cblu && p[3] == (float)ca);
                if (!isClear) {
                    count++;
                    if ((long)x < xmin) xmin = x; if ((long)x > xmax) xmax = x;
                    if ((long)y < ymin) ymin = y; if ((long)y > ymax) ymax = y;
                }
            }
        }
        gResult[@"bbox"] = @{@"xmin": @(xmin), @"ymin": @(ymin), @"xmax": @(xmax), @"ymax": @(ymax),
                              @"count": @(count), @"total": @(W * H)};
        free(px);
    } else if ([readback isEqualToString:@"corner"]) {
        NSDictionary *corner = c[@"corner"];
        NSUInteger cx = [corner[@"x"] unsignedIntegerValue], cy = [corner[@"y"] unsignedIntegerValue];
        NSUInteger cw = [corner[@"w"] unsignedIntegerValue], ch = [corner[@"h"] unsignedIntegerValue];
        gResult[@"pixels"] = readTexturePixelsF32(target, cx, cy, cw, ch, 0);
    } else if ([readback isEqualToString:@"corners"]) {
        NSArray *corners = c[@"corners"];
        NSMutableArray *allPix = [NSMutableArray array];
        for (NSDictionary *corner in corners) {
            NSUInteger cx = [corner[@"x"] unsignedIntegerValue], cy = [corner[@"y"] unsignedIntegerValue];
            NSUInteger cw = [corner[@"w"] unsignedIntegerValue], ch = [corner[@"h"] unsignedIntegerValue];
            [allPix addObjectsFromArray:readTexturePixelsF32(target, cx, cy, cw, ch, 0)];
        }
        gResult[@"pixels"] = allPix;
    } else if ([readback isEqualToString:@"layers"]) {
        NSMutableArray *lp = [NSMutableArray array];
        for (NSUInteger l = 0; l < layers; l++) {
            NSArray *one = readTexturePixelsF32(target, W / 2, H / 2, 1, 1, l);
            if (one.count == 1) {
                NSMutableDictionary *d = [one[0] mutableCopy];
                d[@"layer"] = @(l);
                [lp addObject:d];
            }
        }
        gResult[@"layer_pixels"] = lp;
    } else { // grid
        gResult[@"pixels"] = readTexturePixelsF32(target, 0, 0, W, H, 0);
    }

    if (wantDepth) {
        NSDictionary *corner = c[@"corner"];
        if ([readback isEqualToString:@"corner"] && corner) {
            NSUInteger cx = [corner[@"x"] unsignedIntegerValue], cy = [corner[@"y"] unsignedIntegerValue];
            NSUInteger cw = [corner[@"w"] unsignedIntegerValue], ch = [corner[@"h"] unsignedIntegerValue];
            float *dpx = (float *)malloc(sizeof(float) * cw * ch);
            @try {
                [depthTex getBytes:dpx bytesPerRow:(NSUInteger)(cw * sizeof(float))
                         fromRegion:MTLRegionMake2D(cx, cy, cw, ch) mipmapLevel:0];
                NSMutableArray *dout = [NSMutableArray array];
                for (NSUInteger i = 0; i < cw * ch; i++) [dout addObject:@(dpx[i])];
                gResult[@"depth_pixels"] = dout;
            } @catch (NSException *ex) { gResult[@"depth_readback_exception"] = [ex reason] ?: @"?"; }
            free(dpx);
        } else {
            float *dpx = (float *)malloc(sizeof(float) * W * H);
            @try {
                [depthTex getBytes:dpx bytesPerRow:(NSUInteger)(W * sizeof(float))
                         fromRegion:MTLRegionMake2D(0, 0, W, H) mipmapLevel:0];
                NSMutableArray *dout = [NSMutableArray array];
                for (NSUInteger i = 0; i < W * H; i++) [dout addObject:@(dpx[i])];
                gResult[@"depth_pixels"] = dout;
            } @catch (NSException *ex) { gResult[@"depth_readback_exception"] = [ex reason] ?: @"?"; }
            free(dpx);
        }
    }
    if (wantOcclusion) {
        uint64_t *vc = (uint64_t *)[visBuf contents];
        gResult[@"occlusion_count"] = @(vc[0]);
    }

    setStatus(@"OK");
    emitAndExit(0);
}

// ------------------------------------------------------------ op:multiattach
static void opMultiattach(NSDictionary *c, id<MTLDevice> dev) {
    NSInteger n = [c[@"n_attachments"] integerValue];
    NSString *src = c[@"metal_source"];
    NSUInteger W = [c[@"width"] unsignedIntegerValue], H = [c[@"height"] unsignedIntegerValue];
    BOOL ok;
    id<MTLLibrary> lib = compileLib(dev, src, &ok);
    if (!ok) emitAndExit(1);
    id<MTLFunction> vf = [lib newFunctionWithName:c[@"vertex_fn"]];
    id<MTLFunction> ff = [lib newFunctionWithName:c[@"fragment_fn"]];
    if (!vf || !ff) { setStatus(@"FUNCTION_MISSING"); emitAndExit(1); }

    MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
    pd.vertexFunction = vf;
    pd.fragmentFunction = ff;
    NSInteger buildCount = n > 8 ? 8 : n;
    for (NSInteger i = 0; i < buildCount; i++) pd.colorAttachments[i].pixelFormat = MTLPixelFormatRGBA32Float;

    if (n > 8) {
        // Attempt the out-of-range property access itself: this is the
        // construction of the "first invalid" case for the attachment-count
        // limit -- MTLRenderPipelineColorAttachmentDescriptorArray is a
        // fixed 8-slot array (indices 0..7).
        @try {
            MTLRenderPipelineColorAttachmentDescriptor *extra = pd.colorAttachments[(NSUInteger)(n - 1)];
            extra.pixelFormat = MTLPixelFormatRGBA32Float;
            gResult[@"oob_access_result"] = @"NO_EXCEPTION_UNEXPECTED";
        } @catch (NSException *ex) {
            gResult[@"oob_access_result"] = @"EXCEPTION";
            gResult[@"oob_access_reason"] = [ex reason] ?: @"?";
        }
        setStatus(@"OK");
        emitAndExit(0);
    }

    NSError *err = nil;
    id<MTLRenderPipelineState> pso = nil;
    @try { pso = [dev newRenderPipelineStateWithDescriptor:pd error:&err]; }
    @catch (NSException *ex) { setStatus(@"EXCEPTION"); setError([ex reason]); emitAndExit(1); }
    if (!pso) { setStatus(@"PIPELINE_FAIL"); setErrFromNSError(err); emitAndExit(1); }

    id<MTLCommandQueue> queue = [dev newCommandQueue];
    MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor new];
    NSMutableArray *textures = [NSMutableArray array];
    for (NSInteger i = 0; i < buildCount; i++) {
        MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float
                                                                                        width:W height:H mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
        td.storageMode = MTLStorageModeShared;
        id<MTLTexture> t = [dev newTextureWithDescriptor:td];
        [textures addObject:t];
        rp.colorAttachments[i].texture = t;
        rp.colorAttachments[i].loadAction = MTLLoadActionClear;
        rp.colorAttachments[i].clearColor = MTLClearColorMake(-1, -1, -1, -1);
        rp.colorAttachments[i].storeAction = MTLStoreActionStore;
    }
    id<MTLCommandBuffer> cb = [queue commandBuffer];
    id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
    [enc setRenderPipelineState:pso];
    [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
    [enc endEncoding];
    [cb commit];
    [cb waitUntilCompleted];
    if ([cb status] == MTLCommandBufferStatusError) { setStatus(@"CMDBUF_ERROR"); setErrFromNSError([cb error]); emitAndExit(1); }

    NSMutableArray *per = [NSMutableArray array];
    for (NSInteger i = 0; i < buildCount; i++) {
        NSArray *px = readTexturePixelsF32(textures[i], W / 2, H / 2, 1, 1, 0);
        [per addObject:@{@"attachment": @(i), @"pixel": px.count ? px[0] : @{}}];
    }
    gResult[@"per_attachment"] = per;
    setStatus(@"OK");
    emitAndExit(0);
}

// --------------------------------------------------------------- op:texcreate
static NSUInteger pixFmtBytesPerTexel(MTLPixelFormat f) {
    if (f == MTLPixelFormatRGBA32Float) return 16;
    if (f == MTLPixelFormatR8Unorm) return 1;
    return 4;
}

static void opTexcreate(NSDictionary *c, id<MTLDevice> dev) {
    NSString *type = c[@"texture_type"];
    NSString *fmtName = c[@"pixel_format"] ?: @"r8unorm";
    MTLPixelFormat fmt = [fmtName isEqualToString:@"rgba32float"] ? MTLPixelFormatRGBA32Float : MTLPixelFormatR8Unorm;
    NSUInteger W = [c[@"width"] unsignedIntegerValue];
    NSUInteger H = [c[@"height"] unsignedIntegerValue];
    NSUInteger D = c[@"depth"] ? [c[@"depth"] unsignedIntegerValue] : 1;
    NSUInteger mips = c[@"mip_level_count"] ? [c[@"mip_level_count"] unsignedIntegerValue] : 1;

    MTLTextureDescriptor *td = [MTLTextureDescriptor new];
    if ([type isEqualToString:@"3d"]) td.textureType = MTLTextureType3D;
    else if ([type isEqualToString:@"cube"]) td.textureType = MTLTextureTypeCube;
    else if ([type isEqualToString:@"2d_array"]) td.textureType = MTLTextureType2DArray;
    else td.textureType = MTLTextureType2D;
    td.pixelFormat = fmt;
    td.width = W; td.height = H;
    if ([type isEqualToString:@"3d"]) td.depth = D;
    if ([type isEqualToString:@"2d_array"]) td.arrayLength = D;
    td.mipmapLevelCount = mips;
    td.usage = MTLTextureUsageShaderRead | MTLTextureUsageRenderTarget;
    td.storageMode = MTLStorageModeShared;

    id<MTLTexture> tex = nil;
    @try {
        tex = [dev newTextureWithDescriptor:td];
    } @catch (NSException *ex) {
        gResult[@"create_status"] = @"EXCEPTION";
        gResult[@"create_error"] = [ex reason] ?: @"?";
        setStatus(@"OK");
        emitAndExit(0);
    }
    if (!tex) {
        gResult[@"create_status"] = @"NIL";
        setStatus(@"OK");
        emitAndExit(0);
    }
    gResult[@"create_status"] = @"OK";
    gResult[@"actual_width"] = @(tex.width);
    gResult[@"actual_height"] = @(tex.height);
    gResult[@"actual_depth"] = @(tex.depth);
    gResult[@"actual_array_length"] = @(tex.arrayLength);
    gResult[@"actual_mip_level_count"] = @(tex.mipmapLevelCount);
    gResult[@"bytes_per_texel"] = @(pixFmtBytesPerTexel(fmt));

    if ([c[@"do_render"] boolValue]) {
        NSString *src = c[@"metal_source"];
        BOOL ok;
        id<MTLLibrary> lib = compileLib(dev, src, &ok);
        if (!ok) emitAndExit(1);
        id<MTLFunction> vf = [lib newFunctionWithName:c[@"vertex_fn"]];
        id<MTLFunction> ff = [lib newFunctionWithName:c[@"fragment_fn"]];
        if (!vf || !ff) { setStatus(@"FUNCTION_MISSING"); emitAndExit(1); }
        MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
        pd.vertexFunction = vf; pd.fragmentFunction = ff;
        pd.colorAttachments[0].pixelFormat = fmt;
        NSError *err = nil;
        id<MTLRenderPipelineState> pso = nil;
        @try { pso = [dev newRenderPipelineStateWithDescriptor:pd error:&err]; }
        @catch (NSException *ex) { gResult[@"render_status"] = @"EXCEPTION"; gResult[@"render_error"] = [ex reason]; setStatus(@"OK"); emitAndExit(0); }
        if (!pso) { gResult[@"render_status"] = @"PIPELINE_FAIL"; gResult[@"render_error"] = [err localizedDescription]; setStatus(@"OK"); emitAndExit(0); }

        id<MTLCommandQueue> queue = [dev newCommandQueue];
        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor new];
        rp.colorAttachments[0].texture = tex;
        rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 0);
        rp.colorAttachments[0].storeAction = MTLStoreActionStore;
        if ([type isEqualToString:@"2d_array"]) rp.renderTargetArrayLength = D;
        id<MTLCommandBuffer> cb = [queue commandBuffer];
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];
        if ([cb status] == MTLCommandBufferStatusError) {
            gResult[@"render_status"] = @"CMDBUF_ERROR";
            setErrFromNSError([cb error]);
            setStatus(@"OK"); emitAndExit(0);
        }
        gResult[@"render_status"] = @"OK";
        NSArray *corners = c[@"corners"];
        NSMutableArray *allPix = [NSMutableArray array];
        for (NSDictionary *corner in corners) {
            NSUInteger cx = [corner[@"x"] unsignedIntegerValue], cy = [corner[@"y"] unsignedIntegerValue];
            NSUInteger cw = [corner[@"w"] unsignedIntegerValue], ch = [corner[@"h"] unsignedIntegerValue];
            if (fmt == MTLPixelFormatRGBA32Float) {
                [allPix addObjectsFromArray:readTexturePixelsF32(tex, cx, cy, cw, ch, 0)];
            } else {
                unsigned char *px = (unsigned char *)malloc(cw * ch);
                @try {
                    [tex getBytes:px bytesPerRow:cw fromRegion:MTLRegionMake2D(cx, cy, cw, ch) mipmapLevel:0];
                    for (NSUInteger i = 0; i < cw * ch; i++)
                        [allPix addObject:@{@"x": @(cx + i % cw), @"y": @(cy + i / cw), @"v8": @(px[i])}];
                } @catch (NSException *ex) { [allPix addObject:@{@"exception": [ex reason] ?: @"?"}]; }
                free(px);
            }
        }
        gResult[@"pixels"] = allPix;
    }
    setStatus(@"OK");
    emitAndExit(0);
}

// ---------------------------------------------------------- op:bufferindex
static void opBufferindex(NSDictionary *c, id<MTLDevice> dev) {
    NSString *src = c[@"metal_source"];
    NSString *stage = c[@"stage"];
    NSInteger index = [c[@"index"] integerValue];
    float value = [c[@"buffer_value"] floatValue];
    BOOL ok;
    id<MTLLibrary> lib = compileLib(dev, src, &ok);
    if (!ok) emitAndExit(1);
    id<MTLFunction> vf = [lib newFunctionWithName:c[@"vertex_fn"]];
    id<MTLFunction> ff = [lib newFunctionWithName:c[@"fragment_fn"]];
    if (!vf || !ff) { setStatus(@"FUNCTION_MISSING"); emitAndExit(1); }
    MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
    pd.vertexFunction = vf; pd.fragmentFunction = ff;
    pd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA32Float;
    NSError *err = nil;
    id<MTLRenderPipelineState> pso = nil;
    @try { pso = [dev newRenderPipelineStateWithDescriptor:pd error:&err]; }
    @catch (NSException *ex) { setStatus(@"EXCEPTION"); setError([ex reason]); emitAndExit(1); }
    if (!pso) { setStatus(@"PIPELINE_FAIL"); setErrFromNSError(err); emitAndExit(1); }

    NSUInteger W = 2, H = 2;
    id<MTLTexture> target;
    {
        MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float
                                                                                        width:W height:H mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget; td.storageMode = MTLStorageModeShared;
        target = [dev newTextureWithDescriptor:td];
    }
    id<MTLBuffer> buf = [dev newBufferWithLength:16 options:MTLResourceStorageModeShared];
    ((float *)[buf contents])[0] = value;
    ((float *)[buf contents])[1] = value;
    ((float *)[buf contents])[2] = value;
    ((float *)[buf contents])[3] = 1.0f;

    id<MTLCommandQueue> queue = [dev newCommandQueue];
    MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor new];
    rp.colorAttachments[0].texture = target;
    rp.colorAttachments[0].loadAction = MTLLoadActionClear;
    rp.colorAttachments[0].clearColor = MTLClearColorMake(-1, -1, -1, -1);
    rp.colorAttachments[0].storeAction = MTLStoreActionStore;
    id<MTLCommandBuffer> cb = [queue commandBuffer];
    id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
    [enc setRenderPipelineState:pso];
    NSString *bindExc = nil;
    @try {
        if ([stage isEqualToString:@"vertex"]) [enc setVertexBuffer:buf offset:0 atIndex:(NSUInteger)index];
        else [enc setFragmentBuffer:buf offset:0 atIndex:(NSUInteger)index];
    } @catch (NSException *ex) { bindExc = [ex reason] ?: @"?"; }
    if (bindExc) gResult[@"bind_exception"] = bindExc;
    @try { [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3]; }
    @catch (NSException *ex) { gResult[@"draw_exception"] = [ex reason] ?: @"?"; }
    [enc endEncoding];
    [cb commit];
    [cb waitUntilCompleted];
    if ([cb status] == MTLCommandBufferStatusError) { setStatus(@"CMDBUF_ERROR"); setErrFromNSError([cb error]); emitAndExit(1); }
    NSArray *px = readTexturePixelsF32(target, 0, 0, 1, 1, 0);
    gResult[@"pixel"] = px.count ? px[0] : @{};
    setStatus(@"OK");
    emitAndExit(0);
}

// ------------------------------------------------------------ op:bytesconst
static void opBytesconst(NSDictionary *c, id<MTLDevice> dev) {
    NSString *src = c[@"metal_source"];
    NSString *stage = c[@"stage"];
    NSUInteger length = [c[@"length"] unsignedIntegerValue];
    BOOL ok;
    id<MTLLibrary> lib = compileLib(dev, src, &ok);
    if (!ok) emitAndExit(1);
    id<MTLFunction> vf = [lib newFunctionWithName:c[@"vertex_fn"]];
    id<MTLFunction> ff = [lib newFunctionWithName:c[@"fragment_fn"]];
    if (!vf || !ff) { setStatus(@"FUNCTION_MISSING"); emitAndExit(1); }
    MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
    pd.vertexFunction = vf; pd.fragmentFunction = ff;
    pd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA32Float;
    NSError *err = nil;
    id<MTLRenderPipelineState> pso = nil;
    @try { pso = [dev newRenderPipelineStateWithDescriptor:pd error:&err]; }
    @catch (NSException *ex) { setStatus(@"EXCEPTION"); setError([ex reason]); emitAndExit(1); }
    if (!pso) { setStatus(@"PIPELINE_FAIL"); setErrFromNSError(err); emitAndExit(1); }

    unsigned char *blob = (unsigned char *)malloc(length > 0 ? length : 1);
    for (NSUInteger i = 0; i < length; i++) blob[i] = (unsigned char)(i & 0xFF);
    uint32_t checkIdx = length > 0 ? (uint32_t)(length - 1) : 0;

    NSUInteger W = 2, H = 2;
    MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float
                                                                                    width:W height:H mipmapped:NO];
    td.usage = MTLTextureUsageRenderTarget; td.storageMode = MTLStorageModeShared;
    id<MTLTexture> target = [dev newTextureWithDescriptor:td];

    id<MTLCommandQueue> queue = [dev newCommandQueue];
    MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor new];
    rp.colorAttachments[0].texture = target;
    rp.colorAttachments[0].loadAction = MTLLoadActionClear;
    rp.colorAttachments[0].clearColor = MTLClearColorMake(-1, -1, -1, -1);
    rp.colorAttachments[0].storeAction = MTLStoreActionStore;
    id<MTLCommandBuffer> cb = [queue commandBuffer];
    id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
    [enc setRenderPipelineState:pso];
    BOOL secondBuffer = c[@"second_buffer"] ? [c[@"second_buffer"] boolValue] : YES;
    NSString *bindExc = nil;
    @try {
        if ([stage isEqualToString:@"vertex"]) {
            [enc setVertexBytes:blob length:length atIndex:0];
            if (secondBuffer) [enc setVertexBytes:&checkIdx length:sizeof(checkIdx) atIndex:1];
        } else {
            [enc setFragmentBytes:blob length:length atIndex:0];
            if (secondBuffer) [enc setFragmentBytes:&checkIdx length:sizeof(checkIdx) atIndex:1];
        }
    } @catch (NSException *ex) { bindExc = [ex reason] ?: @"?"; }
    free(blob);
    gResult[@"check_index"] = @(checkIdx);
    gResult[@"second_buffer"] = @(secondBuffer);
    if (bindExc) gResult[@"bind_exception"] = bindExc;
    @try { [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3]; }
    @catch (NSException *ex) { gResult[@"draw_exception"] = [ex reason] ?: @"?"; }
    [enc endEncoding];
    [cb commit];
    [cb waitUntilCompleted];
    if ([cb status] == MTLCommandBufferStatusError) { setStatus(@"CMDBUF_ERROR"); setErrFromNSError([cb error]); emitAndExit(1); }
    NSArray *px = readTexturePixelsF32(target, 0, 0, 1, 1, 0);
    gResult[@"pixel"] = px.count ? px[0] : @{};
    setStatus(@"OK");
    emitAndExit(0);
}

// ----------------------------------------------------------- op:bufferalign
static void opBufferalign(NSDictionary *c, id<MTLDevice> dev) {
    NSString *src = c[@"metal_source"];
    NSUInteger offset = [c[@"offset"] unsignedIntegerValue];
    NSUInteger patternLen = 4096;
    BOOL ok;
    id<MTLLibrary> lib = compileLib(dev, src, &ok);
    if (!ok) emitAndExit(1);
    id<MTLFunction> vf = [lib newFunctionWithName:c[@"vertex_fn"]];
    id<MTLFunction> ff = [lib newFunctionWithName:c[@"fragment_fn"]];
    if (!vf || !ff) { setStatus(@"FUNCTION_MISSING"); emitAndExit(1); }
    MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
    pd.vertexFunction = vf; pd.fragmentFunction = ff;
    pd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA32Float;
    NSError *err = nil;
    id<MTLRenderPipelineState> pso = nil;
    @try { pso = [dev newRenderPipelineStateWithDescriptor:pd error:&err]; }
    @catch (NSException *ex) { setStatus(@"EXCEPTION"); setError([ex reason]); emitAndExit(1); }
    if (!pso) { setStatus(@"PIPELINE_FAIL"); setErrFromNSError(err); emitAndExit(1); }

    id<MTLBuffer> buf = [dev newBufferWithLength:patternLen + 256 options:MTLResourceStorageModeShared];
    unsigned char *bp = (unsigned char *)[buf contents];
    for (NSUInteger i = 0; i < patternLen + 256; i++) bp[i] = (unsigned char)((i * 37 + 11) & 0xFF);

    NSUInteger W = 2, H = 2;
    MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float
                                                                                    width:W height:H mipmapped:NO];
    td.usage = MTLTextureUsageRenderTarget; td.storageMode = MTLStorageModeShared;
    id<MTLTexture> target = [dev newTextureWithDescriptor:td];

    id<MTLCommandQueue> queue = [dev newCommandQueue];
    MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor new];
    rp.colorAttachments[0].texture = target;
    rp.colorAttachments[0].loadAction = MTLLoadActionClear;
    rp.colorAttachments[0].clearColor = MTLClearColorMake(-1, -1, -1, -1);
    rp.colorAttachments[0].storeAction = MTLStoreActionStore;
    id<MTLCommandBuffer> cb = [queue commandBuffer];
    id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
    [enc setRenderPipelineState:pso];
    NSString *bindExc = nil;
    @try { [enc setFragmentBuffer:buf offset:offset atIndex:0]; }
    @catch (NSException *ex) { bindExc = [ex reason] ?: @"?"; }
    if (bindExc) gResult[@"bind_exception"] = bindExc;
    @try { [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3]; }
    @catch (NSException *ex) { gResult[@"draw_exception"] = [ex reason] ?: @"?"; }
    [enc endEncoding];
    [cb commit];
    [cb waitUntilCompleted];
    if ([cb status] == MTLCommandBufferStatusError) { setStatus(@"CMDBUF_ERROR"); setErrFromNSError([cb error]); emitAndExit(1); }
    NSArray *px = readTexturePixelsF32(target, 0, 0, 1, 1, 0);
    gResult[@"pixel"] = px.count ? px[0] : @{};
    // Expected value at this offset is computed host-side in Python from the
    // same `(i*37+11)&0xFF` pattern formula -- not duplicated here.
    setStatus(@"OK");
    emitAndExit(0);
}

// ------------------------------------------------------------ op:texturebind
static void opTexturebind(NSDictionary *c, id<MTLDevice> dev) {
    NSString *src = c[@"metal_source"];
    NSInteger index = [c[@"index"] integerValue];
    BOOL ok;
    id<MTLLibrary> lib = compileLib(dev, src, &ok);
    if (!ok) emitAndExit(1);
    id<MTLFunction> vf = [lib newFunctionWithName:c[@"vertex_fn"]];
    id<MTLFunction> ff = [lib newFunctionWithName:c[@"fragment_fn"]];
    if (!vf || !ff) { setStatus(@"FUNCTION_MISSING"); emitAndExit(1); }
    MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
    pd.vertexFunction = vf; pd.fragmentFunction = ff;
    pd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA32Float;
    NSError *err = nil;
    id<MTLRenderPipelineState> pso = nil;
    @try { pso = [dev newRenderPipelineStateWithDescriptor:pd error:&err]; }
    @catch (NSException *ex) { setStatus(@"EXCEPTION"); setError([ex reason]); emitAndExit(1); }
    if (!pso) { setStatus(@"PIPELINE_FAIL"); setErrFromNSError(err); emitAndExit(1); }

    MTLTextureDescriptor *std_ = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float
                                                                                      width:1 height:1 mipmapped:NO];
    std_.usage = MTLTextureUsageShaderRead; std_.storageMode = MTLStorageModeShared;
    id<MTLTexture> srcTex = [dev newTextureWithDescriptor:std_];
    float texel[4] = {0.25f, 0.5f, 0.75f, 1.0f};
    [srcTex replaceRegion:MTLRegionMake2D(0, 0, 1, 1) mipmapLevel:0 withBytes:texel bytesPerRow:16];

    NSUInteger W = 2, H = 2;
    MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float
                                                                                    width:W height:H mipmapped:NO];
    td.usage = MTLTextureUsageRenderTarget; td.storageMode = MTLStorageModeShared;
    id<MTLTexture> target = [dev newTextureWithDescriptor:td];

    id<MTLCommandQueue> queue = [dev newCommandQueue];
    MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor new];
    rp.colorAttachments[0].texture = target;
    rp.colorAttachments[0].loadAction = MTLLoadActionClear;
    rp.colorAttachments[0].clearColor = MTLClearColorMake(-1, -1, -1, -1);
    rp.colorAttachments[0].storeAction = MTLStoreActionStore;
    id<MTLCommandBuffer> cb = [queue commandBuffer];
    id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
    [enc setRenderPipelineState:pso];
    NSString *bindExc = nil;
    @try { [enc setFragmentTexture:srcTex atIndex:(NSUInteger)index]; }
    @catch (NSException *ex) { bindExc = [ex reason] ?: @"?"; }
    if (bindExc) gResult[@"bind_exception"] = bindExc;
    @try { [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3]; }
    @catch (NSException *ex) { gResult[@"draw_exception"] = [ex reason] ?: @"?"; }
    [enc endEncoding];
    [cb commit];
    [cb waitUntilCompleted];
    if ([cb status] == MTLCommandBufferStatusError) { setStatus(@"CMDBUF_ERROR"); setErrFromNSError([cb error]); emitAndExit(1); }
    NSArray *px = readTexturePixelsF32(target, 0, 0, 1, 1, 0);
    gResult[@"pixel"] = px.count ? px[0] : @{};
    setStatus(@"OK");
    emitAndExit(0);
}

int main(int argc, char *argv[]) {
    @autoreleasepool {
        gResult = [NSMutableDictionary dictionary];
        if (argc < 2) { fprintf(stderr, "usage: rasterprobe CASE.json\n"); return 2; }
        NSString *casePath = [NSString stringWithUTF8String:argv[1]];
        NSData *cd = [NSData dataWithContentsOfFile:casePath];
        if (!cd) { fprintf(stderr, "cannot read %s\n", argv[1]); return 2; }
        NSError *jerr = nil;
        NSDictionary *c = [NSJSONSerialization JSONObjectWithData:cd options:0 error:&jerr];
        if (!c) { fprintf(stderr, "bad json: %s\n", [[jerr localizedDescription] UTF8String]); return 2; }
        gResult[@"op"] = c[@"op"] ?: @"?";
        gResult[@"case_id"] = c[@"case_id"] ?: @"?";

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) { setStatus(@"NO_DEVICE"); emitAndExit(1); }

        NSString *op = c[@"op"];
        if ([op isEqualToString:@"render"]) opRender(c, dev);
        else if ([op isEqualToString:@"multiattach"]) opMultiattach(c, dev);
        else if ([op isEqualToString:@"texcreate"]) opTexcreate(c, dev);
        else if ([op isEqualToString:@"bufferindex"]) opBufferindex(c, dev);
        else if ([op isEqualToString:@"bytesconst"]) opBytesconst(c, dev);
        else if ([op isEqualToString:@"bufferalign"]) opBufferalign(c, dev);
        else if ([op isEqualToString:@"texturebind"]) opTexturebind(c, dev);
        else { setStatus(@"UNKNOWN_OP"); emitAndExit(2); }
    }
    return 0;
}
