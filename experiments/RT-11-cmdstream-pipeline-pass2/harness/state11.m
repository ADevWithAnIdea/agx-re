// state11.m — RT-11 regression re-check of CONFIRMED cmdstream/pipeline facts.
//
// Purpose: quick change-one-parameter re-check that the RT-2a/RT-4 corrections did
// not disturb the CONFIRMED facts: state packets (depth +0x38 / stencil +0x3c /
// raster +0x70 / PPP-length), programmable blend (rewrites FS, not a FF LUT), tile
// 32x32 grid (+0x904/+0x908), memoryless poison, occlusion query, GPU timestamp.
// DIFFERENT program (fresh shaders, occlusion + timestamp added).
//
// CLEAN-ROOM: OWN-SHADER + public Metal API. Our own MSL compiled at runtime.
//
// Build (device): clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o state11 state11.m
//
// Usage: state11 [--w W --h H] [--depth] [--dcmp FUNC] [--stencil] [--sref N]
//                [--cull none|front|back] [--clip clip|clamp] [--blend] [--mlcolor]
//                [--occlusion] [--timestamp] [--dump]

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void pva(const char*l,uint64_t va){ printf("VA %-10s = 0x%016llx\n",l,(unsigned long long)va); }
static MTLCompareFunction cmp(const char*s){
    if(!strcmp(s,"never"))return MTLCompareFunctionNever;
    if(!strcmp(s,"less"))return MTLCompareFunctionLess;
    if(!strcmp(s,"equal"))return MTLCompareFunctionEqual;
    if(!strcmp(s,"lequal"))return MTLCompareFunctionLessEqual;
    if(!strcmp(s,"greater"))return MTLCompareFunctionGreater;
    if(!strcmp(s,"nequal"))return MTLCompareFunctionNotEqual;
    if(!strcmp(s,"gequal"))return MTLCompareFunctionGreaterEqual;
    return MTLCompareFunctionAlways;
}
static MTLCullMode cull(const char*s){
    if(!strcmp(s,"front"))return MTLCullModeFront;
    if(!strcmp(s,"back"))return MTLCullModeBack;
    return MTLCullModeNone;
}

