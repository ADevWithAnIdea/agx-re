/*
 * EXP-0048 clean-room Metal render probe.
 *
 * All MSL below is authored in this file.  The probe observes only its own
 * buffer-backed attachment bytes and an authored atomic counter.  It requests
 * a SIGUSR1 snapshot after GPU completion; the companion interposer is limited
 * to a fixed, pre-registered command/state BO allowlist.
 */
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

enum Kind { K_RGBA8, K_BGRA8, K_SRGBA8, K_R32F, K_R32U };

typedef struct {
    const char *name;
    enum Kind k0, k1;
    MTLLoadAction load;
    MTLStoreAction store;
    int draw, blend, atomic;
} Case;

static const Case cases[] = {
    {"rgba8-clear-store-draw",       K_RGBA8,  K_RGBA8, MTLLoadActionClear,    MTLStoreActionStore,    1,0,0},
    {"rgba8-clear-store-empty",      K_RGBA8,  K_RGBA8, MTLLoadActionClear,    MTLStoreActionStore,    0,0,0},
    {"rgba8-load-store-empty",       K_RGBA8,  K_RGBA8, MTLLoadActionLoad,     MTLStoreActionStore,    0,0,0},
    {"rgba8-dontcare-store-draw",    K_RGBA8,  K_RGBA8, MTLLoadActionDontCare, MTLStoreActionStore,    1,0,0},
    {"rgba8-clear-dontcare-draw",    K_RGBA8,  K_RGBA8, MTLLoadActionClear,    MTLStoreActionDontCare, 1,0,0},
    {"bgra8-clear-store-draw",       K_BGRA8,  K_RGBA8, MTLLoadActionClear,    MTLStoreActionStore,    1,0,0},
    {"rgba8srgb-clear-store-draw",   K_SRGBA8, K_RGBA8, MTLLoadActionClear,    MTLStoreActionStore,    1,0,0},
    {"r32f-clear-store-draw",        K_R32F,   K_RGBA8, MTLLoadActionClear,    MTLStoreActionStore,    1,0,0},
    {"r32u-clear-store-draw",        K_R32U,   K_RGBA8, MTLLoadActionClear,    MTLStoreActionStore,    1,0,0},
    {"rgba8-load-store-blend",       K_RGBA8,  K_RGBA8, MTLLoadActionLoad,     MTLStoreActionStore,    1,1,0},
    {"rgba8-clear-store-atomic",     K_RGBA8,  K_RGBA8, MTLLoadActionClear,    MTLStoreActionStore,    1,0,1},
    {"mixed-r32f-clear-store",       K_RGBA8,  K_R32F,  MTLLoadActionClear,    MTLStoreActionStore,    1,0,0},
};

static MTLPixelFormat pixel_format(enum Kind k) {
    switch (k) {
        case K_RGBA8:  return MTLPixelFormatRGBA8Unorm;
        case K_BGRA8:  return MTLPixelFormatBGRA8Unorm;
        case K_SRGBA8: return MTLPixelFormatRGBA8Unorm_sRGB;
        case K_R32F:   return MTLPixelFormatR32Float;
        case K_R32U:   return MTLPixelFormatR32Uint;
    }
    return MTLPixelFormatInvalid;
}

static const char *kind_name(enum Kind k) {
    switch (k) {
        case K_RGBA8: return "rgba8";
        case K_BGRA8: return "bgra8";
        case K_SRGBA8: return "rgba8srgb";
        case K_R32F: return "r32f";
        case K_R32U: return "r32u";
    }
    return "invalid";
}

static uint64_t fnv1a_active(const uint8_t *p, size_t bpr, size_t width,
                             size_t height) {
    uint64_t h = 1469598103934665603ULL;
    for (size_t y = 0; y < height; ++y) {
        for (size_t x = 0; x < width * 4; ++x) {
            h ^= p[y * bpr + x];
            h *= 1099511628211ULL;
        }
    }
    return h;
}

static void init_surface(uint8_t *p, size_t allocation_size, size_t bpr,
                         size_t width, size_t height, enum Kind k, int attachment) {
    memset(p, 0xa5, allocation_size);
    for (size_t y = 0; y < height; ++y) {
        for (size_t x = 0; x < width; ++x) {
            uint8_t *q = p + y * bpr + x * 4;
            if (k == K_R32F) {
                float v = attachment ? 0.125f : 0.375f;
                memcpy(q, &v, 4);
            } else if (k == K_R32U) {
                uint32_t v = attachment ? 11u : 19u;
                memcpy(q, &v, 4);
            } else if (attachment) {
                q[0] = 16; q[1] = 24; q[2] = 32; q[3] = 255;
            } else {
                q[0] = 64; q[1] = 32; q[2] = 16; q[3] = 255;
            }
        }
    }
}

