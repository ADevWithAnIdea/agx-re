// render.m -- EXP-0129 HW-PROBE render/dispatch harness (OWN-SHADER + HW-PROBE).
//
// Real draws on the real device, real readbacks, no splicing. One process
// per invocation, one --mode per invocation, prints a single JSON object to
// stdout on success or {"status":"FAIL",...} on any Metal-reported failure.
// Pattern follows EXP-0109/EXP-0117's render.m (our own prior authored code
// in this project).
//
// CLEAN-ROOM: public Metal API only, on our own MSL source.
//
// Build: clang -fobjc-arc -framework Metal -framework Foundation -o render render.m

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !__has_feature(objc_arc)
#error compile with -fobjc-arc
#endif

static void usageDie(const char *m) { fprintf(stderr, "render: %s\n", m); exit(1); }
static void jfail(NSString *stage, NSError *err) {
    NSString *msg = err ? [[err localizedDescription] stringByReplacingOccurrencesOfString:@"\"" withString:@"'"] : @"";
    msg = [msg stringByReplacingOccurrencesOfString:@"\n" withString:@" "];
    printf("{\"status\":\"FAIL\",\"stage\":\"%s\",\"error\":\"%s\"}\n", [stage UTF8String], [msg UTF8String]);
}
static id<MTLDevice> GDEV;
static id<MTLCommandQueue> GQ;
static id<MTLLibrary> GLIB;

static id<MTLFunction> reqFn(NSString *name) {
    id<MTLFunction> f = [GLIB newFunctionWithName:name];
    if (!f) { jfail(@"function", nil); exit(0); }
    return f;
}

enum { O_SRC=128, O_MODE, O_VARIANT, O_MODEBLEND };
static const struct option L[] = {
    {"source",required_argument,0,O_SRC}, {"mode",required_argument,0,O_MODE},
    {"variant",required_argument,0,O_VARIANT}, {"blendmode",required_argument,0,O_MODEBLEND},
    {0,0,0,0}
};

static const unsigned W = 64, H = 64;