int main(int argc,char**argv){@autoreleasepool{
    long W=64,H=64,sref=0; const char*dcmpS="less",*cullS="none",*clipS="clip";
    int depth=0,stencil=0,blend=0,mlcolor=0,occ=0,ts=0,doDump=0;
    for(int i=1;i<argc;i++){
        if(!strcmp(argv[i],"--w")&&i+1<argc)W=strtol(argv[++i],0,0);
        else if(!strcmp(argv[i],"--h")&&i+1<argc)H=strtol(argv[++i],0,0);
        else if(!strcmp(argv[i],"--dcmp")&&i+1<argc){depth=1;dcmpS=argv[++i];}
        else if(!strcmp(argv[i],"--depth"))depth=1;
        else if(!strcmp(argv[i],"--stencil")){depth=1;stencil=1;}
        else if(!strcmp(argv[i],"--sref")&&i+1<argc){depth=1;stencil=1;sref=strtol(argv[++i],0,0);}
        else if(!strcmp(argv[i],"--cull")&&i+1<argc)cullS=argv[++i];
        else if(!strcmp(argv[i],"--clip")&&i+1<argc)clipS=argv[++i];
        else if(!strcmp(argv[i],"--blend"))blend=1;
        else if(!strcmp(argv[i],"--mlcolor"))mlcolor=1;
        else if(!strcmp(argv[i],"--occlusion"))occ=1;
        else if(!strcmp(argv[i],"--timestamp"))ts=1;
        else if(!strcmp(argv[i],"--dump"))doDump=1;
    }
    id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
    printf("DEVICE %s\n",[[dev name]UTF8String]);
    printf("CONFIG w=%ld h=%ld depth=%d dcmp=%s stencil=%d sref=%ld cull=%s clip=%s blend=%d mlcolor=%d occ=%d ts=%d\n",
           W,H,depth,dcmpS,stencil,sref,cullS,clipS,blend,mlcolor,occ,ts);

    NSString*vs=@"#include <metal_stdlib>\nusing namespace metal;\n"
      "struct V{float4 p [[position]]; float4 c;};\n"
      "vertex V vm(uint vid [[vertex_id]], const device float2* q [[buffer(0)]]){ V o; o.p=float4(q[vid],0,1); o.c=float4(0.3,0.6,0.9,0.5); return o; }\n";
    NSString*fs=@"#include <metal_stdlib>\nusing namespace metal;\n"
      "struct V{float4 p [[position]]; float4 c;};\n"
      "fragment float4 fm(V in [[stage_in]]){ return in.c; }\n";
    NSError*err=nil;
    id<MTLLibrary> vl=[dev newLibraryWithSource:vs options:nil error:&err];
    id<MTLLibrary> fl=[dev newLibraryWithSource:fs options:nil error:&err];
    if(!vl||!fl){printf("SHADER_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
    MTLPixelFormat dsfmt = stencil?MTLPixelFormatDepth32Float_Stencil8:MTLPixelFormatDepth32Float;
    MTLRenderPipelineDescriptor*pd=[MTLRenderPipelineDescriptor new];
    pd.vertexFunction=[vl newFunctionWithName:@"vm"];
    pd.fragmentFunction=[fl newFunctionWithName:@"fm"];
    pd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
    if(blend){ pd.colorAttachments[0].blendingEnabled=YES;
        pd.colorAttachments[0].sourceRGBBlendFactor=MTLBlendFactorSourceAlpha;
        pd.colorAttachments[0].destinationRGBBlendFactor=MTLBlendFactorOneMinusSourceAlpha; }
    if(depth) pd.depthAttachmentPixelFormat=dsfmt;
    if(stencil) pd.stencilAttachmentPixelFormat=dsfmt;
    id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
    if(!pso){printf("PIPELINE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}

    id<MTLDepthStencilState> dss=nil;
    if(depth){ MTLDepthStencilDescriptor*dsd=[MTLDepthStencilDescriptor new];
        dsd.depthCompareFunction=cmp(dcmpS); dsd.depthWriteEnabled=YES;
        if(stencil){ MTLStencilDescriptor*sd=[MTLStencilDescriptor new];
            sd.stencilCompareFunction=MTLCompareFunctionEqual;
            sd.depthStencilPassOperation=MTLStencilOperationReplace;
            sd.readMask=0xff; sd.writeMask=0xff; dsd.frontFaceStencil=sd; dsd.backFaceStencil=sd; }
        dss=[dev newDepthStencilStateWithDescriptor:dsd]; }

    NSUInteger bpr=((W*4+255)&~255UL);
    id<MTLTexture> target=nil; id<MTLBuffer> rtb=nil;
    MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:W height:H mipmapped:NO];
    td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead;
    if(mlcolor){ td.storageMode=MTLStorageModeMemoryless; target=[dev newTextureWithDescriptor:td]; }
    else { td.storageMode=MTLStorageModeShared; rtb=[dev newBufferWithLength:bpr*H options:MTLResourceStorageModeShared];
           target=[rtb newTextureWithDescriptor:td offset:0 bytesPerRow:bpr]; pva("rtBuf",[rtb gpuAddress]); }

    id<MTLTexture> dsTex=nil;
    if(depth){ MTLTextureDescriptor*dd=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:dsfmt width:W height:H mipmapped:NO];
        dd.usage=MTLTextureUsageRenderTarget; dd.storageMode=MTLStorageModePrivate; dsTex=[dev newTextureWithDescriptor:dd]; }

    id<MTLBuffer> vb=[dev newBufferWithLength:64 options:MTLResourceStorageModeShared];
    float*vp=(float*)[vb contents]; vp[0]=-1;vp[1]=-1;vp[2]=3;vp[3]=-1;vp[4]=-1;vp[5]=3;
    pva("vtxBuf",[vb gpuAddress]);

    id<MTLBuffer> visb=nil;
    if(occ){ visb=[dev newBufferWithLength:64 options:MTLResourceStorageModeShared]; pva("visBuf",[visb gpuAddress]); }

    // Timestamp counter sample buffer (stage-boundary) if requested/available
    id<MTLCounterSampleBuffer> tsbuf=nil; id<MTLCounterSet> tset=nil;
    if(ts){
        for(id<MTLCounterSet> cs in [dev counterSets]) if([[cs name] isEqualToString:MTLCommonCounterSetTimestamp]) tset=cs;
        printf("TS timestampPeriod=? counterSetFound=%d\n",tset!=nil);
        if(tset){ MTLCounterSampleBufferDescriptor*cd=[MTLCounterSampleBufferDescriptor new];
            cd.counterSet=tset; cd.storageMode=MTLStorageModeShared; cd.sampleCount=4;
            tsbuf=[dev newCounterSampleBufferWithDescriptor:cd error:&err];
            if(!tsbuf) printf("TS sampleBuffer FAIL %s\n",[[err localizedDescription]UTF8String]); }
    }

    id<MTLCommandQueue> q=[dev newCommandQueue];
    MTLRenderPassDescriptor*rp=[MTLRenderPassDescriptor new];
    rp.colorAttachments[0].texture=target;
    rp.colorAttachments[0].loadAction=MTLLoadActionClear;
    rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,1);
    rp.colorAttachments[0].storeAction=mlcolor?MTLStoreActionDontCare:MTLStoreActionStore;
    if(depth){ rp.depthAttachment.texture=dsTex; rp.depthAttachment.loadAction=MTLLoadActionClear;
        rp.depthAttachment.clearDepth=1.0; rp.depthAttachment.storeAction=MTLStoreActionDontCare;
        if(stencil){ rp.stencilAttachment.texture=dsTex; rp.stencilAttachment.loadAction=MTLLoadActionClear;
            rp.stencilAttachment.clearStencil=0; rp.stencilAttachment.storeAction=MTLStoreActionDontCare; } }
    if(occ) rp.visibilityResultBuffer=visb;
    if(tsbuf){ rp.sampleBufferAttachments[0].sampleBuffer=tsbuf;
        rp.sampleBufferAttachments[0].startOfVertexSampleIndex=0;
        rp.sampleBufferAttachments[0].endOfVertexSampleIndex=1;
        rp.sampleBufferAttachments[0].startOfFragmentSampleIndex=2;
        rp.sampleBufferAttachments[0].endOfFragmentSampleIndex=3; }

    id<MTLCommandBuffer> cb=[q commandBuffer];
    id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
    [enc setRenderPipelineState:pso];
    MTLViewport v={0,0,(double)W,(double)H,0,1}; [enc setViewport:v];
    [enc setCullMode:cull(cullS)];
    [enc setDepthClipMode:!strcmp(clipS,"clamp")?MTLDepthClipModeClamp:MTLDepthClipModeClip];
    [enc setVertexBuffer:vb offset:0 atIndex:0];
    if(dss){ [enc setDepthStencilState:dss]; if(stencil)[enc setStencilReferenceValue:(uint32_t)sref]; }
    if(blend) [enc setBlendColorRed:0.1 green:0.2 blue:0.3 alpha:0.4];
    if(occ) [enc setVisibilityResultMode:MTLVisibilityResultModeCounting offset:0];
    [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
    [enc endEncoding];
    [cb commit]; [cb waitUntilCompleted];
    printf("SUBMIT done status=%ld\n",(long)[cb status]);
    if(occ){ uint64_t*r=(uint64_t*)[visb contents]; printf("OCCLUSION passed=%llu\n",(unsigned long long)r[0]); }
    if(ts){ printf("TS gpuStart=%llu gpuEnd=%llu\n",(unsigned long long)[cb GPUStartTime]*0,(unsigned long long)[cb GPUEndTime]*0);
        if(tsbuf){ NSData*d=[tsbuf resolveCounterRange:NSMakeRange(0,4)];
            if(d){ const uint64_t*t=(const uint64_t*)[d bytes]; NSUInteger n=[d length]/8;
                printf("TS samples n=%lu:",(unsigned long)n); for(NSUInteger i=0;i<n&&i<4;i++) printf(" %llu",(unsigned long long)t[i]); printf("\n"); } } }
    if(doDump){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(400000); }
    return 0;
}}
