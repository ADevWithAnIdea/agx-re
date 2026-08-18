/*
 * EXP-0055 authored public-Metal scissor/depth-bias probe.
 *
 * This program observes only public status and resources it allocates. The
 * companion interposer performs the separately bounded two-VA DATA-TRACE.
 */
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <math.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

enum {
    W = 16,
    H = 16,
    PIXEL_BYTES = W * H * 4,
    GUARD = 32,
    GUARDED_BYTES = GUARD + PIXEL_BYTES + GUARD,
    PAD_BYTES = 65536,
};

static const uint8_t CLEAR_RGBA[4] = {0x01, 0x02, 0x03, 0x04};
static const uint8_t SINGLE_RGBA[4] = {0x11, 0x22, 0x33, 0xff};
static const uint8_t MULTI0_RGBA[4] = {0x21, 0x43, 0x65, 0xff};
static const uint8_t MULTI1_RGBA[4] = {0x9a, 0x57, 0xc3, 0xff};
static const uint8_t DEPTH_RGBA[4] = {0xcc, 0x33, 0x11, 0xff};

typedef enum { KIND_SCISSOR, KIND_MULTI, KIND_DBIAS } CaseKind;

typedef struct {
    const char *name;
    CaseKind kind;
    MTLScissorRect r0, r1;
    float constant_bias, slope, clamp;
} ProbeCase;

static const ProbeCase CASES[] = {
    {"scissor-base", KIND_SCISSOR, {2, 3, 7, 5}, {0, 0, 0, 0}, 0, 0, 0},
    {"scissor-x", KIND_SCISSOR, {4, 3, 7, 5}, {0, 0, 0, 0}, 0, 0, 0},
    {"scissor-y", KIND_SCISSOR, {2, 5, 7, 5}, {0, 0, 0, 0}, 0, 0, 0},
    {"scissor-width", KIND_SCISSOR, {2, 3, 9, 5}, {0, 0, 0, 0}, 0, 0, 0},
    {"scissor-height", KIND_SCISSOR, {2, 3, 7, 8}, {0, 0, 0, 0}, 0, 0, 0},
    {"scissor-empty-width", KIND_SCISSOR, {2, 3, 0, 5}, {0, 0, 0, 0}, 0, 0, 0},
    {"scissor-empty-height", KIND_SCISSOR, {2, 3, 7, 0}, {0, 0, 0, 0}, 0, 0, 0},
    {"multi-base", KIND_MULTI, {1, 2, 5, 6}, {9, 3, 4, 10}, 0, 0, 0},
    {"multi-slot0-x", KIND_MULTI, {2, 2, 5, 6}, {9, 3, 4, 10}, 0, 0, 0},
    {"multi-slot1-x", KIND_MULTI, {1, 2, 5, 6}, {11, 3, 4, 10}, 0, 0, 0},
    {"dbias-zero", KIND_DBIAS, {0, 0, 0, 0}, {0, 0, 0, 0}, 0.0f, 0.0f, 0.0f},
    {"dbias-constant-negative", KIND_DBIAS, {0, 0, 0, 0}, {0, 0, 0, 0}, -1.0f, 0.0f, 0.0f},
    {"dbias-constant-positive", KIND_DBIAS, {0, 0, 0, 0}, {0, 0, 0, 0}, 1.0f, 0.0f, 0.0f},
    {"dbias-slope-negative", KIND_DBIAS, {0, 0, 0, 0}, {0, 0, 0, 0}, 0.0f, -1.0f, 0.0f},
    {"dbias-slope-positive", KIND_DBIAS, {0, 0, 0, 0}, {0, 0, 0, 0}, 0.0f, 1.0f, 0.0f},
    {"dbias-large-negative", KIND_DBIAS, {0, 0, 0, 0}, {0, 0, 0, 0}, -100000.0f, 0.0f, 0.0f},
    {"dbias-clamp-negative", KIND_DBIAS, {0, 0, 0, 0}, {0, 0, 0, 0}, -100000.0f, 0.0f, -0.001f},
    {"dbias-large-positive", KIND_DBIAS, {0, 0, 0, 0}, {0, 0, 0, 0}, 100000.0f, 0.0f, 0.0f},
    {"dbias-clamp-positive", KIND_DBIAS, {0, 0, 0, 0}, {0, 0, 0, 0}, 100000.0f, 0.0f, 0.001f},
};

