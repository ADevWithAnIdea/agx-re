/*
 * EXP-0054 public-Metal scissor/depth-bias HW probe.
 *
 * Clean-room boundary: authored Objective-C/MSL and complete authored resource
 * readbacks only. This program performs no tracing, BO inspection, pointer
 * following, mutation, replay, archive extraction, or compiled-shader inspection.
 */
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

enum { W = 16, H = 16, PIXEL_BYTES = W * H * 4, GUARD = 32,
       GUARDED_BYTES = GUARD + PIXEL_BYTES + GUARD };

static const uint8_t CLEAR_RGBA[4] = {0x01, 0x02, 0x03, 0x04};
static const uint8_t SINGLE_RGBA[4] = {0x11, 0x22, 0x33, 0xff};
static const uint8_t MULTI0_RGBA[4] = {0x21, 0x43, 0x65, 0xff};
static const uint8_t MULTI1_RGBA[4] = {0x9a, 0x57, 0xc3, 0xff};
static const uint8_t BASE_RGBA[4] = {0x22, 0x44, 0x88, 0xff};
static const uint8_t BIAS_RGBA[4] = {0xcc, 0x33, 0x11, 0xff};

typedef struct {
    const char *name;
    NSUInteger x, y, width, height;
} ScissorCase;

typedef struct {
    const char *name;
    BOOL sloped;
    MTLCompareFunction compare;
    const char *compare_name;
    float constant_bias, slope, clamp;
} BiasCase;

static const ScissorCase SCISSOR_CASES[] = {
    {"scissor-full", 0, 0, 16, 16},
    {"scissor-asymmetric", 3, 5, 7, 4},
    {"scissor-edge", 15, 14, 1, 2},
    {"scissor-empty-width", 6, 7, 0, 5},
    {"scissor-empty-height", 6, 7, 5, 0},
};

static const BiasCase BIAS_CASES[] = {
    {"dbias-flat-zero", NO, MTLCompareFunctionLess, "less", 0.0f, 0.0f, 0.0f},
    {"dbias-flat-negative", NO, MTLCompareFunctionLess, "less", -1.0f, 0.0f, 0.0f},
    {"dbias-flat-positive", NO, MTLCompareFunctionLess, "less", 1.0f, 0.0f, 0.0f},
    {"dbias-flat-slope-negative", NO, MTLCompareFunctionLess, "less", 0.0f, -1.0f, 0.0f},
    {"dbias-flat-slope-positive", NO, MTLCompareFunctionLess, "less", 0.0f, 1.0f, 0.0f},
    {"dbias-slope-zero", YES, MTLCompareFunctionLess, "less", 0.0f, 0.0f, 0.0f},
    {"dbias-slope-negative", YES, MTLCompareFunctionLess, "less", 0.0f, -1.0f, 0.0f},
    {"dbias-slope-positive", YES, MTLCompareFunctionLess, "less", 0.0f, 1.0f, 0.0f},
    {"dbias-large-negative", NO, MTLCompareFunctionLess, "less", -100000.0f, 0.0f, 0.0f},
    {"dbias-clamp-negative", NO, MTLCompareFunctionLess, "less", -100000.0f, 0.0f, -0.001f},
    {"dbias-large-positive", NO, MTLCompareFunctionGreater, "greater", 100000.0f, 0.0f, 0.0f},
    {"dbias-clamp-positive", NO, MTLCompareFunctionGreater, "greater", 100000.0f, 0.0f, 0.001f},
};

static NSString *single_source(void) {
    return @"#include <metal_stdlib>\n"
            "using namespace metal;\n"
            "struct VOut { float4 position [[position]]; };\n"
            "vertex VOut v_single(uint vid [[vertex_id]], constant float4 *p [[buffer(0)]]) {\n"
            "  VOut o; o.position = p[vid]; return o;\n"
            "}\n"
            "fragment float4 f_color(constant float4 &color [[buffer(0)]]) { return color; }\n";
}

