// rtvar.m — parametric OWN Metal DRAW for RENDER-TARGET ("PBE") attachment-descriptor RE.
// EXP-G1b objectives 2 & 3. Extends the EXP-0021 tvar.m TBDR harness with the one change a
// full field-map needs: EVERY color attachment is buffer-backed shared so its surface GPU VA
// is printable (for pointer→VA correlation) and its rendered pixels are read back. We then
// byte-diff the 3D attachment descriptor (gpu_va 0x10000110000) across single-parameter
// changes (RT size, format, load/store action, MRT count) under the read-only tools/iotrace
// interposer, and pin surface-VA / dims / stride / load-store / resolve / compression fields.
//
// CLEAN-ROOM: OWN-SHADER + public Metal API. Our MSL, our resources. No Apple binary read.
// Build (device): clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o rtvar rtvar.m
//
// Usage:
//   rtvar [--w W --h H] [--fmt F] [--mrt N] [--samples N]
//         [--load clear|load|dontcare] [--store store|dontcare]
//         [--depth] [--priv] [--dump]
//     --fmt  : bgra8(default)|rgba8|rgba16f|rgba32f|r8|r32f|rgb10a2|rg11b10
//     --mrt  : 1..4 color attachments (single-sample)
//     --priv : make color[0] a Private (non-buffer-backed) 2D texture (surface encoding
//              contrast vs the buffer-backed linear default)
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void print_va(const char*l,uint64_t va){ printf("VA %-12s = 0x%016llx\n",l,(unsigned long long)va); }

static MTLPixelFormat parse_fmt(const char*s,int*bpp){
  if(!strcmp(s,"rgba8"))   { *bpp=4;  return MTLPixelFormatRGBA8Unorm; }
  if(!strcmp(s,"rgba16f")) { *bpp=8;  return MTLPixelFormatRGBA16Float; }
  if(!strcmp(s,"rgba32f")) { *bpp=16; return MTLPixelFormatRGBA32Float; }
  if(!strcmp(s,"r8"))      { *bpp=1;  return MTLPixelFormatR8Unorm; }
  if(!strcmp(s,"r32f"))    { *bpp=4;  return MTLPixelFormatR32Float; }
  if(!strcmp(s,"rg11b10")) { *bpp=4;  return MTLPixelFormatRG11B10Float; }
  if(!strcmp(s,"rgb10a2")) { *bpp=4;  return MTLPixelFormatRGB10A2Unorm; }
  *bpp=4; return MTLPixelFormatBGRA8Unorm;
}
static MTLLoadAction parse_load(const char*s){
  if(!strcmp(s,"load")) return MTLLoadActionLoad;
  if(!strcmp(s,"dontcare")) return MTLLoadActionDontCare;
  return MTLLoadActionClear;
}
static MTLStoreAction parse_store(const char*s){
  if(!strcmp(s,"dontcare")) return MTLStoreActionDontCare;
  return MTLStoreActionStore;
}
static NSString* vsrc(void){
  return @"#include <metal_stdlib>\nusing namespace metal;\n"
          "struct VO{float4 pos [[position]]; float4 col;};\n"
          "vertex VO v_main(uint vid [[vertex_id]], const device float2* p [[buffer(0)]]){\n"
          "  VO o; o.pos=float4(p[vid],0,1); o.col=float4(0.25,0.5,0.75,1); return o;}\n";
}
static NSString* fsrc(int nrt){
  if(nrt<=1)
    return @"#include <metal_stdlib>\nusing namespace metal;\n"
            "struct VO{float4 pos [[position]]; float4 col;};\n"
            "fragment float4 f_main(VO in [[stage_in]]){ return in.col; }\n";
  NSMutableString* s=[NSMutableString stringWithString:
    @"#include <metal_stdlib>\nusing namespace metal;\n"
     "struct VO{float4 pos [[position]]; float4 col;};\nstruct FO{\n"];
  for(int i=0;i<nrt;i++)[s appendFormat:@"  float4 c%d [[color(%d)]];\n",i,i];
  [s appendString:@"};\nfragment FO f_main(VO in [[stage_in]]){ FO o;\n"];
  for(int i=0;i<nrt;i++)[s appendFormat:@"  o.c%d=in.col*float(%d+1)*0.25;\n",i,i];
  [s appendString:@"  return o; }\n"];
  return s;
}

