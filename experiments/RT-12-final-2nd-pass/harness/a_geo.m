// a_geo.m -- RT-12 Part A: independent re-verify of geometry-output cmdstream fields.
//   viewport count word  0x68000+0x900 = ((count-1)<<12)|0x0C00
//   clip-distance mask   0x58000+0x20 bits[7:0]
//   point_size           0x58000+0x20 bit18
//   viewport_array_index 0x58000+0x20 bit19
//   primitive-restart cut index 0x18000+0x68 = all-ones of index width
// DIFFERENT parameter values than RT-6 (nvp 4/16, clip 3/8): here nvp 2/8, clip 5; own MSL.
//   flags: --nvp N | --clip K | --point | --vpidx | --restart u16list|u16strip|u32strip
// CLEAN-ROOM: OWN-SHADER + public Metal API + DATA-TRACE (read-only iotrace). See ../../CLAUDE.md.
// Build: clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o a_geo a_geo.m
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
static void pv(const char*l,uint64_t v){printf("VA %-10s = 0x%016llx\n",l,(unsigned long long)v);}
int main(int argc,char**argv){ @autoreleasepool{
  long nvp=0,clip=0; int point=0,vpidx=0,doDump=0; const char*restart=0;
  for(int i=1;i<argc;i++){ const char*a=argv[i];
    if(!strcmp(a,"--nvp")&&i+1<argc) nvp=strtol(argv[++i],0,0);
    else if(!strcmp(a,"--clip")&&i+1<argc) clip=strtol(argv[++i],0,0);
    else if(!strcmp(a,"--point")) point=1;
    else if(!strcmp(a,"--vpidx")) vpidx=1;
    else if(!strcmp(a,"--restart")&&i+1<argc) restart=argv[++i];
    else if(!strcmp(a,"--dump")) doDump=1; }
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice(); NSError*err=nil;
  printf("DEVICE %s CONFIG nvp=%ld clip=%ld point=%d vpidx=%d restart=%s\n",
    [[dev name]UTF8String],nvp,clip,point,vpidx,restart?restart:"-");
  // build VS with requested outputs
  NSMutableString*vs=[NSMutableString stringWithString:
    @"#include <metal_stdlib>\nusing namespace metal;\n"
     "struct VO{float4 pos [[position]];float4 col;\n"];
  if(point) [vs appendString:@" float psize [[point_size]];\n"];
  if(vpidx||nvp>0) [vs appendString:@" uint vpi [[viewport_array_index]];\n"];
  if(clip==1) [vs appendString:@" float cd [[clip_distance]];\n"];
  else if(clip>1) [vs appendFormat:@" float cd [[clip_distance]] [%ld];\n",clip];
  [vs appendString:
    @"};\nvertex VO v_main(uint vid [[vertex_id]]){\n"
     " float2 p[4]={float2(-0.8,-0.8),float2(0.8,-0.8),float2(-0.8,0.8),float2(0.8,0.8)};\n"
     " VO o;o.pos=float4(p[vid&3],0,1);o.col=float4(0.1,0.7,0.2,1);\n"];
  if(point) [vs appendString:@" o.psize=6.0;\n"];
  if(vpidx||nvp>0) [vs appendString:@" o.vpi=0;\n"];
  if(clip==1) [vs appendString:@" o.cd=o.pos.x+0.5;\n"];
  else if(clip>1){ for(long k=0;k<clip;k++) [vs appendFormat:@" o.cd[%ld]=o.pos.x+%f;\n",k,0.5-0.02*k]; }
  [vs appendString:@" return o;\n}\n"];
  NSString*fs=@"#include <metal_stdlib>\nusing namespace metal;\n"
    "struct VO{float4 pos [[position]];float4 col;};\n"
    "fragment float4 f_main(VO in [[stage_in]]){return in.col;}\n";
  id<MTLLibrary> vl=[dev newLibraryWithSource:vs options:nil error:&err];
  if(!vl){printf("VS_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
  id<MTLLibrary> fl=[dev newLibraryWithSource:fs options:nil error:&err];
  MTLPrimitiveType prim = point?MTLPrimitiveTypePoint:MTLPrimitiveTypeTriangleStrip;
  MTLRenderPipelineDescriptor*pd=[MTLRenderPipelineDescriptor new];
  pd.vertexFunction=[vl newFunctionWithName:@"v_main"];
  pd.fragmentFunction=[fl newFunctionWithName:@"f_main"];
  pd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
  if(point) pd.inputPrimitiveTopology=MTLPrimitiveTopologyClassPoint;
  id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
  if(!pso){printf("PSO_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
  long W=64,H=64; NSUInteger bpr=((W*4)+255)&~255UL;
  MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:W height:H mipmapped:NO];
  td.usage=MTLTextureUsageRenderTarget; td.storageMode=MTLStorageModeShared;
  id<MTLBuffer> rtb=[dev newBufferWithLength:bpr*H options:MTLResourceStorageModeShared];
  id<MTLTexture> target=[rtb newTextureWithDescriptor:td offset:0 bytesPerRow:bpr];
  // index buffer for restart
  id<MTLBuffer> ib=nil; NSUInteger idxCount=0; int u32=0,indexed=0;
  if(restart){ indexed=1; u32=(strstr(restart,"u32")!=NULL);
    int list=(strstr(restart,"list")!=NULL);
    uint32_t seq[8]; int n=0;
    if(list){ seq[0]=0;seq[1]=1;seq[2]=2; n=3; }
    else { seq[0]=0;seq[1]=1;seq[2]=2; seq[3]=u32?0xffffffffu:0xffffu; seq[4]=1;seq[5]=2;seq[6]=3; n=7; }
    idxCount=n;
    if(u32){ ib=[dev newBufferWithLength:n*4 options:MTLResourceStorageModeShared]; uint32_t*Q=(uint32_t*)[ib contents]; for(int k=0;k<n;k++)Q[k]=seq[k]; }
    else { ib=[dev newBufferWithLength:n*2 options:MTLResourceStorageModeShared]; uint16_t*Q=(uint16_t*)[ib contents]; for(int k=0;k<n;k++)Q[k]=(uint16_t)seq[k]; }
    prim = list?MTLPrimitiveTypeTriangle:MTLPrimitiveTypeTriangleStrip;
    pv("idxBuf",[ib gpuAddress]);
  }
  id<MTLCommandQueue> q=[dev newCommandQueue];
  MTLRenderPassDescriptor*rp=[MTLRenderPassDescriptor new];
  rp.colorAttachments[0].texture=target; rp.colorAttachments[0].loadAction=MTLLoadActionClear;
  rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,1); rp.colorAttachments[0].storeAction=MTLStoreActionStore;
  id<MTLCommandBuffer> cb=[q commandBuffer];
  id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
  if(nvp>0){ MTLViewport vps[16]; for(long i=0;i<nvp&&i<16;i++){ vps[i].originX=i;vps[i].originY=2*i;vps[i].width=60-i;vps[i].height=50-i;vps[i].znear=0.02*i;vps[i].zfar=1.0-0.02*i; } [enc setViewports:vps count:(NSUInteger)nvp]; }
  else { MTLViewport vpt={0,0,(double)W,(double)H,0,1}; [enc setViewport:vpt]; }
  [enc setRenderPipelineState:pso];
  @try{
    if(indexed) [enc drawIndexedPrimitives:prim indexCount:idxCount indexType:(u32?MTLIndexTypeUInt32:MTLIndexTypeUInt16) indexBuffer:ib indexBufferOffset:0];
    else [enc drawPrimitives:prim vertexStart:0 vertexCount:4];
  }@catch(NSException*e){printf("DRAW_EXC %s\n",[[e reason]UTF8String]);}
  [enc endEncoding]; [cb commit]; [cb waitUntilCompleted];
  printf("SUBMIT status=%ld\n",(long)[cb status]);
  if([cb error]) printf("CB_ERROR %s\n",[[[cb error]localizedDescription]UTF8String]);
  if(doDump){fflush(stdout);kill(getpid(),SIGUSR1);usleep(500000);}
  return 0;
}}