static NSString *source(void) {
    return @"#include <metal_stdlib>\n"
            "using namespace metal;\n"
            "struct VOut { float4 position [[position]]; };\n"
            "struct VMOut { float4 position [[position]]; uint viewport [[viewport_array_index]]; };\n"
            "vertex VOut v_single(uint vid [[vertex_id]], constant float4 *p [[buffer(0)]]) {\n"
            "  VOut o; o.position = p[vid]; return o;\n"
            "}\n"
            "vertex VMOut v_multi(uint vid [[vertex_id]], constant float4 *p [[buffer(0)]],\n"
            "                       constant uint &viewport [[buffer(1)]]) {\n"
            "  VMOut o; o.position = p[vid]; o.viewport = viewport; return o;\n"
            "}\n"
            "fragment float4 f_color(constant float4 &color [[buffer(0)]]) { return color; }\n";
}

static const ProbeCase *find_case(const char *name) {
    for (size_t i = 0; i < sizeof(CASES) / sizeof(CASES[0]); ++i)
        if (!strcmp(CASES[i].name, name)) return &CASES[i];
    return NULL;
}

static const char *kind_name(CaseKind kind) {
    switch (kind) {
        case KIND_SCISSOR: return "scissor";
        case KIND_MULTI: return "multi";
        case KIND_DBIAS: return "dbias";
    }
    return "invalid";
}

static uint32_t float_bits(float value) {
    uint32_t bits;
    memcpy(&bits, &value, sizeof(bits));
    return bits;
}

static void fill_guarded(uint8_t bytes[GUARDED_BYTES]) {
    memset(bytes, 0xcc, GUARDED_BYTES);
    for (size_t i = 0; i < GUARD; ++i) {
        bytes[i] = (uint8_t)(0xa0u + i);
        bytes[GUARD + PIXEL_BYTES + i] = (uint8_t)(0x5fu - i);
    }
}

static unsigned guard_errors(const uint8_t bytes[GUARDED_BYTES]) {
    unsigned errors = 0;
    for (size_t i = 0; i < GUARD; ++i) {
        errors += bytes[i] != (uint8_t)(0xa0u + i);
        errors += bytes[GUARD + PIXEL_BYTES + i] != (uint8_t)(0x5fu - i);
    }
    return errors;
}

static void print_hex(const uint8_t *bytes, size_t size) {
    for (size_t i = 0; i < size; ++i) printf("%02x", bytes[i]);
}

static void print_string_hex(NSString *value) {
    if (!value) {
        printf("none");
        return;
    }
    const char *bytes = [[value description] UTF8String];
    print_hex((const uint8_t *)bytes, strlen(bytes));
}

static id<MTLTexture> color_texture(id<MTLDevice> dev) {
    MTLTextureDescriptor *td = [MTLTextureDescriptor
        texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm
        width:W height:H mipmapped:NO];
    td.usage = MTLTextureUsageRenderTarget;
    td.storageMode = MTLStorageModeShared;
    return [dev newTextureWithDescriptor:td];
}

static id<MTLTexture> depth_texture(id<MTLDevice> dev) {
    MTLTextureDescriptor *td = [MTLTextureDescriptor
        texture2DDescriptorWithPixelFormat:MTLPixelFormatDepth32Float
        width:W height:H mipmapped:NO];
    td.usage = MTLTextureUsageRenderTarget;
    td.storageMode = MTLStorageModeShared;
    return [dev newTextureWithDescriptor:td];
}

