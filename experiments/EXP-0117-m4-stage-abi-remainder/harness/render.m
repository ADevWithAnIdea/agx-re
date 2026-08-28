// render.m -- EXP-0117 HW-PROBE render/dispatch harness (OWN-SHADER + HW-PROBE).
//
// Real draws/dispatches on the real device, real readbacks, no splicing.
// One process per invocation, one --mode per invocation, prints a single
// JSON object to stdout on success or {"status":"FAIL",...} on any
// Metal-reported failure. Multi-mode in one binary (build-count economy),
// following EXP-0109's harness/render_probe.m convention.
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
#include <math.h>

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

enum { O_SRC=128, O_MODE, O_CASE, O_W, O_H, O_SAMPLES, O_NATT, O_CFMT,
       O_SRCR, O_SRCG, O_SRCB, O_SRCA, O_DSTR, O_DSTG, O_DSTB, O_DSTA,
       O_SR, O_DR, O_SA, O_DA, O_RGBOP, O_AOP, O_MASK,
       O_CONSTR, O_CONSTG, O_CONSTB, O_CONSTA, O_BLEND,
       O_UVAL, O_UVAL2, O_FRAG, O_FRAG2, O_MASKVAL, O_SVAL, O_STYPE,
       O_PASSDEPTH, O_FAILDEPTH, O_DEPTHFAILOP, O_DEPTHPASSOP, O_STENCILREF,
       O_A2C, O_A2O, O_SRC1R, O_SRC1G, O_SRC1B, O_SRC1A };

static const struct option L[] = {
    {"source", required_argument,0,O_SRC}, {"mode",required_argument,0,O_MODE}, {"case",required_argument,0,O_CASE},
    {"w",required_argument,0,O_W}, {"h",required_argument,0,O_H}, {"samples",required_argument,0,O_SAMPLES},
    {"natt",required_argument,0,O_NATT}, {"colorformat",required_argument,0,O_CFMT},
    {"srcr",required_argument,0,O_SRCR},{"srcg",required_argument,0,O_SRCG},{"srcb",required_argument,0,O_SRCB},{"srca",required_argument,0,O_SRCA},
    {"dstr",required_argument,0,O_DSTR},{"dstg",required_argument,0,O_DSTG},{"dstb",required_argument,0,O_DSTB},{"dsta",required_argument,0,O_DSTA},
    {"sr",required_argument,0,O_SR},{"dr",required_argument,0,O_DR},{"sa",required_argument,0,O_SA},{"da",required_argument,0,O_DA},
    {"rgbop",required_argument,0,O_RGBOP},{"aop",required_argument,0,O_AOP},{"mask",required_argument,0,O_MASK},
    {"constr",required_argument,0,O_CONSTR},{"constg",required_argument,0,O_CONSTG},{"constb",required_argument,0,O_CONSTB},{"consta",required_argument,0,O_CONSTA},
    {"blendenabled",required_argument,0,O_BLEND},
    {"uval",required_argument,0,O_UVAL},{"uval2",required_argument,0,O_UVAL2},
    {"fragment",required_argument,0,O_FRAG},{"fragment2",required_argument,0,O_FRAG2},
    {"maskval",required_argument,0,O_MASKVAL},
    {"sval",required_argument,0,O_SVAL},{"stype",required_argument,0,O_STYPE},
    {"passdepth",required_argument,0,O_PASSDEPTH},{"faildepth",required_argument,0,O_FAILDEPTH},
    {"depthfailop",required_argument,0,O_DEPTHFAILOP},{"depthpassop",required_argument,0,O_DEPTHPASSOP},
    {"stencilref",required_argument,0,O_STENCILREF},
    {"a2c",required_argument,0,O_A2C},{"a2o",required_argument,0,O_A2O},
    {"src1r",required_argument,0,O_SRC1R},{"src1g",required_argument,0,O_SRC1G},
    {"src1b",required_argument,0,O_SRC1B},{"src1a",required_argument,0,O_SRC1A},
    {0,0,0,0}
};

