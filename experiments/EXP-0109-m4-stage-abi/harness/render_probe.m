// render_probe.m — EXP-0109 HW-PROBE render harness (OWN-SHADER + HW-PROBE).
//
// Compiles OUR OWN MSL (kernels/mrt_interp.metal) through the public Metal
// runtime, issues real draws on the real device, and reads back real
// results (device-buffer contents, color/depth/stencil texture bytes) with
// no splicing — pure API-level black-box observation of OUR OWN compiled
// shaders. One process per invocation, one mode per invocation, prints a
// single JSON object to stdout on success (or {"status":"FAIL","error":...}
// on any Metal-reported failure) and exits nonzero only on a USAGE error.
//
// CLEAN-ROOM: public Metal API only, on our own MSL source. Never
// disassembles or introspects any Apple binary.
//
// Build: clang -fobjc-arc -framework Metal -framework Foundation \
//          -o render_probe render_probe.m
// Modes: vsfetch | frontfacing | mrt | dualsource | depth | stencil

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

static void usageDie(const char *m) {
    fprintf(stderr, "render_probe: %s\n", m);
    exit(1);
}
static void jfail(NSString *stage, NSError *err) {
    printf("{\"status\":\"FAIL\",\"stage\":\"%s\",\"error\":\"%s\"}\n",
           [stage UTF8String],
           err ? [[[err localizedDescription] stringByReplacingOccurrencesOfString:@"\"" withString:@"'"] UTF8String] : "");
}

enum { O_SRC = 128, O_MODE, O_CASE, O_NATT, O_FMT, O_NVERT, O_NINST, O_BASEV, O_BASEI,
       O_VBUFN, O_OOBIDX, O_SVAL, O_DVAL, O_DFUNC, O_SFUNC };
static const struct option L[] = {
    {"source", required_argument, 0, O_SRC},
    {"mode",   required_argument, 0, O_MODE},
    {"case",   required_argument, 0, O_CASE},
    {"natt",   required_argument, 0, O_NATT},
    {"format", required_argument, 0, O_FMT},     // MTLVertexFormat raw value (vsfetch)
    {"nvert",  required_argument, 0, O_NVERT},   // vertex-buffer element count (vsfetch)
    {"ninst",  required_argument, 0, O_NINST},   // instanceCount (vsfetch)
    {"basev",  required_argument, 0, O_BASEV},   // baseVertex (vsfetch)
    {"basei",  required_argument, 0, O_BASEI},   // baseInstance (vsfetch)
    {"oobidx", required_argument, 0, O_OOBIDX},  // 1 = include one OOB index in index buffer (vsfetch)
    {"sval",   required_argument, 0, O_SVAL},    // stencil value to write (stencil)
    {"dval",   required_argument, 0, O_DVAL},    // depth value to write (depth), x1000 int
    {"dfunc",  required_argument, 0, O_DFUNC},   // depth fragment function name (depth)
    {"sfunc",  required_argument, 0, O_SFUNC},   // stencil-mode fragment function name (stencil)
    {0,0,0,0}
};

