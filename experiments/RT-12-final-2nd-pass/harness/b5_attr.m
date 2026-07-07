// b5_attr.m -- RT-12 Part B: re-verify "vertex attribute fetch = IN-SHADER SOFTWARE".
// Compiles a fixed [[stage_in]] VS against a CONFIGURABLE MTLVertexDescriptor, serializes the
// render pipeline to an MTLBinaryArchive (like shdump --render), so agxparse can extract the VS
// AGX bytes. Varying ONE descriptor knob (stride/offset/format/step) and diffing the VS bytes
// proves the fetch is compiled into the VS (impossible if it were fixed-function).
// Own MSL only; no Apple binary inspected. Model: our shdump.m render path + a vertex descriptor.
// Build: clang -fobjc-arc -framework Metal -framework Foundation -o b5_attr b5_attr.m
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <string.h>
static void die(const char*m,NSError*e){ fprintf(stderr,"b5_attr: %s: %s\n",m,e?[[e localizedDescription]UTF8String]:""); exit(1);}
int main(int argc,char**argv){ @autoreleasepool{
  const char*out=0; long stride=32,a1off=16; const char*a0fmt="float3",*a1fmt="float4",*step="vertex";
  for(int i=1;i<argc;i++){ const char*a=argv[i];
    if(!strcmp(a,"-o")&&i+1<argc) out=argv[++i];
    else if(!strcmp(a,"--stride")&&i+1<argc) stride=strtol(argv[++i],0,0);
    else if(!strcmp(a,"--a1off")&&i+1<argc) a1off=strtol(argv[++i],0,0);
    else if(!strcmp(a,"--a0fmt")&&i+1<argc) a0fmt=argv[++i];
    else if(!strcmp(a,"--a1fmt")&&i+1<argc) a1fmt=argv[++i];
    else if(!strcmp(a,"--step")&&i+1<argc) step=argv[++i];
  }
  if(!out){fprintf(stderr,"need -o\n");return 2;}
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice(); NSError*err=nil;
  NSString*src=@"#include <metal_stdlib>\nusing namespace metal;\n"
    "struct VIn{float3 a0 [[attribute(0)]];float4 a1 [[attribute(1)]];};\n"
    "struct VO{float4 pos [[position]];float4 col;};\n"
    "vertex VO v_main(VIn in [[stage_in]]){VO o;o.pos=float4(in.a0,1);o.col=in.a1;return o;}\n"
    "fragment float4 f_main(VO in [[stage_in]]){return in.col;}\n";
  MTLCompileOptions*opts=[MTLCompileOptions new]; [opts setFastMathEnabled:YES];
  id<MTLLibrary> lib=[dev newLibraryWithSource:src options:opts error:&err]; if(!lib) die("compile",err);
  MTLBinaryArchiveDescriptor*adesc=[MTLBinaryArchiveDescriptor new];
  id<MTLBinaryArchive> arc=[dev newBinaryArchiveWithDescriptor:adesc error:&err]; if(!arc) die("arc",err);
  MTLRenderPipelineDescriptor*rd=[MTLRenderPipelineDescriptor new];
  rd.vertexFunction=[lib newFunctionWithName:@"v_main"];
  rd.fragmentFunction=[lib newFunctionWithName:@"f_main"];
  rd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
  // configurable vertex descriptor
  MTLVertexDescriptor*vd=[MTLVertexDescriptor new];
  struct{const char*n;MTLVertexFormat f;} FM[]={
    {"float2",MTLVertexFormatFloat2},{"float3",MTLVertexFormatFloat3},{"float4",MTLVertexFormatFloat4},
    {"half4",MTLVertexFormatHalf4},{"uchar4n",MTLVertexFormatUChar4Normalized},{"short2",MTLVertexFormatShort2}};
  MTLVertexFormat f0=MTLVertexFormatFloat3,f1=MTLVertexFormatFloat4;
  for(int i=0;i<6;i++){ if(!strcmp(a0fmt,FM[i].n)) f0=FM[i].f; if(!strcmp(a1fmt,FM[i].n)) f1=FM[i].f; }
  vd.attributes[0].format=f0; vd.attributes[0].offset=0; vd.attributes[0].bufferIndex=0;
  vd.attributes[1].format=f1; vd.attributes[1].offset=(NSUInteger)a1off; vd.attributes[1].bufferIndex=0;
  vd.layouts[0].stride=(NSUInteger)stride;
  vd.layouts[0].stepFunction=!strcmp(step,"instance")?MTLVertexStepFunctionPerInstance:MTLVertexStepFunctionPerVertex;
  vd.layouts[0].stepRate=1;
  rd.vertexDescriptor=vd;
  id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:rd error:&err]; if(!pso) die("pso",err);
  fprintf(stderr,"b5_attr: pso OK stride=%ld a1off=%ld a0=%s a1=%s step=%s\n",stride,a1off,a0fmt,a1fmt,step);
  if(![arc addRenderPipelineFunctionsWithDescriptor:rd error:&err]) die("addRPF",err);
  NSURL*url=[NSURL fileURLWithPath:[NSString stringWithUTF8String:out]];
  if(![arc serializeToURL:url error:&err]) die("serialize",err);
  fprintf(stderr,"b5_attr: wrote %s\n",out);
  return 0;
}}
