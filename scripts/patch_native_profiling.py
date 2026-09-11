from pathlib import Path
import shutil
root=Path('/mnt/simulations/carla/Unreal/CarlaUnreal/Plugins/Carla/Source/Carla/Sensor');backup=Path('data/reliability-backup/profiling');backup.mkdir(exist_ok=True)
for name in ['GpuSensorDispatcher.cpp','GpuSensorDispatcher.h','ImageUtil.cpp']:
 p=root/name
 if not (backup/name).exists():shutil.copy2(p,backup/name)
p=root/'GpuSensorDispatcher.h';s=p.read_text().replace('  void Startup();','  void ProfileSample(const FString& Name, double Milliseconds);\n  void Startup();');p.write_text(s)
p=root/'GpuSensorDispatcher.cpp';s=p.read_text().replace('#include "RenderUtils.h"','#include "RenderUtils.h"\n#include "Misc/FileHelper.h"\n#include "Misc/Paths.h"\n#include "HAL/FileManager.h"')
s=s.replace('  TArray<FCarlaGpuRay> Rays;', '  FRenderQueryRHIRef QueryStart, QueryEnd;\n  double GpuMs=-1, Dispatched=0, Ready=0;\n  TArray<FCarlaGpuRay> Rays;',1)
a=s.index('    FComputeShaderUtils::AddPass(Graph, RDG_EVENT_NAME("Carla GPU sensor rays')
b=s.index('    Batch->Readback =',a)
s=s[:a]+'''    if (GSupportsTimestampRenderQueries) {
      Batch->QueryStart=RHICreateRenderQuery(RQT_AbsoluteTime);
      Batch->QueryEnd=RHICreateRenderQuery(RQT_AbsoluteTime);
    }
    Batch->Dispatched=FPlatformTime::Seconds();
    Graph.AddPass(RDG_EVENT_NAME("Carla GPU sensor rays (%u)",Params->RayCount),Params,ERDGPassFlags::Compute,
      [Batch,Params,Shader](FRHICommandList& Cmd) {
        if (Batch->QueryStart) Cmd.EndRenderQuery(Batch->QueryStart);
        FComputeShaderUtils::Dispatch(Cmd,Shader,*Params,FIntVector(FMath::DivideAndRoundUp(Params->RayCount,32u),1,1));
        if (Batch->QueryEnd) Cmd.EndRenderQuery(Batch->QueryEnd);
      });
'''+s[b:]
s=s.replace('      const void* Data = Batch->Readback->Lock(Bytes);','''      Batch->Ready=FPlatformTime::Seconds();
      uint64 Start=0,End=0;
      if (Batch->QueryStart && RHIGetRenderQueryResult(Batch->QueryStart,Start,false) && RHIGetRenderQueryResult(Batch->QueryEnd,End,false) && End>=Start)
        Batch->GpuMs=double(End-Start)/1000.;
      const void* Data = Batch->Readback->Lock(Bytes);''')
s=s.replace('    InFlight.Remove(Batch->Owner);','''    ProfileSample(TEXT("ray_gpu_ms"),Batch->GpuMs);
    ProfileSample(TEXT("ray_queue_ms"),(Batch->Dispatched-Batch->Submitted)*1000);
    ProfileSample(TEXT("ray_dispatch_to_readback_ms"),(Batch->Ready-Batch->Dispatched)*1000);
    InFlight.Remove(Batch->Owner);''',1)
pos=s.index('bool IsEnabled()')
s=s[:pos]+'''void ProfileSample(const FString& Name, double Milliseconds)
{
  if (!FMath::IsFinite(Milliseconds) || Milliseconds<0) return;
  // Called from render/background tasks as well as the game thread.
  static FCriticalSection Mutex;
  FScopeLock Lock(&Mutex);
  static TMap<FString,TArray<double>> Samples;
  static double LastWrite=0;
  auto& Values=Samples.FindOrAdd(Name); Values.Add(Milliseconds);
  if (Values.Num()>120) Values.RemoveAt(0);
  const double Now=FPlatformTime::Seconds();
  if (Now-LastWrite<1) return;
  LastWrite=Now;
  FString Json=TEXT("{\\\"metrics\\\":{"); bool First=true;
  for (const auto& Pair : Samples) {
    auto Sorted=Pair.Value;Sorted.Sort();double Sum=0;for (double V : Sorted) Sum+=V;
    if (!First) Json+=TEXT(",");First=false;
    Json+=FString::Printf(TEXT("\\\"%s\\\":{\\\"mean\\\":%.4f,\\\"p95\\\":%.4f,\\\"samples\\\":%d}"),*Pair.Key,Sum/Sorted.Num(),Sorted[FMath::CeilToInt(.95*Sorted.Num())-1],Sorted.Num());
  }
  Json+=TEXT("}}");
  const FString Dir=FPaths::Combine(FPaths::ProjectSavedDir(),TEXT("SensorProfiles"));
  IFileManager::Get().MakeDirectory(*Dir,true);
  const FString Path=FPaths::Combine(Dir,FString::Printf(TEXT("%u.json"),FPlatformProcess::GetCurrentProcessId()));
  FFileHelper::SaveStringToFile(Json,*(Path+TEXT(".tmp")));
  IFileManager::Get().Move(*Path,*(Path+TEXT(".tmp")),true);
}

'''+s[pos:]
s=s.replace('#include "HAL/FileManager.h"','#include "HAL/FileManager.h"\n#include "HAL/PlatformProcess.h"\n#include "Misc/ScopeLock.h"')
p.write_text(s)
p=root/'ImageUtil.cpp';s=p.read_text().replace('    int32 SlotIndex = INDEX_NONE;', '    int32 SlotIndex = INDEX_NONE;\n    double Enqueued=0;\n    FRenderQueryRHIRef CopyStart,CopyEnd;',1)
s=s.replace('    Self.Readback->EnqueueCopy(CmdList, Texture, ResolveRect);','''    Self.Enqueued=FPlatformTime::Seconds();
    if (GSupportsTimestampRenderQueries) {Self.CopyStart=RHICreateRenderQuery(RQT_AbsoluteTime);Self.CopyEnd=RHICreateRenderQuery(RQT_AbsoluteTime);CmdList.EndRenderQuery(Self.CopyStart);}
    Self.Readback->EnqueueCopy(CmdList, Texture, ResolveRect);
    if (Self.CopyEnd) CmdList.EndRenderQuery(Self.CopyEnd);''',1)
s=s.replace('      Self.Callback(MappedPtr, RowPitch, BufferHeight, Self.Format, Self.Size);','''      const double Started=FPlatformTime::Seconds();
      Self.Callback(MappedPtr, RowPitch, BufferHeight, Self.Format, Self.Size);
      CarlaGpuSensors::ProfileSample(TEXT("camera_convert_serialize_ms"),(FPlatformTime::Seconds()-Started)*1000);''',1)
s=s.replace('      ReadImageDataEnd(std::move(Self));','''      CarlaGpuSensors::ProfileSample(TEXT("camera_readback_ready_ms"),(FPlatformTime::Seconds()-Self.Enqueued)*1000);
      uint64 Start=0,End=0;
      if (Self.CopyStart && RHIGetRenderQueryResult(Self.CopyStart,Start,false) && RHIGetRenderQueryResult(Self.CopyEnd,End,false) && End>=Start)
        CarlaGpuSensors::ProfileSample(TEXT("camera_copy_gpu_ms"),double(End-Start)/1000.);
      ReadImageDataEnd(std::move(Self));''',1)
p.write_text(s)