int main(int argc, char **argv) { @autoreleasepool {
    const char *srcp = 0, *mode = 0, *casename = "case";
    unsigned natt = 1, fmt = 9 /*UChar4Normalized*/, nvert = 8, ninst = 1;
    int basev = 0; unsigned basei = 0; int oobidx = 0;
    unsigned sval = 5; int dvalMilli = 250; const char *dfunc = "f_depth_any"; const char *sfunc = "f_stencil_out";
    int c;
    while ((c = getopt_long(argc, argv, "", L, 0)) > 0) {
        switch (c) {
            case O_SRC: srcp = optarg; break;
            case O_MODE: mode = optarg; break;
            case O_CASE: casename = optarg; break;
            case O_NATT: natt = (unsigned)strtoul(optarg,0,0); break;
            case O_FMT: fmt = (unsigned)strtoul(optarg,0,0); break;
            case O_NVERT: nvert = (unsigned)strtoul(optarg,0,0); break;
            case O_NINST: ninst = (unsigned)strtoul(optarg,0,0); break;
            case O_BASEV: basev = atoi(optarg); break;
            case O_BASEI: basei = (unsigned)strtoul(optarg,0,0); break;
            case O_OOBIDX: oobidx = atoi(optarg); break;
            case O_SVAL: sval = (unsigned)strtoul(optarg,0,0); break;
            case O_DVAL: dvalMilli = atoi(optarg); break;
            case O_DFUNC: dfunc = optarg; break;
            case O_SFUNC: sfunc = optarg; break;
        }
    }
    if (!srcp || !mode) usageDie("need --source and --mode");

    NSError *err = nil;
    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    if (!dev) usageDie("no device");
    id<MTLCommandQueue> q = [dev newCommandQueue];
    NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:srcp]
                                               encoding:NSUTF8StringEncoding error:&err];
    if (!src) usageDie("read src");
    MTLCompileOptions *co = [MTLCompileOptions new];
    id<MTLLibrary> lib = [dev newLibraryWithSource:src options:co error:&err];
    if (!lib) { jfail(@"compile", err); return 0; }

    NSString *m = [NSString stringWithUTF8String:mode];

    // ---------------------------------------------------------------- vsfetch
    if ([m isEqualToString:@"vsfetch"]) {
        id<MTLFunction> vf = [lib newFunctionWithName:@"v_fetch_probe"];
        if (!vf) { jfail(@"function", nil); return 0; }
        MTLVertexDescriptor *vd = [MTLVertexDescriptor new];
        vd.attributes[0].format = (MTLVertexFormat)fmt;
        vd.attributes[0].offset = 0;
        vd.attributes[0].bufferIndex = 0;
        vd.layouts[0].stride = 4; // tightly-packed 4-byte UChar4Normalized elements (see vertex-buffer fill below)
        vd.layouts[0].stepFunction = MTLVertexStepFunctionPerVertex;
        vd.layouts[0].stepRate = 1;

        MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new];
        rd.vertexFunction = vf;
        rd.vertexDescriptor = vd;
        rd.rasterizationEnabled = NO;
        id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:rd error:&err];
        if (!pso) { jfail(@"pipeline", err); return 0; }

        // Vertex buffer: nvert elements of 4 bytes each (uchar4), value[i] = (i,i,i,i) clipped to 255.
        NSUInteger vbufBytes = (NSUInteger)nvert * 4;
        id<MTLBuffer> vbuf = [dev newBufferWithLength:vbufBytes options:MTLResourceStorageModeShared];
        uint8_t *vp = (uint8_t *)vbuf.contents;
        for (unsigned i = 0; i < nvert; i++) { uint8_t v = (uint8_t)(i > 255 ? 255 : i); vp[i*4]=v; vp[i*4+1]=v; vp[i*4+2]=v; vp[i*4+3]=255; }

        // Index buffer: 0..nvert-1 in range, plus one OOB index (nvert+50) if requested.
        unsigned nidx = nvert + (oobidx ? 1 : 0);
        id<MTLBuffer> ibuf = [dev newBufferWithLength:(NSUInteger)nidx*4 options:MTLResourceStorageModeShared];
        uint32_t *ip = (uint32_t *)ibuf.contents;
        for (unsigned i = 0; i < nvert; i++) ip[i] = i;
        if (oobidx) ip[nvert] = nvert + 50;

        NSUInteger recCap = (NSUInteger)nidx * (ninst > 0 ? ninst : 1) + 4;
        id<MTLBuffer> outbuf = [dev newBufferWithLength:recCap * 32 options:MTLResourceStorageModeShared];
        memset(outbuf.contents, 0xAA, recCap * 32); // poison, so "untouched" is visible
        id<MTLBuffer> cnt = [dev newBufferWithLength:4 options:MTLResourceStorageModeShared];
        memset(cnt.contents, 0, 4);

        id<MTLCommandBuffer> cb = [q commandBuffer];
        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
        rp.renderTargetWidth = 1; rp.renderTargetHeight = 1; rp.defaultRasterSampleCount = 1;
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        [enc setVertexBuffer:vbuf offset:0 atIndex:0];
        [enc setVertexBuffer:outbuf offset:0 atIndex:1];
        [enc setVertexBuffer:cnt offset:0 atIndex:2];
        [enc drawIndexedPrimitives:MTLPrimitiveTypePoint indexCount:nidx
                          indexType:MTLIndexTypeUInt32 indexBuffer:ibuf indexBufferOffset:0
                      instanceCount:ninst baseVertex:basev baseInstance:basei];
        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];
        if (cb.error) { jfail(@"cmdbuf", cb.error); return 0; }

        uint32_t total = *(uint32_t *)cnt.contents;
        NSMutableString *recs = [NSMutableString string];
        float *fp = (float *)outbuf.contents;
        for (uint32_t i = 0; i < total; i++) {
            float *base = fp + i * 8; // FetchRecord = 4 floats attr + 4 uints = 8*4 bytes = 32B
            uint32_t *ubase = (uint32_t *)base;
            [recs appendFormat:@"%s{\"attr\":[%.6g,%.6g,%.6g,%.6g],\"vid\":%u,\"iid\":%u,\"bv\":%u,\"bi\":%u}",
                i ? "," : "", base[0], base[1], base[2], base[3], ubase[4], ubase[5], ubase[6], ubase[7]];
        }
        printf("{\"status\":\"OK\",\"mode\":\"vsfetch\",\"case\":\"%s\",\"nvert\":%u,\"ninst\":%u,"
               "\"nidx\":%u,\"oobidx\":%d,\"basev\":%d,\"basei\":%u,\"total_records\":%u,\"records\":[%s]}\n",
               casename, nvert, ninst, nidx, oobidx, basev, basei, total, [recs UTF8String]);
        return 0;
    }

    // ------------------------------------------------------------ frontfacing
    if ([m isEqualToString:@"frontfacing"]) {
        id<MTLFunction> vf = [lib newFunctionWithName:@"v_frontfacing"];
        id<MTLFunction> ff = [lib newFunctionWithName:@"f_frontfacing"];
        if (!vf || !ff) { jfail(@"function", nil); return 0; }
        const int W = 32, H = 32;
        MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:W height:H mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget; td.storageMode = MTLStorageModeShared;
        id<MTLTexture> tex = [dev newTextureWithDescriptor:td];

        MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new];
        rd.vertexFunction = vf; rd.fragmentFunction = ff;
        rd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA8Unorm;
        id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:rd error:&err];
        if (!pso) { jfail(@"pipeline", err); return 0; }

        id<MTLCommandBuffer> cb = [q commandBuffer];
        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
        rp.colorAttachments[0].texture = tex;
        rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].clearColor = MTLClearColorMake(0,0,0,1);
        rp.colorAttachments[0].storeAction = MTLStoreActionStore;
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        [enc setCullMode:MTLCullModeNone];
        [enc setFrontFacingWinding:MTLWindingCounterClockwise]; // Metal API default
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3 instanceCount:2];
        [enc endEncoding];
        [cb commit]; [cb waitUntilCompleted];
        if (cb.error) { jfail(@"cmdbuf", cb.error); return 0; }

        uint8_t px[4];
        // Sample the two disjoint triangle interiors.
        [tex getBytes:px bytesPerRow:4 fromRegion:MTLRegionMake2D(6,26,1,1) mipmapLevel:0]; // CCW triangle (instance 0)
        uint8_t ccw_r = px[0];
        [tex getBytes:px bytesPerRow:4 fromRegion:MTLRegionMake2D(19,26,1,1) mipmapLevel:0]; // CW triangle (instance 1)
        uint8_t cw_r = px[0];
        printf("{\"status\":\"OK\",\"mode\":\"frontfacing\",\"case\":\"%s\",\"ccw_red\":%u,\"cw_red\":%u}\n",
               casename, ccw_r, cw_r);
        return 0;
    }

    // -------------------------------------------------------------------- mrt
    if ([m isEqualToString:@"mrt"]) {
        NSString *fn = [NSString stringWithFormat:@"f_mrt%u", natt];
        id<MTLFunction> vf = [lib newFunctionWithName:@"v_common"];
        id<MTLFunction> ffn = [lib newFunctionWithName:fn];
        if (!vf || !ffn) { jfail(@"function", nil); return 0; }
        const int W = 8, H = 8;
        MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new];
        rd.vertexFunction = vf; rd.fragmentFunction = ffn;
        NSMutableArray *texs = [NSMutableArray array];
        for (unsigned i = 0; i < natt; i++) {
            rd.colorAttachments[i].pixelFormat = MTLPixelFormatRGBA16Float;
            MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA16Float width:W height:H mipmapped:NO];
            td.usage = MTLTextureUsageRenderTarget; td.storageMode = MTLStorageModeShared;
            [texs addObject:[dev newTextureWithDescriptor:td]];
        }
        id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:rd error:&err];
        if (!pso) { jfail(@"pipeline", err); return 0; }
        id<MTLCommandBuffer> cb = [q commandBuffer];
        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
        for (unsigned i = 0; i < natt; i++) {
            rp.colorAttachments[i].texture = texs[i];
            rp.colorAttachments[i].loadAction = MTLLoadActionClear;
            rp.colorAttachments[i].clearColor = MTLClearColorMake(0.123,0.123,0.123,0.123);
            rp.colorAttachments[i].storeAction = MTLStoreActionStore;
        }
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc endEncoding];
        [cb commit]; [cb waitUntilCompleted];
        if (cb.error) { jfail(@"cmdbuf", cb.error); return 0; }
        NSMutableString *out = [NSMutableString string];
        for (unsigned i = 0; i < natt; i++) {
            uint16_t px[4]; // half4
            [texs[i] getBytes:px bytesPerRow:8 fromRegion:MTLRegionMake2D(4,4,1,1) mipmapLevel:0];
            // report raw half bits; python analysis decodes.
            [out appendFormat:@"%s{\"att\":%u,\"half_bits\":[%u,%u,%u,%u]}", i?",":"", i, px[0],px[1],px[2],px[3]];
        }
        printf("{\"status\":\"OK\",\"mode\":\"mrt\",\"case\":\"%s\",\"natt\":%u,\"targets\":[%s]}\n",
               casename, natt, [out UTF8String]);
        return 0;
    }

    // ------------------------------------------------------------- dualsource
    if ([m isEqualToString:@"dualsource"]) {
        id<MTLFunction> vf = [lib newFunctionWithName:@"v_common"];
        id<MTLFunction> ffn = [lib newFunctionWithName:@"f_dualsource"];
        if (!vf || !ffn) { jfail(@"function", nil); return 0; }
        const int W = 8, H = 8;
        MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA16Float width:W height:H mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget; td.storageMode = MTLStorageModeShared;
        id<MTLTexture> tex = [dev newTextureWithDescriptor:td];
        MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new];
        rd.vertexFunction = vf; rd.fragmentFunction = ffn;
        rd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA16Float;
        rd.colorAttachments[0].blendingEnabled = YES;
        // out = 1*src1 + 0*dst  -- isolates the index(1) output as the sole contributor.
        rd.colorAttachments[0].sourceRGBBlendFactor = MTLBlendFactorSource1Color;
        rd.colorAttachments[0].destinationRGBBlendFactor = MTLBlendFactorZero;
        rd.colorAttachments[0].sourceAlphaBlendFactor = MTLBlendFactorSource1Alpha;
        rd.colorAttachments[0].destinationAlphaBlendFactor = MTLBlendFactorZero;
        id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:rd error:&err];
        if (!pso) { jfail(@"pipeline", err); return 0; }
        id<MTLCommandBuffer> cb = [q commandBuffer];
        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
        rp.colorAttachments[0].texture = tex;
        rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].clearColor = MTLClearColorMake(0.9,0.9,0.9,0.9);
        rp.colorAttachments[0].storeAction = MTLStoreActionStore;
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc endEncoding];
        [cb commit]; [cb waitUntilCompleted];
        if (cb.error) { jfail(@"cmdbuf", cb.error); return 0; }
        uint16_t px[4];
        [tex getBytes:px bytesPerRow:8 fromRegion:MTLRegionMake2D(4,4,1,1) mipmapLevel:0];
        printf("{\"status\":\"OK\",\"mode\":\"dualsource\",\"case\":\"%s\",\"half_bits\":[%u,%u,%u,%u]}\n",
               casename, px[0],px[1],px[2],px[3]);
        return 0;
    }

    // ------------------------------------------------------------------ depth
    if ([m isEqualToString:@"depth"]) {
        id<MTLFunction> vf = [lib newFunctionWithName:@"v_common"];
        id<MTLFunction> ffn = [lib newFunctionWithName:[NSString stringWithUTF8String:dfunc]];
        if (!vf || !ffn) { jfail(@"function", nil); return 0; }
        const int W = 8, H = 8;
        MTLTextureDescriptor *ctd = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA16Float width:W height:H mipmapped:NO];
        ctd.usage = MTLTextureUsageRenderTarget; ctd.storageMode = MTLStorageModeShared;
        id<MTLTexture> ctex = [dev newTextureWithDescriptor:ctd];
        MTLTextureDescriptor *dtd = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatDepth32Float width:W height:H mipmapped:NO];
        dtd.usage = MTLTextureUsageRenderTarget; dtd.storageMode = MTLStorageModePrivate;
        id<MTLTexture> dtex = [dev newTextureWithDescriptor:dtd];

        MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new];
        rd.vertexFunction = vf; rd.fragmentFunction = ffn;
        rd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA16Float;
        rd.depthAttachmentPixelFormat = MTLPixelFormatDepth32Float;
        id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:rd error:&err];
        if (!pso) { jfail(@"pipeline", err); return 0; }

        MTLDepthStencilDescriptor *dsd = [MTLDepthStencilDescriptor new];
        dsd.depthCompareFunction = MTLCompareFunctionAlways;
        dsd.depthWriteEnabled = YES;
        id<MTLDepthStencilState> dss = [dev newDepthStencilStateWithDescriptor:dsd];

        float dval = (float)dvalMilli / 1000.0f;
        id<MTLBuffer> dvalBuf = [dev newBufferWithBytes:&dval length:4 options:MTLResourceStorageModeShared];

        id<MTLCommandBuffer> cb = [q commandBuffer];
        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
        rp.colorAttachments[0].texture = ctex;
        rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].clearColor = MTLClearColorMake(0,0,0,0);
        rp.colorAttachments[0].storeAction = MTLStoreActionStore;
        rp.depthAttachment.texture = dtex;
        rp.depthAttachment.loadAction = MTLLoadActionClear;
        rp.depthAttachment.clearDepth = 0.111;
        rp.depthAttachment.storeAction = MTLStoreActionStore;
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        [enc setDepthStencilState:dss];
        [enc setFragmentBuffer:dvalBuf offset:0 atIndex:0];
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc endEncoding];

        id<MTLBuffer> readback = [dev newBufferWithLength:(NSUInteger)W*H*4 options:MTLResourceStorageModeShared];
        id<MTLBlitCommandEncoder> blit = [cb blitCommandEncoder];
        [blit copyFromTexture:dtex sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0)
                     sourceSize:MTLSizeMake(W,H,1) toBuffer:readback destinationOffset:0
                destinationBytesPerRow:W*4 destinationBytesPerImage:W*H*4];
        [blit endEncoding];
        [cb commit]; [cb waitUntilCompleted];
        if (cb.error) { jfail(@"cmdbuf", cb.error); return 0; }
        float *dp = (float *)readback.contents;
        float centerDepth = dp[4*W + 4]; // (4,4)
        float cornerDepth = dp[0*W + 0]; // (0,0) — outside the triangle, should be the clear value
        printf("{\"status\":\"OK\",\"mode\":\"depth\",\"case\":\"%s\",\"dfunc\":\"%s\",\"requested\":%.6f,"
               "\"center_depth\":%.6f,\"corner_depth\":%.6f}\n",
               casename, dfunc, dval, centerDepth, cornerDepth);
        return 0;
    }

    // ---------------------------------------------------------------- stencil
    if ([m isEqualToString:@"stencil"]) {
        id<MTLFunction> vf = [lib newFunctionWithName:@"v_common"];
        id<MTLFunction> ffn = [lib newFunctionWithName:[NSString stringWithUTF8String:sfunc]];
        if (!vf || !ffn) { jfail(@"function", nil); return 0; }
        const int W = 8, H = 8;
        MTLTextureDescriptor *ctd = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA16Float width:W height:H mipmapped:NO];
        ctd.usage = MTLTextureUsageRenderTarget; ctd.storageMode = MTLStorageModeShared;
        id<MTLTexture> ctex = [dev newTextureWithDescriptor:ctd];
        MTLTextureDescriptor *std_ = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatStencil8 width:W height:H mipmapped:NO];
        std_.usage = MTLTextureUsageRenderTarget; std_.storageMode = MTLStorageModePrivate;
        id<MTLTexture> stex = [dev newTextureWithDescriptor:std_];

        MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new];
        rd.vertexFunction = vf; rd.fragmentFunction = ffn;
        rd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA16Float;
        rd.stencilAttachmentPixelFormat = MTLPixelFormatStencil8;
        id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:rd error:&err];
        if (!pso) { jfail(@"pipeline", err); return 0; }

        MTLStencilDescriptor *sfd = [MTLStencilDescriptor new];
        sfd.stencilCompareFunction = MTLCompareFunctionAlways;
        sfd.depthStencilPassOperation = MTLStencilOperationReplace;
        MTLDepthStencilDescriptor *dsd = [MTLDepthStencilDescriptor new];
        dsd.frontFaceStencil = sfd; dsd.backFaceStencil = sfd;
        id<MTLDepthStencilState> dss = [dev newDepthStencilStateWithDescriptor:dsd];

        id<MTLBuffer> svalBuf = [dev newBufferWithBytes:&sval length:4 options:MTLResourceStorageModeShared];

        id<MTLCommandBuffer> cb = [q commandBuffer];
        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
        rp.colorAttachments[0].texture = ctex;
        rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].clearColor = MTLClearColorMake(0,0,0,0);
        rp.colorAttachments[0].storeAction = MTLStoreActionStore;
        rp.stencilAttachment.texture = stex;
        rp.stencilAttachment.loadAction = MTLLoadActionClear;
        rp.stencilAttachment.clearStencil = 77;
        rp.stencilAttachment.storeAction = MTLStoreActionStore;
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        [enc setDepthStencilState:dss];
        [enc setStencilReferenceValue:200]; // encode-time constant, deliberately DIFFERENT from sval
        [enc setFragmentBuffer:svalBuf offset:0 atIndex:0];
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc endEncoding];

        id<MTLBuffer> readback = [dev newBufferWithLength:(NSUInteger)W*H options:MTLResourceStorageModeShared];
        id<MTLBlitCommandEncoder> blit = [cb blitCommandEncoder];
        [blit copyFromTexture:stex sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0)
                     sourceSize:MTLSizeMake(W,H,1) toBuffer:readback destinationOffset:0
                destinationBytesPerRow:W destinationBytesPerImage:W*H];
        [blit endEncoding];
        [cb commit]; [cb waitUntilCompleted];
        if (cb.error) { jfail(@"cmdbuf", cb.error); return 0; }
        uint8_t *sp = (uint8_t *)readback.contents;
        uint8_t centerStencil = sp[4*W + 4];
        uint8_t cornerStencil = sp[0*W + 0];
        printf("{\"status\":\"OK\",\"mode\":\"stencil\",\"case\":\"%s\",\"sfunc\":\"%s\",\"requested_sval\":%u,"
               "\"encode_ref\":200,\"clear_value\":77,\"center_stencil\":%u,\"corner_stencil\":%u}\n",
               casename, sfunc, sval, centerStencil, cornerStencil);
        return 0;
    }

    usageDie("unknown --mode");
    return 1;
}}
