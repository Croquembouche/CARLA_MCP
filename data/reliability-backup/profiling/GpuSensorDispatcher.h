// Copyright (c) 2026. Licensed under the MIT license.
#pragma once

#include "CoreMinimal.h"
#include "Engine/HitResult.h"
#include "Templates/Function.h"

class FRHICommandListImmediate;
class AActor;

// Positions and distances are in Unreal centimetres. One hardware ray query
// runs per compute thread. The result is against render geometry, not Chaos.
struct FCarlaGpuRay
{
  FVector Origin;
  FVector Direction;
  float Range;
};

struct FCarlaGpuHit
{
  FHitResult Hit;
  FVector TargetVelocity = FVector::ZeroVector;
};

namespace CarlaGpuSensors
{
  void Startup();
  void Shutdown();
  bool IsEnabled();
  // Called both by the core ticker and CARLA's synchronous RPC wait loop.
  // Completion is pumped on the game thread even when the client awaits a
  // sensor frame before requesting its next simulation tick.
  void Pump();
  // Game-thread replica backpressure, before applying the next primary frame.
  bool HasPendingFrames();
  void BeginSensorTick(AActor& Owner);
  void Submit(AActor& Owner, TArray<FCarlaGpuRay>&& Rays,
      TUniqueFunction<void(TArray<FCarlaGpuHit>&&)>&& Complete);

  // Render-thread only. A single shared polling queue replaces per-image
  // blocking queries and sleeping task-graph workers. Return true to retire.
  void PollReadback(TUniqueFunction<bool()>&& Poll);
  void DispatchReadbackCallback(TUniqueFunction<void()>&& Callback);
  // Image conversion can run in the background; UObject access and delivery
  // return to the game thread, including during synchronous RPC waits.
  void EnqueueGameThread(TUniqueFunction<void()>&& Callback);
}