static NSString *fragment_source(const Case *c) {
    NSString *t0 = c->k0 == K_R32U ? @"uint4" : @"float4";
    NSString *t1 = c->k1 == K_R32U ? @"uint4" : @"float4";
    NSString *v0 = c->k0 == K_R32U ? @"uint4(37u,0u,0u,1u)" : @"float4(0.25,0.5,0.75,0.5)";
    NSString *v1 = c->k1 == K_R32U ? @"uint4(73u,0u,0u,1u)" :
                   (c->k1 == K_R32F ? @"float4(0.625,0.0,0.0,1.0)" : @"float4(0.5,0.25,0.125,1.0)");
    NSString *arg = c->atomic ? @"device atomic_uint *counter [[buffer(0)]]" : @"";
    NSString *body = c->atomic ? @"atomic_fetch_add_explicit(counter,1u,memory_order_relaxed);" : @"";
    return [NSString stringWithFormat:
        @"#include <metal_stdlib>\n"
         "using namespace metal;\n"
         "struct VO { float4 pos [[position]]; };\n"
         "struct FO { %@ c0 [[color(0)]]; %@ c1 [[color(1)]]; };\n"
         "fragment FO f_main(VO in [[stage_in]]%@%@) {\n"
         "  (void)in; %@ FO o; o.c0=%@; o.c1=%@; return o;\n"
         "}\n",
         t0, t1, c->atomic ? @", " : @"", arg, body, v0, v1];
}

static NSString *vertex_source(void) {
    return @"#include <metal_stdlib>\n"
            "using namespace metal;\n"
            "struct VO { float4 pos [[position]]; };\n"
            "vertex VO v_main(uint vid [[vertex_id]]) {\n"
            "  float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)};\n"
            "  VO o; o.pos=float4(p[vid],0,1); return o;\n"
            "}\n";
}

static void print_first(const char *label, const uint8_t *p) {
    printf("FIRST %s=%02x%02x%02x%02x u32=0x%08x\n", label,
           p[0], p[1], p[2], p[3], *(const uint32_t *)p);
}

static int uniform_active(const uint8_t *p, size_t bpr, size_t width,
                          size_t height) {
    for (size_t y = 0; y < height; ++y)
        for (size_t x = 0; x < width; ++x)
            if (memcmp(p, p + y * bpr + x * 4, 4)) return 0;
    return 1;
}

