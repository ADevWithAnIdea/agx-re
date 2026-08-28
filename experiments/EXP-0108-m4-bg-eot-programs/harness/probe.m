/*
 * EXP-0108 render-pass matrix probe.
 *
 * Authored MSL only (generated inline below from the case config). Reads
 * one case's JSON config from argv[1], renders it, prints one JSON result
 * line to stdout, and (with --dump) triggers a wtrace.dylib SIGUSR1
 * snapshot of the process's registered IOKit resource-map BOs. This probe
 * inspects only: its own generated MSL, its own buffer-backed readback
 * bytes, and Metal API return values/errors. It does not read any BO
 * content itself -- that is the companion interposer's job, gated by its
 * own compile-time content-capture policy (see harness/wtrace.c).
 */
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static MTLPixelFormat fmt_from_name(NSString *s) {
    struct { const char *n; MTLPixelFormat f; } tbl[] = {
        {"RGBA8Unorm", MTLPixelFormatRGBA8Unorm},
        {"BGRA8Unorm", MTLPixelFormatBGRA8Unorm},
        {"RGBA8Unorm_sRGB", MTLPixelFormatRGBA8Unorm_sRGB},
        {"R32Float", MTLPixelFormatR32Float},
        {"R32Uint", MTLPixelFormatR32Uint},
        {"RGBA16Float", MTLPixelFormatRGBA16Float},
        {"R8Unorm", MTLPixelFormatR8Unorm},
        {"RG8Unorm", MTLPixelFormatRG8Unorm},
        {"Depth32Float", MTLPixelFormatDepth32Float},
        {"Stencil8", MTLPixelFormatStencil8},
        {"Depth32Float_Stencil8", MTLPixelFormatDepth32Float_Stencil8},
    };
    for (size_t i = 0; i < sizeof(tbl)/sizeof(tbl[0]); ++i)
        if ([s isEqualToString:@(tbl[i].n)]) return tbl[i].f;
    return MTLPixelFormatInvalid;
}

static MTLLoadAction load_from_name(NSString *s) {
    if ([s isEqualToString:@"Clear"]) return MTLLoadActionClear;
    if ([s isEqualToString:@"Load"]) return MTLLoadActionLoad;
    return MTLLoadActionDontCare;
}

static MTLStoreAction store_from_name(NSString *s) {
    if ([s isEqualToString:@"Store"]) return MTLStoreActionStore;
    if ([s isEqualToString:@"MultisampleResolve"]) return MTLStoreActionMultisampleResolve;
    if ([s isEqualToString:@"StoreAndMultisampleResolve"]) return MTLStoreActionStoreAndMultisampleResolve;
    return MTLStoreActionDontCare;
}

static NSString *elem_type_for_fmt(MTLPixelFormat f) {
    if (f == MTLPixelFormatR32Uint) return @"uint4";
    return @"float4";
}