int main(int argc,char**argv){ @autoreleasepool {
  long W=64,H=64,mrt=1,samples=1; const char*fmtS="bgra8",*loadS="clear",*storeS="store";
  int depth=0,priv=0,doDump=0;
  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--w")&&i+1<argc) W=strtol(argv[++i],0,0);
    else if(!strcmp(argv[i],"--h")&&i+1<argc) H=strtol(argv[++i],0,0);
    else if(!strcmp(argv[i],"--fmt")&&i+1<argc) fmtS=argv[++i];
    else if(!strcmp(argv[i],"--mrt")&&i+1<argc) mrt=strtol(argv[++i],0,0);
    else if(!strcmp(argv[i],"--samples")&&i+1<argc) samples=strtol(argv[++i],0,0);
    else if(!strcmp(argv[i],"--load")&&i+1<argc) loadS=argv[++i];
    else if(!strcmp(argv[i],"--store")&&i+1<argc) storeS=argv[++i];
    else if(!strcmp(argv[i],"--depth")) depth=1;
    else if(!strcmp(argv[i],"--priv")) priv=1;
    else if(!strcmp(argv[i],"--dump")) doDump=1;
  }
  if(mrt<1)mrt=1; if(mrt>4)mrt=4;
  int bpp=4; MTLPixelFormat fmt=parse_fmt(fmtS,&bpp);
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s\nCONFIG w=%ld h=%ld fmt=%s bpp=%d mrt=%ld samples=%ld load=%s store=%s depth=%d priv=%d\n",
    [[dev name] UTF8String],W,H,fmtS,bpp,mrt,samples,loadS,storeS,depth,priv);

  NSError* err=nil;
  id<MTLLibrary> vl=[dev newLibraryWithSource:vsrc() options:nil error:&err];
  id<MTLLibrary> fl=[dev newLibraryWithSource:fsrc((int)mrt) options:nil error:&err];
  if(!vl||!fl){ printf("PIPELINE_FAIL lib %s\n",[[err localizedDescription] UTF8String]); return 1; }
  MTLRenderPipelineDescriptor* pd=[MTLRenderPipelineDescriptor new];
  pd.vertexFunction=[vl newFunctionWithName:@"v_main"];
  pd.fragmentFunction=[fl newFunctionWithName:@"f_main"];
  for(int i=0;i<(samples>1?1:mrt);i++) pd.colorAttachments[i].pixelFormat=fmt;
  if(depth) pd.depthAttachmentPixelFormat=MTLPixelFormatDepth32Float;
  if(samples>1) pd.rasterSampleCount=(NSUInteger)samples;
  id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
  if(!pso){ printf("PIPELINE_FAIL pso %s\n",[[err localizedDescription] UTF8String]); return 1; }

  NSUInteger bpr=(NSUInteger)(W*bpp); bpr=(bpr+255)&~255UL;
  id<MTLTexture> color[4]={nil,nil,nil,nil}; id<MTLTexture> msaaColor=nil,resolveTex=nil;
  id<MTLBuffer> rtb[4]={nil,nil,nil,nil}, resb=nil;

  if(samples>1){
    MTLTextureDescriptor* md=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:fmt width:W height:H mipmapped:NO];
    md.textureType=MTLTextureType2DMultisample; md.sampleCount=samples;
    md.usage=MTLTextureUsageRenderTarget; md.storageMode=MTLStorageModePrivate;
    msaaColor=[dev newTextureWithDescriptor:md];
    MTLTextureDescriptor* rd=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:fmt width:W height:H mipmapped:NO];
    rd.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead; rd.storageMode=MTLStorageModeShared;
    resb=[dev newBufferWithLength:bpr*H options:MTLResourceStorageModeShared];
    resolveTex=[resb newTextureWithDescriptor:rd offset:0 bytesPerRow:bpr];
    if(resolveTex) print_va("resBuf",[resb gpuAddress]); else resolveTex=[dev newTextureWithDescriptor:rd];
    color[0]=msaaColor;
  } else {
    for(int i=0;i<mrt;i++){
      MTLTextureDescriptor* td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:fmt width:W height:H mipmapped:NO];
      td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead; td.storageMode=MTLStorageModeShared;
      if(i==0 && priv){
        td.storageMode=MTLStorageModePrivate;
        color[0]=[dev newTextureWithDescriptor:td];
      } else {
        rtb[i]=[dev newBufferWithLength:bpr*H options:MTLResourceStorageModeShared];
        color[i]=[rtb[i] newTextureWithDescriptor:td offset:0 bytesPerRow:bpr];
        if(color[i]){ char l[16]; snprintf(l,sizeof l,"rtBuf%d",i); print_va(l,[rtb[i] gpuAddress]); }
        else color[i]=[dev newTextureWithDescriptor:td];
      }
    }
  }

  id<MTLTexture> depthTex=nil; id<MTLDepthStencilState> dss=nil;
  if(depth){
    MTLTextureDescriptor* dd=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatDepth32Float width:W height:H mipmapped:NO];
    if(samples>1){ dd.textureType=MTLTextureType2DMultisample; dd.sampleCount=samples; }
    dd.usage=MTLTextureUsageRenderTarget; dd.storageMode=MTLStorageModePrivate;
    depthTex=[dev newTextureWithDescriptor:dd];
    MTLDepthStencilDescriptor* dsd=[MTLDepthStencilDescriptor new];
    dsd.depthCompareFunction=MTLCompareFunctionLess; dsd.depthWriteEnabled=YES;
    dss=[dev newDepthStencilStateWithDescriptor:dsd];
  }

  id<MTLBuffer> vb=[dev newBufferWithLength:24 options:MTLResourceStorageModeShared];
  float* vp=(float*)[vb contents]; vp[0]=-1;vp[1]=-1;vp[2]=3;vp[3]=-1;vp[4]=-1;vp[5]=3;
  print_va("vtxBuf",[vb gpuAddress]);

  id<MTLCommandQueue> q=[dev newCommandQueue];
  MTLRenderPassDescriptor* rp=[MTLRenderPassDescriptor new];
  for(int i=0;i<(samples>1?1:mrt);i++){
    rp.colorAttachments[i].texture=color[i];
    rp.colorAttachments[i].loadAction=parse_load(loadS);
    rp.colorAttachments[i].clearColor=MTLClearColorMake(0,0,0,1);
    if(samples>1){ rp.colorAttachments[i].resolveTexture=resolveTex; rp.colorAttachments[i].storeAction=MTLStoreActionMultisampleResolve; }
    else rp.colorAttachments[i].storeAction=parse_store(storeS);
  }
  if(depth){ rp.depthAttachment.texture=depthTex; rp.depthAttachment.loadAction=MTLLoadActionClear;
             rp.depthAttachment.clearDepth=1.0; rp.depthAttachment.storeAction=MTLStoreActionDontCare; }
  id<MTLCommandBuffer> cb=[q commandBuffer];
  id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
  [enc setRenderPipelineState:pso];
  MTLViewport vpp={0,0,(double)W,(double)H,0,1}; [enc setViewport:vpp];
  [enc setVertexBuffer:vb offset:0 atIndex:0];
  if(dss)[enc setDepthStencilState:dss];
  [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
  [enc endEncoding]; [cb commit]; [cb waitUntilCompleted];
  printf("SUBMIT status=%ld err=%s\n",(long)[cb status],[cb error]?[[[cb error] localizedDescription] UTF8String]:"none");

  id<MTLTexture> rb=(samples>1)?resolveTex:color[0];
  if(rb && rb.storageMode==MTLStorageModeShared){
    unsigned char px[16]; memset(px,0,sizeof px);
    [rb getBytes:px bytesPerRow:bpr fromRegion:MTLRegionMake2D(0,0,1,1) mipmapLevel:0];
    printf("PIXEL b0..3=%02x%02x%02x%02x\n",px[0],px[1],px[2],px[3]);
  }
  if(doDump){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(400000); }
  return 0;
}}