static MTLRenderPassDescriptor *pass_descriptor(id<MTLTexture> color,
                                                 id<MTLTexture> depth) {
    MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor new];
    rp.colorAttachments[0].texture = color;
    rp.colorAttachments[0].loadAction = MTLLoadActionClear;
    rp.colorAttachments[0].clearColor = MTLClearColorMake(
        CLEAR_RGBA[0] / 255.0, CLEAR_RGBA[1] / 255.0,
        CLEAR_RGBA[2] / 255.0, CLEAR_RGBA[3] / 255.0);
    rp.colorAttachments[0].storeAction = MTLStoreActionStore;
    if (depth) {
        rp.depthAttachment.texture = depth;
        rp.depthAttachment.loadAction = MTLLoadActionClear;
        rp.depthAttachment.clearDepth = 1.0;
        rp.depthAttachment.storeAction = MTLStoreActionStore;
    }
    return rp;
}

static void set_color(id<MTLRenderCommandEncoder> enc, const uint8_t rgba[4]) {
    float color[4] = {rgba[0] / 255.0f, rgba[1] / 255.0f,
                      rgba[2] / 255.0f, rgba[3] / 255.0f};
    [enc setFragmentBytes:color length:sizeof(color) atIndex:0];
}

static void get_guarded(id<MTLTexture> texture,
                        uint8_t bytes[GUARDED_BYTES]) {
    fill_guarded(bytes);
    [texture getBytes:bytes + GUARD bytesPerRow:W * 4
            fromRegion:MTLRegionMake2D(0, 0, W, H) mipmapLevel:0];
}

static unsigned pad_errors(id<MTLBuffer> pad) {
    if (!pad) return 0;
    const uint8_t *bytes = [pad contents];
    unsigned errors = 0;
    for (size_t i = 0; i < PAD_BYTES; ++i)
        errors += bytes[i] != (uint8_t)((i * 37u + 0x5bu) & 0xffu);
    return errors;
}