static NSString *multi_source(void) {
    return @"#include <metal_stdlib>\n"
            "using namespace metal;\n"
            "struct VOut { float4 position [[position]]; uint viewport [[viewport_array_index]]; };\n"
            "vertex VOut v_multi(uint vid [[vertex_id]], constant float4 *p [[buffer(0)]],\n"
            "                    constant uint &viewport [[buffer(1)]]) {\n"
            "  VOut o; o.position = p[vid]; o.viewport = viewport; return o;\n"
            "}\n";
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
    if (!value) { printf("none"); return; }
    const uint8_t *bytes = (const uint8_t *)[[value description] UTF8String];
    print_hex(bytes, strlen((const char *)bytes));
}

static uint32_t float_bits(float value) {
    uint32_t bits;
    memcpy(&bits, &value, sizeof(bits));
    return bits;
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

static void count_colors(const uint8_t *pixels, const uint8_t a[4], const uint8_t b[4],
                         unsigned *count_a, unsigned *count_b, unsigned *clear,
                         unsigned *other) {
    *count_a = *count_b = *clear = *other = 0;
    for (size_t i = 0; i < W * H; ++i) {
        const uint8_t *p = pixels + i * 4;
        if (!memcmp(p, a, 4)) ++*count_a;
        else if (!memcmp(p, b, 4)) ++*count_b;
        else if (!memcmp(p, CLEAR_RGBA, 4)) ++*clear;
        else ++*other;
    }
}

static void get_guarded(id<MTLTexture> texture, uint8_t bytes[GUARDED_BYTES]) {
    fill_guarded(bytes);
    [texture getBytes:bytes + GUARD bytesPerRow:W * 4
            fromRegion:MTLRegionMake2D(0, 0, W, H) mipmapLevel:0];
}

static NSString *command_error(id<MTLCommandBuffer> cb) {
    return [cb error] ? [[cb error] localizedDescription] : nil;
}

static BOOL run_scissor(id<MTLDevice> dev, id<MTLCommandQueue> queue,
                        id<MTLRenderPipelineState> pso, const float positions[12],
                        const ScissorCase *c) {
    id<MTLTexture> color = color_texture(dev);
    if (!color) {
        printf("CASE kind=scissor name=%s accepted=0 status=-1 error_hex=7265736f75726365 color_guarded_hex=none\n", c->name);
        return NO;
    }
    id<MTLCommandBuffer> cb = [queue commandBuffer];
    id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:pass_descriptor(color, nil)];
    NSString *exception = nil;
    @try {
        [enc setRenderPipelineState:pso];
        MTLViewport vp = {0, 0, W, H, 0, 1};
        [enc setViewport:vp];
        MTLScissorRect rect = {c->x, c->y, c->width, c->height};
        [enc setScissorRect:rect];
        [enc setVertexBytes:positions length:sizeof(float) * 12 atIndex:0];
        set_color(enc, SINGLE_RGBA);
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc endEncoding];
    } @catch (NSException *e) {
        exception = [e reason];
        @try { [enc endEncoding]; } @catch (NSException *ignored) { (void)ignored; }
    }
    if (exception) {
        printf("CASE kind=scissor name=%s x=%lu y=%lu width=%lu height=%lu accepted=0 status=-1 error_hex=",
               c->name, (unsigned long)c->x, (unsigned long)c->y,
               (unsigned long)c->width, (unsigned long)c->height);
        print_string_hex(exception);
        printf(" changed=0 clear=0 other=0 guard_errors=0 color_guarded_hex=none\n");
        return YES;
    }
    [cb commit]; [cb waitUntilCompleted];
    NSInteger status = [cb status];
    uint8_t guarded[GUARDED_BYTES];
    get_guarded(color, guarded);
    unsigned changed, unused, clear, other;
    count_colors(guarded + GUARD, SINGLE_RGBA, MULTI1_RGBA, &changed, &unused, &clear, &other);
    printf("CASE kind=scissor name=%s x=%lu y=%lu width=%lu height=%lu accepted=1 status=%ld error_hex=",
           c->name, (unsigned long)c->x, (unsigned long)c->y,
           (unsigned long)c->width, (unsigned long)c->height, (long)status);
    print_string_hex(command_error(cb));
    printf(" changed=%u clear=%u other=%u guard_errors=%u color_guarded_hex=",
           changed, clear, other, guard_errors(guarded));
    print_hex(guarded, sizeof(guarded)); printf("\n");
    return status == MTLCommandBufferStatusCompleted && ![cb error];
}

