// Copyright (c) 2026. Licensed under the MIT license.
#include "Carla/Sensor/GpuSensorDispatcher.h"
#include "Carla.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "Components/StaticMeshComponent.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "TimerManager.h"

namespace CarlaGpuSensorTest
{
void RunSensorGpuSelfTest(UWorld* World)
{
  if (!World || !CarlaGpuSensors::IsEnabled())
  {
    UE_LOG(LogCarla, Error, TEXT("GPU self-test requires a game world and carla.Sensors.GpuRayTracing=1"));
    return;
  }
  UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
  check(Cube);
  const FVector Origin(0, 0, 100000);
  auto* Owner = World->SpawnActor<AActor>();
  auto SpawnCube = [&](double X, bool Blocks)
  {
    auto* Actor = World->SpawnActor<AStaticMeshActor>();
    auto* Mesh = Actor->GetStaticMeshComponent();
    Mesh->SetMobility(EComponentMobility::Movable);
    // StaticMeshActor otherwise restores its mesh's default collision profile
    // when physics/render state is recreated during mesh loading or scaling.
    Mesh->SetCollisionProfileName(TEXT("Custom"));
    Mesh->SetStaticMesh(Cube);
    Mesh->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    Mesh->SetCollisionResponseToAllChannels(ECR_Ignore);
    Mesh->SetCollisionResponseToChannel(ECC_GameTraceChannel2, Blocks ? ECR_Block : ECR_Ignore);
    Actor->SetActorLocation(Origin + FVector(X, 0, 0));
    Actor->SetActorScale3D(FVector(2));
    return Actor;
  };
  auto* Occluder = SpawnCube(500, false);
  auto* Target = SpawnCube(1000, true);
  const TWeakObjectPtr<AActor> WeakOwner(Owner);
  const TWeakObjectPtr<AStaticMeshActor> WeakTarget(Target), WeakOccluder(Occluder);
  // Let render proxies and BLAS updates reach the renderer before submitting.
  FTimerHandle Timer;
  World->GetTimerManager().SetTimer(Timer, [World, Origin, WeakOwner, WeakTarget, WeakOccluder]
  {
    if (!WeakOwner.IsValid() || !WeakTarget.IsValid() || !WeakOccluder.IsValid()) return;
    if (WeakOccluder->GetStaticMeshComponent()->GetCollisionResponseToChannel(ECC_GameTraceChannel2) != ECR_Ignore ||
        WeakTarget->GetStaticMeshComponent()->GetCollisionResponseToChannel(ECC_GameTraceChannel2) != ECR_Block)
      UE_LOG(LogCarla, Fatal, TEXT("GPU SELF TEST FIXTURE FAILED: collision responses changed"));
    constexpr int32 Count = 65536;
    TArray<FCarlaGpuRay> Rays;
    TArray<FHitResult> Reference;
    Rays.Reserve(Count);
    Reference.SetNum(Count);
    FCollisionQueryParams Params(SCENE_QUERY_STAT(CarlaGpuSensorSelfTest), true, WeakOwner.Get());
    const double CpuStart = FPlatformTime::Seconds();
    for (int32 I = 0; I < Count; ++I)
    {
      const FVector Direction = (I % 2) ? FVector(0, 1, 0) : FVector(1, 0, 0);
      Rays.Add({Origin, Direction, 2000});
      World->LineTraceSingleByChannel(Reference[I], Origin, Origin + Direction * 2000,
          ECC_GameTraceChannel2, Params);
    }
    const double CpuMs = (FPlatformTime::Seconds() - CpuStart) * 1000;
    if (Reference[0].GetActor() != WeakTarget.Get() || Reference[1].bBlockingHit)
      UE_LOG(LogCarla, Fatal, TEXT("GPU SELF TEST FIXTURE FAILED: CPU reference did not hit the target and miss empty space"));
    const double Submitted = FPlatformTime::Seconds();
    CarlaGpuSensors::Submit(*WeakOwner.Get(), MoveTemp(Rays),
        [Reference = MoveTemp(Reference), WeakOwner, WeakTarget, WeakOccluder, CpuMs, Submitted]
        (TArray<FCarlaGpuHit>&& Hits)
    {
      double MaxError = 0;
      uint32 HitCount = 0;
      for (int32 I = 0; I < Hits.Num(); ++I)
      {
        if (Hits[I].Hit.bBlockingHit != Reference[I].bBlockingHit)
          UE_LOG(LogCarla, Fatal, TEXT("GPU SELF TEST FAILED: hit/miss mismatch at ray %d"), I);
        if (!Hits[I].Hit.bBlockingHit) continue;
        ++HitCount;
        MaxError = FMath::Max(MaxError, double(FMath::Abs(Hits[I].Hit.Distance - Reference[I].Distance)));
        const double NormalDot = FVector::DotProduct(Hits[I].Hit.ImpactNormal, Reference[I].ImpactNormal);
        if (Hits[I].Hit.GetActor() != WeakTarget.Get() || !FMath::IsFinite(MaxError) || MaxError > 0.5 ||
            !FMath::IsFinite(NormalDot) || NormalDot < 0.99)
          UE_LOG(LogCarla, Fatal, TEXT("GPU SELF TEST FAILED ray=%d: GPU distance=%.6f CPU distance=%.6f error=%.6f normal dot=%.6f GPU normal=%s CPU normal=%s GPU actor=%s expected=%s"),
              I, double(Hits[I].Hit.Distance), double(Reference[I].Distance), MaxError, NormalDot,
              *Hits[I].Hit.ImpactNormal.ToString(), *Reference[I].ImpactNormal.ToString(),
              *GetNameSafe(Hits[I].Hit.GetActor()), *GetNameSafe(WeakTarget.Get()));
      }
      if (Hits.Num() != 65536 || HitCount != 32768)
        UE_LOG(LogCarla, Fatal, TEXT("GPU SELF TEST FAILED: unexpected output count"));
      const FString Report = FString::Printf(
          TEXT("{\"passed\":true,\"rays\":65536,\"hits\":32768,\"max_distance_error_cm\":%.6f,\"cpu_serial_ms\":%.3f,\"gpu_end_to_end_ms\":%.3f}"),
          MaxError, CpuMs, (FPlatformTime::Seconds() - Submitted) * 1000);
      const FString Directory = FPaths::Combine(FPlatformMisc::GetEnvironmentVariable(TEXT("SIMULATIONS_LINUX")), TEXT("verification"));
      const FString File = FPaths::Combine(Directory, TEXT("gpu-ray-self-test.json"));
      if (!FFileHelper::SaveStringToFile(Report, *File))
        UE_LOG(LogCarla, Fatal, TEXT("GPU SELF TEST: could not write %s"), *File);
      UE_LOG(LogCarla, Display, TEXT("GPU SENSOR SELF TEST PASSED: %s"), *Report);
      if (WeakTarget.IsValid()) WeakTarget->Destroy();
      if (WeakOccluder.IsValid()) WeakOccluder->Destroy();
      if (WeakOwner.IsValid()) WeakOwner->Destroy();
    });
  }, 2.0f, false);
}

FAutoConsoleCommandWithWorld SelfTestCommand(TEXT("carla.Sensors.GpuSelfTest"),
    TEXT("Compare 65536 hardware GPU rays with Chaos: hit/miss, distance, normal, ID and ignored collision surface."),
    FConsoleCommandWithWorldDelegate::CreateStatic(&RunSensorGpuSelfTest));
}