int main(int argc, char **argv) { @autoreleasepool {
    const char *srcp = 0, *modep = 0, *variant = "";
    int blendmode = 0;
    int c;
    while ((c = getopt_long(argc, argv, "", L, 0)) > 0) {
        switch (c) {
            case O_SRC: srcp = optarg; break;
            case O_MODE: modep = optarg; break;
            case O_VARIANT: variant = optarg; break;
            case O_MODEBLEND: blendmode = atoi(optarg); break;
        }
    }
    if (!srcp || !modep) usageDie("need --source --mode");
    NSString *m = [NSString stringWithUTF8String:modep];
    NSString *vs = [NSString stringWithUTF8String:variant];

    NSError *err = nil;
    GDEV = MTLCreateSystemDefaultDevice();
    if (!GDEV) usageDie("no device");
    GQ = [GDEV newCommandQueue];
    NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:srcp]
                                               encoding:NSUTF8StringEncoding error:&err];
    if (!src) usageDie("read src");
    MTLCompileOptions *co = [MTLCompileOptions new];
    GLIB = [GDEV newLibraryWithSource:src options:co error:&err];
    if (!GLIB) { jfail(@"compile", err); return 0; }

    // =============================================================== bary
    if ([m isEqualToString:@"bary"]) {
        NSString *vfn = nil, *ffn = nil;
        int natt = 2, needDbg = 0;
        float tags[3] = {10.0f, 20.0f, 30.0f};
        if ([vs isEqualToString:@"base"]) { vfn=@"v_bary"; ffn=@"f_base"; natt=2; }
        else if ([vs isEqualToString:@"pos3"]) { vfn=@"v_bary"; ffn=@"f_pos3"; natt=3; }
        else if ([vs isEqualToString:@"count3_const"]) { vfn=@"v_bary"; ffn=@"f_count3_const"; natt=3; }
        else if ([vs isEqualToString:@"count3_vary"]) { vfn=@"v_bary_extra"; ffn=@"f_count3_vary"; natt=3; }
        else if ([vs isEqualToString:@"pos2"]) { vfn=@"v_bary"; ffn=@"f_pos2"; natt=2; }
        else if ([vs isEqualToString:@"posread_noout"]) { vfn=@"v_bary"; ffn=@"f_posread_noout"; natt=2; needDbg=1; }
        else if ([vs isEqualToString:@"attach3ctrl"]) { vfn=@"v_bary"; ffn=@"f_base"; natt=3; }
        else if ([vs isEqualToString:@"base2"]) { vfn=@"v_bary2"; ffn=@"f_base2"; natt=2; tags[0]=100.0f; tags[1]=-50.0f; tags[2]=7.0f; }
        else if ([vs isEqualToString:@"pos3_2"]) { vfn=@"v_bary2"; ffn=@"f_pos3_2"; natt=3; tags[0]=100.0f; tags[1]=-50.0f; tags[2]=7.0f; }
        else usageDie("unknown --variant for bary mode");

        id<MTLFunction> vf = reqFn(vfn);
        id<MTLFunction> ff = reqFn(ffn);
        MTLTextureDescriptor *t0 = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:W height:H mipmapped:NO];
        t0.usage = MTLTextureUsageRenderTarget; t0.storageMode = MTLStorageModeShared;
        id<MTLTexture> tex[3];
        for (int i = 0; i < natt; i++) tex[i] = [GDEV newTextureWithDescriptor:t0];

        MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new];
        rd.vertexFunction = vf; rd.fragmentFunction = ff;
        for (int i = 0; i < natt; i++) rd.colorAttachments[i].pixelFormat = MTLPixelFormatRGBA32Float;
        id<MTLRenderPipelineState> pso = [GDEV newRenderPipelineStateWithDescriptor:rd error:&err];
        if (!pso) { jfail(@"pipeline", err); return 0; }

        id<MTLBuffer> tbuf = [GDEV newBufferWithBytes:tags length:12 options:MTLResourceStorageModeShared];
        id<MTLBuffer> dbgbuf = nil;
        if (needDbg) dbgbuf = [GDEV newBufferWithLength:16 options:MTLResourceStorageModeShared];

        id<MTLCommandBuffer> cb = [GQ commandBuffer];
        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
        for (int i = 0; i < natt; i++) {
            rp.colorAttachments[i].texture = tex[i];
            rp.colorAttachments[i].loadAction = MTLLoadActionClear;
            rp.colorAttachments[i].clearColor = MTLClearColorMake(-9,-9,-9,-9);
            rp.colorAttachments[i].storeAction = MTLStoreActionStore;
        }
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        [enc setFragmentBuffer:tbuf offset:0 atIndex:0];
        if (needDbg) [enc setFragmentBuffer:dbgbuf offset:0 atIndex:1];
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc endEncoding];
        [cb commit]; [cb waitUntilCompleted];
        if (cb.error) { jfail(@"cmdbuf", cb.error); return 0; }

        float px[3][4];
        for (int i = 0; i < natt; i++)
            [tex[i] getBytes:px[i] bytesPerRow:16*W fromRegion:MTLRegionMake2D(W/2,H/2,1,1) mipmapLevel:0];
        for (int i = natt; i < 3; i++) { px[i][0]=px[i][1]=px[i][2]=px[i][3]=-99.0f; }

        printf("{\"status\":\"OK\",\"mode\":\"bary\",\"variant\":\"%s\",\"natt\":%d,\"w\":%u,\"h\":%u,"
               "\"c0\":[%.8g,%.8g,%.8g,%.8g],\"c1\":[%.8g,%.8g,%.8g,%.8g],\"c2\":[%.8g,%.8g,%.8g,%.8g]}\n",
               variant, natt, W, H,
               px[0][0],px[0][1],px[0][2],px[0][3],
               px[1][0],px[1][1],px[1][2],px[1][3],
               px[2][0],px[2][1],px[2][2],px[2][3]);
        return 0;
    }

    // ======================================================= split epilog
    if ([m isEqualToString:@"splitepilog"]) {
        id<MTLFunction> vf = reqFn(@"v_split_common");
        id<MTLFunction> ff = reqFn(@"f_split_epilog");
        MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:4 height:4 mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget; td.storageMode = MTLStorageModeShared;
        id<MTLTexture> tex = [GDEV newTextureWithDescriptor:td];
        MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new];
        rd.vertexFunction = vf; rd.fragmentFunction = ff;
        rd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA32Float;
        id<MTLRenderPipelineState> pso = [GDEV newRenderPipelineStateWithDescriptor:rd error:&err];
        if (!pso) { jfail(@"pipeline", err); return 0; }

        float srcColor[4] = {0.7f, 0.4f, 0.2f, 0.9f};
        float dstClear[4] = {0.3f, 0.6f, 0.8f, 0.1f};
        struct { float srcF[4]; float dstF[4]; unsigned mode; float _pad[3]; } bp;
        bp.srcF[0]=0.5f; bp.srcF[1]=0.5f; bp.srcF[2]=0.5f; bp.srcF[3]=1.0f;
        bp.dstF[0]=0.25f; bp.dstF[1]=0.25f; bp.dstF[2]=0.25f; bp.dstF[3]=1.0f;
        bp.mode = (unsigned)blendmode;

        id<MTLBuffer> srcBuf = [GDEV newBufferWithBytes:srcColor length:16 options:MTLResourceStorageModeShared];
        id<MTLBuffer> bpBuf = [GDEV newBufferWithBytes:&bp length:sizeof(bp) options:MTLResourceStorageModeShared];

        id<MTLCommandBuffer> cb = [GQ commandBuffer];
        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
        rp.colorAttachments[0].texture = tex;
        rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].clearColor = MTLClearColorMake(dstClear[0],dstClear[1],dstClear[2],dstClear[3]);
        rp.colorAttachments[0].storeAction = MTLStoreActionStore;
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        [enc setFragmentBuffer:srcBuf offset:0 atIndex:0];
        [enc setFragmentBuffer:bpBuf offset:0 atIndex:1];
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc endEncoding];
        [cb commit]; [cb waitUntilCompleted];
        if (cb.error) { jfail(@"cmdbuf", cb.error); return 0; }

        float px[4];
        [tex getBytes:px bytesPerRow:16*4 fromRegion:MTLRegionMake2D(2,2,1,1) mipmapLevel:0];
        printf("{\"status\":\"OK\",\"mode\":\"splitepilog\",\"blendmode\":%d,"
               "\"src\":[%.8g,%.8g,%.8g,%.8g],\"dst\":[%.8g,%.8g,%.8g,%.8g],"
               "\"srcFactor\":[%.8g,%.8g,%.8g,%.8g],\"dstFactor\":[%.8g,%.8g,%.8g,%.8g],"
               "\"result\":[%.8g,%.8g,%.8g,%.8g]}\n",
               blendmode, srcColor[0],srcColor[1],srcColor[2],srcColor[3],
               dstClear[0],dstClear[1],dstClear[2],dstClear[3],
               bp.srcF[0],bp.srcF[1],bp.srcF[2],bp.srcF[3],
               bp.dstF[0],bp.dstF[1],bp.dstF[2],bp.dstF[3],
               px[0],px[1],px[2],px[3]);
        return 0;
    }

    // ============================================================ negctrl
    // Numeric check for kernels/split_negctrl.metal: does an entry-only
    // attribute ([[color(0)]]) on a non-entry helper's parameter actually
    // deliver the tile-read value (forwarded ordinary argument), or
    // something else (uninitialized / re-invoked mechanism)?
    if ([m isEqualToString:@"negctrl"]) {
        id<MTLFunction> vf = reqFn(@"v_negctrl");
        id<MTLFunction> ff = reqFn(@"f_negctrl_caller");
        MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:4 height:4 mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget; td.storageMode = MTLStorageModeShared;
        id<MTLTexture> tex = [GDEV newTextureWithDescriptor:td];
        MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new];
        rd.vertexFunction = vf; rd.fragmentFunction = ff;
        rd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA32Float;
        id<MTLRenderPipelineState> pso = [GDEV newRenderPipelineStateWithDescriptor:rd error:&err];
        if (!pso) { jfail(@"pipeline", err); return 0; }
        float clearv[4] = {0.11f, 0.22f, 0.33f, 0.44f};
        id<MTLCommandBuffer> cb = [GQ commandBuffer];
        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
        rp.colorAttachments[0].texture = tex;
        rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].clearColor = MTLClearColorMake(clearv[0],clearv[1],clearv[2],clearv[3]);
        rp.colorAttachments[0].storeAction = MTLStoreActionStore;
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc endEncoding];
        [cb commit]; [cb waitUntilCompleted];
        if (cb.error) { jfail(@"cmdbuf", cb.error); return 0; }
        float px[4];
        [tex getBytes:px bytesPerRow:16*4 fromRegion:MTLRegionMake2D(2,2,1,1) mipmapLevel:0];
        printf("{\"status\":\"OK\",\"mode\":\"negctrl\",\"clear\":[%.8g,%.8g,%.8g,%.8g],\"result\":[%.8g,%.8g,%.8g,%.8g]}\n",
               clearv[0],clearv[1],clearv[2],clearv[3], px[0],px[1],px[2],px[3]);
        return 0;
    }

    // ======================================================= split prolog
    if ([m isEqualToString:@"splitprolog"]) {
        id<MTLFunction> vf = reqFn(@"v_split_prolog");
        MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new];
        rd.vertexFunction = vf;
        rd.rasterizationEnabled = NO;
        id<MTLRenderPipelineState> pso = [GDEV newRenderPipelineStateWithDescriptor:rd error:&err];
        if (!pso) { jfail(@"pipeline", err); return 0; }

        // 6 in-range indices (4-byte tightly-packed uchar4 stride, matching
        // EXP-0109's vsfetch_hw_inrange), + 1 deliberately out-of-range
        // index (nvert+50) as a paired positive/negative control, exactly
        // as EXP-0109 S1.3 did for the INLINE fetch case -- here for the
        // genuinely CALLED fetch_attr().
        unsigned char vbuf[6*4];
        for (int i = 0; i < 6; i++) for (int k = 0; k < 4; k++) vbuf[i*4+k] = (unsigned char)(i*40 + k);
        id<MTLBuffer> vBuf = [GDEV newBufferWithBytes:vbuf length:sizeof(vbuf) options:MTLResourceStorageModeShared];
        unsigned zero = 0;
        id<MTLBuffer> cBuf = [GDEV newBufferWithBytes:&zero length:4 options:MTLResourceStorageModeShared];
        id<MTLBuffer> oBuf = [GDEV newBufferWithLength:7*32 options:MTLResourceStorageModeShared]; // FetchRec padded generously
        memset(oBuf.contents, 0xEE, 7*32); // poison pattern, distinguishable from any real fetch

        uint32_t idx[7] = {0,1,2,3,4,5, 56}; // index 6 = deliberate OOB (buffer holds 6 elements)
        id<MTLBuffer> iBuf = [GDEV newBufferWithBytes:idx length:sizeof(idx) options:MTLResourceStorageModeShared];

        id<MTLCommandBuffer> cb = [GQ commandBuffer];
        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
        rp.renderTargetWidth = 1; rp.renderTargetHeight = 1; rp.defaultRasterSampleCount = 1;
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        [enc setVertexBuffer:vBuf offset:0 atIndex:0];
        [enc setVertexBuffer:cBuf offset:0 atIndex:1];
        [enc setVertexBuffer:oBuf offset:0 atIndex:2];
        [enc drawIndexedPrimitives:MTLPrimitiveTypePoint indexCount:7 indexType:MTLIndexTypeUInt32
                        indexBuffer:iBuf indexBufferOffset:0];
        [enc endEncoding];
        [cb commit]; [cb waitUntilCompleted];
        if (cb.error) { jfail(@"cmdbuf", cb.error); return 0; }

        unsigned char *base = (unsigned char *)oBuf.contents;
        NSMutableString *recs = [NSMutableString stringWithString:@"["];
        for (int i = 0; i < 7; i++) {
            float attr[4]; memcpy(attr, base + i*32, 16);
            uint32_t vid; memcpy(&vid, base + i*32 + 16, 4);
            [recs appendFormat:@"%s{\"attr\":[%.8g,%.8g,%.8g,%.8g],\"vid\":%u}", i?",":"", attr[0],attr[1],attr[2],attr[3], vid];
        }
        [recs appendString:@"]"];
        printf("{\"status\":\"OK\",\"mode\":\"splitprolog\",\"records\":%s}\n", [recs UTF8String]);
        return 0;
    }

    printf("{\"status\":\"FAIL\",\"stage\":\"mode\",\"error\":\"unknown mode\"}\n");
    return 0;
}}