static BOOL run_multi(id<MTLDevice> dev, id<MTLCommandQueue> queue,
                      id<MTLRenderPipelineState> pso, const float positions[12],
                      const char *name, const MTLScissorRect rects[2]) {
    if (!pso) {
        printf("CASE kind=multi name=%s accepted=0 status=-1 error_hex=756e737570706f72746564 red=0 green=0 clear=0 other=0 guard_errors=0 color_guarded_hex=none\n", name);
        return YES;
    }
    id<MTLTexture> color = color_texture(dev);
    id<MTLCommandBuffer> cb = [queue commandBuffer];
    id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:pass_descriptor(color, nil)];
    NSString *exception = nil;
    @try {
        [enc setRenderPipelineState:pso];
        MTLViewport viewports[2] = {{0, 0, W, H, 0, 1}, {0, 0, W, H, 0, 1}};
        [enc setViewports:viewports count:2];
        [enc setScissorRects:rects count:2];
        [enc setVertexBytes:positions length:sizeof(float) * 12 atIndex:0];
        uint32_t viewport = 0;
        [enc setVertexBytes:&viewport length:sizeof(viewport) atIndex:1];
        set_color(enc, MULTI0_RGBA);
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        viewport = 1;
        [enc setVertexBytes:&viewport length:sizeof(viewport) atIndex:1];
        set_color(enc, MULTI1_RGBA);
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc endEncoding];
    } @catch (NSException *e) {
        exception = [e reason];
        @try { [enc endEncoding]; } @catch (NSException *ignored) { (void)ignored; }
    }
    if (exception) {
        printf("CASE kind=multi name=%s accepted=0 status=-1 error_hex=", name);
        print_string_hex(exception);
        printf(" red=0 green=0 clear=0 other=0 guard_errors=0 color_guarded_hex=none\n");
        return YES;
    }
    [cb commit]; [cb waitUntilCompleted];
    NSInteger status = [cb status];
    uint8_t guarded[GUARDED_BYTES]; get_guarded(color, guarded);
    unsigned red, green, clear, other;
    count_colors(guarded + GUARD, MULTI0_RGBA, MULTI1_RGBA, &red, &green, &clear, &other);
    printf("CASE kind=multi name=%s accepted=1 status=%ld error_hex=", name, (long)status);
    print_string_hex(command_error(cb));
    printf(" red=%u green=%u clear=%u other=%u guard_errors=%u color_guarded_hex=",
           red, green, clear, other, guard_errors(guarded));
    print_hex(guarded, sizeof(guarded)); printf("\n");
    return status == MTLCommandBufferStatusCompleted && ![cb error];
}

static id<MTLDepthStencilState> depth_state(id<MTLDevice> dev,
                                             MTLCompareFunction compare) {
    MTLDepthStencilDescriptor *desc = [MTLDepthStencilDescriptor new];
    desc.depthCompareFunction = compare;
    desc.depthWriteEnabled = YES;
    return [dev newDepthStencilStateWithDescriptor:desc];
}