int main(int argc, char **argv) {
    @autoreleasepool {
        if (argc < 3) { fprintf(stderr, "usage: probe <case.json> <result.json> [--dump]\n"); return 2; }
        int do_dump = (argc > 3 && !strcmp(argv[3], "--dump"));
        NSError *err = nil;
        NSData *cfgData = [NSData dataWithContentsOfFile:@(argv[1])];
        if (!cfgData) { fprintf(stderr, "CONFIG_READ_FAIL\n"); return 2; }
        NSDictionary *cfg = [NSJSONSerialization JSONObjectWithData:cfgData options:0 error:&err];
        if (!cfg) { fprintf(stderr, "CONFIG_PARSE_FAIL %s\n", [[err localizedDescription] UTF8String]); return 2; }

        NSMutableDictionary *result = [NSMutableDictionary dictionary];
        result[@"name"] = cfg[@"name"];

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) { fprintf(stderr, "NO_DEVICE\n"); return 3; }
        result[@"device"] = [dev name];

        NSInteger ncolor = [cfg[@"ncolor"] integerValue];
        NSArray *fmtNames = cfg[@"fmt"];
        NSArray *loadNames = cfg[@"load"];
        NSArray *storeNames = cfg[@"store"];
        NSArray *memless = cfg[@"memoryless"];
        NSInteger samples = [cfg[@"samples"] integerValue];
        BOOL depth = [cfg[@"depth"] boolValue];
        BOOL depthWrite = [cfg[@"depthWrite"] boolValue];
        BOOL depthMemoryless = [cfg[@"depthMemoryless"] boolValue];
        NSString *depthLoadN = cfg[@"depthLoad"], *depthStoreN = cfg[@"depthStore"];
        BOOL stencil = [cfg[@"stencil"] boolValue];
        BOOL stencilWrite = [cfg[@"stencilWrite"] boolValue];
        NSString *stencilLoadN = cfg[@"stencilLoad"], *stencilStoreN = cfg[@"stencilStore"];
        BOOL draw = [cfg[@"draw"] boolValue];
        NSUInteger W = [cfg[@"width"] unsignedIntegerValue], H = [cfg[@"height"] unsignedIntegerValue];
        NSUInteger instances = [cfg[@"instances"] unsignedIntegerValue];
        const NSUInteger BPR_SMALL = 256, LEN_SMALL = 0x4000;

        MTLPixelFormat fmt[4]; BOOL ml[4];
        for (NSInteger i = 0; i < ncolor; ++i) {
            fmt[i] = fmt_from_name(fmtNames[i]);
            ml[i] = [memless[i] boolValue];
            if (fmt[i] == MTLPixelFormatInvalid) { fprintf(stderr, "BAD_FORMAT %ld\n", (long)i); return 2; }
        }

        NSString *vsrc =
            @"#include <metal_stdlib>\nusing namespace metal;\n"
             "struct VO { float4 pos [[position]]; };\n"
             "vertex VO v_main(uint vid [[vertex_id]], uint iid [[instance_id]]) {\n"
             "  float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)};\n"
             "  float j = fract(float(iid) * 0.6180339887) * 0.0005;\n"
             "  VO o; o.pos=float4(p[vid]+j,0,1); return o;\n"
             "}\n";
        NSMutableString *fbody = [NSMutableString stringWithString:
            @"#include <metal_stdlib>\nusing namespace metal;\n"
             "struct VO { float4 pos [[position]]; };\n"
             "struct FO {\n"];
        for (NSInteger i = 0; i < ncolor; ++i)
            [fbody appendFormat:@"  %@ c%ld [[color(%ld)]];\n", elem_type_for_fmt(fmt[i]), (long)i, (long)i];
        [fbody appendString:@"};\n"
             "fragment FO f_main(VO in [[stage_in]]) {\n"
             "  (void)in; FO o;\n"];
        for (NSInteger i = 0; i < ncolor; ++i) {
            if (fmt[i] == MTLPixelFormatR32Uint)
                [fbody appendFormat:@"  o.c%ld = uint4(37u,0u,0u,1u);\n", (long)i];
            else
                [fbody appendFormat:@"  o.c%ld = float4(0.25,0.5,0.75,0.5);\n", (long)i];
        }
        [fbody appendString:@"  return o;\n}\n"];

        id<MTLLibrary> vl = [dev newLibraryWithSource:vsrc options:nil error:&err];
        if (!vl) { fprintf(stderr, "VERTEX_COMPILE_FAIL %s\n", [[err localizedDescription] UTF8String]); return 5; }
        id<MTLLibrary> fl = [dev newLibraryWithSource:fbody options:nil error:&err];
        if (!fl) { fprintf(stderr, "FRAGMENT_COMPILE_FAIL %s\n%s\n",
                           [[err localizedDescription] UTF8String], [fbody UTF8String]); return 6; }

        MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
        pd.vertexFunction = [vl newFunctionWithName:@"v_main"];
        pd.fragmentFunction = [fl newFunctionWithName:@"f_main"];
        pd.rasterSampleCount = (NSUInteger)samples;
        for (NSInteger i = 0; i < ncolor; ++i) pd.colorAttachments[i].pixelFormat = fmt[i];
        if (depth) pd.depthAttachmentPixelFormat = MTLPixelFormatDepth32Float;
        if (stencil) pd.stencilAttachmentPixelFormat = MTLPixelFormatStencil8;
        id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:pd error:&err];
        if (!pso) {
            result[@"status"] = @"PIPELINE_FAIL";
            result[@"error"] = [err localizedDescription] ?: @"unknown";
            NSData *out = [NSJSONSerialization dataWithJSONObject:result options:0 error:nil];
            [out writeToFile:@(argv[2]) atomically:NO];
            printf("STATUS PIPELINE_FAIL\n"); fflush(stdout);
            return 0; /* not a harness fault: a rejected config is itself a result */
        }

        id<MTLDepthStencilState> dss = nil;
        if (depthWrite || stencilWrite) {
            MTLDepthStencilDescriptor *dsd = [MTLDepthStencilDescriptor new];
            dsd.depthCompareFunction = MTLCompareFunctionAlways;
            dsd.depthWriteEnabled = depthWrite;
            if (stencilWrite) {
                MTLStencilDescriptor *sd = [MTLStencilDescriptor new];
                sd.stencilCompareFunction = MTLCompareFunctionAlways;
                sd.depthStencilPassOperation = MTLStencilOperationReplace;
                dsd.frontFaceStencil = sd; dsd.backFaceStencil = sd;
            }
            dss = [dev newDepthStencilStateWithDescriptor:dsd];
        }

        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor new];
        id<MTLTexture> colorTex[4] = {0}, resolveTex[4] = {0};
        id<MTLBuffer> colorBuf[4] = {0};
        NSUInteger bpr = W * 4, len = W * H * 4 + 0x1000;
        BOOL smallBuffered = (W == 32 && H == 32);
        if (smallBuffered) { bpr = BPR_SMALL; len = LEN_SMALL; }

        for (NSInteger i = 0; i < ncolor; ++i) {
            BOOL memoryless = ml[i];
            if (samples == 1 && !memoryless && smallBuffered) {
                colorBuf[i] = [dev newBufferWithLength:len options:MTLResourceStorageModeShared];
                memset([colorBuf[i] contents], 0xa5, len);
                MTLTextureDescriptor *td = [MTLTextureDescriptor
                    texture2DDescriptorWithPixelFormat:fmt[i] width:W height:H mipmapped:NO];
                td.usage = MTLTextureUsageRenderTarget; td.storageMode = MTLStorageModeShared;
                colorTex[i] = [colorBuf[i] newTextureWithDescriptor:td offset:0 bytesPerRow:bpr];
            } else {
                MTLTextureDescriptor *td = [MTLTextureDescriptor new];
                td.textureType = (samples > 1) ? MTLTextureType2DMultisample : MTLTextureType2D;
                td.pixelFormat = fmt[i]; td.width = W; td.height = H; td.sampleCount = (NSUInteger)samples;
                td.usage = MTLTextureUsageRenderTarget;
                td.storageMode = memoryless ? MTLStorageModeMemoryless : MTLStorageModePrivate;
                colorTex[i] = [dev newTextureWithDescriptor:td];
                MTLStoreAction sa = store_from_name(storeNames[i]);
                if (sa == MTLStoreActionMultisampleResolve || sa == MTLStoreActionStoreAndMultisampleResolve) {
                    MTLTextureDescriptor *rtd = [MTLTextureDescriptor
                        texture2DDescriptorWithPixelFormat:fmt[i] width:W height:H mipmapped:NO];
                    rtd.usage = MTLTextureUsageRenderTarget;
                    if (smallBuffered) {
                        colorBuf[i] = [dev newBufferWithLength:len options:MTLResourceStorageModeShared];
                        memset([colorBuf[i] contents], 0xa5, len);
                        rtd.storageMode = MTLStorageModeShared;
                        resolveTex[i] = [colorBuf[i] newTextureWithDescriptor:rtd offset:0 bytesPerRow:bpr];
                    } else {
                        resolveTex[i] = [dev newTextureWithDescriptor:rtd];
                    }
                }
            }
            if (!colorTex[i]) {
                result[@"status"] = @"COLOR_TEXTURE_CREATE_FAIL";
                NSData *out = [NSJSONSerialization dataWithJSONObject:result options:0 error:nil];
                [out writeToFile:@(argv[2]) atomically:NO];
                printf("STATUS COLOR_TEXTURE_CREATE_FAIL\n"); fflush(stdout);
                return 0;
            }
            rp.colorAttachments[i].texture = colorTex[i];
            rp.colorAttachments[i].loadAction = load_from_name(loadNames[i]);
            rp.colorAttachments[i].storeAction = store_from_name(storeNames[i]);
            rp.colorAttachments[i].clearColor = MTLClearColorMake(0.125, 0.25, 0.375, 0.5);
            if (resolveTex[i]) rp.colorAttachments[i].resolveTexture = resolveTex[i];
        }

        if (depth) {
            MTLTextureDescriptor *td = [MTLTextureDescriptor
                texture2DDescriptorWithPixelFormat:MTLPixelFormatDepth32Float width:W height:H mipmapped:NO];
            td.textureType = (samples > 1) ? MTLTextureType2DMultisample : MTLTextureType2D;
            td.sampleCount = (NSUInteger)samples;
            td.usage = MTLTextureUsageRenderTarget;
            td.storageMode = depthMemoryless ? MTLStorageModeMemoryless : MTLStorageModePrivate;
            id<MTLTexture> depthTex = [dev newTextureWithDescriptor:td];
            if (!depthTex) {
                result[@"status"] = @"DEPTH_TEXTURE_CREATE_FAIL";
                NSData *out = [NSJSONSerialization dataWithJSONObject:result options:0 error:nil];
                [out writeToFile:@(argv[2]) atomically:NO]; printf("STATUS DEPTH_TEXTURE_CREATE_FAIL\n");
                fflush(stdout); return 0;
            }
            rp.depthAttachment.texture = depthTex;
            rp.depthAttachment.loadAction = load_from_name(depthLoadN);
            rp.depthAttachment.storeAction = store_from_name(depthStoreN);
            rp.depthAttachment.clearDepth = 0.75;
        }
        if (stencil) {
            MTLTextureDescriptor *td = [MTLTextureDescriptor
                texture2DDescriptorWithPixelFormat:MTLPixelFormatStencil8 width:W height:H mipmapped:NO];
            td.textureType = (samples > 1) ? MTLTextureType2DMultisample : MTLTextureType2D;
            td.sampleCount = (NSUInteger)samples;
            td.usage = MTLTextureUsageRenderTarget;
            td.storageMode = MTLStorageModePrivate;
            id<MTLTexture> stencilTex = [dev newTextureWithDescriptor:td];
            if (!stencilTex) {
                result[@"status"] = @"STENCIL_TEXTURE_CREATE_FAIL";
                NSData *out = [NSJSONSerialization dataWithJSONObject:result options:0 error:nil];
                [out writeToFile:@(argv[2]) atomically:NO]; printf("STATUS STENCIL_TEXTURE_CREATE_FAIL\n");
                fflush(stdout); return 0;
            }
            rp.stencilAttachment.texture = stencilTex;
            rp.stencilAttachment.loadAction = load_from_name(stencilLoadN);
            rp.stencilAttachment.storeAction = store_from_name(stencilStoreN);
            rp.stencilAttachment.clearStencil = 0x55;
        }

        id<MTLCommandQueue> q = [dev newCommandQueue];
        id<MTLCommandBuffer> cb = [q commandBuffer];
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        if (!enc) {
            result[@"status"] = @"ENCODER_CREATE_FAIL";
            NSData *out = [NSJSONSerialization dataWithJSONObject:result options:0 error:nil];
            [out writeToFile:@(argv[2]) atomically:NO]; printf("STATUS ENCODER_CREATE_FAIL\n");
            fflush(stdout); return 0;
        }
        [enc setRenderPipelineState:pso];
        if (dss) [enc setDepthStencilState:dss];
        [enc setStencilReferenceValue:0xAA];
        MTLViewport viewport = {0, 0, (double)W, (double)H, 0, 1};
        [enc setViewport:viewport];
        if (draw) [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3 instanceCount:instances];
        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];

        /* Buffer-backed resource GPU addresses only (used solely to locate the
         * depth/stencil clear-value candidate region by address arithmetic;
         * see run.py find_zs_clear_candidate). Private/memoryless textures
         * have no CPU-visible buffer and are not included. */
        NSMutableArray *colorGpuAddrs = [NSMutableArray array];
        for (NSInteger i = 0; i < ncolor; ++i) {
            if (colorBuf[i]) [colorGpuAddrs addObject:[NSString stringWithFormat:@"0x%llx",
                (unsigned long long)[colorBuf[i] gpuAddress]]];
        }
        result[@"color_gpu_addresses"] = colorGpuAddrs;

        result[@"cb_status"] = @((long)[cb status]);
        result[@"cb_error"] = [cb error] ? [[[cb error] localizedDescription] description] : [NSNull null];
        result[@"status"] = ([cb status] == MTLCommandBufferStatusCompleted && ![cb error]) ? @"OK" : @"CMDBUF_ERROR";

        NSMutableArray *rts = [NSMutableArray array];
        for (NSInteger i = 0; i < ncolor; ++i) {
            id<MTLBuffer> b = resolveTex[i] ? colorBuf[i] : colorBuf[i];
            if (b) {
                uint8_t *p = [b contents];
                char hex[9];
                snprintf(hex, sizeof(hex), "%02x%02x%02x%02x", p[0], p[1], p[2], p[3]);
                [rts addObject:@{@"i": @(i), @"first4_hex": @(hex)}];
            } else {
                [rts addObject:@{@"i": @(i), @"first4_hex": [NSNull null]}];
            }
        }
        result[@"rts"] = rts;

        NSData *out = [NSJSONSerialization dataWithJSONObject:result options:0 error:nil];
        [out writeToFile:@(argv[2]) atomically:NO];
        printf("STATUS %s\n", [result[@"status"] UTF8String]);
        fflush(stdout);
        if (do_dump) { kill(getpid(), SIGUSR1); usleep(500000); }
        return 0;
    }
}