int main(int argc, char **argv) {
    @autoreleasepool {
        const char *case_name = NULL, *source_out = NULL;
        int do_dump = 0;
        for (int i = 1; i < argc; ++i) {
            if (!strcmp(argv[i], "--case") && i + 1 < argc) case_name = argv[++i];
            else if (!strcmp(argv[i], "--source-out") && i + 1 < argc) source_out = argv[++i];
            else if (!strcmp(argv[i], "--dump")) do_dump = 1;
            else { fprintf(stderr, "unknown/missing argument: %s\n", argv[i]); return 2; }
        }
        const Case *c = NULL;
        for (size_t i = 0; i < sizeof(cases)/sizeof(cases[0]); ++i)
            if (case_name && !strcmp(case_name, cases[i].name)) c = &cases[i];
        if (!c || !source_out) { fprintf(stderr, "--case and --source-out required\n"); return 2; }

        /*
         * Keep all three user allocations in the 0x4000 size class used by the
         * prior MRT correlation.  This avoids consuming the driver's separate
         * small-allocation command/state arena before render encoding.
         */
        const NSUInteger W = 32, H = 32, BPR = 256, LEN = 0x4000;
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) { fprintf(stderr, "NO_DEVICE\n"); return 3; }
        printf("DEVICE %s\n", [[dev name] UTF8String]);
        printf("CASE %s fmt0=%s fmt1=%s load=%lu store=%lu draw=%d blend=%d atomic=%d w=32 h=32 bpr=256\n",
               c->name, kind_name(c->k0), kind_name(c->k1),
               (unsigned long)c->load, (unsigned long)c->store,
               c->draw, c->blend, c->atomic);

        NSString *vsrc = vertex_source();
        NSString *fsrc = fragment_source(c);
        NSString *combined = [NSString stringWithFormat:@"// VERTEX\n%@\n// FRAGMENT\n%@", vsrc, fsrc];
        NSError *err = nil;
        if (![combined writeToFile:[NSString stringWithUTF8String:source_out]
                         atomically:NO encoding:NSUTF8StringEncoding error:&err]) {
            fprintf(stderr, "SOURCE_WRITE_FAIL %s\n", [[err localizedDescription] UTF8String]); return 4;
        }
        id<MTLLibrary> vl = [dev newLibraryWithSource:vsrc options:nil error:&err];
        if (!vl) { fprintf(stderr, "VERTEX_COMPILE_FAIL %s\n", [[err localizedDescription] UTF8String]); return 5; }
        id<MTLLibrary> fl = [dev newLibraryWithSource:fsrc options:nil error:&err];
        if (!fl) { fprintf(stderr, "FRAGMENT_COMPILE_FAIL %s\n%s\n",
                           [[err localizedDescription] UTF8String], [fsrc UTF8String]); return 6; }

        MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
        pd.vertexFunction = [vl newFunctionWithName:@"v_main"];
        pd.fragmentFunction = [fl newFunctionWithName:@"f_main"];
        pd.colorAttachments[0].pixelFormat = pixel_format(c->k0);
        pd.colorAttachments[1].pixelFormat = pixel_format(c->k1);
        if (c->blend) {
            MTLRenderPipelineColorAttachmentDescriptor *a = pd.colorAttachments[0];
            a.blendingEnabled = YES;
            a.rgbBlendOperation = MTLBlendOperationAdd;
            a.alphaBlendOperation = MTLBlendOperationAdd;
            a.sourceRGBBlendFactor = MTLBlendFactorSourceAlpha;
            a.destinationRGBBlendFactor = MTLBlendFactorOneMinusSourceAlpha;
            a.sourceAlphaBlendFactor = MTLBlendFactorSourceAlpha;
            a.destinationAlphaBlendFactor = MTLBlendFactorOneMinusSourceAlpha;
        }
        id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:pd error:&err];
        if (!pso) { fprintf(stderr, "PIPELINE_FAIL %s\n", [[err localizedDescription] UTF8String]); return 7; }

        id<MTLBuffer> counter = [dev newBufferWithLength:LEN options:MTLResourceStorageModeShared];
        memset([counter contents], 0, LEN);
        id<MTLBuffer> b0 = [dev newBufferWithLength:LEN options:MTLResourceStorageModeShared];
        id<MTLBuffer> b1 = [dev newBufferWithLength:LEN options:MTLResourceStorageModeShared];
        init_surface([b0 contents], LEN, BPR, W, H, c->k0, 0);
        init_surface([b1 contents], LEN, BPR, W, H, c->k1, 1);

        MTLTextureDescriptor *td0 = [MTLTextureDescriptor
            texture2DDescriptorWithPixelFormat:pixel_format(c->k0) width:W height:H mipmapped:NO];
        MTLTextureDescriptor *td1 = [MTLTextureDescriptor
            texture2DDescriptorWithPixelFormat:pixel_format(c->k1) width:W height:H mipmapped:NO];
        td0.usage = MTLTextureUsageRenderTarget; td0.storageMode = MTLStorageModeShared;
        td1.usage = MTLTextureUsageRenderTarget; td1.storageMode = MTLStorageModeShared;
        id<MTLTexture> t0 = [b0 newTextureWithDescriptor:td0 offset:0 bytesPerRow:BPR];
        id<MTLTexture> t1 = [b1 newTextureWithDescriptor:td1 offset:0 bytesPerRow:BPR];
        if (!t0 || !t1) { fprintf(stderr, "TEXTURE_CREATE_FAIL\n"); return 8; }
        printf("USER_VA counter=0x%llx rt0=0x%llx rt1=0x%llx\n",
               (unsigned long long)[counter gpuAddress], (unsigned long long)[b0 gpuAddress],
               (unsigned long long)[b1 gpuAddress]);

        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor new];
        id<MTLTexture> textures[2] = {t0, t1};
        for (NSUInteger i = 0; i < 2; ++i) {
            rp.colorAttachments[i].texture = textures[i];
            rp.colorAttachments[i].loadAction = c->load;
            rp.colorAttachments[i].storeAction = c->store;
        }
        rp.colorAttachments[0].clearColor = MTLClearColorMake(32.0/255.0, 64.0/255.0,
                                                              96.0/255.0, 128.0/255.0);
        rp.colorAttachments[1].clearColor = MTLClearColorMake(160.0/255.0, 96.0/255.0,
                                                              48.0/255.0, 192.0/255.0);

        id<MTLCommandQueue> q = [dev newCommandQueue];
        id<MTLCommandBuffer> cb = [q commandBuffer];
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        MTLViewport viewport = {0, 0, W, H, 0, 1};
        [enc setViewport:viewport];
        if (c->atomic) [enc setFragmentBuffer:counter offset:0 atIndex:0];
        if (c->draw) [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];
        printf("COMMAND status=%ld error=%s\n", (long)[cb status],
               [cb error] ? [[[[cb error] localizedDescription] description] UTF8String] : "none");
        if ([cb status] != MTLCommandBufferStatusCompleted || [cb error]) return 9;

        uint8_t *p0 = [b0 contents], *p1 = [b1 contents];
        print_first("rt0", p0); print_first("rt1", p1);
        printf("RESULT rt0_fnv=0x%016llx rt1_fnv=0x%016llx rt0_uniform=%d rt1_uniform=%d counter=%u\n",
               (unsigned long long)fnv1a_active(p0, BPR, W, H),
               (unsigned long long)fnv1a_active(p1, BPR, W, H),
               uniform_active(p0, BPR, W, H), uniform_active(p1, BPR, W, H),
               *(uint32_t *)[counter contents]);
        fflush(stdout);
        if (do_dump) { kill(getpid(), SIGUSR1); usleep(500000); }
        return 0;
    }
}