static BOOL run_bias(id<MTLDevice> dev, id<MTLCommandQueue> queue,
                     id<MTLRenderPipelineState> pso, id<MTLDepthStencilState> always,
                     id<MTLDepthStencilState> less, id<MTLDepthStencilState> greater,
                     const float flat[12], const float sloped[12], const BiasCase *c) {
    id<MTLTexture> color = color_texture(dev);
    id<MTLTexture> depth = depth_texture(dev);
    if (!color || !depth) {
        printf("CASE kind=dbias name=%s accepted=0 status=-1 error_hex=7265736f75726365 color_guarded_hex=none depth_guarded_hex=none\n", c->name);
        return NO;
    }
    const float *positions = c->sloped ? sloped : flat;
    id<MTLCommandBuffer> cb = [queue commandBuffer];
    id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:pass_descriptor(color, depth)];
    NSString *exception = nil;
    @try {
        [enc setRenderPipelineState:pso];
        MTLViewport vp = {0, 0, W, H, 0, 1}; [enc setViewport:vp];
        MTLScissorRect sc = {0, 0, W, H}; [enc setScissorRect:sc];
        [enc setVertexBytes:positions length:sizeof(float) * 12 atIndex:0];
        [enc setDepthStencilState:always];
        [enc setDepthBias:0.0f slopeScale:0.0f clamp:0.0f];
        set_color(enc, BASE_RGBA);
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc setDepthStencilState:(c->compare == MTLCompareFunctionLess ? less : greater)];
        [enc setDepthBias:c->constant_bias slopeScale:c->slope clamp:c->clamp];
        set_color(enc, BIAS_RGBA);
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc endEncoding];
    } @catch (NSException *e) {
        exception = [e reason];
        @try { [enc endEncoding]; } @catch (NSException *ignored) { (void)ignored; }
    }
    if (exception) {
        printf("CASE kind=dbias name=%s geometry=%s compare=%s constant_bits=%08x slope_bits=%08x clamp_bits=%08x accepted=0 status=-1 error_hex=",
               c->name, c->sloped ? "sloped" : "flat", c->compare_name,
               float_bits(c->constant_bias), float_bits(c->slope), float_bits(c->clamp));
        print_string_hex(exception);
        printf(" base=0 biased=0 clear=0 other=0 finite=0 guard_errors=0 color_guarded_hex=none depth_guarded_hex=none\n");
        return YES;
    }
    [cb commit]; [cb waitUntilCompleted];
    NSInteger status = [cb status];
    uint8_t color_bytes[GUARDED_BYTES], depth_bytes[GUARDED_BYTES];
    get_guarded(color, color_bytes); get_guarded(depth, depth_bytes);
    unsigned base, biased, clear, other;
    count_colors(color_bytes + GUARD, BASE_RGBA, BIAS_RGBA, &base, &biased, &clear, &other);
    unsigned finite = 0;
    const float *depth_values = (const float *)(depth_bytes + GUARD);
    for (size_t i = 0; i < W * H; ++i) finite += isfinite(depth_values[i]);
    printf("CASE kind=dbias name=%s geometry=%s compare=%s constant_bits=%08x slope_bits=%08x clamp_bits=%08x accepted=1 status=%ld error_hex=",
           c->name, c->sloped ? "sloped" : "flat", c->compare_name,
           float_bits(c->constant_bias), float_bits(c->slope), float_bits(c->clamp), (long)status);
    print_string_hex(command_error(cb));
    printf(" base=%u biased=%u clear=%u other=%u finite=%u guard_errors=%u color_guarded_hex=",
           base, biased, clear, other, finite,
           guard_errors(color_bytes) + guard_errors(depth_bytes));
    print_hex(color_bytes, sizeof(color_bytes));
    printf(" depth_guarded_hex="); print_hex(depth_bytes, sizeof(depth_bytes)); printf("\n");
    return status == MTLCommandBufferStatusCompleted && ![cb error];
}

static void fatal(NSString *phase, NSError *error) {
    printf("FATAL phase=%s error_hex=", [phase UTF8String]);
    print_string_hex(error ? [error localizedDescription] : @"unknown");
    printf("\nRESULT FAIL\n");
}