int main(int argc, char **argv) { @autoreleasepool {
    const char *srcp=0, *mode=0, *casename="case";
    unsigned W=4,H=4,samples=1,natt=1;
    unsigned long cfmt = 125; // RGBA32Float
    double srcr=1,srcg=1,srcb=1,srca=1, dstr=0,dstg=0,dstb=0,dsta=0;
    unsigned long sr=1,dr=0,sa=1,da=0,rgbop=0,aop=0,mask=0xf;
    double constr=0,constg=0,constb=0,consta=0;
    int blendEnabled=1;
    unsigned long uval=0, uval2=0, maskval=0xf;
    const char *fragName=0, *fragName2=0;
    long long sval=0; const char *stype="u32";
    double passdepth=0.2, faildepth=0.8;
    unsigned long depthfailop=0 /*Keep*/, depthpassop=2 /*Replace*/;
    unsigned stencilref=100;
    int a2c=0, a2o=0;
    double src1r=1,src1g=1,src1b=1,src1a=1;
    int c;
    while ((c = getopt_long(argc, argv, "", L, 0)) > 0) {
        switch (c) {
            case O_SRC: srcp=optarg; break; case O_MODE: mode=optarg; break; case O_CASE: casename=optarg; break;
            case O_W: W=(unsigned)strtoul(optarg,0,0); break; case O_H: H=(unsigned)strtoul(optarg,0,0); break;
            case O_SAMPLES: samples=(unsigned)strtoul(optarg,0,0); break; case O_NATT: natt=(unsigned)strtoul(optarg,0,0); break;
            case O_CFMT: cfmt=strtoul(optarg,0,0); break;
            case O_SRCR: srcr=atof(optarg); break; case O_SRCG: srcg=atof(optarg); break; case O_SRCB: srcb=atof(optarg); break; case O_SRCA: srca=atof(optarg); break;
            case O_DSTR: dstr=atof(optarg); break; case O_DSTG: dstg=atof(optarg); break; case O_DSTB: dstb=atof(optarg); break; case O_DSTA: dsta=atof(optarg); break;
            case O_SR: sr=strtoul(optarg,0,0); break; case O_DR: dr=strtoul(optarg,0,0); break;
            case O_SA: sa=strtoul(optarg,0,0); break; case O_DA: da=strtoul(optarg,0,0); break;
            case O_RGBOP: rgbop=strtoul(optarg,0,0); break; case O_AOP: aop=strtoul(optarg,0,0); break;
            case O_MASK: mask=strtoul(optarg,0,0); break;
            case O_CONSTR: constr=atof(optarg); break; case O_CONSTG: constg=atof(optarg); break;
            case O_CONSTB: constb=atof(optarg); break; case O_CONSTA: consta=atof(optarg); break;
            case O_BLEND: blendEnabled=atoi(optarg); break;
            case O_UVAL: uval=strtoul(optarg,0,0); break; case O_UVAL2: uval2=strtoul(optarg,0,0); break;
            case O_FRAG: fragName=optarg; break; case O_FRAG2: fragName2=optarg; break;
            case O_MASKVAL: maskval=strtoul(optarg,0,0); break;
            case O_SVAL: sval=strtoll(optarg,0,0); break; case O_STYPE: stype=optarg; break;
            case O_PASSDEPTH: passdepth=atof(optarg); break; case O_FAILDEPTH: faildepth=atof(optarg); break;
            case O_DEPTHFAILOP: depthfailop=strtoul(optarg,0,0); break; case O_DEPTHPASSOP: depthpassop=strtoul(optarg,0,0); break;
            case O_STENCILREF: stencilref=(unsigned)strtoul(optarg,0,0); break;
            case O_A2C: a2c=atoi(optarg); break; case O_A2O: a2o=atoi(optarg); break;
            case O_SRC1R: src1r=atof(optarg); break; case O_SRC1G: src1g=atof(optarg); break;
            case O_SRC1B: src1b=atof(optarg); break; case O_SRC1A: src1a=atof(optarg); break;
        }
    }
    if (!srcp || !mode) usageDie("need --source and --mode");

    NSError *err=nil;
    GDEV = MTLCreateSystemDefaultDevice();
    if (!GDEV) usageDie("no device");
    GQ = [GDEV newCommandQueue];
    NSString *src = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:srcp] encoding:NSUTF8StringEncoding error:&err];
    if (!src) usageDie("read src");
    MTLCompileOptions *co = [MTLCompileOptions new];
    GLIB = [GDEV newLibraryWithSource:src options:co error:&err];
    if (!GLIB) { jfail(@"compile", err); return 0; }
    NSString *m = [NSString stringWithUTF8String:mode];

    // ============================================================ blendrender
    if ([m isEqualToString:@"blendrender"]) {
        id<MTLFunction> vf = reqFn(@"v_full");
        id<MTLFunction> ff = reqFn(fragName ? [NSString stringWithUTF8String:fragName] : @"f_solid");
        MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:(MTLPixelFormat)cfmt width:W height:H mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget; td.storageMode = MTLStorageModeShared;
        id<MTLTexture> tex = [GDEV newTextureWithDescriptor:td];
        MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new];
        rd.vertexFunction = vf; rd.fragmentFunction = ff;
        rd.colorAttachments[0].pixelFormat = (MTLPixelFormat)cfmt;
        rd.colorAttachments[0].blendingEnabled = blendEnabled ? YES : NO;
        rd.colorAttachments[0].sourceRGBBlendFactor = (MTLBlendFactor)sr;
        rd.colorAttachments[0].destinationRGBBlendFactor = (MTLBlendFactor)dr;
        rd.colorAttachments[0].sourceAlphaBlendFactor = (MTLBlendFactor)sa;
        rd.colorAttachments[0].destinationAlphaBlendFactor = (MTLBlendFactor)da;
        rd.colorAttachments[0].rgbBlendOperation = (MTLBlendOperation)rgbop;
        rd.colorAttachments[0].alphaBlendOperation = (MTLBlendOperation)aop;
        rd.colorAttachments[0].writeMask = (MTLColorWriteMask)mask;
        id<MTLRenderPipelineState> pso = [GDEV newRenderPipelineStateWithDescriptor:rd error:&err];
        if (!pso) { jfail(@"pipeline", err); return 0; }
        float srcv[4] = {(float)srcr,(float)srcg,(float)srcb,(float)srca};
        id<MTLBuffer> sbuf = [GDEV newBufferWithBytes:srcv length:16 options:MTLResourceStorageModeShared];
        float src1v[4] = {(float)src1r,(float)src1g,(float)src1b,(float)src1a};
        id<MTLBuffer> s1buf = [GDEV newBufferWithBytes:src1v length:16 options:MTLResourceStorageModeShared];
        id<MTLCommandBuffer> cb = [GQ commandBuffer];
        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
        rp.colorAttachments[0].texture = tex;
        rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].clearColor = MTLClearColorMake(dstr,dstg,dstb,dsta);
        rp.colorAttachments[0].storeAction = MTLStoreActionStore;
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        [enc setBlendColorRed:(float)constr green:(float)constg blue:(float)constb alpha:(float)consta];
        [enc setFragmentBuffer:sbuf offset:0 atIndex:0];
        [enc setFragmentBuffer:s1buf offset:0 atIndex:1]; // harmless no-op for functions without a buffer(1) argument
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc endEncoding];
        [cb commit]; [cb waitUntilCompleted];
        if (cb.error) { jfail(@"cmdbuf", cb.error); return 0; }
        // Readback as raw bytes; caller (analysis/decode.py) interprets by cfmt.
        NSUInteger bpp = (cfmt==125)?16:(cfmt==115)?8:(cfmt==70||cfmt==71||cfmt==73)?4:16;
        NSMutableData *buf = [NSMutableData dataWithLength:bpp*W*H];
        [tex getBytes:[buf mutableBytes] bytesPerRow:bpp*W fromRegion:MTLRegionMake2D(0,0,W,H) mipmapLevel:0];
        const uint8_t *bytes = (const uint8_t*)[buf bytes];
        NSMutableString *hex = [NSMutableString string];
        for (NSUInteger i=0;i<bpp;i++) [hex appendFormat:@"%02x", bytes[(H/2)*bpp*W + (W/2)*bpp + i]]; // center texel
        printf("{\"status\":\"OK\",\"mode\":\"blendrender\",\"case\":\"%s\",\"cfmt\":%lu,\"bpp\":%lu,\"center_hex\":\"%s\"}\n",
               casename, cfmt, (unsigned long)bpp, [hex UTF8String]);
        return 0;
    }

    // ============================================================= mrtapiceil
    // Pure API-surface probe: does INDEXING colorAttachments[N-1] (the
    // MTLRenderPipelineColorAttachmentDescriptorArray accessor itself, no
    // pipeline creation, no shader function requirement) raise past the
    // documented 8-slot array -- independent of whether we authored a
    // matching N-output fragment function.
    if ([m isEqualToString:@"mrtapiceil"]) {
        @try {
            MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new];
            MTLRenderPipelineColorAttachmentDescriptor *a = rd.colorAttachments[natt-1];
            a.pixelFormat = MTLPixelFormatRGBA16Float;
            printf("{\"status\":\"OK\",\"mode\":\"mrtapiceil\",\"case\":\"%s\",\"natt\":%u,\"outcome\":\"INDEX_OK\"}\n", casename, natt);
        } @catch (NSException *e) {
            printf("{\"status\":\"OK\",\"mode\":\"mrtapiceil\",\"case\":\"%s\",\"natt\":%u,\"outcome\":\"OBJC_EXCEPTION\",\"error\":\"%s\"}\n",
                   casename, natt, [[[e reason] stringByReplacingOccurrencesOfString:@"\"" withString:@"'"] UTF8String]);
        }
        return 0;
    }

    // ================================================================ mrtceil
    if ([m isEqualToString:@"mrtceil"]) {
        @try {
            NSString *fname = [NSString stringWithFormat:@"f_mrt%u", natt];
            id<MTLFunction> vf = reqFn(@"v_mrt");
            id<MTLFunction> ff = [GLIB newFunctionWithName:fname];
            if (!ff) { printf("{\"status\":\"OK\",\"mode\":\"mrtceil\",\"case\":\"%s\",\"natt\":%u,\"outcome\":\"NO_SUCH_FUNCTION\"}\n", casename, natt); return 0; }
            MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new];
            rd.vertexFunction = vf; rd.fragmentFunction = ff;
            NSMutableArray *texs = [NSMutableArray array];
            for (unsigned i=0;i<natt;i++) {
                rd.colorAttachments[i].pixelFormat = MTLPixelFormatRGBA16Float;
                MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA16Float width:4 height:4 mipmapped:NO];
                td.usage = MTLTextureUsageRenderTarget; td.storageMode = MTLStorageModeShared;
                [texs addObject:[GDEV newTextureWithDescriptor:td]];
            }
            id<MTLRenderPipelineState> pso = [GDEV newRenderPipelineStateWithDescriptor:rd error:&err];
            if (!pso) { printf("{\"status\":\"OK\",\"mode\":\"mrtceil\",\"case\":\"%s\",\"natt\":%u,\"outcome\":\"PIPELINE_CREATE_FAIL\",\"error\":\"%s\"}\n",
                               casename, natt, [[[err localizedDescription] stringByReplacingOccurrencesOfString:@"\"" withString:@"'"] UTF8String]); return 0; }
            id<MTLCommandBuffer> cb = [GQ commandBuffer];
            MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
            for (unsigned i=0;i<natt;i++) {
                rp.colorAttachments[i].texture = texs[i];
                rp.colorAttachments[i].loadAction = MTLLoadActionClear;
                rp.colorAttachments[i].clearColor = MTLClearColorMake(0.111,0.111,0.111,0.111);
                rp.colorAttachments[i].storeAction = MTLStoreActionStore;
            }
            id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
            [enc setRenderPipelineState:pso];
            [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
            [enc endEncoding];
            [cb commit]; [cb waitUntilCompleted];
            if (cb.error) { printf("{\"status\":\"OK\",\"mode\":\"mrtceil\",\"case\":\"%s\",\"natt\":%u,\"outcome\":\"CMDBUF_ERROR\",\"error\":\"%s\"}\n",
                               casename, natt, [[[cb.error localizedDescription] stringByReplacingOccurrencesOfString:@"\"" withString:@"'"] UTF8String]); return 0; }
            NSMutableString *outj = [NSMutableString string];
            for (unsigned i=0;i<natt;i++) {
                uint16_t px[4];
                [texs[i] getBytes:px bytesPerRow:8 fromRegion:MTLRegionMake2D(2,2,1,1) mipmapLevel:0];
                [outj appendFormat:@"%s{\"att\":%u,\"half_bits\":[%u,%u,%u,%u]}", i?",":"", i, px[0],px[1],px[2],px[3]];
            }
            printf("{\"status\":\"OK\",\"mode\":\"mrtceil\",\"case\":\"%s\",\"natt\":%u,\"outcome\":\"RENDERED\",\"targets\":[%s]}\n", casename, natt, [outj UTF8String]);
        } @catch (NSException *e) {
            printf("{\"status\":\"OK\",\"mode\":\"mrtceil\",\"case\":\"%s\",\"natt\":%u,\"outcome\":\"OBJC_EXCEPTION\",\"error\":\"%s\"}\n",
                   casename, natt, [[[e reason] stringByReplacingOccurrencesOfString:@"\"" withString:@"'"] UTF8String]);
        }
        return 0;
    }

    // ================================================================== logic
    if ([m isEqualToString:@"logic"]) {
        id<MTLFunction> vf = reqFn(@"v_full");
        id<MTLFunction> ff = reqFn([NSString stringWithUTF8String:fragName]);
        MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatR32Uint width:W height:H mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget; td.storageMode = MTLStorageModeShared;
        id<MTLTexture> tex = [GDEV newTextureWithDescriptor:td];
        // Pass 1: write a known dst pattern directly (no blend semantics involved -- avoids
        // relying on clearColor's integer-format reinterpretation, which is unconfirmed
        // in the surveyed public docs).
        id<MTLFunction> wfn = reqFn(@"f_logic_copy");
        MTLRenderPipelineDescriptor *rd1 = [MTLRenderPipelineDescriptor new];
        rd1.vertexFunction = vf; rd1.fragmentFunction = wfn;
        rd1.colorAttachments[0].pixelFormat = MTLPixelFormatR32Uint;
        id<MTLRenderPipelineState> pso1 = [GDEV newRenderPipelineStateWithDescriptor:rd1 error:&err];
        if (!pso1) { jfail(@"pipeline1", err); return 0; }
        uint32_t dstv = (uint32_t)uval2;
        id<MTLBuffer> dstbuf = [GDEV newBufferWithBytes:&dstv length:4 options:MTLResourceStorageModeShared];
        id<MTLCommandBuffer> cb1 = [GQ commandBuffer];
        MTLRenderPassDescriptor *rp1 = [MTLRenderPassDescriptor renderPassDescriptor];
        rp1.colorAttachments[0].texture = tex;
        rp1.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp1.colorAttachments[0].clearColor = MTLClearColorMake(0,0,0,0);
        rp1.colorAttachments[0].storeAction = MTLStoreActionStore;
        id<MTLRenderCommandEncoder> enc1 = [cb1 renderCommandEncoderWithDescriptor:rp1];
        [enc1 setRenderPipelineState:pso1];
        [enc1 setFragmentBuffer:dstbuf offset:0 atIndex:0];
        [enc1 drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc1 endEncoding];
        [cb1 commit]; [cb1 waitUntilCompleted];
        if (cb1.error) { jfail(@"cmdbuf1", cb1.error); return 0; }
        // Pass 2: LoadActionLoad (preserve dst), run the epilog function which reads
        // [[color(0)]] (tile_read) and writes the computed result.
        MTLRenderPipelineDescriptor *rd2 = [MTLRenderPipelineDescriptor new];
        rd2.vertexFunction = vf; rd2.fragmentFunction = ff;
        rd2.colorAttachments[0].pixelFormat = MTLPixelFormatR32Uint;
        id<MTLRenderPipelineState> pso2 = [GDEV newRenderPipelineStateWithDescriptor:rd2 error:&err];
        if (!pso2) { jfail(@"pipeline2", err); return 0; }
        uint32_t srcv = (uint32_t)uval;
        id<MTLBuffer> srcbuf = [GDEV newBufferWithBytes:&srcv length:4 options:MTLResourceStorageModeShared];
        id<MTLCommandBuffer> cb2 = [GQ commandBuffer];
        MTLRenderPassDescriptor *rp2 = [MTLRenderPassDescriptor renderPassDescriptor];
        rp2.colorAttachments[0].texture = tex;
        rp2.colorAttachments[0].loadAction = MTLLoadActionLoad;
        rp2.colorAttachments[0].storeAction = MTLStoreActionStore;
        id<MTLRenderCommandEncoder> enc2 = [cb2 renderCommandEncoderWithDescriptor:rp2];
        [enc2 setRenderPipelineState:pso2];
        [enc2 setFragmentBuffer:srcbuf offset:0 atIndex:0];
        [enc2 drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc2 endEncoding];
        [cb2 commit]; [cb2 waitUntilCompleted];
        if (cb2.error) { jfail(@"cmdbuf2", cb2.error); return 0; }
        uint32_t result;
        [tex getBytes:&result bytesPerRow:4*W fromRegion:MTLRegionMake2D(W/2,H/2,1,1) mipmapLevel:0];
        printf("{\"status\":\"OK\",\"mode\":\"logic\",\"case\":\"%s\",\"fragment\":\"%s\",\"src\":%u,\"dst\":%u,\"result\":%u}\n",
               casename, fragName, srcv, dstv, result);
        return 0;
    }

    // =================================================================== a2c
    if ([m isEqualToString:@"a2c"]) {
        id<MTLFunction> vf = reqFn(@"v_full");
        id<MTLFunction> ff = reqFn(@"f_alpha_out");
        MTLTextureDescriptor *mtd = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:W height:H mipmapped:NO];
        mtd.usage = MTLTextureUsageRenderTarget; mtd.storageMode = MTLStorageModeShared;
        BOOL ms = samples > 1;
        if (ms) { mtd.textureType = MTLTextureType2DMultisample; mtd.sampleCount = samples; }
        id<MTLTexture> mstex = [GDEV newTextureWithDescriptor:mtd];
        id<MTLTexture> restex = mstex;
        if (ms) {
            MTLTextureDescriptor *rtd = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:W height:H mipmapped:NO];
            rtd.usage = MTLTextureUsageRenderTarget; rtd.storageMode = MTLStorageModeShared;
            restex = [GDEV newTextureWithDescriptor:rtd];
        }
        MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new];
        rd.vertexFunction = vf; rd.fragmentFunction = ff;
        rd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA32Float;
        rd.rasterSampleCount = samples;
        rd.alphaToCoverageEnabled = a2c ? YES : NO;
        rd.alphaToOneEnabled = a2o ? YES : NO;
        id<MTLRenderPipelineState> pso = [GDEV newRenderPipelineStateWithDescriptor:rd error:&err];
        if (!pso) { jfail(@"pipeline", err); return 0; }
        float srcv[4] = {(float)srcr,(float)srcg,(float)srcb,(float)srca};
        id<MTLBuffer> sbuf = [GDEV newBufferWithBytes:srcv length:16 options:MTLResourceStorageModeShared];
        id<MTLCommandBuffer> cb = [GQ commandBuffer];
        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
        rp.colorAttachments[0].texture = mstex;
        rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].clearColor = MTLClearColorMake(0,0,0,0);
        if (ms) { rp.colorAttachments[0].resolveTexture = restex; rp.colorAttachments[0].storeAction = MTLStoreActionMultisampleResolve; }
        else { rp.colorAttachments[0].storeAction = MTLStoreActionStore; }
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        [enc setFragmentBuffer:sbuf offset:0 atIndex:0];
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc endEncoding];
        [cb commit]; [cb waitUntilCompleted];
        if (cb.error) { jfail(@"cmdbuf", cb.error); return 0; }
        float px[4];
        [restex getBytes:px bytesPerRow:16*W fromRegion:MTLRegionMake2D(W/2,H/2,1,1) mipmapLevel:0];
        printf("{\"status\":\"OK\",\"mode\":\"a2c\",\"case\":\"%s\",\"samples\":%u,\"a2c\":%d,\"a2o\":%d,\"src\":[%.6g,%.6g,%.6g,%.6g],\"resolved\":[%.6g,%.6g,%.6g,%.6g]}\n",
               casename, samples, a2c, a2o, srcr,srcg,srcb,srca, px[0],px[1],px[2],px[3]);
        return 0;
    }

    // =================================================================== srgb
    if ([m isEqualToString:@"srgb"]) {
        id<MTLFunction> vf = reqFn(@"v_full");
        id<MTLFunction> ff = reqFn(@"f_solid");
        MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:(MTLPixelFormat)cfmt width:W height:H mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget; td.storageMode = MTLStorageModeShared;
        id<MTLTexture> tex = [GDEV newTextureWithDescriptor:td];
        MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new];
        rd.vertexFunction = vf; rd.fragmentFunction = ff;
        rd.colorAttachments[0].pixelFormat = (MTLPixelFormat)cfmt;
        rd.colorAttachments[0].blendingEnabled = blendEnabled ? YES : NO;
        rd.colorAttachments[0].sourceRGBBlendFactor = (MTLBlendFactor)sr;
        rd.colorAttachments[0].destinationRGBBlendFactor = (MTLBlendFactor)dr;
        rd.colorAttachments[0].sourceAlphaBlendFactor = (MTLBlendFactor)sa;
        rd.colorAttachments[0].destinationAlphaBlendFactor = (MTLBlendFactor)da;
        id<MTLRenderPipelineState> pso = [GDEV newRenderPipelineStateWithDescriptor:rd error:&err];
        if (!pso) { jfail(@"pipeline", err); return 0; }
        float srcv[4] = {(float)srcr,(float)srcg,(float)srcb,(float)srca};
        id<MTLBuffer> sbuf = [GDEV newBufferWithBytes:srcv length:16 options:MTLResourceStorageModeShared];
        id<MTLCommandBuffer> cb = [GQ commandBuffer];
        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
        rp.colorAttachments[0].texture = tex;
        rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].clearColor = MTLClearColorMake(dstr,dstg,dstb,dsta);
        rp.colorAttachments[0].storeAction = MTLStoreActionStore;
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        [enc setFragmentBuffer:sbuf offset:0 atIndex:0];
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc endEncoding];
        [cb commit]; [cb waitUntilCompleted];
        if (cb.error) { jfail(@"cmdbuf", cb.error); return 0; }
        uint8_t px[4];
        [tex getBytes:px bytesPerRow:4*W fromRegion:MTLRegionMake2D(W/2,H/2,1,1) mipmapLevel:0];
        printf("{\"status\":\"OK\",\"mode\":\"srgb\",\"case\":\"%s\",\"cfmt\":%lu,\"src\":[%.6g,%.6g,%.6g,%.6g],\"dst\":[%.6g,%.6g,%.6g,%.6g],\"stored_u8\":[%u,%u,%u,%u]}\n",
               casename, cfmt, srcr,srcg,srcb,srca, dstr,dstg,dstb,dsta, px[0],px[1],px[2],px[3]);
        return 0;
    }

    // =================================================================== nan
    if ([m isEqualToString:@"nan"]) {
        id<MTLFunction> vf = reqFn(@"v_full");
        id<MTLFunction> ff = reqFn(@"f_solid");
        MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:W height:H mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget; td.storageMode = MTLStorageModeShared;
        id<MTLTexture> tex = [GDEV newTextureWithDescriptor:td];
        MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new];
        rd.vertexFunction = vf; rd.fragmentFunction = ff;
        rd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA32Float;
        rd.colorAttachments[0].blendingEnabled = blendEnabled ? YES : NO;
        rd.colorAttachments[0].sourceRGBBlendFactor = (MTLBlendFactor)sr;
        rd.colorAttachments[0].destinationRGBBlendFactor = (MTLBlendFactor)dr;
        rd.colorAttachments[0].sourceAlphaBlendFactor = (MTLBlendFactor)sa;
        rd.colorAttachments[0].destinationAlphaBlendFactor = (MTLBlendFactor)da;
        id<MTLRenderPipelineState> pso = [GDEV newRenderPipelineStateWithDescriptor:rd error:&err];
        if (!pso) { jfail(@"pipeline", err); return 0; }
        union { uint32_t u; float f; } bits; bits.u = (uint32_t)uval; // caller supplies exact NaN/Inf bit pattern
        float srcv[4] = {bits.f, 0.0f, 0.0f, 1.0f};
        id<MTLBuffer> sbuf = [GDEV newBufferWithBytes:srcv length:16 options:MTLResourceStorageModeShared];
        id<MTLCommandBuffer> cb = [GQ commandBuffer];
        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
        rp.colorAttachments[0].texture = tex;
        rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].clearColor = MTLClearColorMake(dstr,dstg,dstb,dsta);
        rp.colorAttachments[0].storeAction = MTLStoreActionStore;
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        [enc setFragmentBuffer:sbuf offset:0 atIndex:0];
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc endEncoding];
        [cb commit]; [cb waitUntilCompleted];
        if (cb.error) { jfail(@"cmdbuf", cb.error); return 0; }
        uint32_t px[4];
        [tex getBytes:px bytesPerRow:16*W fromRegion:MTLRegionMake2D(W/2,H/2,1,1) mipmapLevel:0];
        printf("{\"status\":\"OK\",\"mode\":\"nan\",\"case\":\"%s\",\"src_bits\":%u,\"result_bits\":[%u,%u,%u,%u]}\n",
               casename, (uint32_t)uval, px[0],px[1],px[2],px[3]);
        return 0;
    }

    // =============================================================== bary
    if ([m isEqualToString:@"bary"]) {
        id<MTLFunction> vf = reqFn(@"v_bary");
        id<MTLFunction> ff = reqFn(@"f_bary");
        MTLTextureDescriptor *t0 = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:W height:H mipmapped:NO];
        t0.usage = MTLTextureUsageRenderTarget; t0.storageMode = MTLStorageModeShared;
        id<MTLTexture> rawtex = [GDEV newTextureWithDescriptor:t0];
        id<MTLTexture> manualtex = [GDEV newTextureWithDescriptor:t0];
        MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new];
        rd.vertexFunction = vf; rd.fragmentFunction = ff;
        rd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA32Float;
        rd.colorAttachments[1].pixelFormat = MTLPixelFormatRGBA32Float;
        id<MTLRenderPipelineState> pso = [GDEV newRenderPipelineStateWithDescriptor:rd error:&err];
        if (!pso) { jfail(@"pipeline", err); return 0; }
        float tags[3] = {10.0f, 20.0f, 30.0f};
        id<MTLBuffer> tbuf = [GDEV newBufferWithBytes:tags length:12 options:MTLResourceStorageModeShared];
        id<MTLCommandBuffer> cb = [GQ commandBuffer];
        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
        rp.colorAttachments[0].texture = rawtex; rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].clearColor = MTLClearColorMake(-9,-9,-9,-9); rp.colorAttachments[0].storeAction = MTLStoreActionStore;
        rp.colorAttachments[1].texture = manualtex; rp.colorAttachments[1].loadAction = MTLLoadActionClear;
        rp.colorAttachments[1].clearColor = MTLClearColorMake(-9,-9,-9,-9); rp.colorAttachments[1].storeAction = MTLStoreActionStore;
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        [enc setFragmentBuffer:tbuf offset:0 atIndex:0];
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc endEncoding];
        [cb commit]; [cb waitUntilCompleted];
        if (cb.error) { jfail(@"cmdbuf", cb.error); return 0; }
        float raw[4], man[4];
        [rawtex getBytes:raw bytesPerRow:16*W fromRegion:MTLRegionMake2D(W/2,H/2,1,1) mipmapLevel:0];
        [manualtex getBytes:man bytesPerRow:16*W fromRegion:MTLRegionMake2D(W/2,H/2,1,1) mipmapLevel:0];
        printf("{\"status\":\"OK\",\"mode\":\"bary\",\"case\":\"%s\",\"w\":%u,\"h\":%u,\"raw\":[%.8g,%.8g,%.8g],\"manual\":%.8g}\n",
               casename, W, H, raw[0],raw[1],raw[2], man[0]);
        return 0;
    }

    // ========================================================== pid family
    if ([m isEqualToString:@"pid"] || [m isEqualToString:@"pid_indexed"] || [m isEqualToString:@"pid_instanced"]) {
        id<MTLFunction> vf = reqFn(@"v_pidquad");
        id<MTLFunction> ff = reqFn(@"f_pid");
        MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Uint width:W height:H mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget; td.storageMode = MTLStorageModeShared;
        id<MTLTexture> tex = [GDEV newTextureWithDescriptor:td];
        MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new];
        rd.vertexFunction = vf; rd.fragmentFunction = ff;
        rd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA32Uint;
        id<MTLRenderPipelineState> pso = [GDEV newRenderPipelineStateWithDescriptor:rd error:&err];
        if (!pso) { jfail(@"pipeline", err); return 0; }
        id<MTLCommandBuffer> cb = [GQ commandBuffer];
        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
        rp.colorAttachments[0].texture = tex; rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].clearColor = MTLClearColorMake(999,999,0,0); rp.colorAttachments[0].storeAction = MTLStoreActionStore;
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        unsigned instCount = [m isEqualToString:@"pid_instanced"] ? 2 : 1;
        if ([m isEqualToString:@"pid_indexed"]) {
            // Shuffled index buffer: submit triangle 3's vertices FIRST, then 0,1,2 --
            // primitive_id must track ASSEMBLY order (0 for whichever triangle is
            // submitted first), not the raw vertex-index VALUES used.
            uint32_t idx[12] = { 9,10,11, 0,1,2, 3,4,5, 6,7,8 };
            id<MTLBuffer> ibuf = [GDEV newBufferWithBytes:idx length:sizeof(idx) options:MTLResourceStorageModeShared];
            [enc drawIndexedPrimitives:MTLPrimitiveTypeTriangle indexCount:12 indexType:MTLIndexTypeUInt32
                             indexBuffer:ibuf indexBufferOffset:0 instanceCount:instCount];
        } else {
            [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:12 instanceCount:instCount];
        }
        [enc endEncoding];
        [cb commit]; [cb waitUntilCompleted];
        if (cb.error) { jfail(@"cmdbuf", cb.error); return 0; }
        // Row H/4 = window-top-quarter = NDC y in [0,1] = instance 1's half;
        // row 3H/4 = window-bottom-quarter = NDC y in [-1,0] = instance 0's
        // half (Metal window convention is y-down, per FS-03/EXP-0111).
        NSMutableString *outj = [NSMutableString string];
        BOOL first = YES;
        for (unsigned row = 0; row < 2; row++) {
            unsigned py = row == 0 ? H/4 : (3*H)/4;
            unsigned expectIid = row == 0 ? 1 : 0;
            for (unsigned col=0; col<4; col++) {
                unsigned px = (col*W)/4 + (W/8);
                uint32_t rec[4];
                [tex getBytes:rec bytesPerRow:16*W fromRegion:MTLRegionMake2D(px,py,1,1) mipmapLevel:0];
                // NOTE: field named "primid" (not "pid") -- "pid" collides with
                // run.py's NONDET_FORBIDDEN process-id guard even though this is
                // primitive_id, a fully deterministic shader value.
                [outj appendFormat:@"%s{\"col\":%u,\"row_half_for_iid\":%u,\"primid\":%u,\"iid\":%u}", first?"":",", col, expectIid, rec[0], rec[1]];
                first = NO;
            }
        }
        printf("{\"status\":\"OK\",\"mode\":\"%s\",\"case\":\"%s\",\"w\":%u,\"h\":%u,\"instances\":%u,\"records\":[%s]}\n",
               [m UTF8String], casename, W, H, instCount, [outj UTF8String]);
        return 0;
    }

    // ============================================================ msaadiff
    if ([m isEqualToString:@"msaadiff"]) {
        id<MTLFunction> vf = reqFn(@"v_msaadiff");
        id<MTLFunction> ff = reqFn(@"f_msaadiff");
        MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:1 height:1 mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget; td.storageMode = MTLStorageModeShared;
        td.textureType = MTLTextureType2DMultisample; td.sampleCount = samples;
        id<MTLTexture> tex = [GDEV newTextureWithDescriptor:td];
        MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new];
        rd.vertexFunction = vf; rd.fragmentFunction = ff;
        rd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA8Unorm;
        rd.rasterSampleCount = samples;
        id<MTLRenderPipelineState> pso = [GDEV newRenderPipelineStateWithDescriptor:rd error:&err];
        if (!pso) { jfail(@"pipeline", err); return 0; }
        NSUInteger cap = samples + 4;
        id<MTLBuffer> outbuf = [GDEV newBufferWithLength:cap*16 options:MTLResourceStorageModeShared];
        memset(outbuf.contents, 0xAA, cap*16);
        id<MTLBuffer> cnt = [GDEV newBufferWithLength:4 options:MTLResourceStorageModeShared];
        memset(cnt.contents, 0, 4);
        id<MTLCommandBuffer> cb = [GQ commandBuffer];
        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
        rp.colorAttachments[0].texture = tex; rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].clearColor = MTLClearColorMake(0,0,0,1); rp.colorAttachments[0].storeAction = MTLStoreActionStore;
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        [enc setFragmentBuffer:outbuf offset:0 atIndex:0];
        [enc setFragmentBuffer:cnt offset:0 atIndex:1];
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc endEncoding];
        [cb commit]; [cb waitUntilCompleted];
        if (cb.error) { jfail(@"cmdbuf", cb.error); return 0; }
        uint32_t total = *(uint32_t*)cnt.contents;
        NSMutableString *recs = [NSMutableString string];
        uint8_t *base = (uint8_t*)outbuf.contents;
        for (uint32_t i=0;i<total;i++) {
            uint32_t *r = (uint32_t*)(base + i*16);
            uint32_t sid = r[0];
            float vsample = *(float*)&r[1], vcentroid = *(float*)&r[2], vcenter = *(float*)&r[3];
            [recs appendFormat:@"%s{\"sid\":%u,\"vsample\":%.8g,\"vcentroid\":%.8g,\"vcenter\":%.8g}", i?",":"", sid, vsample, vcentroid, vcenter];
        }
        printf("{\"status\":\"OK\",\"mode\":\"msaadiff\",\"case\":\"%s\",\"samples\":%u,\"total\":%u,\"records\":[%s]}\n",
               casename, samples, total, [recs UTF8String]);
        return 0;
    }

    // ========================================================== samplemask
    if ([m isEqualToString:@"samplemask"]) {
        id<MTLFunction> vf = reqFn(@"v_full");
        id<MTLFunction> ff = reqFn(@"f_samplemask_probe");
        MTLTextureDescriptor *mtd = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:1 height:1 mipmapped:NO];
        mtd.usage = MTLTextureUsageRenderTarget; mtd.storageMode = MTLStorageModeShared;
        mtd.textureType = (samples>1) ? MTLTextureType2DMultisample : MTLTextureType2D; mtd.sampleCount = samples;
        id<MTLTexture> mstex = [GDEV newTextureWithDescriptor:mtd];
        id<MTLTexture> restex = mstex;
        if (samples > 1) {
            MTLTextureDescriptor *rtd = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA32Float width:1 height:1 mipmapped:NO];
            rtd.usage = MTLTextureUsageRenderTarget; rtd.storageMode = MTLStorageModeShared;
            restex = [GDEV newTextureWithDescriptor:rtd];
        }
        MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new];
        rd.vertexFunction = vf; rd.fragmentFunction = ff;
        rd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA32Float;
        rd.rasterSampleCount = samples;
        id<MTLRenderPipelineState> pso = [GDEV newRenderPipelineStateWithDescriptor:rd error:&err];
        if (!pso) { jfail(@"pipeline", err); return 0; }
        uint32_t mv = (uint32_t)maskval;
        id<MTLBuffer> mbuf = [GDEV newBufferWithBytes:&mv length:4 options:MTLResourceStorageModeShared];
        id<MTLCommandBuffer> cb = [GQ commandBuffer];
        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
        rp.colorAttachments[0].texture = mstex; rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].clearColor = MTLClearColorMake(0,0,0,0);
        if (samples > 1) { rp.colorAttachments[0].resolveTexture = restex; rp.colorAttachments[0].storeAction = MTLStoreActionMultisampleResolve; }
        else { rp.colorAttachments[0].storeAction = MTLStoreActionStore; }
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        [enc setFragmentBuffer:mbuf offset:0 atIndex:0];
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc endEncoding];
        [cb commit]; [cb waitUntilCompleted];
        if (cb.error) { jfail(@"cmdbuf", cb.error); return 0; }
        float px[4];
        [restex getBytes:px bytesPerRow:16 fromRegion:MTLRegionMake2D(0,0,1,1) mipmapLevel:0];
        printf("{\"status\":\"OK\",\"mode\":\"samplemask\",\"case\":\"%s\",\"samples\":%u,\"maskval\":%u,\"resolved\":[%.8g,%.8g,%.8g,%.8g]}\n",
               casename, samples, mv, px[0],px[1],px[2],px[3]);
        return 0;
    }

    // ========================================================= stencilover
    if ([m isEqualToString:@"stencilover"]) {
        NSString *fname = [NSString stringWithFormat:@"f_stencil_%s", stype];
        id<MTLFunction> vf = reqFn(@"v_full");
        id<MTLFunction> ff = reqFn(fname);
        MTLTextureDescriptor *ctd = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:W height:H mipmapped:NO];
        ctd.usage = MTLTextureUsageRenderTarget; ctd.storageMode = MTLStorageModeShared;
        id<MTLTexture> ctex = [GDEV newTextureWithDescriptor:ctd];
        MTLTextureDescriptor *std_ = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatStencil8 width:W height:H mipmapped:NO];
        std_.usage = MTLTextureUsageRenderTarget; std_.storageMode = MTLStorageModePrivate;
        id<MTLTexture> stex = [GDEV newTextureWithDescriptor:std_];
        MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new];
        rd.vertexFunction = vf; rd.fragmentFunction = ff;
        rd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA8Unorm;
        rd.stencilAttachmentPixelFormat = MTLPixelFormatStencil8;
        id<MTLRenderPipelineState> pso = [GDEV newRenderPipelineStateWithDescriptor:rd error:&err];
        if (!pso) { jfail(@"pipeline", err); return 0; }
        MTLStencilDescriptor *sfd = [MTLStencilDescriptor new];
        sfd.stencilCompareFunction = MTLCompareFunctionAlways;
        sfd.depthStencilPassOperation = MTLStencilOperationReplace;
        MTLDepthStencilDescriptor *dsd = [MTLDepthStencilDescriptor new];
        dsd.frontFaceStencil = sfd; dsd.backFaceStencil = sfd;
        id<MTLDepthStencilState> dss = [GDEV newDepthStencilStateWithDescriptor:dsd];
        id<MTLBuffer> svalBuf;
        if (strcmp(stype,"u32")==0) { uint32_t v=(uint32_t)sval; svalBuf=[GDEV newBufferWithBytes:&v length:4 options:MTLResourceStorageModeShared]; }
        else if (strcmp(stype,"u16")==0) { uint16_t v=(uint16_t)sval; svalBuf=[GDEV newBufferWithBytes:&v length:2 options:MTLResourceStorageModeShared]; }
        else { int32_t v=(int32_t)sval; svalBuf=[GDEV newBufferWithBytes:&v length:4 options:MTLResourceStorageModeShared]; }
        id<MTLCommandBuffer> cb = [GQ commandBuffer];
        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
        rp.colorAttachments[0].texture = ctex; rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].clearColor = MTLClearColorMake(0,0,0,0); rp.colorAttachments[0].storeAction = MTLStoreActionStore;
        rp.stencilAttachment.texture = stex; rp.stencilAttachment.loadAction = MTLLoadActionClear;
        rp.stencilAttachment.clearStencil = 77; rp.stencilAttachment.storeAction = MTLStoreActionStore;
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        [enc setDepthStencilState:dss];
        [enc setStencilReferenceValue:stencilref];
        [enc setFragmentBuffer:svalBuf offset:0 atIndex:0];
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc endEncoding];
        id<MTLBuffer> readback = [GDEV newBufferWithLength:(NSUInteger)W*H options:MTLResourceStorageModeShared];
        id<MTLBlitCommandEncoder> blit = [cb blitCommandEncoder];
        [blit copyFromTexture:stex sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0)
                     sourceSize:MTLSizeMake(W,H,1) toBuffer:readback destinationOffset:0
                destinationBytesPerRow:W destinationBytesPerImage:W*H];
        [blit endEncoding];
        [cb commit]; [cb waitUntilCompleted];
        if (cb.error) { jfail(@"cmdbuf", cb.error); return 0; }
        uint8_t *sp = (uint8_t*)readback.contents;
        uint8_t centerStencil = sp[(H/2)*W + (W/2)];
        printf("{\"status\":\"OK\",\"mode\":\"stencilover\",\"case\":\"%s\",\"stype\":\"%s\",\"requested_sval\":%lld,\"observed\":%u}\n",
               casename, stype, sval, centerStencil);
        return 0;
    }

    // =========================================================== fsorder_cmp
    if ([m isEqualToString:@"fsorder_cmp"]) {
        id<MTLFunction> vf = reqFn(@"v_half");
        id<MTLFunction> ffA = reqFn(@"f_order_ab");
        id<MTLFunction> ffB = reqFn(@"f_order_ba");
        NSArray *fns = @[ffA, ffB];
        NSMutableArray *outs = [NSMutableArray array];
        for (id<MTLFunction> ff in fns) {
            MTLTextureDescriptor *ctd = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:W height:H mipmapped:NO];
            ctd.usage = MTLTextureUsageRenderTarget; ctd.storageMode = MTLStorageModeShared;
            id<MTLTexture> ctex = [GDEV newTextureWithDescriptor:ctd];
            MTLTextureDescriptor *dtd = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatDepth32Float width:W height:H mipmapped:NO];
            dtd.usage = MTLTextureUsageRenderTarget; dtd.storageMode = MTLStorageModePrivate;
            id<MTLTexture> dtex = [GDEV newTextureWithDescriptor:dtd];
            MTLTextureDescriptor *std_ = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatStencil8 width:W height:H mipmapped:NO];
            std_.usage = MTLTextureUsageRenderTarget; std_.storageMode = MTLStorageModePrivate;
            id<MTLTexture> stex = [GDEV newTextureWithDescriptor:std_];
            MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new];
            rd.vertexFunction = vf; rd.fragmentFunction = ff;
            rd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA8Unorm;
            rd.depthAttachmentPixelFormat = MTLPixelFormatDepth32Float;
            rd.stencilAttachmentPixelFormat = MTLPixelFormatStencil8;
            id<MTLRenderPipelineState> pso = [GDEV newRenderPipelineStateWithDescriptor:rd error:&err];
            if (!pso) { jfail(@"pipeline", err); return 0; }
            MTLDepthStencilDescriptor *dsd = [MTLDepthStencilDescriptor new];
            dsd.depthCompareFunction = MTLCompareFunctionAlways; dsd.depthWriteEnabled = YES;
            MTLStencilDescriptor *sfd = [MTLStencilDescriptor new];
            sfd.stencilCompareFunction = MTLCompareFunctionAlways; sfd.depthStencilPassOperation = MTLStencilOperationReplace;
            dsd.frontFaceStencil = sfd; dsd.backFaceStencil = sfd;
            id<MTLDepthStencilState> dss = [GDEV newDepthStencilStateWithDescriptor:dsd];
            float d2[3] = {(float)passdepth, (float)faildepth, (float)W/2.0f};
            id<MTLBuffer> dbuf = [GDEV newBufferWithBytes:d2 length:12 options:MTLResourceStorageModeShared];
            id<MTLCommandBuffer> cb = [GQ commandBuffer];
            MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
            rp.colorAttachments[0].texture = ctex; rp.colorAttachments[0].loadAction = MTLLoadActionClear;
            rp.colorAttachments[0].clearColor = MTLClearColorMake(0,0,0,0); rp.colorAttachments[0].storeAction = MTLStoreActionStore;
            rp.depthAttachment.texture = dtex; rp.depthAttachment.loadAction = MTLLoadActionClear;
            rp.depthAttachment.clearDepth = 0.5; rp.depthAttachment.storeAction = MTLStoreActionStore;
            rp.stencilAttachment.texture = stex; rp.stencilAttachment.loadAction = MTLLoadActionClear;
            rp.stencilAttachment.clearStencil = 77; rp.stencilAttachment.storeAction = MTLStoreActionStore;
            id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
            [enc setRenderPipelineState:pso];
            [enc setDepthStencilState:dss];
            [enc setStencilReferenceValue:stencilref];
            [enc setFragmentBuffer:dbuf offset:0 atIndex:0];
            [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
            [enc endEncoding];
            id<MTLBuffer> dread = [GDEV newBufferWithLength:(NSUInteger)W*H*4 options:MTLResourceStorageModeShared];
            id<MTLBuffer> sread = [GDEV newBufferWithLength:(NSUInteger)W*H options:MTLResourceStorageModeShared];
            id<MTLBlitCommandEncoder> blit = [cb blitCommandEncoder];
            [blit copyFromTexture:dtex sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(W,H,1)
                          toBuffer:dread destinationOffset:0 destinationBytesPerRow:W*4 destinationBytesPerImage:W*H*4];
            [blit copyFromTexture:stex sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(W,H,1)
                          toBuffer:sread destinationOffset:0 destinationBytesPerRow:W destinationBytesPerImage:W*H];
            [blit endEncoding];
            [cb commit]; [cb waitUntilCompleted];
            if (cb.error) { jfail(@"cmdbuf", cb.error); return 0; }
            uint8_t px[4];
            [ctex getBytes:px bytesPerRow:4*W fromRegion:MTLRegionMake2D(W/4,H/2,1,1) mipmapLevel:0];
            float *dp = (float*)dread.contents;
            uint8_t *sp = (uint8_t*)sread.contents;
            [outs addObject:@{@"color":@[@(px[0]),@(px[1]),@(px[2]),@(px[3])], @"depth":@(dp[(H/2)*W+(W/4)]), @"stencil":@(sp[(H/2)*W+(W/4)])}];
        }
        NSData *jd = [NSJSONSerialization dataWithJSONObject:outs options:0 error:nil];
        NSString *js = [[NSString alloc] initWithData:jd encoding:NSUTF8StringEncoding];
        printf("{\"status\":\"OK\",\"mode\":\"fsorder_cmp\",\"case\":\"%s\",\"results\":%s}\n", casename, [js UTF8String]);
        return 0;
    }

    // ======================================================= fsorder_suppress
    if ([m isEqualToString:@"fsorder_suppress"]) {
        id<MTLFunction> vf = reqFn(@"v_half");
        id<MTLFunction> ff = reqFn(@"f_fsorder_probe");
        MTLTextureDescriptor *ctd = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:W height:H mipmapped:NO];
        ctd.usage = MTLTextureUsageRenderTarget; ctd.storageMode = MTLStorageModeShared;
        id<MTLTexture> ctex = [GDEV newTextureWithDescriptor:ctd];
        MTLTextureDescriptor *dtd = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatDepth32Float width:W height:H mipmapped:NO];
        dtd.usage = MTLTextureUsageRenderTarget; dtd.storageMode = MTLStorageModePrivate;
        id<MTLTexture> dtex = [GDEV newTextureWithDescriptor:dtd];
        MTLTextureDescriptor *std_ = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatStencil8 width:W height:H mipmapped:NO];
        std_.usage = MTLTextureUsageRenderTarget; std_.storageMode = MTLStorageModePrivate;
        id<MTLTexture> stex = [GDEV newTextureWithDescriptor:std_];
        MTLRenderPipelineDescriptor *rd = [MTLRenderPipelineDescriptor new];
        rd.vertexFunction = vf; rd.fragmentFunction = ff;
        rd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA8Unorm;
        rd.depthAttachmentPixelFormat = MTLPixelFormatDepth32Float;
        rd.stencilAttachmentPixelFormat = MTLPixelFormatStencil8;
        id<MTLRenderPipelineState> pso = [GDEV newRenderPipelineStateWithDescriptor:rd error:&err];
        if (!pso) { jfail(@"pipeline", err); return 0; }
        MTLDepthStencilDescriptor *dsd = [MTLDepthStencilDescriptor new];
        dsd.depthCompareFunction = MTLCompareFunctionLess; dsd.depthWriteEnabled = YES;
        MTLStencilDescriptor *sfd = [MTLStencilDescriptor new];
        sfd.stencilCompareFunction = MTLCompareFunctionAlways;
        sfd.depthFailureOperation = (MTLStencilOperation)depthfailop;
        sfd.depthStencilPassOperation = (MTLStencilOperation)depthpassop;
        dsd.frontFaceStencil = sfd; dsd.backFaceStencil = sfd;
        id<MTLDepthStencilState> dss = [GDEV newDepthStencilStateWithDescriptor:dsd];
        float d2[3] = {(float)passdepth, (float)faildepth, (float)W/2.0f}; // clear depth = 0.5; Less means value<0.5 passes
        id<MTLBuffer> dbuf = [GDEV newBufferWithBytes:d2 length:12 options:MTLResourceStorageModeShared];
        id<MTLCommandBuffer> cb = [GQ commandBuffer];
        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
        rp.colorAttachments[0].texture = ctex; rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].clearColor = MTLClearColorMake(0,0,0,0); rp.colorAttachments[0].storeAction = MTLStoreActionStore;
        rp.depthAttachment.texture = dtex; rp.depthAttachment.loadAction = MTLLoadActionClear;
        rp.depthAttachment.clearDepth = 0.5; rp.depthAttachment.storeAction = MTLStoreActionStore;
        rp.stencilAttachment.texture = stex; rp.stencilAttachment.loadAction = MTLLoadActionClear;
        rp.stencilAttachment.clearStencil = 77; rp.stencilAttachment.storeAction = MTLStoreActionStore;
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        [enc setDepthStencilState:dss];
        [enc setStencilReferenceValue:stencilref];
        [enc setFragmentBuffer:dbuf offset:0 atIndex:0];
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc endEncoding];
        id<MTLBuffer> dread = [GDEV newBufferWithLength:(NSUInteger)W*H*4 options:MTLResourceStorageModeShared];
        id<MTLBuffer> sread = [GDEV newBufferWithLength:(NSUInteger)W*H options:MTLResourceStorageModeShared];
        id<MTLBlitCommandEncoder> blit = [cb blitCommandEncoder];
        [blit copyFromTexture:dtex sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(W,H,1)
                      toBuffer:dread destinationOffset:0 destinationBytesPerRow:W*4 destinationBytesPerImage:W*H*4];
        [blit copyFromTexture:stex sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(W,H,1)
                      toBuffer:sread destinationOffset:0 destinationBytesPerRow:W destinationBytesPerImage:W*H];
        [blit endEncoding];
        [cb commit]; [cb waitUntilCompleted];
        if (cb.error) { jfail(@"cmdbuf", cb.error); return 0; }
        uint8_t pxL[4], pxR[4];
        [ctex getBytes:pxL bytesPerRow:4*W fromRegion:MTLRegionMake2D(W/4,H/2,1,1) mipmapLevel:0];
        [ctex getBytes:pxR bytesPerRow:4*W fromRegion:MTLRegionMake2D((3*W)/4,H/2,1,1) mipmapLevel:0];
        float *dp = (float*)dread.contents;
        uint8_t *sp = (uint8_t*)sread.contents;
        printf("{\"status\":\"OK\",\"mode\":\"fsorder_suppress\",\"case\":\"%s\","
               "\"left_color\":[%u,%u,%u,%u],\"right_color\":[%u,%u,%u,%u],"
               "\"left_depth\":%.6f,\"right_depth\":%.6f,\"left_stencil\":%u,\"right_stencil\":%u}\n",
               casename, pxL[0],pxL[1],pxL[2],pxL[3], pxR[0],pxR[1],pxR[2],pxR[3],
               dp[(H/2)*W+(W/4)], dp[(H/2)*W+(3*W)/4], sp[(H/2)*W+(W/4)], sp[(H/2)*W+(3*W)/4]);
        return 0;
    }

    usageDie("unknown --mode");
    return 1;
}}