static BOOL encode_case(const ProbeCase *c, id<MTLDevice> dev,
                        id<MTLCommandQueue> queue,
                        id<MTLRenderPipelineState> single_pso,
                        id<MTLRenderPipelineState> multi_pso,
                        id<MTLRenderPipelineState> depth_pso,
                        id<MTLDepthStencilState> depth_state,
                        id<MTLTexture> color, id<MTLTexture> depth,
                        id<MTLCommandBuffer> *out_cb) {
    const float full[12] = {-1, -1, 0.5f, 1, 3, -1, 0.5f, 1,
                            -1, 3, 0.5f, 1};
    const float sloped[12] = {-1, -1, 0.2f, 1, 3, -1, 0.8f, 1,
                              -1, 3, 0.35f, 1};
    id<MTLCommandBuffer> cb = [queue commandBuffer];
    id<MTLRenderCommandEncoder> enc =
        [cb renderCommandEncoderWithDescriptor:pass_descriptor(color, depth)];
    @try {
        MTLViewport viewport = {0, 0, W, H, 0, 1};
        if (c->kind == KIND_SCISSOR) {
            [enc setRenderPipelineState:single_pso];
            [enc setViewport:viewport];
            [enc setScissorRect:c->r0];
            [enc setVertexBytes:full length:sizeof(full) atIndex:0];
            set_color(enc, SINGLE_RGBA);
            [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        } else if (c->kind == KIND_MULTI) {
            [enc setRenderPipelineState:multi_pso];
            MTLViewport viewports[2] = {viewport, viewport};
            MTLScissorRect rects[2] = {c->r0, c->r1};
            [enc setViewports:viewports count:2];
            [enc setScissorRects:rects count:2];
            [enc setVertexBytes:full length:sizeof(full) atIndex:0];
            uint32_t index = 0;
            [enc setVertexBytes:&index length:sizeof(index) atIndex:1];
            set_color(enc, MULTI0_RGBA);
            [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
            index = 1;
            [enc setVertexBytes:&index length:sizeof(index) atIndex:1];
            set_color(enc, MULTI1_RGBA);
            [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        } else {
            [enc setRenderPipelineState:depth_pso];
            [enc setViewport:viewport];
            MTLScissorRect rect = {0, 0, W, H};
            [enc setScissorRect:rect];
            [enc setVertexBytes:sloped length:sizeof(sloped) atIndex:0];
            [enc setDepthStencilState:depth_state];
            [enc setDepthBias:c->constant_bias slopeScale:c->slope clamp:c->clamp];
            set_color(enc, DEPTH_RGBA);
            [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        }
        [enc endEncoding];
    } @catch (NSException *exception) {
        printf("FATAL phase=encode error_hex=");
        print_string_hex([exception reason]);
        printf("\n");
        @try { [enc endEncoding]; } @catch (NSException *ignored) { (void)ignored; }
        return NO;
    }
    [cb commit];
    [cb waitUntilCompleted];
    *out_cb = cb;
    return YES;
}

static void fatal(NSString *phase, NSError *error) {
    printf("FATAL phase=%s error_hex=", [phase UTF8String]);
    print_string_hex(error ? [error localizedDescription] : @"unknown");
    printf("\nRESULT FAIL\n");
}

int main(int argc, char **argv) {
    @autoreleasepool {
        const char *case_name = NULL;
        const char *schedule = NULL;
        BOOL do_dump = NO;
        for (int i = 1; i < argc; ++i) {
            if (!strcmp(argv[i], "--case") && i + 1 < argc) case_name = argv[++i];
            else if (!strcmp(argv[i], "--schedule") && i + 1 < argc) schedule = argv[++i];
            else if (!strcmp(argv[i], "--dump")) do_dump = YES;
            else { fprintf(stderr, "invalid argument\n"); return 2; }
        }
        const ProbeCase *c = case_name ? find_case(case_name) : NULL;
        BOOL padded = schedule && !strcmp(schedule, "pad64k");
        if (!c || !schedule || (!padded && strcmp(schedule, "plain"))) {
            fprintf(stderr, "usage: probe --case NAME --schedule plain|pad64k --dump\n");
            return 2;
        }

        NSError *error = nil;
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) { printf("FATAL phase=device error_hex=6e6f6e65\nRESULT FAIL\n"); return 1; }
        printf("DEVICE %s\n", [[dev name] UTF8String]);
        printf("SCOPE trace=exact-0x58000-0x68000 shader_bytes=uninspected "
               "pointer_following=0 mutation=0\n");

        id<MTLBuffer> pad = nil;
        if (padded) {
            pad = [dev newBufferWithLength:PAD_BYTES options:MTLResourceStorageModeShared];
            if (!pad) { printf("FATAL phase=pad error_hex=6e6f6e65\nRESULT FAIL\n"); return 1; }
            uint8_t *bytes = [pad contents];
            for (size_t i = 0; i < PAD_BYTES; ++i)
                bytes[i] = (uint8_t)((i * 37u + 0x5bu) & 0xffu);
        }

        id<MTLLibrary> library = [dev newLibraryWithSource:source() options:nil error:&error];
        if (!library) { fatal(@"library", error); return 1; }
        MTLRenderPipelineDescriptor *single_desc = [MTLRenderPipelineDescriptor new];
        single_desc.vertexFunction = [library newFunctionWithName:@"v_single"];
        single_desc.fragmentFunction = [library newFunctionWithName:@"f_color"];
        single_desc.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA8Unorm;
        id<MTLRenderPipelineState> single_pso =
            [dev newRenderPipelineStateWithDescriptor:single_desc error:&error];
        if (!single_pso) { fatal(@"single-pipeline", error); return 1; }

        MTLRenderPipelineDescriptor *multi_desc = [MTLRenderPipelineDescriptor new];
        multi_desc.vertexFunction = [library newFunctionWithName:@"v_multi"];
        multi_desc.fragmentFunction = [library newFunctionWithName:@"f_color"];
        multi_desc.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA8Unorm;
        id<MTLRenderPipelineState> multi_pso =
            [dev newRenderPipelineStateWithDescriptor:multi_desc error:&error];
        if (!multi_pso) { fatal(@"multi-pipeline", error); return 1; }

        MTLRenderPipelineDescriptor *depth_desc = [single_desc copy];
        depth_desc.depthAttachmentPixelFormat = MTLPixelFormatDepth32Float;
        id<MTLRenderPipelineState> depth_pso =
            [dev newRenderPipelineStateWithDescriptor:depth_desc error:&error];
        if (!depth_pso) { fatal(@"depth-pipeline", error); return 1; }

        MTLDepthStencilDescriptor *ds_desc = [MTLDepthStencilDescriptor new];
        ds_desc.depthCompareFunction = MTLCompareFunctionAlways;
        ds_desc.depthWriteEnabled = YES;
        id<MTLDepthStencilState> ds = [dev newDepthStencilStateWithDescriptor:ds_desc];
        id<MTLCommandQueue> queue = [dev newCommandQueue];
        id<MTLTexture> color = color_texture(dev);
        id<MTLTexture> depth = c->kind == KIND_DBIAS ? depth_texture(dev) : nil;
        if (!ds || !queue || !color || (c->kind == KIND_DBIAS && !depth)) {
            printf("FATAL phase=resource error_hex=6e6f6e65\nRESULT FAIL\n");
            return 1;
        }

        printf("INPUT kind=%s name=%s schedule=%s pad_bytes=%u ",
               kind_name(c->kind), c->name, schedule, padded ? PAD_BYTES : 0);
        if (c->kind == KIND_SCISSOR) {
            printf("x=%lu y=%lu width=%lu height=%lu\n",
                   (unsigned long)c->r0.x, (unsigned long)c->r0.y,
                   (unsigned long)c->r0.width, (unsigned long)c->r0.height);
        } else if (c->kind == KIND_MULTI) {
            printf("r0=%lu,%lu,%lu,%lu r1=%lu,%lu,%lu,%lu\n",
                   (unsigned long)c->r0.x, (unsigned long)c->r0.y,
                   (unsigned long)c->r0.width, (unsigned long)c->r0.height,
                   (unsigned long)c->r1.x, (unsigned long)c->r1.y,
                   (unsigned long)c->r1.width, (unsigned long)c->r1.height);
        } else {
            printf("constant_bits=%08x slope_bits=%08x clamp_bits=%08x\n",
                   float_bits(c->constant_bias), float_bits(c->slope),
                   float_bits(c->clamp));
        }

        id<MTLCommandBuffer> cb = nil;
        if (!encode_case(c, dev, queue, single_pso, multi_pso, depth_pso, ds,
                         color, depth, &cb)) {
            printf("RESULT FAIL\n");
            return 1;
        }
        NSInteger status = [cb status];
        printf("COMMAND status=%ld error_hex=", (long)status);
        print_string_hex([cb error] ? [[cb error] localizedDescription] : nil);
        printf("\n");

        uint8_t color_bytes[GUARDED_BYTES];
        uint8_t depth_bytes[GUARDED_BYTES];
        get_guarded(color, color_bytes);
        if (depth) get_guarded(depth, depth_bytes);
        unsigned color_errors = guard_errors(color_bytes);
        unsigned depth_errors = depth ? guard_errors(depth_bytes) : 0;
        unsigned padding_errors = pad_errors(pad);
        printf("READBACK color_guard_errors=%u depth_guard_errors=%u pad_errors=%u "
               "color_guarded_hex=", color_errors, depth_errors, padding_errors);
        print_hex(color_bytes, sizeof(color_bytes));
        printf(" depth_guarded_hex=");
        if (depth) print_hex(depth_bytes, sizeof(depth_bytes));
        else printf("none");
        printf("\n");

        BOOL ok = status == MTLCommandBufferStatusCompleted && ![cb error] &&
                  color_errors == 0 && depth_errors == 0 && padding_errors == 0;
        if (ok && do_dump) {
            fflush(stdout);
            kill(getpid(), SIGUSR1);
            usleep(500000);
        }
        printf("RESULT %s\n", ok ? "OK" : "FAIL");
        fflush(stdout);
        return ok ? 0 : 10;
    }
}