int main(void) {
    @autoreleasepool {
        NSError *error = nil;
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (!dev) { printf("FATAL phase=device error_hex=6e6f6e65\nRESULT FAIL\n"); return 1; }
        printf("DEVICE %s\n", [[dev name] UTF8String]);
        printf("SCOPE trace=none compiled_shader_bytes=uninspected integer_bias_selector=absent_public_header\n");

        MTLCompileOptions *options = [MTLCompileOptions new]; options.fastMathEnabled = NO;
        id<MTLLibrary> single_lib = [dev newLibraryWithSource:single_source() options:options error:&error];
        if (!single_lib) { fatal(@"single-library", error); return 1; }
        MTLRenderPipelineDescriptor *single_desc = [MTLRenderPipelineDescriptor new];
        single_desc.vertexFunction = [single_lib newFunctionWithName:@"v_single"];
        single_desc.fragmentFunction = [single_lib newFunctionWithName:@"f_color"];
        single_desc.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA8Unorm;
        id<MTLRenderPipelineState> single_pso = [dev newRenderPipelineStateWithDescriptor:single_desc error:&error];
        if (!single_pso) { fatal(@"single-pipeline", error); return 1; }

        MTLRenderPipelineDescriptor *depth_desc = [single_desc copy];
        depth_desc.depthAttachmentPixelFormat = MTLPixelFormatDepth32Float;
        id<MTLRenderPipelineState> depth_pso = [dev newRenderPipelineStateWithDescriptor:depth_desc error:&error];
        if (!depth_pso) { fatal(@"depth-pipeline", error); return 1; }

        error = nil;
        id<MTLLibrary> multi_lib = [dev newLibraryWithSource:multi_source() options:options error:&error];
        id<MTLRenderPipelineState> multi_pso = nil;
        NSString *multi_error = nil;
        if (multi_lib) {
            MTLRenderPipelineDescriptor *multi_desc = [MTLRenderPipelineDescriptor new];
            multi_desc.vertexFunction = [multi_lib newFunctionWithName:@"v_multi"];
            multi_desc.fragmentFunction = [single_lib newFunctionWithName:@"f_color"];
            multi_desc.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA8Unorm;
            multi_pso = [dev newRenderPipelineStateWithDescriptor:multi_desc error:&error];
        }
        if (!multi_pso) multi_error = error ? [error localizedDescription] : @"multi library unavailable";
        printf("MULTI supported=%u error_hex=", multi_pso ? 1u : 0u);
        print_string_hex(multi_error); printf("\n");

        id<MTLDepthStencilState> always = depth_state(dev, MTLCompareFunctionAlways);
        id<MTLDepthStencilState> less = depth_state(dev, MTLCompareFunctionLess);
        id<MTLDepthStencilState> greater = depth_state(dev, MTLCompareFunctionGreater);
        id<MTLCommandQueue> queue = [dev newCommandQueue];
        if (!always || !less || !greater || !queue) {
            printf("FATAL phase=state error_hex=6e6f6e65\nRESULT FAIL\n"); return 1;
        }

        const float flat[12] = {-1, -1, 0.5f, 1, 3, -1, 0.5f, 1, -1, 3, 0.5f, 1};
        const float sloped[12] = {-1, -1, 0.2f, 1, 3, -1, 0.8f, 1, -1, 3, 0.35f, 1};
        BOOL ok = YES;
        for (size_t i = 0; i < sizeof(SCISSOR_CASES) / sizeof(SCISSOR_CASES[0]); ++i)
            ok &= run_scissor(dev, queue, single_pso, flat, &SCISSOR_CASES[i]);

        const MTLScissorRect multi_base[2] = {{1, 2, 5, 6}, {9, 3, 4, 10}};
        const MTLScissorRect multi_change[2] = {{1, 2, 5, 6}, {11, 8, 3, 5}};
        ok &= run_multi(dev, queue, multi_pso, flat, "multi-base", multi_base);
        ok &= run_multi(dev, queue, multi_pso, flat, "multi-rect1-change", multi_change);

        for (size_t i = 0; i < sizeof(BIAS_CASES) / sizeof(BIAS_CASES[0]); ++i)
            ok &= run_bias(dev, queue, depth_pso, always, less, greater,
                           flat, sloped, &BIAS_CASES[i]);
        printf("RESULT %s\n", ok ? "OK" : "FAIL");
        fflush(stdout);
        return ok ? 0 : 10;
    }
}
